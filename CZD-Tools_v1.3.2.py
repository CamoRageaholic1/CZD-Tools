#!/usr/bin/env python3
# Consolidate Pyright directives to suppress common editor warnings.
# The reportMissingImports directive suppresses import errors for optional modules like 'pystyle'.
# The reportGeneralTypeIssues directive prevents Pylance from flagging legitimate Python 3.10+ type hint syntax (e.g. `str | None`).
# The reportAttributeAccessIssue directive avoids spurious attribute errors on our fallback Colors class.
# If you wish to see these warnings again, remove or adjust the directives below.
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false, reportAttributeAccessIssue=false
import os
import sys
import json
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Optional, List, Tuple, Dict  # for Python <3.10 type hints

# ---------- UI deps ----------
try:
    from pystyle import Colors, Colorate  # type: ignore[reportMissingImports]
except ImportError:
    class _C:
        pass
    Colors = _C()
    for k in (
        "white",
        "black",
        "red",
        "green",
        "blue",
        "yellow",
        "purple",
        "cyan",
        "orange",
        "pink",
        "turquoise",
        "light_gray",
        "dark_gray",
        "gray",
        "light_red",
        "light_green",
        "light_blue",
        "dark_red",
        "dark_green",
        "dark_blue",
        "reset",
    ):
        setattr(Colors, k, "")
    class _Col:
        @staticmethod
        def Vertical(color, text, *_):
            return text
    Colorate = _Col()

# ---------- Globals / Rename to CZD-Tools ----------
ROOT = os.path.abspath(os.path.expanduser("~/CZD-Tools"))
OLD_ROOT = os.path.abspath(os.path.expanduser("~/iSH-tools"))
TOOLS_DIR = os.path.join(ROOT, "tools")
RESOURCES_DIR = os.path.join(ROOT, "resources")
CHECK_JSON = os.path.join(ROOT, "check.json")
THEME_JSON = os.path.join(ROOT, "theme.json")

# Create base dirs/files
os.makedirs(TOOLS_DIR, exist_ok=True)
os.makedirs(RESOURCES_DIR, exist_ok=True)

# Migrate old state if present and new files missing
def migrate_old() -> None:
    try:
        if os.path.isdir(OLD_ROOT):
            for name in ("check.json", "theme.json"):
                src = os.path.join(OLD_ROOT, name)
                dst = os.path.join(ROOT, name)
                if not os.path.exists(dst) and os.path.exists(src):
                    shutil.copy2(src, dst)
            old_tools = os.path.join(OLD_ROOT, "tools")
            if os.path.isdir(old_tools):
                for entry in os.listdir(old_tools):
                    src = os.path.join(old_tools, entry)
                    dst = os.path.join(TOOLS_DIR, entry)
                    if not os.path.exists(dst):
                        try:
                            if os.path.isdir(src):
                                shutil.copytree(src, dst)
                            else:
                                shutil.copy2(src, dst)
                        except Exception:
                            pass
    except Exception:
        pass

migrate_old()

if not os.path.exists(CHECK_JSON):
    with open(CHECK_JSON, "w") as f:
        json.dump({"tools": {}}, f, indent=4)
if not os.path.exists(THEME_JSON):
    with open(THEME_JSON, "w") as f:
        json.dump({"theme": "rainbow"}, f, indent=4)

SINGLE_COLORS = [
    "white",
    "black",
    "red",
    "green",
    "blue",
    "yellow",
    "purple",
    "cyan",
    "orange",
    "pink",
    "turquoise",
    "light_gray",
    "dark_gray",
    "gray",
    "light_red",
    "light_green",
    "light_blue",
    "dark_red",
    "dark_green",
    "dark_blue",
]

# ---------- OS / Package manager detection ----------
def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def current_os() -> str:
    sysname = platform.system().lower()
    if "darwin" in sysname:
        return "darwin"
    if "linux" in sysname:
        return "linux"
    return sysname

def detect_pkg_mgr() -> Optional[str]:
    if have("brew"):
        return "brew"
    if have("apt"):
        return "apt"
    if have("apk"):
        return "apk"
    if have("dnf"):
        return "dnf"
    if have("pacman"):
        return "pacman"
    return None

def ensure_pip() -> Optional[str]:
    return "pipx" if have("pipx") else ("pip3" if have("pip3") else None)

