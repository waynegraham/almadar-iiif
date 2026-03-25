# almadar-iiif-clean

Developer README for the local IIIF image preparation and manifest-generation utilities in this repository.

## What This Repo Does

This repo contains a small, file-based pipeline for preparing image assets for IIIF delivery:

1. Normalize image filenames to deterministic identifiers.
2. Audit source images for format, dimensions, colorspace, and naming issues.
3. Convert incompatible sources to TIFF where needed.
4. Generate pyramidal TIFF delivery derivatives.
5. Generate IIIF Presentation API v3 manifests from the prepared images.
6. Generate a lightweight manifest index for QA or UI consumption.

The code is intentionally simple:

- Python scripts use only the standard library.
- Shell scripts wrap `magick`, `vips`, and common Unix tools.
- Input and output are plain files under the repo working tree.

## Expected Repo Layout

The scripts assume a workspace shaped roughly like this:

```text
.
|- images/
|- manifests/
|- qa/
|  \- reports/
|- normalize_image_filenames.py
|- qa_image_audit.py
|- generate_manifests.py
|- generate_manifest_index.py
|- iiif_filename_rules.py
|- convert-to-tif.sh
|- create-pyramidal-tif.sh
\- filemanifest.sh
```

Key conventions:

- `images/` is the primary input directory for local assets.
- `manifests/` is where generated IIIF manifests are written.
- `qa/reports/` is where QA reports and filename normalization reports are written by default.

## Prerequisites

### Required

- Python 3
- A filesystem layout containing an `images/` directory

### Required for image QA and conversion

- ImageMagick CLI available as `magick`

Used by:

- [qa_image_audit.py](/e:/projects/almadar-iiif-clean/qa_image_audit.py)
- [convert-to-tif.sh](/e:/projects/almadar-iiif-clean/convert-to-tif.sh)

### Required for pyramidal TIFF generation

- libvips CLI available as `vips`

Used by:

- [create-pyramidal-tif.sh](/e:/projects/almadar-iiif-clean/create-pyramidal-tif.sh)

### Required for shell scripts on Windows

- Git Bash, WSL, or another Bash-compatible environment

The `.sh` scripts use Bash features, `find`, `sort`, `awk`, `mktemp`, and `realpath`.

### Required for manifest generation

- A running IIIF image server exposing `info.json` responses

By default, [generate_manifests.py](/e:/projects/almadar-iiif-clean/generate_manifests.py) expects:

- Image server base: `http://localhost:8182`
- Manifest base: `http://localhost:8182/manifests`

For each image filename identifier, the script requests:

```text
http://localhost:8182/iiif/3/<identifier>/info.json
```

## Filename and Object-ID Rules

Filename behavior is centralized in [iiif_filename_rules.py](/e:/projects/almadar-iiif-clean/iiif_filename_rules.py).

Canonical filename normalization:

- Unicode is normalized and reduced to ASCII.
- Names are lowercased.
- Non-alphanumeric runs become `_`.
- `&` becomes `and`.
- Duplicate underscores are collapsed.
- Extensions are lowercased.

Example:

```text
Foo & Bar (Primary Image).JPG
-> foo_and_bar_primary_image.jpg
```

Collision handling:

- If two files would normalize to the same target name, `normalize_image_filenames.py` can append an 8-character SHA-1 suffix based on the original relative path.

Object grouping for manifests:

- [generate_manifests.py](/e:/projects/almadar-iiif-clean/generate_manifests.py) derives an object ID from the first three underscore-delimited stem tokens.
- Files whose stems contain `PRIMARY_IMAGE` are treated as primary images.
- A few typo variants of `ADDITIONAL` are normalized during role detection.

Implication:

- Naming consistency matters. If the first three stem tokens do not encode the object identifier correctly, the file will not be grouped as intended during manifest generation.

## Typical Workflow

### 1. Preview filename normalization

```bash
python normalize_image_filenames.py
```

Default output:

- `qa/reports/filename_normalization_map.json`

Apply renames in place:

```bash
python normalize_image_filenames.py --apply
```

### 2. Run image QA

```bash
python qa_image_audit.py
```

Default outputs:

- `qa/reports/image_qa_report.json`
- `qa/reports/image_qa_report.md`

This checks, among other things:

- canonical filename compliance
- suspicious filename patterns like `copy` or `screenshot`
- unreadable or non-image files inside `images/`
- unsupported ingest formats like `HEIC` and `DNG`
- CMYK images that require sRGB conversion
- alpha channels
- dimension thresholds by image role
- unusually large file sizes or megapixel counts

Default dimension thresholds:

- `PRIMARY`: 3000px minimum shorter side
- `ADDITIONAL`: 1200px minimum shorter side

### 3. Convert unsupported or CMYK sources to TIFF

```bash
./convert-to-tif.sh
```

What it does:

- Converts `PSD`, `DNG`, `HEIC`, and `HEIF` files to TIFF.
- Converts CMYK image files to sRGB TIFF.
- Moves original non-TIFF sources into `images/other_file_types/`.

