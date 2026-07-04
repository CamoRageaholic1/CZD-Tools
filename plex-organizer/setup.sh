#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

OS="$(uname -s)"

# Install ffmpeg (provides ffprobe) if missing
if ! command -v ffprobe >/dev/null 2>&1; then
  case "$OS" in
    Darwin)
      if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew not found. Install from https://brew.sh first."
        exit 1
      fi
      echo "Installing ffmpeg via Homebrew..."
      brew install ffmpeg
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        echo "Installing ffmpeg via apt..."
        sudo apt-get update
        sudo apt-get install -y ffmpeg
      elif command -v dnf >/dev/null 2>&1; then
        echo "Installing ffmpeg via dnf..."
        sudo dnf install -y ffmpeg
      elif command -v pacman >/dev/null 2>&1; then
        echo "Installing ffmpeg via pacman..."
        sudo pacman -S --noconfirm ffmpeg
      else
        echo "Could not detect a package manager. Install ffmpeg manually, then re-run."
        exit 1
      fi
      ;;
    *)
      echo "Unsupported OS: $OS. Install ffmpeg manually, then re-run."
      exit 1
      ;;
  esac
fi

# Find a Python 3.10+ interpreter
PY=""
for cand in python3 python3.14 python3.13 python3.12 python3.11 python3.10 \
            /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$cand"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "No Python 3.10+ found. Install python3 (and python3-venv on Debian/Ubuntu) and re-run."
  exit 1
fi

# Create venv if needed. Detect a stale venv copied from another machine
# (its bin/* shebangs point at an absolute python path that does not exist
# on this host) and rebuild it transparently.
venv_is_broken() {
  [ -d .venv ] || return 0
  ./.venv/bin/python -c 'import sys' >/dev/null 2>&1 || return 0
  return 1
}
if venv_is_broken; then
  if [ -d .venv ]; then
    echo "Existing .venv is from another machine or broken; rebuilding..."
    rm -rf .venv
  fi
  echo "Creating virtualenv with $PY ..."
  "$PY" -m venv .venv || {
    echo "venv creation failed. On Debian/Ubuntu try: sudo apt-get install -y python3-venv"
    exit 1
  }
fi

./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

# Make sure config dir exists; warn if no key set
mkdir -p "$HOME/.config/plex-organizer"
if [ ! -f "$HOME/.config/plex-organizer/config.json" ]; then
  cat > "$HOME/.config/plex-organizer/config.json" <<'JSON'
{
  "tmdb_api_key": ""
}
JSON
  chmod 600 "$HOME/.config/plex-organizer/config.json"
  echo
  echo "NOTE: Add your TMDb API key to ~/.config/plex-organizer/config.json"
  echo "      or export TMDB_API_KEY=... before running."
fi

echo
echo "Setup complete."
echo "Run with:  $(pwd)/run.sh"
