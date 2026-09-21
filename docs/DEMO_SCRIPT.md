# Melovia 5-Minute Demonstration Script

This document details the rehearsed 5-minute live demonstration flow for Melovia, covering all **six core WOW moments**. It provides tested seed sets, step-by-step narration guidelines, exact expected system behaviors, and a multi-tier fallback plan.

---

## Demo Overview & Timing

| Minute | Stage | Focus / WOW Moment | Key Takeaway |
| :---: | :--- | :--- | :--- |
| **0:00 - 0:45** | **1. Onboarding & Seeds** | Quick Presets / Seed Search | $\le 2$ clicks to first recommendations. |
| **0:45 - 1:30** | **2. Steerable Discovery** | **WOW #1**: Discovery Slider ($d=0.0 \to 0.75$) | Real-time musical transformation without re-querying. |
| **1:30 - 2:15** | **3. Signal-True Explanations** | **WOW #3**: "Why This Track?" Drawer | Glass-box transparency rooted in ranking signals. |
| **2:15 - 3:15** | **4. Conversational Steering** | **WOW #4**: Natural Language Refinement | *"Too mainstream, darker and more experimental"*. |
| **3:15 - 3:50** | **5. Horizon Discovery** | **WOW #5**: Musical Blindspot Explorer | Bridging tracks to uncharted catalog regions. |
| **3:50 - 4:30** | **6. Interactive 3D Universe** | **WOW #2**: 3D Taste Universe | Visualizing taste modes (*"Map visualizes, model decides"*). |
| **4:30 - 5:00** | **7. Portable Export & Study** | **WOW #6**: Offline File Export & Study Mode | Zero-vendor lock-in, zero PII, and scientific rigor. |

---

## Tested Seed Sets (Catalog Shipped)

Use any of these three pre-verified seed sets from the shipped catalog bundle:

### Seed Set 1: "Night Drive" (Electronic / Synthwave / Ambient) — **Primary Recommendation**
- **Track 1**: *Endless Reflection, Pt. 1* — Lunar Fables (`f312f449-e24b-5b91-83a4-69c6e61ff5b1`)
- **Track 2**: *Quiet Pulse* — Amber Currents (`23e1e2d9-1c6c-59e5-b1e9-4444c1143899`)

### Seed Set 2: "Ambient Focus" (Minimalist / Ethereal / Drone)
- **Track 1**: *Inner Solitude* — Ghost Drift (`d21e8ca8-fef1-5a02-a720-d3bb6304fb9c`)
- **Track 2**: *Ancient Silence* — Silent Machines (`161f3070-5f07-5509-9ec4-3151be670494`)

### Seed Set 3: "Cosmic Drift" (Space Ambient / Krautrock / Post-Rock)
- **Track 1**: *Endless Reflection, Pt. 1* — Lunar Fables (`f312f449-e24b-5b91-83a4-69c6e61ff5b1`)
- **Track 2**: *Quiet Pulse* — Azure Frequency (`ee84d0a1-0a12-5973-9b4e-de6a9635b586`)

---

## Step-by-Step Walkthrough Flow

### 1. Onboarding & First Recommendations (0:00 - 0:45)
- **Action**: Open `http://localhost:3000`. Point out the ambient 2D particle field and the 3-step quick start banner.
- **Click**: Click the **"Night Drive"** quick preset button.
- **Narration**:
  > *"Melovia is built for user agency rather than passive auto-play. In two clicks, we anchor our taste with two seed tracks. The system instantly generates our first coherent 30-track recommendation sequence in under 40 milliseconds."*
- **Expected Behavior**: The seed shelf populates with 2 tracks, and the recommendation list loads with smooth acoustic transitions and energy indicators.

### 2. WOW #1: Familiarity ↔ Discovery Slider (0:45 - 1:30)
- **Action**: Drag the Discovery Slider from **Familiarity (0%)** toward **Exploratory Discovery (75%)**.
- **Narration**:
  > *"Most recommenders lock you into an opaque popularity bubble. Melovia gives you an explicit steerability control. At 0%, recommendations stay tightly bound to our seed artists and core genres. As we slide up to 75%, our Gaussian novelty function and dynamic relevance floor push recommendations out into adventurous long-tail gems—all in sub-100ms without re-fetching."*
- **Expected Behavior**: Track list smoothly re-ranks; novelty badges appear, popularity percentiles decrease, and stylistic dispersion increases.

