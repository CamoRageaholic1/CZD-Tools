#!/usr/bin/env python3
"""Convert an Obsidian vault into a browsable HTML mirror.

Source of truth stays Markdown. This generates a parallel tree of .html files
with resolved wikilinks, embedded images, and a CSS stylesheet for readable
viewing on desktop and mobile.
"""

import argparse
import html
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import frontmatter
import markdown

DEFAULT_VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents"
DEFAULT_OUT = Path.home() / "Documents/Vault-HTML"
TOOL_DIR = Path(__file__).resolve().parent

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".smart-connections", ".smart-env"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
ATTACHMENT_EXTS = IMAGE_EXTS | {".pdf", ".mp4", ".mp3", ".wav", ".m4a", ".mov", ".webm"}

MD_EXTENSIONS = [
    "extra",
    "sane_lists",
    "admonition",
    "toc",
    "pymdownx.tasklist",
    "pymdownx.superfences",
    "pymdownx.tilde",
    "pymdownx.highlight",
    "pymdownx.magiclink",
    "pymdownx.smartsymbols",
    "pymdownx.betterem",
]

MD_EXTENSION_CONFIGS = {
    "pymdownx.tasklist": {"custom_checkbox": True},
    "pymdownx.highlight": {"css_class": "highlight", "guess_lang": False},
    "toc": {"permalink": False},
}


def slugify_anchor(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)


def should_skip(path: Path, vault: Path) -> bool:
    rel = path.relative_to(vault)
    return any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts)


def collect_notes(vault: Path):
    notes = []
    attachments = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.startswith("."):
                continue
            p = Path(root) / f
            if p.suffix.lower() == ".md":
                notes.append(p)
            elif p.suffix.lower() in ATTACHMENT_EXTS:
                attachments.append(p)
    return notes, attachments


def build_indexes(notes, attachments, vault):
    """Return (note_index, attachment_index).

    note_index maps lookup keys to vault-relative .md paths:
      - lowercased basename without .md
      - lowercased relative path without .md
    attachment_index maps lowercased basename to vault-relative path.
    """
    note_index = {}
    for n in notes:
        rel = n.relative_to(vault)
        stem = rel.stem.lower()
        full = str(rel.with_suffix("")).lower()
        note_index.setdefault(stem, rel)
        note_index[full] = rel
    attachment_index = {}
    for a in attachments:
        rel = a.relative_to(vault)
        attachment_index.setdefault(rel.name.lower(), rel)
        attachment_index[str(rel).lower()] = rel
    return note_index, attachment_index


def rel_html_path(target_rel_md: Path, current_rel_md: Path) -> str:
    target_html = target_rel_md.with_suffix(".html")
    current_dir = current_rel_md.parent
    return os.path.relpath(target_html, start=current_dir).replace(os.sep, "/")


def rel_asset_path(target_rel: Path, current_rel_md: Path) -> str:
    current_dir = current_rel_md.parent
    return os.path.relpath(target_rel, start=current_dir).replace(os.sep, "/")


WIKILINK_RE = re.compile(r"(!?)\[\[([^\]\n]+)\]\]")


def replace_wikilinks(text: str, current_rel: Path, note_index, attachment_index):
    def repl(m):
        bang, body = m.group(1), m.group(2).strip()
        display = None
        if "|" in body:
            body, display = body.split("|", 1)
            body = body.strip()
            display = display.strip()
        anchor = ""
        if "#" in body:
            target, frag = body.split("#", 1)
            target = target.strip()
            anchor = "#" + slugify_anchor(frag)
        else:
            target = body
        key = target.lower()

        if bang == "!":
            ext = Path(target).suffix.lower()
            if ext in IMAGE_EXTS or key in attachment_index:
                att_rel = attachment_index.get(key) or attachment_index.get(target.lower())
                if att_rel is not None:
                    src = rel_asset_path(att_rel, current_rel)
                    alt = html.escape(display or att_rel.name)
                    if att_rel.suffix.lower() in IMAGE_EXTS:
                        return f'<img src="{src}" alt="{alt}" loading="lazy">'
                    return f'<a href="{src}" class="attachment">{alt}</a>'
            return f'<span class="broken-embed" title="missing: {html.escape(target)}">![[{html.escape(body)}]]</span>'

        if key in note_index:
            href = rel_html_path(note_index[key], current_rel) + anchor
            label = html.escape(display or target)
            return f'<a href="{href}" class="wikilink">{label}</a>'
        label = html.escape(display or target)
        return f'<span class="broken-link" title="not found: {html.escape(target)}">{label}</span>'

    return WIKILINK_RE.sub(repl, text)


TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][\w/\-]*)")


def linkify_tags(text: str) -> str:
    return TAG_RE.sub(lambda m: f'<span class="tag">#{m.group(1)}</span>', text)


def render_breadcrumbs(rel_md: Path) -> str:
    parts = list(rel_md.with_suffix("").parts)
    crumbs = []
    depth = len(parts) - 1
    home_href = "../" * depth + "index.html" if depth > 0 else "index.html"
    crumbs.append(f'<a href="{home_href}">vault</a>')
    accum = []
    for i, part in enumerate(parts[:-1]):
        accum.append(part)
        href = ("../" * (depth - i - 1)) + "index.html" if (depth - i - 1) > 0 else "index.html"
        crumbs.append(f'<a href="{href}">{html.escape(part)}</a>')
    crumbs.append(f'<span class="current">{html.escape(parts[-1])}</span>')
    return ' <span class="sep">/</span> '.join(crumbs)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<header class="breadcrumbs">{breadcrumbs}</header>
<main class="note">
<h1 class="note-title">{title_h}</h1>
{meta_block}
<article class="content">
{content}
</article>
</main>
<footer><a href="{home_href}">← index</a></footer>
</body>
</html>
"""


def render_meta_block(meta: dict) -> str:
    if not meta:
        return ""
    rows = []
    for k, v in meta.items():
        if v is None or v == "":
            continue
        if isinstance(v, list):
            v_str = ", ".join(str(x) for x in v)
        else:
            v_str = str(v)
        rows.append(f'<div class="meta-row"><span class="meta-key">{html.escape(str(k))}</span><span class="meta-val">{html.escape(v_str)}</span></div>')
    if not rows:
        return ""
    return '<aside class="meta">' + "".join(rows) + "</aside>"


def convert_note(md_path: Path, vault: Path, out: Path, note_index, attachment_index, md_engine):
    rel_md = md_path.relative_to(vault)
    out_path = out / rel_md.with_suffix(".html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw = md_path.read_text(encoding="utf-8", errors="replace")
    post = frontmatter.loads(raw)
    body = post.content
    body = replace_wikilinks(body, rel_md, note_index, attachment_index)

    md_engine.reset()
    body_html = md_engine.convert(body)
    body_html = linkify_tags(body_html)

    depth = len(rel_md.parts) - 1
    css_href = ("../" * depth) + "style.css" if depth > 0 else "style.css"
    home_href = ("../" * depth) + "index.html" if depth > 0 else "index.html"

    title = rel_md.stem
    page = PAGE_TEMPLATE.format(
        title=html.escape(title),
        title_h=html.escape(title),
        css_href=css_href,
        breadcrumbs=render_breadcrumbs(rel_md),
        meta_block=render_meta_block(post.metadata),
        content=body_html,
        home_href=home_href,
    )
    out_path.write_text(page, encoding="utf-8")
    return out_path


def copy_attachments(attachments, vault, out):
    copied = 0
    for a in attachments:
        rel = a.relative_to(vault)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not dest.exists() or dest.stat().st_mtime < a.stat().st_mtime:
                shutil.copy2(a, dest)
                copied += 1
        except OSError as e:
            print(f"  warn: could not copy {rel}: {e}", file=sys.stderr)
    return copied


def build_simple_tree(notes, vault):
    """Build a nested dict tree from note paths."""
    root = {"dirs": {}, "files": []}
    for n in sorted(notes):
        rel = n.relative_to(vault).with_suffix("")
        parts = rel.parts
        node = root
        for p in parts[:-1]:
            node = node["dirs"].setdefault(p, {"dirs": {}, "files": []})
        node["files"].append(parts[-1])
    return root


def render_tree(node, current_path=""):
    parts = []
    for name in sorted(node["dirs"].keys(), key=str.lower):
        child = node["dirs"][name]
        count = count_notes(child)
        sub_path = f"{current_path}{name}/" if current_path else f"{name}/"
        parts.append(f'<details class="folder"><summary>{html.escape(name)} <span class="count">{count}</span></summary>')
        parts.append(render_tree(child, sub_path))
        parts.append("</details>")
    if node["files"]:
        parts.append('<ul class="files">')
        for fname in sorted(node["files"], key=str.lower):
            href = f"{current_path}{fname}.html"
            parts.append(f'<li><a href="{href}">{html.escape(fname)}</a></li>')
        parts.append("</ul>")
    return "".join(parts)


def count_notes(node):
    return len(node["files"]) + sum(count_notes(d) for d in node["dirs"].values())


INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vault index</title>
<link rel="stylesheet" href="style.css">
</head>
<body class="index-page">
<header class="breadcrumbs"><span class="current">vault index</span></header>
<main class="index">
<h1>Vault ({n_notes} notes)</h1>
<p class="generated">Generated {ts}</p>
<div class="tree">
{tree_html}
</div>
</main>
</body>
</html>
"""


