#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from iiif_filename_rules import canonicalize_filename, suspicious_name_reasons


PRIMARY_PATTERN = re.compile(r"(^|_)PRIMARY_IMAGE($|_)", re.IGNORECASE)
KNOWN_TYPO_NORMALIZATIONS = (
    ("ADITIONAL_IMAGE", "ADDITIONAL_IMAGE"),
    ("ADITIONAL", "ADDITIONAL"),
    ("ADDITONAL", "ADDITIONAL"),
)

CONVERSION_REQUIRED_FORMATS = {"HEIC", "DNG"}
SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".jp2",
    ".j2k",
    ".jpf",
    ".jpx",
    ".bmp",
    ".gif",
    ".webp",
    ".heic",
    ".dng",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit images for IIIF suitability and output JSON + Markdown reports."
    )
    parser.add_argument("--images-dir", default="images")
    parser.add_argument("--json-out", default="qa/reports/image_qa_report.json")
    parser.add_argument("--md-out", default="qa/reports/image_qa_report.md")
    parser.add_argument("--schema-version", default="1.0.0")
    parser.add_argument("--primary-min-dimension", type=int, default=3000)
    parser.add_argument("--additional-min-dimension", type=int, default=1200)
    parser.add_argument("--warn-max-file-size-mb", type=float, default=500.0)
    parser.add_argument("--warn-max-megapixels", type=float, default=200.0)
    parser.add_argument("--magick-bin", default="magick")
    return parser.parse_args()


def normalize_name(name: str) -> str:
    out = name
    for old, new in KNOWN_TYPO_NORMALIZATIONS:
        out = re.sub(old, new, out, flags=re.IGNORECASE)
    return out


def infer_role(file_name: str) -> str:
    stem = Path(file_name).stem
    normalized = normalize_name(stem)
    if PRIMARY_PATTERN.search(normalized):
        return "PRIMARY"
    return "ADDITIONAL"


def identify_image(magick_bin: str, path: Path):
    fmt = "%m|%w|%h|%z|%[colorspace]|%[channels]|%[compression]\n"
    proc = subprocess.run(
        [magick_bin, "identify", "-ping", "-format", fmt, str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, proc.stderr.strip() or "identify failed"
    first_line = next((line for line in proc.stdout.splitlines() if line.strip()), "")
    parts = first_line.split("|")
    if len(parts) != 7:
        return None, f"unexpected identify payload: {proc.stdout.strip()[:200]}"
    return {
        "format": parts[0],
        "width": int(parts[1]),
        "height": int(parts[2]),
        "bitDepth": int(parts[3]),
        "colorSpace": parts[4],
        "channels": parts[5],
        "compression": parts[6],
    }, None


def append_issue(issues, code, severity, message, recommendation):
    issues.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "recommendation": recommendation,
        }
    )