def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    print(Colors.yellow + "$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, **kwargs)

def run_try(cmd: List[str], **kwargs) -> bool:
    try:
        run(cmd, **kwargs)
        return True
    except Exception as e:
        print(Colors.red + f"[!] Command failed: {' '.join(cmd)} -> {e}")
        return False

# ---------- State helpers ----------
def cd_root() -> None:
    os.chdir(ROOT)

def check_install() -> dict:
    cd_root()
    with open(CHECK_JSON, "r") as f:
        return json.load(f)

def save_install_state(data: dict) -> None:
    cd_root()
    with open(CHECK_JSON, "w") as f:
        json.dump(data, f, indent=4)

def tool_installed(tool_id: str) -> bool:
    return check_install()["tools"].get(tool_id, False)

def mark_installed(tool_id: str) -> None:
    data = check_install()
    data.setdefault("tools", {})[tool_id] = True
    save_install_state(data)

def load_theme() -> str:
    try:
        with open(THEME_JSON, "r") as f:
            return json.load(f).get("theme", "rainbow")
    except FileNotFoundError:
        return "rainbow"

# ---------- Installer engines ----------
def install_with_brew(pkgs: List[str]) -> bool:
    return run_try(["brew", "install"] + pkgs)

def install_with_apt(pkgs: List[str]) -> bool:
    if not run_try(["sudo", "apt", "update"]):
        return False
    return run_try(["sudo", "apt", "install", "-y"] + pkgs)

def install_with_apk(pkgs: List[str]) -> bool:
    if not run_try(["sudo", "apk", "update"]):
        return False
    return run_try(["sudo", "apk", "add"] + pkgs)

def install_with_dnf(pkgs: List[str]) -> bool:
    if not run_try(["sudo", "dnf", "makecache"]):
        return False
    return run_try(["sudo", "dnf", "install", "-y"] + pkgs)

def install_with_pacman(pkgs: List[str]) -> bool:
    if not run_try(["sudo", "pacman", "-Sy"]):
        return False
    return run_try(["sudo", "pacman", "-S", "--noconfirm"] + pkgs)

def install_with_pip(pkgs: List[str], prefer_pipx: bool = True) -> bool:
    pip = ensure_pip()
    if not pip:
        print(Colors.red + "[!] No pip/pipx found. Install pipx or pip3 first.")
        return False
    ok = True
    for p in pkgs:
        if pip == "pipx" and prefer_pipx:
            ok = ok and run_try(["pipx", "install", p])
        else:
            ok = ok and run_try([pip, "install", "--user", p])
    return ok

def install_with_git(repo_url: str, dest_dir: str, post_cmds: Optional[List] = None) -> bool:
    if not os.path.exists(dest_dir):
        if not run_try(["git", "clone", repo_url, dest_dir]):
            return False
    else:
        try:
            run(["git", "-C", dest_dir, "pull"])
        except Exception:
            pass
    if post_cmds:
        for c in post_cmds:
            if isinstance(c, str):
                ok = run_try(["bash", "-lc", c], cwd=dest_dir)
            else:
                ok = run_try(c, cwd=dest_dir)
            if not ok:
                return False
    return True

# ---------- Tool Registry ----------
TOOL_REGISTRY: Dict[str, Dict] = {
    "1": {
        "name": "Recon-ng",
        "run": ["recon-ng"],
        "help": "https://github.com/lanmaster53/recon-ng/wiki",
        "open_shell": False,
        "installers": [
            {"brew": ["recon-ng"]},
            {"pip": ["recon-ng"]},
            {
                "git": {
                    "repo": "https://github.com/lanmaster53/recon-ng.git",
                    "dest": os.path.join(TOOLS_DIR, "recon-ng"),
                }
            },
        ],
    },
    "2": {
        "name": "Nikto",
        "run": ["bash"],
        "cwd": os.path.join(TOOLS_DIR, "nikto", "program"),
        "help": "https://github.com/sullo/nikto/wiki",
        "open_shell": True,
        "installers": [
            {"brew": ["nikto"]},
            {
                "git": {
                    "repo": "https://github.com/sullo/nikto.git",
                    "dest": os.path.join(TOOLS_DIR, "nikto"),
                }
            },
        ],
    },
    "3": {
        "name": "DNSrecon",
        "run": ["dnsrecon"],
        "help": "https://github.com/darkoperator/dnsrecon",
        "open_shell": False,
        "installers": [
            {"brew": ["dnsrecon"]},
            {"pip": ["dnsrecon"]},
        ],
    },
    "4": {
        "name": "UDPSCAN",
        "run": ["python3", "UDPSCAN.py"],
        "cwd": os.path.join(TOOLS_DIR, "UDPSCAN"),
        "help": "https://github.com/cons0le7/UDPSCAN",
        "open_shell": False,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/cons0le7/UDPSCAN.git",
                    "dest": os.path.join(TOOLS_DIR, "UDPSCAN"),
                }
            }
        ],
    },
    "5": {
        "name": "Infoga",
        "run": ["python3", "infoga.py"],
        "cwd": os.path.join(TOOLS_DIR, "Infoga-py3"),
        "help": "https://github.com/The404Hacking/Infoga",
        "open_shell": True,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/m4ll0k/Infoga.git",
                    "dest": os.path.join(TOOLS_DIR, "Infoga-py3"),
                }
            }
        ],
    },
    "6": {
        "name": "NoSint",
        "run": ["python3", "nosint.py"],
        "cwd": os.path.join(TOOLS_DIR, "nosint"),
        "help": "https://github.com/cons0le7/nosint",
        "open_shell": True,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/cons0le7/nosint.git",
                    "dest": os.path.join(TOOLS_DIR, "nosint"),
                }
            }
        ],
    },
    "7": {
        "name": "IntelBase",
        "run": ["python3", "intelbase.py"],
        "cwd": os.path.join(TOOLS_DIR, "IntelBase-CLI"),
        "help": "https://github.com/cons0le7/IntelBase-CLI",
        "open_shell": True,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/cons0le7/IntelBase-CLI.git",
                    "dest": os.path.join(TOOLS_DIR, "IntelBase-CLI"),
                }
            }
        ],
    },
    "8": {
        "name": "XSStrike",
        "run": ["python3", "xsstrike.py"],
        "cwd": os.path.join(TOOLS_DIR, "XSStrike"),
        "help": "https://github.com/s0md3v/XSStrike/wiki/Usage",
        "open_shell": True,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/s0md3v/XSStrike.git",
                    "dest": os.path.join(TOOLS_DIR, "XSStrike"),
                    "post_cmds": [
                        ["python3", "-m", "pip", "install", "-r", "requirements.txt"]
                    ],
                }
            }
        ],
    },
    "9": {
        "name": "sqlmap",
        "run": ["python3", "sqlmap.py", "-h"],
        "cwd": os.path.join(TOOLS_DIR, "sqlmap-dev"),
        "help": "https://github.com/sqlmapproject/sqlmap",
        "open_shell": True,
        "installers": [
            {"brew": ["sqlmap"]},
            {
                "git": {
                    "repo": "https://github.com/sqlmapproject/sqlmap.git",
                    "dest": os.path.join(TOOLS_DIR, "sqlmap-dev"),
                }
            },
        ],
    },
    "10": {
        "name": "ZipBrute (FBF)",
        "run": ["python3", "zipbrute.py"],
        "cwd": os.path.join(TOOLS_DIR, "FileBruteforcers"),
        "help": "https://github.com/midwestcoder2020/FileBruteforcers",
        "open_shell": True,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/midwestcoder2020/FileBruteforcers.git",
                    "dest": os.path.join(TOOLS_DIR, "FileBruteforcers"),
                }
            }
        ],
    },
    "11": {
        "name": "PDFBrute (FBF)",
        "run": ["python3", "pdfbrute.py"],
        "cwd": os.path.join(TOOLS_DIR, "FileBruteforcers"),
        "help": "https://github.com/midwestcoder2020/FileBruteforcers",
        "open_shell": True,
        "installers": [
            {
                "git": {
                    "repo": "https://github.com/midwestcoder2020/FileBruteforcers.git",
                    "dest": os.path.join(TOOLS_DIR, "FileBruteforcers"),
                }
            }
        ],
    },
    "12": {
        "name": "OpenSSL",
        "run": ["bash", "-lc", "openssl help || true && bash"],
        "help": "https://docs.openssl.org/master",
        "open_shell": True,
        "installers": [
            {"brew": ["openssl"]},
            {"apt": ["openssl"]},
            {"apk": ["openssl"]},
            {"dnf": ["openssl"]},
            {"pacman": ["openssl"]},
        ],
    },
    "13": {
        "name": "GnuPG",
        "run": ["bash", "-lc", "gpg -h || true && bash"],
        "help": "https://www.gnupg.org/documentation",
        "open_shell": True,
        "installers": [
            {"brew": ["gnupg"]},
            {"apt": ["gnupg"]},
            {"apk": ["gnupg"]},
            {"dnf": ["gnupg2"]},
            {"pacman": ["gnupg"]},
        ],
    },
    "14": {
        "name": "nmap",
        "run": ["bash", "-lc", "nmap --help || true && bash"],
        "help": "https://nmap.org/book/",
        "open_shell": True,
        "installers": [
            {"brew": ["nmap"]},
            {"apt": ["nmap"]},
            {"apk": ["nmap"]},
            {"dnf": ["nmap"]},
            {"pacman": ["nmap"]},
        ],
    },
    "15": {
        "name": "gobuster",
        "run": ["bash", "-lc", "gobuster -h || true && bash"],
        "help": "https://github.com/OJ/gobuster",
        "open_shell": True,
        "installers": [
            {"brew": ["gobuster"]},
            {"apt": ["gobuster"]},
            {"dnf": ["gobuster"]},
            {"pacman": ["gobuster"]},
            {
                "git": {
                    "repo": "https://github.com/OJ/gobuster.git",
                    "dest": os.path.join(TOOLS_DIR, "gobuster"),
                    "post_cmds": [
                        ["bash", "-lc", "go version || (echo 'Install Go to build gobuster' && false)"],
                        ["bash", "-lc", "go build -o gobuster ."],
                    ],
                }
            },
        ],
    },
    "16": {
        "name": "theHarvester",
        "run": ["theHarvester", "-h"],
        "help": "https://github.com/laramies/theHarvester",
        "open_shell": False,
        "installers": [
            {"brew": ["theharvester"]},
            {"pip": ["theHarvester"]},
            {
                "git": {
                    "repo": "https://github.com/laramies/theHarvester.git",
                    "dest": os.path.join(TOOLS_DIR, "theHarvester"),
                    "post_cmds": [
                        ["python3", "-m", "pip", "install", "-r", "requirements/base.txt"],
                        ["python3", "-m", "pip", "install", "-r", "requirements/dev.txt"],
                    ],
                }
            },
        ],
    },
    "17": {
        "name": "amass",
        "run": ["bash", "-lc", "amass -h || true && bash"],
        "help": "https://github.com/owasp-amass/amass",
        "open_shell": True,
        "installers": [
            {"brew": ["amass"]},
            {"apt": ["amass"]},
            {"dnf": ["amass"]},
            {"pacman": ["amass"]},
        ],
    },
    "18": {
        "name": "subfinder",
        "run": ["bash", "-lc", "subfinder -h || true && bash"],
        "help": "https://github.com/projectdiscovery/subfinder",
        "open_shell": True,
        "installers": [
            {"brew": ["subfinder"]},
            {"apt": ["subfinder"]},
            {"dnf": ["subfinder"]},
            {"pacman": ["subfinder"]},
        ],
    },
    "19": {
        "name": "ffuf",
        "run": ["bash", "-lc", "ffuf -h || true && bash"],
        "help": "https://github.com/ffuf/ffuf",
        "open_shell": True,
        "installers": [
            {"brew": ["ffuf"]},
            {"apt": ["ffuf"]},
            {"dnf": ["ffuf"]},
            {"pacman": ["ffuf"]},
        ],
    },
    "20": {
        "name": "masscan",
        "run": ["bash", "-lc", "masscan --help || true && bash"],
        "help": "https://github.com/robertdavidgraham/masscan",
        "open_shell": True,
        "installers": [
            {"brew": ["masscan"]},
            {"apt": ["masscan"]},
            {"dnf": ["masscan"]},
            {"pacman": ["masscan"]},
        ],
    },
    "21": {
        "name": "feroxbuster",
        "run": ["bash", "-lc", "feroxbuster -h || true && bash"],
        "help": "https://github.com/epi052/feroxbuster",
        "open_shell": True,
        "installers": [
            {"brew": ["feroxbuster"]},
            {"apt": ["feroxbuster"]},
            {"dnf": ["feroxbuster"]},
            {"pacman": ["feroxbuster"]},
        ],
    },
    "22": {
        "name": "Media Scraper",
        "run": [
            "bash",
            "-lc",
            "echo ''; echo 'Examples:'; echo '  gallery-dl https://www.instagram.com/<user>   # images/photos'; echo '  gallery-dl https://www.reddit.com/r/<sub>     # images/photos'; echo '  yt-dlp <video_or_playlist_url>                # video/audio'; echo ''; echo 'Both tools support --help for full options.'; echo ''; bash",
        ],
        "help": "https://github.com/mikf/gallery-dl | https://github.com/yt-dlp/yt-dlp",
        "open_shell": True,
        "installers": [
            {"brew": ["gallery-dl", "yt-dlp"]},
            {"apt": ["gallery-dl", "yt-dlp"]},
            {"dnf": ["gallery-dl", "yt-dlp"]},
            {"pacman": ["gallery-dl", "yt-dlp"]},
            {"pip": ["gallery-dl", "yt-dlp"]},
        ],
    },
}

