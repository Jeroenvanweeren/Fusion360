#!/bin/sh

set -eu

source_dir="$(cd "$(dirname "$0")/.." && pwd)"
target_dir="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/Midpoints"

mkdir -p "$target_dir"
cp "$source_dir/Midpoints.py" "$target_dir/Midpoints.py"
cp "$source_dir/Midpoints.manifest" "$target_dir/Midpoints.manifest"
rm -rf "$target_dir/resources"
cp -R "$source_dir/resources" "$target_dir/resources"

printf 'Deployed Midpoints to %s\n' "$target_dir"
