# CHANGELOG


## Unreleased

### Chores

- Verify single-path Railway deploy after GitHub disconnect (no-op)
  ([`db90afc`](https://github.com/edycutjong/castiron/commit/db90afcd5b6728d0622bee9dc02c4e17db0e667a))

### Continuous Integration

- Tolerate Railway 'Failed to stream build logs' flake — verify deploy via /healthz instead of
  failing on log-stream error
  ([`109cd5d`](https://github.com/edycutjong/castiron/commit/109cd5d748f52f9533c511906eb3f5f976fd20f9))


## v1.6.0 (2026-08-03)

### Documentation

- **readme**: Add Devpost project badge
  ([`71042c1`](https://github.com/edycutjong/castiron/commit/71042c1d0afb1e5179ed25fbbb48ad84496098bb))

### Features

- Credit sponsors (Backblaze + GMI Cloud) in README, landing footer, and pitch deck
  ([`5183b14`](https://github.com/edycutjong/castiron/commit/5183b14acc0294120252391a7ed5df285569bc12))


## v1.5.0 (2026-08-03)

### Documentation

- **readme**: Wire real demo video URL into Pitch Video badge
  ([`2b6189c`](https://github.com/edycutjong/castiron/commit/2b6189c4d088778d21068888520bc64576f81da0))

### Features

- **landing+pitch**: Add demo video link to footer + pitch deck Ask slide
  ([`2180fa3`](https://github.com/edycutjong/castiron/commit/2180fa33eecfc4682496bb56053daa25d9f658b4))


## v1.4.0 (2026-08-03)

### Features

- **pitch**: Rebuild deck to full spec — 10 slides, presenter mode (P), ESC overview, contrast debug
  (C), print-to-PDF (10 pages), cover animation, doc-quality architecture, real console screenshot
  with numbered callouts, QR ask
  ([`8fbd193`](https://github.com/edycutjong/castiron/commit/8fbd193365ae3abc244d00187bcff4db6ee15c86))


## v1.3.0 (2026-08-03)

### Features

- **pitch**: Add branded single-file pitch deck at /pitch.html (keyboard/swipe nav, 8 slides)
  ([`43c5eb7`](https://github.com/edycutjong/castiron/commit/43c5eb78f0dffae4e0eaa712131c3d63a0addae8))


## v1.2.0 (2026-08-03)

### Features

- **console**: Redesign producer console to match landing (Unbounded/Space Grotesk fonts, green
  gradient button, glass panels, mode pill)
  ([`2941e07`](https://github.com/edycutjong/castiron/commit/2941e078981ca5c3d4ac1772f9e0c8a53b9a8853))


## v1.1.1 (2026-08-03)

### Bug Fixes

- **security**: Upgrade landing to Next 15 + React 19, postcss 8.5, pin sharp≥0.35.3 — clears 24
  Dependabot alerts (0 npm vulns)
  ([`9308d0b`](https://github.com/edycutjong/castiron/commit/9308d0b0bd8239d3488ad991547b345f39f24793))

### Chores

- Prune unused docs assets + landing/readme polish
  ([`09f0cda`](https://github.com/edycutjong/castiron/commit/09f0cdaebd3cb2a9b0ed000bd2a0c6825000e57e))


## v1.1.0 (2026-08-03)

### Features

- **landing**: Web manifest + icons + a11y fixes (contrast, label-in-name), modern browserslist;
  README landing/api badges
  ([`73804d6`](https://github.com/edycutjong/castiron/commit/73804d62bd2a9200a0b99cfe6cf07bea70d4b56f))


## v1.0.1 (2026-08-03)

### Bug Fixes

- **readme**: Quote mermaid node labels so { } don't parse as diamond nodes
  ([`4ffb52c`](https://github.com/edycutjong/castiron/commit/4ffb52c6e84dd8dc2448787e93ce5460cf1ec61d))

### Chores

- Set baseline version to 1.0.0
  ([`b9c6eed`](https://github.com/edycutjong/castiron/commit/b9c6eedc4e3c3238f8a06f6373b6fd52e9508ebb))

- **pages**: Pin custom domain via CNAME
  ([`f31f26b`](https://github.com/edycutjong/castiron/commit/f31f26b23dc411ab6c0d66dcd0425b556a6fb76e))


## v1.0.0 (2026-08-03)

- Initial Release