# Map display numbers (in sequential order) to the original tool ids.  These
# mappings allow the menu to use sequential numbers while preserving
# internal references to the underlying registry keys. When a user
# enters a display number, run_tool_by_id will translate it to the
# corresponding original key via this mapping.
DISPLAY_ID_MAP: Dict[str, str] = {
    "1": "1",    # Recon-ng
    "2": "2",    # Nikto
    "3": "3",    # DNSrecon
    "4": "4",    # UDPSCAN
    "5": "14",   # nmap
    "6": "5",    # Infoga
    "7": "6",    # NoSint
    "8": "7",    # IntelBase
    "9": "16",   # theHarvester
    "10": "17",  # amass
    "11": "18",  # subfinder
    "12": "8",   # XSStrike
    "13": "9",   # sqlmap
    "14": "15",  # gobuster
    "15": "19",  # ffuf
    "16": "21",  # feroxbuster
    "17": "20",  # masscan
    "18": "10",  # ZipBrute (FBF)
    "19": "11",  # PDFBrute (FBF)
    "20": "12",  # OpenSSL
    "21": "13",  # GnuPG
    "22": "22",  # Media Scraper
}

# Resource-related functions
def probable_seclists_paths() -> List[str]:
    paths = [
        "/usr/share/seclists",
        "/opt/homebrew/opt/seclists/share/seclists",
        "/usr/local/opt/seclists/share/seclists",
        os.path.join(RESOURCES_DIR, "SecLists"),
    ]
    return [p for p in paths if os.path.isdir(p)]

