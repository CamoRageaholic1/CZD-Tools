#!/usr/bin/env python3
"""
Plex library organizer.

Scans a source folder for video files, identifies movies and TV episodes
(filename + ffprobe + optional TMDb), and renames/moves them into the
Plex-recommended layout under a destination folder.

Plex layout:
  Movies/Title (Year)/Title (Year) - 1080p.mkv
  TV Shows/Show Name (Year)/Season 01/Show Name - s01e01 - Episode Title.mkv

Defaults to dry-run. Pass --apply to actually move files.
Config (TMDb key) at: ~/.config/plex-organizer/config.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from guessit import guessit
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

CONFIG_PATH = Path.home() / ".config" / "plex-organizer" / "config.json"
STATE_PATH = Path.home() / ".config" / "plex-organizer" / "state.json"

VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".wmv",
    ".flv", ".webm", ".mpg", ".mpeg",
}
SUBTITLE_EXTS = {".srt", ".sub", ".idx", ".ass", ".ssa", ".vtt"}
SAMPLE_MIN_BYTES = 50 * 1024 * 1024  # ignore <50MB; usually trailers/samples

console = Console()


# ---------- config / state ----------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            console.print(f"[red]Could not parse {CONFIG_PATH}[/]")
    return {}


# ---------- ffprobe ----------

def ffprobe_info(path: Path) -> dict:
    """Return basic stream info: resolution tag, codec, hdr flag, duration."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name,color_transfer",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        data = json.loads(out)
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        return {}
    streams = data.get("streams") or []
    if not streams:
        return {}
    s = streams[0]
    height = int(s.get("height") or 0)
    width = int(s.get("width") or 0)
    transfer = (s.get("color_transfer") or "").lower()
    return {
        "width": width,
        "height": height,
        "resolution": resolution_tag(width, height),
        "codec": (s.get("codec_name") or "").lower(),
        "hdr": "smpte2084" in transfer or "arib-std-b67" in transfer,
        "duration": float((data.get("format") or {}).get("duration") or 0),
    }


def resolution_tag(w: int, h: int) -> str:
    if h >= 2000 or w >= 3000:
        return "2160p"
    if h >= 1000:
        return "1080p"
    if h >= 700:
        return "720p"
    if h >= 400:
        return "480p"
    if h:
        return f"{h}p"
    return ""


# ---------- naming helpers ----------

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(s: str) -> str:
    s = _UNSAFE.sub("", s).strip().rstrip(".")
    return re.sub(r"\s+", " ", s)


# ---------- TMDb ----------

