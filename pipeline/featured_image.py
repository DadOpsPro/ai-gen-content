"""
pipeline/featured_image.py
──────────────────────────
Article-of-the-Week hero image: brand-locked prompt + per-slug cache.

Cache lives at images/featured/{slug}.png (webp also accepted if present).
If a file already exists for that slug, it is never regenerated.
If OPENAI_API_KEY is missing or generation fails, return None so the
homepage keeps the solid teal panel.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import httpx

IMAGE_DIR = "images/featured"
EXTENSIONS = (".webp", ".png")
STATIC_FEATURED_DIR = Path(__file__).resolve().parent.parent / "static" / IMAGE_DIR

NAVY = "#0a0f1e"
TEAL = "#00c896"

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
PRIMARY_MODEL = "gpt-image-1"
PRIMARY_SIZE = "1024x1536"  # 2:3, close to the 3:4 hero slot
FALLBACK_MODEL = "dall-e-3"
FALLBACK_SIZE = "1024x1792"

STYLE_LOCK = (
    "Clean, slightly abstract editorial illustration for a professional "
    "developer-security blog. Brand-locked palette only: deep navy "
    f"{NAVY} and teal {TEAL}, with muted navy-gray negative space. "
    "Soft geometric shapes, subtle paper grain, generous empty space. "
    "Not photorealistic. No photoreal faces, no people portraits, "
    "no neon cyberpunk, no vendor logos, no product UI, no watermarks, "
    "no letters, no words, no numbers, no typography anywhere in the image."
)


def _safe_slug(slug: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "", slug or "")
    return cleaned.strip(".-") or "featured"


def build_featured_image_prompt(
    title: str,
    excerpt: str = "",
    concepts: Optional[Iterable[str]] = None,
) -> str:
    """Title + pitch + 1–2 concepts, locked to the brand illustration rules."""
    concept_list = [str(c).strip() for c in (concepts or []) if c and str(c).strip()]
    if not concept_list:
        words = [w for w in re.split(r"\W+", title or "") if len(w) > 3]
        concept_list = words[:2]
    concept_line = ", ".join(concept_list[:2]) or "developer security"
    pitch = " ".join((excerpt or "").split())
    if len(pitch) > 280:
        pitch = pitch[:277].rstrip() + "..."
    return (
        f"{STYLE_LOCK} "
        f"Subject drawn from this week's featured article. "
        f"Title: {title}. "
        f"Pitch: {pitch}. "
        f"Key concepts to evoke (do not render as text): {concept_line}. "
        "Portrait composition, roughly 3:4."
    )


def featured_image_alt(title: str) -> str:
    return f"Editorial illustration for {title} (AI-generated)"


def _candidate_dirs(output_dir: Path) -> List[Path]:
    return [Path(output_dir) / IMAGE_DIR, STATIC_FEATURED_DIR]


def find_cached_featured_image(slug: str, output_dir: Path) -> Optional[Path]:
    """Return the first existing cache file for slug, or None."""
    safe = _safe_slug(slug)
    for folder in _candidate_dirs(output_dir):
        for ext in EXTENSIONS:
            path = folder / f"{safe}{ext}"
            if path.is_file() and path.stat().st_size > 0:
                return path
    return None


def _copy_into_output(cached: Path, output_dir: Path) -> Path:
    dest_dir = Path(output_dir) / IMAGE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / cached.name
    if cached.resolve() != dest.resolve() and not dest.exists():
        shutil.copy2(cached, dest)
    return dest


def _generate_openai_image(prompt: str, dest: Path, api_key: str) -> None:
    """Call OpenAI Images; try gpt-image-1, then DALL·E 3. Writes dest."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    attempts: Sequence[dict] = (
        {"model": PRIMARY_MODEL, "size": PRIMARY_SIZE, "n": 1},
        {
            "model": FALLBACK_MODEL,
            "size": FALLBACK_SIZE,
            "n": 1,
            "response_format": "b64_json",
            "quality": "standard",
        },
    )
    last_error: Optional[str] = None
    for payload in attempts:
        try:
            response = httpx.post(
                OPENAI_IMAGES_URL,
                headers=headers,
                json={"prompt": prompt, **payload},
                timeout=120,
            )
        except Exception as exc:
            last_error = f"{payload['model']} request failed: {exc}"
            continue
        if response.status_code >= 400:
            last_error = (
                f"{payload['model']} HTTP {response.status_code}: "
                f"{response.text[:240]}"
            )
            continue
        item = (response.json().get("data") or [None])[0] or {}
        raw = None
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            image = httpx.get(item["url"], timeout=60)
            image.raise_for_status()
            raw = image.content
        if not raw:
            last_error = f"{payload['model']} returned no image data"
            continue
        dest.write_bytes(raw)
        return
    raise RuntimeError(last_error or "image generation failed")


def ensure_featured_image(record: Optional[Dict], output_dir: Path) -> Optional[str]:
    """
    Return a site-relative path such as images/featured/{slug}.png, or None.

    Never raises. Missing key / API failure / bad cache → None (teal fallback).
    """
    if not record or not record.get("slug"):
        return None

    slug = _safe_slug(str(record["slug"]))
    dest_dir = Path(output_dir) / IMAGE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    cached = find_cached_featured_image(slug, output_dir)
    if cached:
        try:
            dest = _copy_into_output(cached, output_dir)
        except OSError as exc:
            print(f"  ⚠️  Could not copy featured image cache: {exc}")
            return None
        print(f"  🖼️  Featured image cache hit: {dest.name}")
        return f"{IMAGE_DIR}/{dest.name}"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("  ⏭️  Featured image skipped — OPENAI_API_KEY not set (teal fallback)")
        return None

    prompt = build_featured_image_prompt(
        title=record.get("title") or slug,
        excerpt=record.get("excerpt") or "",
        concepts=record.get("tags") or [],
    )
    dest = dest_dir / f"{slug}.png"
    try:
        _generate_openai_image(prompt, dest, api_key)
    except Exception as exc:
        print(f"  ⚠️  Featured image generation failed ({exc}) — teal fallback")
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink()
        return None

    if dest.is_file() and dest.stat().st_size > 0:
        print(f"  🖼️  Featured image generated: {dest.name}")
        return f"{IMAGE_DIR}/{dest.name}"
    return None