def install_seclists() -> bool:
    mgr = detect_pkg_mgr()
    print(Colors.yellow + "[*] Installing SecLists ...")
    if mgr == "brew" and install_with_brew(["seclists"]):
        return True
    if mgr == "apt" and install_with_apt(["seclists"]):
        return True
    if mgr == "dnf" and install_with_dnf(["seclists"]):
        return True
    if mgr == "pacman" and install_with_pacman(["seclists"]):
        return True
    dest = os.path.join(RESOURCES_DIR, "SecLists")
    return install_with_git("https://github.com/danielmiessler/SecLists.git", dest)

def determine_default_wordlist() -> Optional[str]:
    candidates = [
        "Discovery/Web-Content/raft-large-words.txt",
        "Discovery/Web-Content/directory-list-2.3-medium.txt",
    ]
    for root in probable_seclists_paths():
        for rel in candidates:
            p = os.path.join(root, rel)
            if os.path.isfile(p):
                return p
        web_content = os.path.join(root, "Discovery", "Web-Content")
        if os.path.isdir(web_content):
            for name in ("raft-large-words.txt", "directory-list-2.3-medium.txt"):
                p = os.path.join(web_content, name)
                if os.path.isfile(p):
                    return p
            for entry in sorted(Path(web_content).rglob("*.txt")):
                return str(entry)
    return None

