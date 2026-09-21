#!/bin/sh

set -eu

source_dir="$(cd "$(dirname "$0")/.." && pwd)"
target_dir="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/FlattenCurveToPlane"

mkdir -p "$target_dir"
cp "$source_dir/FlattenCurveToPlane.py" "$target_dir/FlattenCurveToPlane.py"
cp "$source_dir/FlattenCurveToPlane.manifest" "$target_dir/FlattenCurveToPlane.manifest"
cp "$source_dir/FlattenCurveToPlane.png" "$target_dir/FlattenCurveToPlane.png"
rm -rf "$target_dir/resources"
cp -R "$source_dir/resources" "$target_dir/resources"

if ! PYTHONPATH="$target_dir" python3 -c 'import debugpy' >/dev/null 2>&1; then
    python3 -m pip install --disable-pip-version-check --quiet --target "$target_dir" debugpy
fi

printf 'Deployed FlattenCurveToPlane to %s\n' "$target_dir"