#!/usr/bin/env bash
# Daily intake: process /Volumes/2TB_OverFlow/Media Intake using configured
# per-kind destinations. Dry-run unless --apply is passed.
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/run.sh" "$@"
