#!/usr/bin/env python3
import hashlib
import re
import unicodedata
from pathlib import Path


SUSPICIOUS_NAME_PATTERNS = (
    re.compile(r"(?i)\bcopy\b"),
    re.compile(r"(?i)\bscreen[\s_-]?shot\b"),
    re.compile(r"(?i)topaz-upscale"),
    re.compile(r"(?i)\.(?:tif|tiff|jpg|jpeg|png)\.(?:tif|tiff|jpg|jpeg|png)$"),
    re.compile(r"\s\.(?:tif|tiff|jpg|jpeg|png)$", re.IGNORECASE),
)


def _slugify_stem(stem: str) -> str:
    text = unicodedata.normalize("NFKD", stem)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return "image"
    return text


def canonicalize_filename(name: str, max_stem_len: int = 100) -> str:
    path = Path(name)
    stem = _slugify_stem(path.stem)[:max_stem_len].rstrip("_")
    if not stem:
        stem = "image"
    return f"{stem}{path.suffix.lower()}"


def canonicalize_with_hash_suffix(name: str, salt: str = "", max_stem_len: int = 100) -> str:
    candidate = canonicalize_filename(name=name, max_stem_len=max_stem_len)
    digest = hashlib.sha1(f"{salt}:{name}".encode("utf-8")).hexdigest()[:8]
    stem = Path(candidate).stem[: max_stem_len - 9].rstrip("_")
    ext = Path(candidate).suffix.lower()
    return f"{stem}_{digest}{ext}"


def is_normalized_filename(name: str, max_stem_len: int = 100) -> bool:
    return name == canonicalize_filename(name=name, max_stem_len=max_stem_len)


def suspicious_name_reasons(name: str):
    reasons = []
    for pattern in SUSPICIOUS_NAME_PATTERNS:
        if pattern.search(name):
            reasons.append(pattern.pattern)
    return reasons