Use `--overwrite` to replace existing TIFF outputs.

### 4. Generate pyramidal TIFF derivatives

```bash
./create-pyramidal-tif.sh
```

What it does:

- Scans TIFF files under `images/`
- Skips `images/other_file_types/`
- Skips existing `images/pyramidal/`
- Writes tiled pyramidal TIFFs under `images/pyramidal/`

Use `--overwrite` to replace existing pyramidal outputs.

### 5. Generate manifests

```bash
python generate_manifests.py
```

Default outputs in `manifests/`:

- one manifest per object, named `<object_id>.json`
- `_primary_image_conflicts.json`
- `_manifest_generation_errors.json`
- `_identifier_normalization_map.json`

Useful stricter mode:

```bash
python generate_manifests.py --enforce-normalized-identifiers --require-qa-pass
```

That mode will:

- fail objects containing non-canonical filenames
- refuse manifest generation unless `qa/reports/image_qa_report.json` has overall status `pass`

### 6. Build manifest index

```bash
python generate_manifest_index.py
```

Default output:

- `manifests/_manifest_index.json`

This produces a small browseable index with:

- manifest path
- thumbnail URL
- canvas count

## Script Reference

### [normalize_image_filenames.py](/e:/projects/almadar-iiif-clean/normalize_image_filenames.py)

Purpose:

- Create a deterministic rename plan for all files under `images/`
- Optionally apply the rename plan

Important flags:

- `--images-dir`
- `--output`
- `--apply`

### [qa_image_audit.py](/e:/projects/almadar-iiif-clean/qa_image_audit.py)

Purpose:

- Audit images for IIIF readiness and emit machine-readable and human-readable reports

Important flags:

- `--images-dir`
- `--json-out`
- `--md-out`
- `--primary-min-dimension`
- `--additional-min-dimension`
- `--warn-max-file-size-mb`
- `--warn-max-megapixels`
- `--magick-bin`

### [generate_manifests.py](/e:/projects/almadar-iiif-clean/generate_manifests.py)

Purpose:

- Generate IIIF Presentation API v3 manifests from local files and remote image-service metadata

Important flags:

- `--images-dir`
- `--manifests-dir`
- `--image-server-base`
- `--manifest-base`
- `--extensions`
- `--enforce-normalized-identifiers`
- `--qa-report`
- `--require-qa-pass`

Notes:

- The script reads only files directly inside `images/`, not nested directories.
- Object IDs come from the first three underscore-separated stem tokens.
- If more than one `PRIMARY_IMAGE` exists for an object, that manifest is skipped and reported as a conflict.

### [generate_manifest_index.py](/e:/projects/almadar-iiif-clean/generate_manifest_index.py)

Purpose:

- Generate a lightweight JSON index of manifests for QA or downstream UI use

Important flags:

- `--manifests-dir`
- `--output`

### [convert-to-tif.sh](/e:/projects/almadar-iiif-clean/convert-to-tif.sh)

Purpose:

- Normalize problematic formats and CMYK assets into TIFFs suitable for the rest of the pipeline

Important flags:

- `-d`, `--dir`
- `--overwrite`

### [create-pyramidal-tif.sh](/e:/projects/almadar-iiif-clean/create-pyramidal-tif.sh)

Purpose:

- Generate tiled pyramidal TIFF derivatives using libvips

Important flags:

- `-d`, `--dir`
- `--overwrite`

### [filemanifest.sh](/e:/projects/almadar-iiif-clean/filemanifest.sh)

Purpose:

- Write a deterministic checksum manifest for a directory tree

Example:

```bash
./filemanifest.sh manifests _manifest-sha256.txt sha256
```

## Outputs Worth Checking Into Review

When changing pipeline behavior, these outputs are the main artifacts to inspect:

- `qa/reports/filename_normalization_map.json`
- `qa/reports/image_qa_report.json`
- `qa/reports/image_qa_report.md`
- `manifests/_primary_image_conflicts.json`
- `manifests/_manifest_generation_errors.json`
- `manifests/_identifier_normalization_map.json`
- `manifests/_manifest_index.json`

## Development Notes

- There is no package structure or dependency manager here; scripts are meant to run directly.
- Python code currently depends only on the standard library.
- The shell utilities assume a Unix-like CLI environment even when run on Windows.
- Manifest generation depends on live `info.json` responses from the configured IIIF image server.
- QA and manifest generation encode rule versions directly in output payloads. If rules change materially, update those version strings intentionally.

## Recommended End-to-End Command Sequence

```bash
python normalize_image_filenames.py
python qa_image_audit.py
./convert-to-tif.sh
./create-pyramidal-tif.sh
python generate_manifests.py --enforce-normalized-identifiers
python generate_manifest_index.py
./filemanifest.sh manifests _manifest-sha256.txt sha256
```

If you want manifest generation to be blocked until QA is fully clean:

```bash
python generate_manifests.py --enforce-normalized-identifiers --require-qa-pass
```