def user_shell_profile() -> str:
    sh = os.environ.get("SHELL", "")
    home = str(Path.home())
    if "zsh" in sh or current_os() == "darwin":
        return os.path.join(home, ".zshrc")
    return os.path.join(home, ".bashrc")

def ensure_profile_lines(lines: List[str]) -> Tuple[str, bool]:
    profile = user_shell_profile()
    Path(profile).touch(exist_ok=True)
    with open(profile, "r", encoding="utf-8", errors="ignore") as f:
        existing = f.read()
    to_write: List[str] = []
    for ln in lines:
        if ln.strip() and ln.strip() not in existing:
            to_write.append(ln)
    if to_write:
        with open(profile, "a") as f:
            f.write("\n# --- CZD-Tools Resources ---\n")
            for ln in to_write:
                f.write(ln + "\n")
        return profile, True
    return profile, False

def setup_resources_and_defaults() -> None:
    ok = install_seclists()
    if not ok:
        input(
            Colors.red
            + "SecLists install failed. Press Enter to continue.\n >>> "
        )
        return
    roots = probable_seclists_paths()
    root = roots[0] if roots else None
    dfl = determine_default_wordlist()
    if not dfl:
        input(
            Colors.red
            + "Could not locate a default wordlist inside SecLists. Press Enter.\n >>> "
        )
        return
    exports: List[str] = []
    if root:
        exports.append(f'export CZD_SECLISTS="{root}"')
    exports.append(f'export CZD_WORDLIST="{dfl}"')
    exports.extend(
        [
            "alias gobuster='function _gb(){ [[ \" $* \" == *\" -w \"* ]] && command gobuster \"$@\" || command gobuster -w \"$CZD_WORDLIST\" \"$@\"; }; _gb'",
            "alias ffuf='function _ff(){ [[ \" $* \" == *\" -w \"* ]] && command ffuf \"$@\" || command ffuf -w \"$CZD_WORDLIST\" \"$@\"; }; _ff'",
            "alias feroxbuster='function _fx(){ [[ \" $* \" == *\" -w \"* ]] && command feroxbuster \"$@\" || command feroxbuster -w \"$CZD_WORDLIST\" \"$@\"; }; _fx'",
        ]
    )
    profile, changed = ensure_profile_lines(exports)
    print(
        Colors.green
        + f"[+] Resources installed.\n  CZD_SECLISTS={root}\n  CZD_WORDLIST={dfl}\n  Aliases added for gobuster, ffuf, feroxbuster in {profile}\n  Open a new shell or source your profile to use them.\n"
    )
    input(Colors.green + "Press Enter to continue.\n >>> ")

# ---------- Install orchestration ----------
def install_tool(tool_id: str) -> bool:
    cfg = TOOL_REGISTRY[tool_id]
    mgr = detect_pkg_mgr()
    print(Colors.yellow + f"[*] Installing {cfg['name']} ...")
    installers = cfg.get("installers", [])
    tried_any = False

    def try_inst(entry: dict) -> bool:
        nonlocal tried_any
        tried_any = True
        if "brew" in entry and mgr == "brew":
            return install_with_brew(entry["brew"])
        if "apt" in entry and mgr == "apt":
            return install_with_apt(entry["apt"])
        if "apk" in entry and mgr == "apk":
            return install_with_apk(entry["apk"])
        if "dnf" in entry and mgr == "dnf":
            return install_with_dnf(entry["dnf"])
        if "pacman" in entry and mgr == "pacman":
            return install_with_pacman(entry["pacman"])
        # cross-try other managers if present
        if "brew" in entry and have("brew"):
            return install_with_brew(entry["brew"])
        if "apt" in entry and have("apt"):
            return install_with_apt(entry["apt"])
        if "apk" in entry and have("apk"):
            return install_with_apk(entry["apk"])
        if "dnf" in entry and have("dnf"):
            return install_with_dnf(entry["dnf"])
        if "pacman" in entry and have("pacman"):
            return install_with_pacman(entry["pacman"])
        if "pip" in entry:
            return install_with_pip(entry["pip"])
        if "git" in entry:
            info = entry["git"]
            return install_with_git(
                info["repo"], info["dest"], info.get("post_cmds")
            )
        return False

    for ent in installers:
        if try_inst(ent):
            print(Colors.green + f"[+] {cfg['name']} installed.")
            return True
    if not tried_any:
        print(Colors.red + "[!] No valid installer option declared for this platform.")
        return False
    print(Colors.red + f"[!] Failed to install {cfg['name']}.")
    return False

