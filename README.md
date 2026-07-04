# CZD-Tools

A menu-driven security tool suite for OSINT, reconnaissance, and web application
testing. CZD-Tools is a single-file Python launcher that shows a colored terminal
menu and installs each tool on demand. When you pick a tool, the launcher checks
whether it is present and, if it is not, installs it using whatever package manager
your system has available (apt, pip, pipx, git, brew, apk, dnf, or pacman). You run
one script, choose a tool from the list, and the launcher handles the setup for you.

Author: David Osisek (CamoZeroDay)

## Why it exists

Security work usually means juggling a dozen separate tools, each with its own
install steps and dependencies. CZD-Tools puts them behind one menu and takes care
of installing them the first time you use them, so you spend time running the tool
instead of setting it up.

## Requirements

- Python 3.9 or newer (developed and tested on Python 3.14).
- Optional: `pystyle`, which draws the colored menu. If it is not installed, the
  launcher falls back to a plain-text menu and still works.

## Usage

```bash
python3 CZD-Tools_v1.3.2.py
```

The launcher writes its per-user state (which tools are installed, the selected
theme) into your home directory the first time it runs, so the program itself can
sit in a read-only location such as `/opt`.

## The tool catalog

The launcher manages roughly two dozen tools spanning OSINT (open-source
intelligence gathering), network reconnaissance, and web application testing.
Third-party tools are fetched on demand rather than copied into this repository.
That keeps this repo small and keeps each tool under its own upstream project and
its own license.

## Bundled helper projects

A few small utilities of my own ship alongside the launcher:

- **plex-organizer** — helper scripts for organizing a Plex media library.
- **vault-to-html** — renders an Obsidian notes vault into a static HTML site for
  read-only viewing.
- **wger-seed** — seed data and helper scripts for a self-hosted wger workout tracker.
- **clear-mac-cache.sh** — a macOS cache-clearing maintenance script.

## Responsible use

These tools are for authorized security testing, research, and education only.
Always confirm you have permission to test a target, respect rate limits and
robots.txt, and follow the laws that apply to you. You are responsible for how you
use them.

## License

MIT. See the [LICENSE](LICENSE) file.
