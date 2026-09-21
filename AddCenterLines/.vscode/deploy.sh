#!/bin/sh

set -eu

source_dir="$(cd "$(dirname "$0")/.." && pwd)"
target_dir="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/CenterLines"
old_target_dir="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/AddCenterLines"

rm -rf "$old_target_dir"
mkdir -p "$target_dir"
cp "$source_dir/CenterLines.py" "$target_dir/CenterLines.py"
cp "$source_dir/CenterLines.manifest" "$target_dir/CenterLines.manifest"
cp "$source_dir/CenterLines.svg" "$target_dir/CenterLines.svg"
rm -f "$target_dir/CenterLines.png"
rm -rf "$target_dir/resources"
cp -R "$source_dir/resources" "$target_dir/resources"

printf 'Deployed CenterLines to %s\n' "$target_dir"