# ---------- Runners / UI ----------

# ---------------------------------------------------------------------------
# Menu Rendering Helpers
# ---------------------------------------------------------------------------
# These helper functions generate fixed-width rows for the two-column menu.
# Each menu row is 73 characters wide (71 interior characters plus borders).
# The left and right columns each receive COL_W characters plus one leading space.
COL_W: int = 34

def hr(sep: str = "╦") -> str:
    """Return a horizontal rule with a separator (╦ for top, ╩ for bottom).

    The returned string is exactly 73 characters wide: a border char '╠',
    35 box-drawing '═' characters, the provided separator, another 35 '═'
    characters, and a border char '╣'.
    """
    return f"╠{'═'*35}{sep}{'═'*35}╣"

def make_row(left: str = "", right: str = "") -> str:
    """Return a single menu row, padding or truncating as needed.

    Both the left and right strings are truncated to COL_W-1 characters and
    appended with an ellipsis if too long. They are then padded with spaces
    to exactly COL_W characters. The row begins with '║ ', followed by the
    left column, then '║ ', then the right column, and finally '║'.
    """
    left  = (left[:COL_W-1] + "…") if len(left) > COL_W else left
    right = (right[:COL_W-1] + "…") if len(right) > COL_W else right
    return f"║ {left:<{COL_W}}║ {right:<{COL_W}}║"
def run_tool_by_id(tool_id: str) -> None:
    """Launch a tool based on its display ID.

    The user sees sequential display IDs in the menu (1 through 22), but
    internally tools are keyed by their original IDs defined in
    ``TOOL_REGISTRY``.  This function looks up the actual tool ID via
    ``DISPLAY_ID_MAP``.  If the display ID isn't in the mapping, it is
    assumed to already be a valid ``TOOL_REGISTRY`` key.  The rest of the
    installation and launch logic then operates on the resolved ID.
    """
    # Map the user‑facing display ID to the internal tool ID.  If the
    # display ID isn't found, fall back to the provided ID to support
    # backwards compatibility.
    actual_id = DISPLAY_ID_MAP.get(tool_id, tool_id)
    cfg = TOOL_REGISTRY[actual_id]
    # Install the tool if it isn't already installed (by internal ID).
    if not tool_installed(actual_id):
        ans = (
            input(
                Colors.green
                + f" {cfg['name']} is not installed. Install now? (y/n):\n >>> "
            )
            .strip()
            .lower()
        )
        if ans != "y":
            return
        if not install_tool(actual_id):
            input(
                Colors.red + "Install failed. Press Enter to continue.\n >>> "
            )
            return
        mark_installed(actual_id)
        input(Colors.green + " Press Enter to run.\n >>> ")
    try:
        print(Colors.yellow + f"Launching {cfg['name']}...")
        if cfg.get("cwd"):
            os.chdir(cfg["cwd"])
        cmd = cfg["run"]
        subprocess.run(cmd)
        if cfg.get("open_shell") and not (
            len(cmd) >= 1 and cmd[0] in ("bash", "zsh")
        ):
            shell = os.environ.get("SHELL") or (
                "/bin/zsh" if current_os() == "darwin" else "/bin/bash"
            )
            subprocess.call([shell])
        sys.exit()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(
            Colors.red
            + f"An error occurred while running {cfg['name']}: {e}"
        )

def menu_lines() -> str:
    """Render a two‑column menu with fixed‑width rows.

    The left column lists categories and their tools.  The right column lists
    available commands and options.  Rows are padded or truncated to fit
    within 73 characters (71 interior + 2 border) and are joined by top
    and bottom horizontal rules.  A separator (╦ for the top, ╩ for the bottom)
    divides the two columns.
    """
    # Build the left column from category definitions.  Category titles
    # appear on their own line, followed by indented tool entries.
    left: List[str] = []
    def cat(title: str) -> None:
        left.append(f"{title}")
    def item(entry: str) -> None:
        left.append(f"  ├── {entry}")

    # Define categories and their display IDs in the order they should appear.
    # Each list of IDs refers to sequential display numbers (e.g. "1", "2", "3"),
    # which are mapped to the corresponding internal tool IDs via
    # ``DISPLAY_ID_MAP``.  This ensures that the menu displays 1–22 in
    # order while still referencing the correct tools in ``TOOL_REGISTRY``.
    categories = [
        ("Reconnaissance", ["1", "2", "3", "4", "5"]),
        ("OSINT", ["6", "7", "8", "9", "10", "11"]),
        ("Web-App Testing", ["12", "13", "14", "15", "16"]),
        ("Scanning", ["17"]),
        ("Password Cracking", ["18", "19"]),
        ("Crypto", ["20", "21"]),
        ("Media", ["22"]),
    ]
    for title, ids in categories:
        cat(title)
        for tid in ids:
            # Resolve the internal ID via DISPLAY_ID_MAP.  If the display
            # ID isn't mapped, use it directly (useful for future tools).
            actual_id = DISPLAY_ID_MAP.get(tid, tid)
            if actual_id in TOOL_REGISTRY:
                item(f"[{tid}] {TOOL_REGISTRY[actual_id]['name']}")

    # Build the right column with static option entries.
    right: List[str] = []
    right.append("Options")
    right.append("  ├── [i] Install All")
    right.append("  ├── [r] Resources")
    right.append("  ├── [t] Themes")
    right.append("  ├── [x] Exit")
    right.append("  ├── [?] Help")
    right.append("  └── [!] Project Page")

    # Pad the shorter column so both have the same number of rows.
    rows = max(len(left), len(right))
    left += [""] * (rows - len(left))
    right += [""] * (rows - len(right))

    # Assemble the output with a top and bottom horizontal rule and each row
    # constructed via make_row().  The separators (╦ and ╩) ensure the
    # correct corners and intersections for the menu box.
    lines: List[str] = []
    lines.append(hr("╦"))
    for lval, rval in zip(left, right):
        lines.append(make_row(lval, rval))
    lines.append(hr("╩"))
    return "\n".join(lines)

