"""Automatic composition search ("render 3, ship 1").

Why this exists: a full-resolution aesthetic render is expensive; a thumbnail
is cheap. Instead of a human eyeballing every candidate, render N small
candidate thumbnails (different preset / rotation / basemap), score each with
three cheap, auditable heuristics, and ship the best. The scoring uses no
randomness, so identical thumbnails always rank identically.

Honest limitations:
- Coverage treats "data" as "pixels brighter than near-black". A dark-on-dark
  colormap or a basemap that is legitimately dark everywhere will score low
  coverage even when the render is fine. This is a heuristic, not a judgment.
- Contrast is the standard deviation of luminance clipped at 0.25. It rewards
  tonal spread; a deliberately flat aesthetic (fog, night) will score lower.
- Label legibility assumes labels are light text drawn over dark areas. Dark
  text on light basemaps inverts the assumption — the caller owns that choice.
- score_thumbnail never sees the data itself, only the render. Garbage data
  that renders with good coverage and contrast will score well. Pair this
  with autopilot.qa upstream of the render.
"""

from __future__ import annotations

import numpy as np

#: Default scoring weights. Coverage dominates because a frame with no visible
#: data is unrecoverable in refinement; contrast matters next; label
#: legibility is the smallest weight because labels can be re-placed later.
DEFAULT_WEIGHTS = {"coverage": 0.4, "contrast": 0.35, "label_legibility": 0.25}

#: Pixels whose brightest channel exceeds this are counted as "data".
_COVERAGE_BRIGHTNESS_FLOOR = 0.05

#: Luminance std is divided by this and clipped to [0, 1] for contrast.
_CONTRAST_NORMALIZER = 0.25


def _as_rgb_float01(thumbnail) -> np.ndarray:
    """Normalize a HxWx3/HxWx4 thumbnail to float64 RGB in [0, 1].

    Accepts uint8 0..255 or float 0..1. Float input with values > 1 is treated
    as 0..255 (a common sloppy-thumbnail mistake) rather than rejected.
    """
    arr = np.asarray(thumbnail)
    if arr.ndim != 3 or arr.shape[-1] not in (3, 4):
        raise ValueError(
            f"thumbnail must be HxWx3 or HxWx4, got shape {arr.shape}"
        )
    rgb = arr[..., :3]
    if rgb.dtype == np.uint8:
        return rgb.astype(np.float64) / 255.0
    rgb = rgb.astype(np.float64)
    with np.errstate(invalid="ignore"):
        peak = np.nanmax(rgb) if rgb.size else 0.0
    if peak > 1.0:
        rgb = rgb / 255.0
    return np.clip(rgb, 0.0, 1.0)


def score_thumbnail(thumbnail, label_boxes=None, weights=None) -> dict:
    """Score a single render thumbnail on three auditable heuristics.

    Args:
        thumbnail: HxWx3 or HxWx4 numpy array, float 0..1 or uint8 0..255.
        label_boxes: optional list of (x0, y0, x1, y1) pixel boxes where labels
            will sit. Score rewards dark backgrounds under labels.
        weights: optional override of DEFAULT_WEIGHTS (partial dicts OK).

    Returns:
        dict with "coverage", "contrast", "label_legibility", "total", and the
        "weights" actually used.

    Component definitions (all in [0, 1], higher is better):
    - coverage: fraction of pixels with max(R,G,B) > 0.05. Heuristic: data
      pixels are brighter than near-black backgrounds.
    - contrast: std of luminance (0.299R + 0.587G + 0.114B), divided by 0.25
      and clipped to [0, 1].
    - label_legibility: 1 - mean luminance inside label_boxes (labels should
      sit on dark areas); 0.5 neutral when no boxes are given.
    - total: weighted sum of the three.
    """
    rgb = _as_rgb_float01(thumbnail)
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    brightest = np.nanmax(rgb, axis=-1)
    coverage = float(np.mean(brightest > _COVERAGE_BRIGHTNESS_FLOOR))

    luminance = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    contrast = float(np.clip(np.nanstd(luminance) / _CONTRAST_NORMALIZER, 0.0, 1.0))

    if label_boxes:
        h, img_w = rgb.shape[:2]
        means = []
        for x0, y0, x1, y1 in label_boxes:
            xa, xb = max(0, int(x0)), min(img_w, int(x1))
            ya, yb = max(0, int(y0)), min(h, int(y1))
            if xb > xa and yb > ya:
                means.append(float(np.nanmean(luminance[ya:yb, xa:xb])))
        label_legibility = 1.0 - float(np.mean(means)) if means else 0.5
    else:
        label_legibility = 0.5

    total = (
        w["coverage"] * coverage
        + w["contrast"] * contrast
        + w["label_legibility"] * label_legibility
    )
    return {
        "coverage": coverage,
        "contrast": contrast,
        "label_legibility": label_legibility,
        "total": float(total),
        "weights": w,
    }


def search_composition(render_thumbnail, candidates, weights=None, label_boxes=None) -> dict:
    """Render every candidate thumbnail, score each, return the winner.

    Args:
        render_thumbnail: caller-supplied callback
            ``render_thumbnail(preset, rotation, basemap) -> thumbnail array``.
            The caller owns rendering entirely, including errors: exceptions
            raised by the callback propagate unchanged so failures are never
            silently swallowed or re-ranked.
        candidates: list of dicts, each with keys "preset", "rotation",
            "basemap" (values are opaque and passed straight through to the
            callback). Extra keys are preserved untouched.
        weights: optional scoring-weight overrides, as in score_thumbnail.
        label_boxes: optional label boxes, as in score_thumbnail.

    Returns:
        {"winner": <candidate dict>, "scores": [...], "weights": {...},
         "n_candidates": N} with "scores" sorted by total descending.
        With an empty candidate list, "winner" is None (honest, not an error).
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    scored = []
    for cand in candidates:
        thumb = render_thumbnail(cand["preset"], cand["rotation"], cand["basemap"])
        s = score_thumbnail(thumb, label_boxes=label_boxes, weights=w)
        scored.append(
            {
                "candidate": dict(cand),
                "coverage": s["coverage"],
                "contrast": s["contrast"],
                "label_legibility": s["label_legibility"],
                "total": s["total"],
            }
        )
    scored.sort(key=lambda d: d["total"], reverse=True)
    return {
        "winner": scored[0]["candidate"] if scored else None,
        "scores": scored,
        "weights": w,
        "n_candidates": len(scored),
    }
