#!/usr/bin/env bash
set -euo pipefail

images_dir="./images"
overwrite=false

usage() {
  cat <<'EOF'
Usage: ./convert-to-tif.sh [-d IMAGES_DIR] [--overwrite]

Options:
  -d, --dir       Images root directory (default: ./images)
  --overwrite     Overwrite existing .tif outputs
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

if ! command -v magick >/dev/null 2>&1; then
  echo "Error: ImageMagick CLI 'magick' not found in PATH." >&2
  exit 1
fi

images_root="$(realpath "$images_dir")"
archive_root="$images_root/other_file_types"
mkdir -p "$archive_root"

converted=0
found=0

is_cmyk() {
  local file="$1"
  local cs
  cs="$(magick identify -ping -format "%[colorspace]" "$file" 2>/dev/null || true)"
  [[ "${cs^^}" == "CMYK" ]]
}

while IFS= read -r -d '' src; do
  found=1

  dst="${src%.*}.tif"
  needs_archive=false
  reason="format"

  src_lc="${src,,}"
  if ! [[ "$src_lc" =~ \.(psd|dng|heic|heif)$ ]]; then
    reason="cmyk"
  fi

  if [[ -f "$dst" && "$overwrite" != true ]]; then
    echo "Skipping conversion (TIF exists): $dst"
  else
    if [[ "$reason" == "cmyk" && "$src" == "$dst" ]]; then
      tmp="${dst}.tmp_srgb.tif"
      echo "Converting CMYK in place: $src -> $dst"
      magick "$src" -colorspace sRGB "$tmp"
      mv -f "$tmp" "$dst"
    else
      echo "Converting ($reason): $src -> $dst"
      magick "$src" -colorspace sRGB "$dst"
    fi
    converted=$((converted + 1))
  fi

  if [[ "$src" != "$dst" ]]; then
    needs_archive=true
  fi

  if [[ "$needs_archive" == true ]]; then
    rel="${src#"$images_root"/}"
    archive_target="$archive_root/$rel"
    mkdir -p "$(dirname "$archive_target")"
    echo "Archiving original: $src -> $archive_target"
    mv -f "$src" "$archive_target"
  fi
done < <(
  while IFS= read -r -d '' file; do
    rel="${file#"$images_root"/}"
    [[ "$rel" == other_file_types/* ]] && continue
    file_lc="${file,,}"
    if [[ "$file_lc" =~ \.(psd|dng|heic|heif)$ ]]; then
      printf '%s\0' "$file"
      continue
    fi
    if [[ "$file_lc" =~ \.(tif|tiff|jpg|jpeg|png|webp|jp2|jpx|j2k|jpf)$ ]] && is_cmyk "$file"; then
      printf '%s\0' "$file"
    fi
  done < <(find "$images_root" -type f -print0)
)

if [[ "$found" -eq 0 ]]; then
  echo "No PSD/DNG/HEIC/CMYK files found under $images_root"
  exit 0
fi

echo "Done. Converted $converted file(s)."