def help_table_lines() -> str:
    lines: List[str] = [
        "╠══════════════╬═══════════════════════════════════════════════╣"
    ]
    for tid in sorted(TOOL_REGISTRY.keys(), key=lambda x: int(x)):
        cfg = TOOL_REGISTRY[tid]
        nm = cfg["name"][:12].ljust(12)
        hp = (cfg.get("help") or "")[:47].ljust(47)
        lines.append(f"║ {nm} ║ {hp} ║")
        lines.append(
            "╠══════════════╬═══════════════════════════════════════════════╣"
        )
    return "\n".join(lines)

def choose_theme() -> None:
    theme = load_theme()
    subprocess.run(["clear"])
    theme_menu = """
======================================================================
||                    CZD Hacking Tools v1.3.2                    ||
======================================================================

Type 'm' to go back to menu."""
    themes: Dict[str, str] = {
        "1": "white",
        "2": "white_to_red",
        "3": "red_to_white",
        "4": "white_to_green",
        "5": "green_to_white",
        "6": "white_to_blue",
        "7": "blue_to_white",
        "8": "black",
        "9": "black_to_red",
        "10": "red_to_black",
        "11": "black_to_green",
        "12": "green_to_black",
        "13": "black_to_blue",
        "14": "blue_to_black",
        "15": "red",
        "16": "green",
        "17": "blue",
        "18": "gray",
        "19": "yellow",
        "20": "purple",
        "21": "cyan",
        "22": "orange",
        "23": "pink",
        "24": "turquoise",
        "25": "light_gray",
        "26": "dark_gray",
        "27": "light_red",
        "28": "light_green",
        "29": "light_blue",
        "30": "dark_red",
        "31": "dark_green",
        "32": "dark_blue",
        "33": "red_to_yellow",
        "34": "yellow_to_red",
        "35": "red_to_purple",
        "36": "purple_to_red",
        "37": "green_to_yellow",
        "38": "yellow_to_green",
        "39": "green_to_cyan",
        "40": "cyan_to_green",
        "41": "blue_to_cyan",
        "42": "cyan_to_blue",
        "43": "blue_to_purple",
        "44": "purple_to_blue",
        "45": "red_to_blue",
        "46": "blue_to_red",
        "47": "red_to_green",
        "48": "green_to_red",
        "49": "green_to_blue",
        "50": "blue_to_green",
        "51": "rainbow",
    }
    single = SINGLE_COLORS[:]
    while True:
        try:
            # Default to an empty string for unknown themes to avoid None + str errors
            color = getattr(Colors, theme, "")
            is_single = theme in single
            print(
                (color + theme_menu)
                if is_single
                else Colorate.Vertical(color, theme_menu, 1)
            )
        except Exception:
            input(
                Colors.red
                + "Error: Invalid color attribute. Press Enter to reload.\n   >>>   "
            )
            return
        theme_choice = input(Colors.green + " └──> ").strip().lower()
        if theme_choice in themes:
            selected = themes[theme_choice]
            try:
                with open(THEME_JSON, "w") as file:
                    json.dump({"theme": selected}, file)
                return
            except IOError as e:
                print(Colors.red + f"Error saving theme: {e}")
                return
        elif theme_choice == "m":
            return
        else:
            input(
                Colors.red
                + "Invalid option, press Enter to try again.\n   >>>   "
            )

