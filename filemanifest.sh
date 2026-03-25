#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <directory> [output_file] [algo]"
  echo "Example: $0 . manifest-sha256.txt sha256"
  echo "Allowed algo: sha1, sha224, sha256, sha384, sha512"
  exit 1
}

[[ $# -lt 1 || $# -gt 3 ]] && usage

DIR="$1"
OUT_NAME="${2:-manifest-sha256.txt}"
ALGO="${3:-sha256}"

case "$ALGO" in
  sha1|sha224|sha256|sha384|sha512) ;;
  *) echo "Unsupported algo: $ALGO" >&2; exit 1 ;;
esac

DIR_ABS="$(cd "$DIR" && pwd)"
if [[ "$OUT_NAME" = /* || "$OUT_NAME" =~ ^[A-Za-z]:/ ]]; then
  OUT_PATH="$OUT_NAME"
else
  OUT_PATH="$DIR_ABS/$OUT_NAME"
fi

# Pick hashing command available in Git Bash
hash_file() {
  local algo="$1" file="$2"
  if command -v "${algo}sum" >/dev/null 2>&1; then
    "${algo}sum" "$file" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    local bits="${algo#sha}"
    shasum -a "$bits" "$file" | awk '{print $1}'
  else
    echo "No suitable hash command found (${algo}sum or shasum)." >&2
    exit 1
  fi
}

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(
  cd "$DIR_ABS"

  REL_OUT=""
  case "$OUT_PATH" in
    "$DIR_ABS"/*) REL_OUT="${OUT_PATH#"$DIR_ABS"/}" ;;
  esac

  find . -type f -print0 | sort -z | while IFS= read -r -d '' f; do
    rel="${f#./}"
    [[ -n "$REL_OUT" && "$rel" == "$REL_OUT" ]] && continue
    h="$(hash_file "$ALGO" "$rel")"
    printf '%s  %s\n' "$h" "$rel"
  done > "$TMP_FILE"
)

mv "$TMP_FILE" "$OUT_PATH"
trap - EXIT

echo "Wrote manifest: $OUT_PATH"