def evaluate_file(path: Path, rel_path: str, metadata, err, args):
    role = infer_role(path.name)
    ext = path.suffix.lower()
    file_size_mb = round(path.stat().st_size / (1024 * 1024), 2)
    issues = []
    canonical_identifier = canonicalize_filename(path.name)
    identifier_compliant = canonical_identifier == path.name

    if not identifier_compliant:
        append_issue(
            issues,
            "IDENTIFIER_NOT_CANONICAL",
            "fail",
            "Filename does not match deterministic canonical identifier rules.",
            f"Rename to canonical form (example: {canonical_identifier}).",
        )

    for _ in suspicious_name_reasons(path.name):
        append_issue(
            issues,
            "SUSPICIOUS_FILENAME_PATTERN",
            "warn",
            "Filename contains quality-risk indicator (copy/screenshot/upscale/double-extension).",
            "Review provenance and keep only approved master assets.",
        )
        break

    if metadata is None:
        if ext in SUPPORTED_IMAGE_EXTENSIONS:
            append_issue(
                issues,
                "UNREADABLE_IMAGE",
                "fail",
                f"Image could not be decoded: {err}",
                "Re-export from source and validate with `magick identify`.",
            )
        else:
            append_issue(
                issues,
                "NON_IMAGE_FILE",
                "fail",
                "File in images directory is not an image asset.",
                "Move to a non-image directory and exclude from IIIF image ingest.",
            )
        return {
            "path": rel_path,
            "fileName": path.name,
            "role": role,
            "isImage": False,
            "identifier": {
                "canonical": canonical_identifier,
                "compliant": identifier_compliant,
            },
            "metadata": None,
            "issues": issues,
        }

    width = metadata["width"]
    height = metadata["height"]
    min_dim = min(width, height)
    megapixels = round((width * height) / 1_000_000, 2)

    fmt = metadata["format"].upper()
    colorspace = metadata["colorSpace"].upper()
    channels = metadata["channels"].lower()

    if fmt in CONVERSION_REQUIRED_FORMATS:
        append_issue(
            issues,
            "REQUIRES_CONVERSION_FORMAT",
            "fail",
            f"Format {fmt} must be converted before IIIF ingest.",
            "Convert to normalized TIFF (sRGB) and generate pyramidal delivery derivative.",
        )

    if colorspace == "CMYK":
        append_issue(
            issues,
            "REQUIRES_CONVERSION_COLORSPACE",
            "fail",
            "CMYK image detected; pipeline requires sRGB normalization.",
            "Convert to sRGB and verify visual fidelity against source.",
        )

    if "alpha" in channels or "rgba" in channels or "cmyka" in channels:
        append_issue(
            issues,
            "HAS_ALPHA_CHANNEL",
            "warn",
            "Alpha/transparency channel detected.",
            "Flatten to opaque background unless transparency is required for use case.",
        )

    min_threshold = args.primary_min_dimension if role == "PRIMARY" else args.additional_min_dimension
    if min_dim < min_threshold:
        append_issue(
            issues,
            "BELOW_ROLE_MIN_DIMENSION",
            "fail",
            f"{role} image min dimension {min_dim}px is below threshold {min_threshold}px.",
            "Use a higher-resolution source or downgrade to supplemental context only.",
        )

    if file_size_mb > args.warn_max_file_size_mb:
        append_issue(
            issues,
            "VERY_LARGE_FILE",
            "warn",
            f"File size {file_size_mb} MB exceeds warning threshold {args.warn_max_file_size_mb} MB.",
            "Avoid direct serving of source; use tiled pyramidal derivatives.",
        )

    if megapixels > args.warn_max_megapixels:
        append_issue(
            issues,
            "VERY_LARGE_PIXEL_COUNT",
            "warn",
            f"Pixel count {megapixels} MP exceeds warning threshold {args.warn_max_megapixels} MP.",
            "Validate necessity; downscale or generate optimized derivatives for IIIF.",
        )

    return {
        "path": rel_path,
        "fileName": path.name,
        "role": role,
        "isImage": True,
        "identifier": {
            "canonical": canonical_identifier,
            "compliant": identifier_compliant,
        },
        "metadata": {
            "format": fmt,
            "width": width,
            "height": height,
            "minDimension": min_dim,
            "megapixels": megapixels,
            "bitDepth": metadata["bitDepth"],
            "colorSpace": metadata["colorSpace"],
            "channels": metadata["channels"],
            "compression": metadata["compression"],
            "fileSizeMB": file_size_mb,
        },
        "issues": issues,
    }


def status_from_issues(issues):
    severities = {issue["severity"] for issue in issues}
    if "fail" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"


def build_summary(items):
    summary = {
        "totalFiles": len(items),
        "totalImages": sum(1 for i in items if i["isImage"]),
        "statusCounts": {"pass": 0, "warn": 0, "fail": 0},
        "issueCounts": {},
        "roleCounts": {"PRIMARY": 0, "ADDITIONAL": 0},
    }
    for item in items:
        status = item["status"]
        summary["statusCounts"][status] += 1
        summary["roleCounts"][item["role"]] += 1
        for issue in item["issues"]:
            summary["issueCounts"][issue["code"]] = summary["issueCounts"].get(issue["code"], 0) + 1
    return summary


