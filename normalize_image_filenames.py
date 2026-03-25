#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from iiif_filename_rules import canonicalize_filename, canonicalize_with_hash_suffix


def parse_args():
    parser = argparse.ArgumentParser(
        description="Normalize image filenames deterministically and emit an identifier mapping."
    )
    parser.add_argument("--images-dir", default="images")
    parser.add_argument(
        "--output",
        default="qa/reports/filename_normalization_map.json",
        help="JSON output path for original/canonical/applied mapping.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rename files in place. Without this flag, script runs in report-only mode.",
    )
    return parser.parse_args()


def build_plan(images_dir: Path):
    files = sorted([p for p in images_dir.rglob("*") if p.is_file()], key=lambda p: p.as_posix().lower())
    plan = []
    seen = set()

    for src in files:
        canonical = canonicalize_filename(src.name)
        candidate = src.with_name(canonical)
        rel = src.relative_to(images_dir).as_posix()

        if candidate in seen or (candidate.exists() and candidate != src):
            canonical = canonicalize_with_hash_suffix(src.name, salt=rel)
            candidate = src.with_name(canonical)

        seen.add(candidate)
        plan.append(
            {
                "source": src,
                "target": candidate,
                "sourceRel": rel,
                "targetRel": candidate.relative_to(images_dir).as_posix(),
                "changed": src != candidate,
            }
        )
    return plan


def apply_plan(plan):
    temp_moves = []
    for item in plan:
        src = item["source"]
        tgt = item["target"]
        if src == tgt:
            continue
        tmp = src.with_name(f".tmp_norm_{src.name}")
        src.rename(tmp)
        temp_moves.append((tmp, tgt))
    for tmp, tgt in temp_moves:
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(tgt)


def main():
    args = parse_args()
    images_dir = Path(args.images_dir)
    plan = build_plan(images_dir)

    if args.apply:
        apply_plan(plan)

    changed = sum(1 for i in plan if i["changed"])
    payload = {
        "rulesVersion": "2026-02-25",
        "imagesDir": str(images_dir),
        "mode": "apply" if args.apply else "report-only",
        "summary": {
            "totalFiles": len(plan),
            "filesNeedingChange": changed,
            "filesChanged": changed if args.apply else 0,
        },
        "items": [
            {
                "source": item["sourceRel"],
                "target": item["targetRel"],
                "changed": item["changed"],
                "applied": bool(args.apply and item["changed"]),
            }
            for item in plan
        ],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Planned: {len(plan)} files")
    print(f"Needs rename: {changed}")
    print(f"Mode: {'apply' if args.apply else 'report-only'}")
    print(f"Map: {out}")


if __name__ == "__main__":
    main()