class TMDb:
    BASE = "https://api.themoviedb.org/3"

    def __init__(self, key: str):
        self.key = key
        self.session = requests.Session()

    def _get(self, path: str, **params):
        if not self.key:
            return None
        params["api_key"] = self.key
        try:
            r = self.session.get(self.BASE + path, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            console.print(f"[yellow]TMDb error on {path}: {e}[/]")
            return None

    def search_movie(self, title: str, year: Optional[int] = None) -> list[dict]:
        params: dict = {"query": title}
        if year:
            params["year"] = year
        data = self._get("/search/movie", **params) or {}
        return data.get("results") or []

    def search_tv(self, title: str) -> list[dict]:
        data = self._get("/search/tv", query=title) or {}
        return data.get("results") or []

    def episode(self, tv_id: int, season: int, episode: int) -> Optional[dict]:
        return self._get(f"/tv/{tv_id}/season/{season}/episode/{episode}")


# ---------- plan ----------

@dataclass
class Plan:
    src: Path
    kind: str = "skip"  # 'movie' | 'episode' | 'skip'
    title: str = ""
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: str = ""
    resolution: str = ""
    codec: str = ""
    hdr: bool = False
    target: Optional[Path] = None
    notes: list[str] = field(default_factory=list)


def pick_match(results: list[dict], kind: str, title: str, src_name: str = "") -> Optional[dict]:
    if src_name:
        console.print(f"\n[bold cyan]Reviewing file:[/] {src_name}")
    table = Table(title=f"TMDb matches for '{title}'")
    table.add_column("#", style="cyan")
    table.add_column("Title")
    table.add_column("Year")
    table.add_column("Overview")
    shown = results[:10]
    for i, r in enumerate(shown, 1):
        if kind == "movie":
            t = r.get("title", "")
            y = (r.get("release_date") or "")[:4]
        else:
            t = r.get("name", "")
            y = (r.get("first_air_date") or "")[:4]
        ov = ((r.get("overview") or "").replace("\n", " "))[:60]
        table.add_row(str(i), t, y, ov)
    console.print(table)
    choice = Prompt.ask("Pick #, 's' to skip TMDb, or 'm' to type manually", default="1")
    if choice in ("s", "S"):
        return None
    if choice in ("m", "M"):
        return {"__manual__": True}
    if choice.isdigit() and 1 <= int(choice) <= len(shown):
        return shown[int(choice) - 1]
    return None


def build_movie_plan(src: Path, dest: Path, info: dict, guessed: dict,
                     tmdb: TMDb, interactive: bool) -> Plan:
    p = Plan(src=src, kind="movie")
    title = str(guessed.get("title") or src.stem)
    year = guessed.get("year")
    if isinstance(year, list):
        year = year[0] if year else None

    matched = None
    if tmdb.key:
        results = tmdb.search_movie(title, year if isinstance(year, int) else None)
        if results:
            best = results[0]
            best_year = (best.get("release_date") or "")[:4]
            unambiguous = (
                len(results) == 1
                or (year and best_year == str(year))
            )
            if unambiguous or not interactive:
                matched = best
            else:
                matched = pick_match(results, "movie", title, src.name)

    if matched and not matched.get("__manual__"):
        title = matched.get("title") or title
        rd = (matched.get("release_date") or "")[:4]
        if rd.isdigit():
            year = int(rd)

    if (matched and matched.get("__manual__")) or (not year and interactive):
        console.print(f"\n[bold cyan]Reviewing file:[/] {src.name}")
        ans = Prompt.ask(f"Title for [bold]{src.name}[/]", default=title)
        if ans:
            title = ans
        y = Prompt.ask(f"Year for [bold]{src.name}[/]", default=str(year) if year else "")
        if y.isdigit():
            year = int(y)

    if not year:
        p.kind = "skip"
        p.notes.append("missing year")
        return p

    p.title = safe_name(title)
    p.year = int(year)
    p.resolution = info.get("resolution") or _resolution_from_guess(guessed)
    p.codec = info.get("codec") or ""
    p.hdr = bool(info.get("hdr"))

    folder = f"{p.title} ({p.year})"
    quality = []
    if p.resolution:
        quality.append(p.resolution)
    if p.hdr:
        quality.append("HDR")
    qtag = f" - {' '.join(quality)}" if quality else ""
    fname = f"{p.title} ({p.year}){qtag}{src.suffix.lower()}"
    p.target = dest / "Movies" / folder / fname
    return p


def build_tv_plan(src: Path, dest: Path, info: dict, guessed: dict,
                  tmdb: TMDb, interactive: bool) -> Plan:
    p = Plan(src=src, kind="episode")
    title = str(guessed.get("title") or "")
    season = guessed.get("season")
    episode = guessed.get("episode")
    year = guessed.get("year")
    if isinstance(season, list):
        season = season[0] if season else None
    if isinstance(episode, list):
        episode = episode[0] if episode else None
    if isinstance(year, list):
        year = year[0] if year else None

    if not (title and season is not None and episode is not None):
        p.kind = "skip"
        p.notes.append("could not parse show/season/episode from filename")
        return p

    matched = None
    if tmdb.key:
        results = tmdb.search_tv(title)
        if results:
            matched = results[0] if not interactive or len(results) == 1 else pick_match(results, "tv", title, src.name)

    show_year = year if isinstance(year, int) else None
    if matched and not matched.get("__manual__"):
        title = matched.get("name") or title
        fad = (matched.get("first_air_date") or "")[:4]
        if fad.isdigit():
            show_year = int(fad)
        ep = tmdb.episode(matched["id"], int(season), int(episode))
        if ep and ep.get("name"):
            p.episode_title = safe_name(ep["name"])

    p.title = safe_name(title)
    p.year = show_year
    p.season = int(season)
    p.episode = int(episode)
    p.resolution = info.get("resolution") or _resolution_from_guess(guessed)
    p.codec = info.get("codec") or ""
    p.hdr = bool(info.get("hdr"))

    show_folder = f"{p.title} ({p.year})" if p.year else p.title
    season_folder = f"Season {p.season:02d}"
    base = f"{p.title} - s{p.season:02d}e{p.episode:02d}"
    if p.episode_title:
        base += f" - {p.episode_title}"
    p.target = dest / "TV Shows" / show_folder / season_folder / f"{base}{src.suffix.lower()}"
    return p


def _resolution_from_guess(guessed: dict) -> str:
    ss = guessed.get("screen_size")
    if not ss:
        return ""
    return str(ss).lower()


def classify(guessed: dict, force_kind: Optional[str]) -> str:
    if force_kind:
        return force_kind
    t = guessed.get("type")
    if t == "movie":
        return "movie"
    if t == "episode":
        return "episode"
    if guessed.get("season") is not None and guessed.get("episode") is not None:
        return "episode"
    return "movie"


# ---------- scan / dedup / execute ----------

def find_videos(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in VIDEO_EXTS:
            continue
        try:
            if p.stat().st_size < SAMPLE_MIN_BYTES:
                continue
        except OSError:
            continue
        yield p


def detect_duplicates(plans: list[Plan]) -> dict[str, list[Plan]]:
    groups: dict[str, list[Plan]] = {}
    for p in plans:
        if p.kind == "skip" or not p.target:
            continue
        # group by target folder + base stem (ignoring quality tag)
        if p.kind == "movie":
            key = f"movie::{p.title}::{p.year}"
        else:
            key = f"tv::{p.title}::s{p.season:02d}e{p.episode:02d}"
        groups.setdefault(key, []).append(p)
    return {k: v for k, v in groups.items() if len(v) > 1}


def _res_rank(res: str) -> int:
    m = re.match(r"(\d+)", res or "")
    return int(m.group(1)) if m else 0


def resolve_duplicates(dupes: dict[str, list[Plan]]) -> None:
    """Keep highest-resolution; mark others as skip with a note."""
    if not dupes:
        return
    console.print(f"\n[bold yellow]Duplicate groups: {len(dupes)}[/]")
    for key, group in dupes.items():
        ranked = sorted(group, key=lambda p: _res_rank(p.resolution), reverse=True)
        keep = ranked[0]
        console.print(f"  [bold]{key}[/] -> keeping {keep.resolution or '?'}: {keep.src.name}")
        for other in ranked[1:]:
            other.kind = "skip"
            other.notes.append(f"duplicate of '{keep.src.name}' (lower quality: {other.resolution or '?'})")
            console.print(f"    [dim]drop {other.resolution or '?'}: {other.src.name}[/]")


def execute(plans: list[Plan], apply_changes: bool) -> tuple[int, int]:
    moved = skipped = 0
    for p in plans:
        if p.kind == "skip" or not p.target:
            console.print(f"[yellow]SKIP[/] {p.src.name} :: {', '.join(p.notes) or 'unrecognized'}")
            skipped += 1
            continue
        if p.target.exists() and p.src.resolve() != p.target.resolve():
            console.print(f"[yellow]EXISTS[/] target already present, skipping: {p.target}")
            skipped += 1
            continue
        action = "[green]MOVE[/]" if apply_changes else "[cyan]PLAN[/]"
        console.print(f"{action} {p.src.name}\n     -> {p.target}")
        if apply_changes:
            p.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p.src), str(p.target))
            for sib in p.src.parent.glob(p.src.stem + "*"):
                if sib.suffix.lower() in SUBTITLE_EXTS and sib.exists():
                    target_sib = p.target.with_name(p.target.stem + sib.suffix.lower())
                    target_sib.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(sib), str(target_sib))
            moved += 1
    return moved, skipped


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Plex library organizer (dry-run by default)")
    ap.add_argument("--source", help="Source folder of unorganized files")
    ap.add_argument("--dest", help="Destination root used for both movies and TV (overridden by per-kind flags)")
    ap.add_argument("--movies-dest", help="Destination root for movies (overrides --dest for movies)")
    ap.add_argument("--tv-dest", help="Destination root for TV shows (overrides --dest for TV)")
    ap.add_argument("--apply", action="store_true", help="Actually move files (otherwise dry-run)")
    ap.add_argument("--kind", choices=["movie", "tv", "auto"], default="auto",
                    help="Force content type (default: auto-detect per file)")
    ap.add_argument("--non-interactive", action="store_true",
                    help="Never prompt; pick best guess or skip")
    args = ap.parse_args()

    cfg = load_config()
    tmdb_key = os.environ.get("TMDB_API_KEY") or cfg.get("tmdb_api_key", "")
    tmdb = TMDb(tmdb_key)
    interactive = not args.non_interactive

    src = args.source or cfg.get("intake_source") or Prompt.ask("Source folder")
    movies_dest = args.movies_dest or args.dest or cfg.get("movies_dest")
    tv_dest = args.tv_dest or args.dest or cfg.get("tv_dest")
    if not movies_dest:
        movies_dest = Prompt.ask("Movies destination")
    if not tv_dest:
        tv_dest = Prompt.ask("TV destination")

    src_root = Path(os.path.expanduser(src)).resolve()
    movies_root = Path(os.path.expanduser(movies_dest)).resolve()
    tv_root = Path(os.path.expanduser(tv_dest)).resolve()

    if not src_root.exists():
        console.print(f"[red]Source does not exist: {src_root}[/]")
        return 1
    movies_root.mkdir(parents=True, exist_ok=True)
    tv_root.mkdir(parents=True, exist_ok=True)

    if not tmdb_key:
        console.print("[yellow]No TMDb API key set. Falling back to filename parsing only.[/]")

    if not shutil.which("ffprobe"):
        console.print("[yellow]ffprobe not found in PATH. Quality detection will fall back to filename parsing.[/]")

    force_kind = None
    if args.kind == "movie":
        force_kind = "movie"
    elif args.kind == "tv":
        force_kind = "episode"

    console.print(f"[bold]Scanning[/] {src_root}")
    console.print(f"  movies -> {movies_root}")
    console.print(f"  tv     -> {tv_root}")
    console.print("[dim]Tip: Ctrl-C any time during prompts to save progress and exit cleanly.[/]")
    plans: list[Plan] = []
    interrupted = False
    try:
        for vid in find_videos(src_root):
            info = ffprobe_info(vid) if shutil.which("ffprobe") else {}
            guessed = guessit(vid.name)
            kind = classify(guessed, force_kind)
            if kind == "movie":
                plan = build_movie_plan(vid, movies_root, info, guessed, tmdb, interactive)
            else:
                plan = build_tv_plan(vid, tv_root, info, guessed, tmdb, interactive)
            plans.append(plan)
    except KeyboardInterrupt:
        interrupted = True
        console.print(f"\n[yellow]Interrupted. Executing the {len(plans)} plans built so far...[/]")

    if not plans:
        console.print("[yellow]No video files found.[/]")
        return 0

    resolve_duplicates(detect_duplicates(plans))
    moved, skipped = execute(plans, args.apply)

    console.print(f"\n[bold]{'Moved' if args.apply else 'Planned'}[/]: {moved}    [bold]Skipped[/]: {skipped}")
    if interrupted:
        console.print("[yellow]Run was interrupted. Already-moved files are saved; re-run the same command to continue with the rest.[/]")
    if not args.apply:
        console.print("[dim]Dry run. Re-run with --apply to actually move files.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
