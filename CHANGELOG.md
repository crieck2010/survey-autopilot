# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-01

### Added
- `autopilot.compose`: optional trend priors in `search_composition`
  (`trend_priors=<survey-trends radar dict>`). Validated strictly:
  must be a dict, `version == 1`, `priors` a dict of str → number with each
  multiplier in [0.25, 4.0]; anything else → priors ignored entirely with
  the reason recorded in `"trend_priors_reason"`. When valid, each
  candidate's `total` is multiplied by the mean prior of its preset's
  format tags (missing tags count as 1.0); score entries keep both
  `"total"` (adjusted) and `"total_unadjusted"`, and winner selection uses
  the adjusted total. `trend_priors=None` is byte-identical to v0.1.0
  scoring (regression-tested). autopilot never imports survey-trends —
  the priors dict is caller-supplied (optional-peer direction).
- `autopilot.compose.PRESET_FORMAT_TAGS`: heuristic preset → format-tag
  mapping (`dark_strands`/`dark_flow` → particle-flow / flow-field),
  documented as heuristic; unknown presets score neutrally (1.0), never
  penalized.
- `tests/test_compose_priors.py`: 22 tests (winner flip via priors, strict
  validation, None-identity regression, unknown-preset neutrality,
  manifest fields).

## [0.1.0] - 2026-10-01

### Added
- `autopilot.compose`: automatic composition search ("render 3, ship 1") —
  `score_thumbnail` (coverage / contrast / label-legibility heuristics) and
  `search_composition` (caller-supplied render callback, winner + ranked scores).
- `autopilot.scaling`: `robust_limits` — NaN-safe percentile colormap limits
  with honest degenerate fallbacks (`degenerate-empty`, `degenerate-constant`)
  and clipped-fraction metadata. Targets the hue/scalar channel; survey-viz's
  p99 brightness channel is untouched.
- `autopilot.qa`: `qa_field` data QA gate (all-NaN steps, out-of-plausible-range
  cells, temporal gaps) returning a `QAReport`; `repair` with `drop` /
  `interpolate` / `fail` policies that record every action, never silently.
- `autopilot.density`: `strand_count_for_bbox` — density-by-area strand counts,
  calibrated to ~3135 strands for the North America bbox at base_density=0.5,
  clamped to [500, 6000].
- `autopilot.salience`: `salience_map` (0.6 speed + 0.4 temperature anomaly,
  NaN-safe) and `rank_label_positions` (salience minus brightness penalty,
  nearest-cell sampling, deterministic).
- `autopilot.stride`: `STRIDE_TABLE` + `recommend_stride` for
  tide / synoptic / seasonal / climate / event phenomena; unknown phenomena
  raise `ValueError` listing valid keys.
- Full pytest suite (39 tests), all green on a fresh clone.