### 3. WOW #3: Signal-True "Why This Track?" (1:30 - 2:15)
- **Action**: Click the **"Why?"** button on any recommended track in the list.
- **Narration**:
  > *"Unlike commercial black boxes that give vague claims like 'Because you listened to X', Melovia's explanation drawer is mathematically signal-true. It reveals exact ranking signals: tag affinity percentage, acoustic audio alignment, novelty boost, and MMR diversification score. If a track has missing audio data, it transparently tells the listener."*
- **Expected Behavior**: The right-hand Why Drawer slides open in $\le 300\text{ ms}$, displaying an acoustic radar chart, anchor seed affinities, and exact mathematical breakdown chips.

### 4. WOW #4: Conversational Steering with Verifier Guard (2:15 - 3:15)
- **Action**: Click into the natural language prompt input and type:
  ```
  too mainstream, darker and more experimental
  ```
  Press **Enter** or click **"Refine"**.
- **Narration**:
  > *"We can also steer via natural language. However, notice Melovia's safety boundary: the LLM never ranks tracks and never invents metadata. It acts as a schema-constrained translator, mapped through our verifier guard. It lowers the popularity ceiling, shifts the semantic context vector toward dark/experimental tags, and recalibrates our candidate pool."*
- **Expected Behavior**: The playlist instantly adapts to deeper, lower-popularity electronic and experimental tracks. A badge reflects the active context shift, with an option to revert.

### 5. WOW #5: Musical Blindspots & Horizon Explorer (3:15 - 3:50)
- **Action**: Scroll down to the **"Musical Horizons & Blindspots"** section.
- **Narration**:
  > *"Every listener has musical blindspots—genres adjacent to their taste that they never encounter due to algorithmic filter bubbles. Melovia identifies unrepresented regions in our vector catalog and provides 'gateway tracks' that bridge from our current seeds to uncharted musical territory."*
- **Expected Behavior**: 2–3 blindspot cards display unexplored musical clusters (e.g. *Polyphonic Pulse* or *Sacred Timber*) with one-click preview and seed addition.

### 6. WOW #2: 3D Interactive Taste Universe (3:50 - 4:30)
- **Action**: Click the **"3D Universe"** button in the top navigation header.
- **Narration**:
  > *"This is Melovia's 3D Taste Universe. 3,000 catalog tracks are projected as an interactive constellation. But notice our fundamental architectural invariant: the 3D map is strictly for visualization; all recommendation decisions happen in the true 256-dimensional vector space. Clicking any node inspects its true cosine nearest neighbors."*
- **Expected Behavior**: Interactive WebGL canvas opens. User can orbit, zoom, and click nodes to view track details and seed cluster regions.

### 7. WOW #6: Portable Export & Blind A/B Study Mode (4:30 - 5:00)
- **Action**:
  1. Click **"Export Playlist"** $\to$ Select **M3U / CSV** $\to$ Click **Download File**.
  2. Click **"Study Mode"** in the header to show the `/study` evaluation trial.
- **Narration**:
  > *"Finally, Melovia guarantees zero platform lock-in and complete listener privacy. We can export our curated playlist 100% offline to M3U, CSV, or sync to Spotify via OAuth PKCE without our tokens ever touching a database. And researchers can run double-blind randomized A/B trials in Study Mode to scientifically benchmark recommendation satisfaction with zero PII."*
- **Expected Behavior**: File exports immediately. The `/study` page presents an informed consent banner and tabbed Playlist A vs Playlist B auditioning without revealing algorithm identities.

---

## Multi-Tier Fallback Strategy

To ensure zero downtime during a live presentation:

### Tier 1: Local Offline Mock Catalog (Primary Demo Path)
- **Mechanism**: The entire catalog runs locally from pre-generated files in `data/bundles/v1/`.
- **Reliability**: 100% independent of external internet connectivity, APIs, or database servers.
- **Activation**: Default configuration (`make make-mock && make dev`).

### Tier 2: LLM Service Unavailable Fallback
- **Mechanism**: If `GEMINI_API_KEY` is unset or the external LLM endpoint times out, Melovia's deterministic rule parser automatically catches the request in `api/app/llm/parser.py`.
- **Reliability**: Queries like *"darker"*, *"more energetic"*, or *"less mainstream"* execute flawlessly using keyword-to-scalar mappings without external network calls.

### Tier 3: Pre-Recorded Video Fallback
- **Mechanism**: If hardware, browser, or projection issues occur, switch to the pre-recorded 1080p demo video:
  - Location: `docs/assets/demo_walkthrough.mp4` (or live slide recording).
  - Backed by static screenshots in `docs/assets/`.
