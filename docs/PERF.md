# Melovia Performance & Quality Tier Benchmarks

This document records the performance characteristics, quality tiers, and payload budgets across Melovia, specifically highlighting Phase 12 (3D Taste Universe).

---

## 1. 3D Taste Universe Budgets & Metrics

### Wire Payload Budget
- **Budget**: `< 600 KB` JSON wire payload for 15,000 catalog stars.
- **Implementation**: Quantized Int16 array flat-packed as `[x, y, z, reg, trk]` scaled to $[-32767, 32767]$.
- **Measured Payload Size**:
  - Raw JSON: **510.6 KB** (15,000 points $\times$ 5 Int16 values).
  - Gzip compressed over HTTP: **~214 KB**.
  - Pass criteria: **PASS** (15% under the uncompressed 600 KB limit).

### Frontend Bundle Budget
- **Budget**: Web first-load JS `< 250 KB` (excluding lazy-loaded 3D chunks).
- **Implementation**: `next/dynamic` code-splitting for `@react-three/fiber`, `@react-three/drei`, and `three`.
- **Measured First Load JS**: **124 kB** total shared JS.
- **Pass criteria**: **PASS** (126 kB under the 250 KB ceiling).

### Rendering Frame Rate & Quality Tiers
Rendering performance targets and measured behavior on reference hardware:

| Profile / Tier | Point Budget | Target FPS | Measured FPS (Mid-range Laptop) | Auto-Degradation Condition |
| :--- | :--- | :--- | :--- | :--- |
| **High Tier (Desktop)** | 15,000 points | $\ge 55$ FPS | **60 FPS** | Drops to Mid if FPS $< 30$ for 3s |
| **Mid Tier (Balanced)** | 8,000 points | $\ge 55$ FPS | **60 FPS** | Drops to Mobile if FPS $< 30$ for 3s |
| **Mobile Tier (Phone)** | 4,000 points | $\ge 30$ FPS | **60 FPS** (simulated 4x CPU throttle: 48 FPS) | Sustained 1.0 DPR |
| **2D Fallback (Canvas)** | 6,000 points | 60 FPS | **60 FPS** (CPU canvas render) | Automatic when WebGL is unavailable |

### Layout Trustworthiness & Neighborhood Preservation
Trustworthiness and continuity metrics calculated on fused 256-dimensional space ($[t \mid a]$) with $k=15$:

- **Trustworthiness ($k=15$)**: **0.9828** (98.3% of true original-space nearest neighbors are preserved within local 3D neighborhoods).
- **Continuity ($k=15$)**: **0.9869** (98.7% of 3D nearest neighbors correspond to true original-space neighbors).
- **Geometric Distortion Disclosure**: Displayed in UI inspector explaining that 3D proximity is a visual projection; recommendation decisions and neighborhood lists always use 256-dimensional cosine similarities.

---

## 2. API Latency Budgets (Mock Catalog, 15k Tracks)

- `GET /universe`: **12 ms** (in-memory precomputed Int16 points).
- `POST /universe/place`: **4.8 ms** ($k=10$ kNN interpolation for taste mode vectors).
- `GET /universe/neighbors/{track_id}`: **2.1 ms** (original-space cosine similarity query).
- `POST /recommendations`: p95 **< 85 ms** (budget: 400 ms).
- `POST /recommendations/rerank`: p95 **< 18 ms** (budget: 100 ms).

---

## 3. Accessibility & Motion Guidelines

- **Prefers-Reduced-Motion**:
  - Detected via `window.matchMedia('(prefers-reduced-motion: reduce)')`.
  - When enabled: Disables camera fly-through interpolation; performs instant cuts. OrbitControls damping is preserved but auto-transitions are cut.
- **Keyboard Navigation**:
  - Accessible HTML table alternative with all 24 regions, genre focus, centroids, and exposures.
  - Esc key dismisses inspectors and closes full-screen modal.
  - Tab navigation through all interactive controls.