def write_index(notes, vault, out):
    tree = build_simple_tree(notes, vault)
    tree_html = render_tree(tree)
    page = INDEX_TEMPLATE.format(
        n_notes=len(notes),
        ts=time.strftime("%Y-%m-%d %H:%M"),
        tree_html=tree_html,
    )
    (out / "index.html").write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Render an Obsidian vault to HTML.")
    ap.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--clean", action="store_true", help="Wipe output dir before building")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N notes (for testing)")
    args = ap.parse_args()

    vault = args.vault.expanduser().resolve()
    out = args.out.expanduser().resolve()

    if not vault.is_dir():
        print(f"vault not found: {vault}", file=sys.stderr)
        sys.exit(1)

    if args.clean and out.exists():
        print(f"cleaning {out}")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    css_src = TOOL_DIR / "style.css"
    if css_src.exists():
        shutil.copy2(css_src, out / "style.css")
    else:
        print(f"warn: missing {css_src}", file=sys.stderr)

    print(f"scanning vault: {vault}")
    t0 = time.time()
    notes, attachments = collect_notes(vault)
    print(f"  found {len(notes)} notes, {len(attachments)} attachments")

    note_index, attachment_index = build_indexes(notes, attachments, vault)

    md_engine = markdown.Markdown(
        extensions=MD_EXTENSIONS,
        extension_configs=MD_EXTENSION_CONFIGS,
        output_format="html5",
    )

    print("copying attachments...")
    n_copied = copy_attachments(attachments, vault, out)
    print(f"  copied {n_copied} new/updated attachments")

    print("rendering notes...")
    target_notes = notes[: args.limit] if args.limit > 0 else notes
    errors = 0
    for i, n in enumerate(target_notes, 1):
        try:
            convert_note(n, vault, out, note_index, attachment_index, md_engine)
        except Exception as e:
            errors += 1
            print(f"  error on {n.relative_to(vault)}: {e}", file=sys.stderr)
        if i % 50 == 0:
            print(f"  {i}/{len(target_notes)}")
    print(f"  rendered {len(target_notes) - errors} notes ({errors} errors)")

    print("writing index...")
    write_index(notes, vault, out)

    elapsed = time.time() - t0
    print(f"done in {elapsed:.1f}s -> {out}")


if __name__ == "__main__":
    main()
