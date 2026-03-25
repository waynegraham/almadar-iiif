#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a lightweight index for QA browsing of IIIF manifests."
    )
    parser.add_argument("--manifests-dir", default="manifests")
    parser.add_argument("--output", default="_manifest_index.json")
    return parser.parse_args()


def first(value, fallback=""):
    if isinstance(value, list) and value:
        return value[0]
    return fallback


def extract_label(manifest, fallback):
    label_obj = manifest.get("label", {})
    if isinstance(label_obj, dict):
        for lang_value in label_obj.values():
            label = first(lang_value)
            if label:
                return str(label)
    return fallback


def extract_thumbnail(manifest):
    items = manifest.get("items", [])
    if not items:
        return ""
    canvas = items[0]
    pages = canvas.get("items", [])
    if not pages:
        return ""
    annotations = pages[0].get("items", [])
    if not annotations:
        return ""
    body = annotations[0].get("body", {})
    services = body.get("service", [])
    if services:
        service_id = services[0].get("id", "")
        if service_id:
            return f"{service_id}/full/!300,300/0/default.jpg"
    return body.get("id", "")


def main():
    args = parse_args()
    manifests_dir = Path(args.manifests_dir)
    output_path = manifests_dir / args.output

    records = []
    for manifest_path in sorted(manifests_dir.glob("*.json")):
        name = manifest_path.name
        if name.startswith("_"):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        object_id = extract_label(manifest, manifest_path.stem)
        records.append(
            {
                "id": object_id,
                "manifestPath": f"manifests/{name}",
                "thumbnail": extract_thumbnail(manifest),
                "canvasCount": len(manifest.get("items", [])),
            }
        )

    payload = {"total": len(records), "items": records}
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path} ({len(records)} records)")


if __name__ == "__main__":
    main()