def help_menu() -> None:
    """Display the help screen with a centered banner and help table.

    The original version of this tool used a large block of ASCII art at the top
    of the help screen. That art looked impressive, but it also made the right
    edges of the menu mis‑align with the rest of the text. To improve
    readability and ensure the lines match up cleanly, we construct a simple
    banner using box‑drawing characters. The banner width (73 characters)
    matches the width of the help table and option lines, so everything lines
    up neatly on both the left and right edges.
    """
    theme = load_theme()
    subprocess.run(["clear"])
    # Build a centred title and heading within a 73‑character wide box.  The
    # title text is centred within the 71‑character interior; the <Help> label
    # is centred as well.  A top and bottom border use heavy box‑drawing
    # characters to match the rest of the UI.
    title = "CZD Hacking Tools v1.3.2"
    heading = "<Help>"
    interior_width = 71  # 73 total minus the two border characters
    # Compute left/right padding for the title and heading.
    left_pad_title = (interior_width - len(title)) // 2
    right_pad_title = interior_width - len(title) - left_pad_title
    left_pad_heading = (interior_width - len(heading)) // 2
    right_pad_heading = interior_width - len(heading) - left_pad_heading
    top_border = "╔" + "═" * interior_width + "╗"
    bottom_border = "╚" + "═" * interior_width + "╝"
    title_line = "║" + " " * left_pad_title + title + " " * right_pad_title + "║"
    heading_line = "║" + " " * left_pad_heading + heading + " " * right_pad_heading + "║"
    # Assemble the help screen.  Insert the help table lines between the
    # heading and the bottom border.  help_table_lines() already returns
    # correctly sized lines (width 73) with box‑drawing characters, so we
    # append them directly.
    helpscreen = (
        f"{top_border}\n"
        f"{title_line}\n"
        f"{top_border}\n"
        f"{heading_line}\n"
        f"{help_table_lines()}\n"
        f"{bottom_border}"
    )
    # Default to an empty string for unknown themes to avoid None + str errors
    color = getattr(Colors, theme, "")
    is_single = theme in SINGLE_COLORS
    print((color + helpscreen) if is_single else Colorate.Vertical(color, helpscreen, 1))
    while True:
        option_2 = input(Colors.green + "Type 'm' to go back.\n └──> ").strip().lower()
        if option_2 == "m":
            return
        input(Colors.red + "\nInvalid option, press Enter to try again. \n   >>>   ")

def report_issue() -> None:
    print(Colors.yellow + "\nProject page: \nhttps://github.com/CamoRageaholic1")
    input(Colors.green + "\n >>> ")
    return

def install_all() -> None:
    for tid in sorted(TOOL_REGISTRY.keys(), key=lambda x: int(x)):
        if not tool_installed(tid):
            print(
                Colors.cyan
                + f"==> Installing {TOOL_REGISTRY[tid]['name']}"
            )
            ok = install_tool(tid)
            if ok:
                mark_installed(tid)
            else:
                print(
                    Colors.red
                    + f"[!] Skipped marking {TOOL_REGISTRY[tid]['name']} due to install failure."
                )
    input(Colors.green + "Install-all complete. Press Enter.\n >>> ")

def main() -> None:
    theme = load_theme()
    subprocess.run(["clear"])
    # Construct a centred title within a 73‑character wide banner.  We
    # compute padding so that the title text is centred within the 71‑character
    # interior of the box.  Two top borders are used to visually separate the
    # title from the menu below.  This design ensures the left and right
    # edges of the banner line up cleanly with the rest of the interface.
    interior_width = 71
    title = "CZD Hacking Tools v1.3.2"
    left_pad_title = (interior_width - len(title)) // 2
    right_pad_title = interior_width - len(title) - left_pad_title
    top_border = "╔" + "═" * interior_width + "╗"
    title_line = "║" + " " * left_pad_title + title + " " * right_pad_title + "║"
    # Assemble the banner.  After the title block we reuse the standard
    # section borders and option lines as before.  The menu_lines() call
    # generates the category and tool listing.
    banner = f"""{top_border}
{title_line}
{top_border}
║                https://github.com/CamoRageaholic1                     ║
{menu_lines()}
║ * Use responsibly and with authorization                              ║
╚═══════════════════════════════════════════════════════════════════════╝"""
    # Default to an empty string for unknown themes to avoid None + str errors
    color = getattr(Colors, theme, "")
    is_single = theme in SINGLE_COLORS
    print(
        (color + banner)
        if is_single
        else Colorate.Vertical(color, banner, 1)
    )
    while True:
        option = input(Colors.green + " └──> ").strip().lower()
        if option == "t":
            choose_theme()
            return main()
        elif option == "i":
            install_all()
            return main()
        elif option in ("?", "h"):
            help_menu()
            return main()
        elif option == "!":
            report_issue()
            return main()
        elif option == "r":
            setup_resources_and_defaults()
            return main()
        elif option == "x":
            subprocess.call(["clear"])
            sys.exit(0)
        # If a numeric option matches a display ID, run the corresponding tool.
        elif option in DISPLAY_ID_MAP:
            run_tool_by_id(option)
            return
        else:
            input(
                Colors.red
                + "Invalid option, press Enter to try again. \n   >>>   "
            )
            subprocess.call(["clear"])
            print(
                (color + banner)
                if is_single
                else Colorate.Vertical(color, banner, 1)
            )

if __name__ == "__main__":
    main()