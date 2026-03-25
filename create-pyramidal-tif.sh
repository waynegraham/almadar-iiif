#!/usr/bin/env bash
set -euo pipefail

images_dir="./images"
overwrite=false

usage() {
  cat <<'EOF'
Usage: ./create-pyramidal-tif.sh [-d IMAGES_DIR] [--overwrite]

Options:
  -d, --dir       Images root directory (default: ./images)
  --overwrite     Overwrite existing pyramidal TIFF outputs
  -h, --help      Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dir)
      images_dir="$2"
      shift 2
      ;;
    --overwrite)
      overwrite=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v vips >/dev/null 2>&1; then
  echo "Error: libvips CLI 'vips' not found in PATH." >&2
  exit 1
fi

images_root="$(realpath "$images_dir")"
count=0
found=0

while IFS= read -r -d '' src; do
  found=1

  rel="${src#"$images_root"/}"
  dst="$images_root/pyramidal/$rel"
  dst_dir="$(dirname "$dst")"

  if [[ -f "$dst" && "$overwrite" != true ]]; then
    echo "Skipping (already exists): $dst"
    continue
  fi

  mkdir -p "$dst_dir"
  echo "Creating pyramidal TIFF: $src -> $dst"
  vips tiffsave "$src" "$dst" \
    --tile \
    --pyramid \
    --compression jpeg \
    --Q 90 \
    --tile-width 256 \
    --tile-height 256 \
    --bigtiff

  count=$((count + 1))
done < <(
  find "$images_root" -type f \( -iname '*.tif' -o -iname '*.tiff' \) \
    -not -path "$images_root/other_file_types/*" \
    -not -path "$images_root/pyramidal/*" \
    -print0
)

if [[ "$found" -eq 0 ]]; then
  echo "No TIFF files found under $images_root"
  exit 0
fi

echo "Done. Created $count pyramidal TIFF file(s)."
