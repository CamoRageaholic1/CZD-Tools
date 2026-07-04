#!/bin/bash
# clear-mac-cache.sh - Clear tmp/cache on macOS to free up reported disk usage
# Usage: ./clear-mac-cache.sh        (safe mode, no sudo)
#        sudo ./clear-mac-cache.sh   (also clears system caches)

set -u

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

bytes_to_human() {
  local b=$1
  if   [ "$b" -gt 1073741824 ]; then printf "%.2f GB" "$(echo "$b/1073741824" | bc -l)"
  elif [ "$b" -gt 1048576 ];    then printf "%.2f MB" "$(echo "$b/1048576" | bc -l)"
  elif [ "$b" -gt 1024 ];       then printf "%.2f KB" "$(echo "$b/1024" | bc -l)"
  else printf "%d B" "$b"; fi
}

disk_free() {
  df -k / | awk 'NR==2 {print $4 * 1024}'
}

START_FREE=$(disk_free)
echo -e "${GREEN}=== macOS Cache Cleaner ===${NC}"
echo "Starting free space: $(bytes_to_human "$START_FREE")"
echo

clean_dir() {
  local desc=$1
  local path=$2
  if [ -d "$path" ]; then
    echo -e "${YELLOW}[*]${NC} Clearing $desc — $path"
    find "$path" -mindepth 1 -not -path "*/.*" -delete 2>/dev/null || true
  fi
}

# User-level caches (no sudo needed)
clean_dir "User cache"            "$HOME/Library/Caches"
clean_dir "User logs"             "$HOME/Library/Logs"
clean_dir "Saved app state"       "$HOME/Library/Saved Application State"
clean_dir "WebKit cache"          "$HOME/Library/WebKit"
clean_dir "Quicklook thumbnails"  "$HOME/Library/Caches/com.apple.QuickLook.thumbnailcache"

# Browser caches
clean_dir "Chrome cache"          "$HOME/Library/Caches/Google/Chrome"
clean_dir "Safari cache"          "$HOME/Library/Caches/com.apple.Safari"
clean_dir "Firefox cache"         "$HOME/Library/Caches/Firefox"
clean_dir "Brave cache"           "$HOME/Library/Caches/BraveSoftware"

# Dev tool caches
clean_dir "npm cache"             "$HOME/.npm/_cacache"
clean_dir "pip cache"             "$HOME/Library/Caches/pip"
clean_dir "pipx cache"            "$HOME/.local/pipx/.cache"
clean_dir "Homebrew cache"        "$(brew --cache 2>/dev/null)"
clean_dir "Docker tmp"            "$HOME/Library/Containers/com.docker.docker/Data/tmp"
clean_dir "Xcode DerivedData"     "$HOME/Library/Developer/Xcode/DerivedData"
clean_dir "Xcode Archives"        "$HOME/Library/Developer/Xcode/Archives"

# Trash
echo -e "${YELLOW}[*]${NC} Emptying ~/.Trash"
rm -rf "$HOME/.Trash/"* 2>/dev/null || true

# System-level (requires sudo)
if [ "$(id -u)" -eq 0 ]; then
  echo
  echo -e "${GREEN}=== Running with sudo: clearing system caches ===${NC}"
  clean_dir "System cache"        "/Library/Caches"
  clean_dir "System logs"         "/Library/Logs"
  clean_dir "Private tmp"         "/private/tmp"
  clean_dir "Private var tmp"     "/private/var/tmp"
  clean_dir "Diagnostic reports"  "/Library/Logs/DiagnosticReports"

  echo -e "${YELLOW}[*]${NC} Purging inactive memory"
  purge 2>/dev/null || true

  echo -e "${YELLOW}[*]${NC} Forcing APFS snapshot cleanup (helps with 'purgeable' space)"
  tmutil thinlocalsnapshots / 999999999999 4 2>/dev/null || true
else
  echo
  echo -e "${YELLOW}Note:${NC} Run with sudo to also clear /Library/Caches, /private/tmp, and APFS snapshots."
fi

echo
END_FREE=$(disk_free)
RECLAIMED=$((END_FREE - START_FREE))
echo -e "${GREEN}=== Done ===${NC}"
echo "Ending free space:   $(bytes_to_human "$END_FREE")"
if [ "$RECLAIMED" -gt 0 ]; then
  echo -e "Reclaimed:           ${GREEN}$(bytes_to_human "$RECLAIMED")${NC}"
else
  echo -e "Reclaimed:           ${RED}$(bytes_to_human "$RECLAIMED")${NC} (snapshots may release later)"
fi