def write_markdown_report(md_out: Path, payload):
    summary = payload["summary"]
    thresholds = payload["thresholds"]
    fail_items = [i for i in payload["items"] if i["status"] == "fail"]
    warn_items = [i for i in payload["items"] if i["status"] == "warn"]

    lines = []
    lines.append("# Image QA Report")
    lines.append("")
    lines.append(f"- Generated: {payload['generatedAt']}")
    lines.append(f"- Overall status: **{payload['status'].upper()}**")
    lines.append(f"- Images directory: `{payload['imagesDir']}`")
    lines.append("")
    lines.append("## Thresholds")
    lines.append("")
    lines.append(f"- PRIMARY min dimension: `{thresholds['primaryMinDimension']}px`")
    lines.append(f"- ADDITIONAL min dimension: `{thresholds['additionalMinDimension']}px`")
    lines.append(f"- Warn max file size: `{thresholds['warnMaxFileSizeMB']} MB`")
    lines.append(f"- Warn max megapixels: `{thresholds['warnMaxMegapixels']} MP`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total files scanned: `{summary['totalFiles']}`")
    lines.append(f"- Image files decoded: `{summary['totalImages']}`")
    lines.append(f"- Pass: `{summary['statusCounts']['pass']}`")
    lines.append(f"- Warn: `{summary['statusCounts']['warn']}`")
    lines.append(f"- Fail: `{summary['statusCounts']['fail']}`")
    lines.append("")
    lines.append("## Top Failure Categories")
    lines.append("")
    for code, count in sorted(summary["issueCounts"].items(), key=lambda kv: kv[1], reverse=True)[:12]:
        lines.append(f"- `{code}`: `{count}`")
    lines.append("")
    lines.append("## Failed Assets (first 100)")
    lines.append("")
    lines.append("| Path | Role | Issues |")
    lines.append("|---|---|---|")
    for item in fail_items[:100]:
        codes = ", ".join(issue["code"] for issue in item["issues"])
        lines.append(f"| `{item['path']}` | `{item['role']}` | `{codes}` |")
    lines.append("")
    lines.append("## Warning Assets (first 100)")
    lines.append("")
    lines.append("| Path | Role | Issues |")
    lines.append("|---|---|---|")
    for item in warn_items[:100]:
        codes = ", ".join(issue["code"] for issue in item["issues"])
        lines.append(f"| `{item['path']}` | `{item['role']}` | `{codes}` |")
    lines.append("")
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    images_dir = Path(args.images_dir)
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)

    items = []
    for path in sorted([p for p in images_dir.rglob("*") if p.is_file()], key=lambda p: p.as_posix().lower()):
        rel = path.relative_to(images_dir).as_posix()
        metadata, err = identify_image(args.magick_bin, path)
        entry = evaluate_file(path=path, rel_path=rel, metadata=metadata, err=err, args=args)
        entry["status"] = status_from_issues(entry["issues"])
        items.append(entry)

    summary = build_summary(items)
    overall_status = "fail" if summary["statusCounts"]["fail"] > 0 else "pass"

    payload = {
        "schemaVersion": args.schema_version,
        "rulesVersion": "2026-02-25",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "imagesDir": str(images_dir),
        "status": overall_status,
        "thresholds": {
            "primaryMinDimension": args.primary_min_dimension,
            "additionalMinDimension": args.additional_min_dimension,
            "warnMaxFileSizeMB": args.warn_max_file_size_mb,
            "warnMaxMegapixels": args.warn_max_megapixels,
        },
        "summary": summary,
        "items": items,
    }

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_report(md_out=md_out, payload=payload)

    print(f"Status: {overall_status}")
    print(f"JSON report: {json_out}")
    print(f"Markdown report: {md_out}")


if __name__ == "__main__":
    main()
