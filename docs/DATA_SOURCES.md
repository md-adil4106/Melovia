# Melovia Data Sources & API Audit

This document records the official data sources, licensing terms, rate limits, verified retrieval dates, and design impacts for all external data services integrated or evaluated for Melovia.

In accordance with Melovia Standing Rules, only official APIs or openly licensed data may be used. No web scraping or unofficial endpoints.

---

## Data Sources Summary Table

| source | licence | retrieved | used-for |
| --- | --- | --- | --- |
| [Spotify Web API](https://developer.spotify.com/documentation/web-api) | Spotify Developer Terms of Service | 2026-09-19 | Platform export (playlist creation), catalog search, and audio previews |
| [Apple Music API / MusicKit](https://developer.apple.com/documentation/applemusicapi) | Apple Developer Program License Agreement | 2026-09-19 | Platform export (playlist creation), ISRC song lookup, user library integration |
| [MusicBrainz](https://musicbrainz.org) | Core: CC0 (Public Domain); Folksonomy Tags/Genres: CC BY-NC-SA 3.0 | 2026-09-19 | Canonical entity resolution (artists, recordings), release metadata, ISRC mapping, controlled tags |
| [ListenBrainz](https://listenbrainz.org) | Data Dumps: CC0; Public API: MetaBrainz Terms | 2026-09-19 | Popularity percentiles, top recordings by artist, collaborative filtering listen signals, JSPF playlists |
| [AcousticBrainz Archive](https://acousticbrainz.org) | CC0 (Public Domain) | 2026-09-19 | Offline acoustic feature extraction benchmark, audio feature exploration (2015–2022 recordings) |
| [Free Music Archive (FMA)](https://github.com/mdeff/fma) | Metadata: CC BY 4.0; Audio: CC Licenses (various) | 2026-09-19 | Openly licensed audio benchmarks, Essentia feature extraction, fallback evaluation dataset |
| [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/index.html) | Apple Affiliate & Public Search Terms | 2026-09-21 | Live, public, keyless search for commercial music up to today's date, 30s audio previews, cover art |

---

## Detailed Data Source Audits

### 1. Spotify Web API
- **Official Documentation**: `https://developer.spotify.com/documentation/web-api`
- **Changelog**: `https://developer.spotify.com/documentation/web-api/concepts/changelog`
- **Retrieval Date**: 2026-09-19
- **License / Terms**: Spotify Developer Terms of Service. Non-commercial and commercial tiers with strict restrictions on storing audio and recreating Spotify features.
- **Rate Limits & Quota**:
  - Rolling window rate limits (returns HTTP 429 with `Retry-After` header).
  - Since July 2026, 429 error responses include a structured JSON `reason` field (e.g. `"reason": "QUOTA_EXCEEDED"`) distinguishing transient rate limits from quota exhaustion.
  - Quota is calculated and shared per developer account rather than per individual Client ID.
- **Development Mode Constraints (Verified 2026 Updates)**:
  - **Account Limit (July 2026)**: Developers are allowed up to 25 Development Mode Client IDs per developer account.
  - **User Allowlist (February 2026)**: Each Development Mode app is strictly limited to a maximum of 5 authorized Spotify users.
  - **Account Requirement (February 2026)**: App owners in Development Mode must maintain an active Spotify Premium subscription.
  - **Scope Reductions**: Certain discovery endpoints have been restricted to Extended Quota mode.
- **Playlist Creation Endpoints**:
  - `POST /v1/me/playlists` (creates a playlist for the authenticated user, replacing the legacy `POST /v1/users/{user_id}/playlists`).
  - `POST /v1/playlists/{playlist_id}/tracks` (adds track URIs in batches of up to 100).
  - Required OAuth Scopes: `playlist-modify-public`, `playlist-modify-private`.
- **Impact on Design**:
  - Melovia recsys **must not** rely on Spotify's proprietary recommendations or audio feature APIs at runtime.
  - Platform integration is strictly confined to `api/app/platforms/spotify.py` behind the `PlatformAdapter` interface.
  - For local development and portfolio demos, user export operates within the 5-user allowlist under Development Mode.
  - All track export operations must handle 429 `QUOTA_EXCEEDED` and `Retry-After` headers gracefully.

---

### 2. Apple Music API & MusicKit
- **Official Documentation**: `https://developer.apple.com/documentation/applemusicapi`
- **Retrieval Date**: 2026-09-19
- **License / Terms**: Apple Developer Program License Agreement. Access requires an active Apple Developer Program membership.
- **Authentication Dual-Token Architecture**:
  - **Developer Token**: A signed JSON Web Token (JWT) using the ES256 algorithm, generated with a private key (`.p8` file) associated with a MusicKit Key ID and Apple Developer Team ID. Valid for up to 180 days. Grants access to the global catalog.
  - **Music User Token (MUT)**: Generated client-side via MusicKit JS (`MusicKit.getInstance().authorize()`) or iOS StoreKit after user explicit authorization. Grants access to personal cloud libraries.
- **ISRC Catalog Lookup**:
  - Endpoint: `GET /v1/catalog/{storefront}/songs?filter[isrc]={isrc}`
  - Enables exact canonical matching from MusicBrainz ISRCs to Apple Music track IDs without lossy text search.
- **Playlist Creation**:
  - Endpoint: `POST /v1/me/library/playlists`
  - Headers required: `Authorization: Bearer <DeveloperToken>` and `Music-User-Token: <MUT>`.
  - Body schema: `{"attributes": {"name": "...", "description": "..."}, "relationships": {"tracks": {"data": [{"id": "...", "type": "songs"}]}}}`.
- **Rate Limits**:
  - Dynamic threshold per IP / developer token. Returns HTTP 429 when exceeded.
- **Impact on Design**:
  - Storing developer private keys securely via environment variables (never committed).
  - The frontend client manages user token negotiation through MusicKit JS, passing the MUT to the backend only during playlist export.
  - ISRC matching enables cross-platform consistency between Spotify and Apple Music.

---

### 3. MusicBrainz
- **Official Documentation**: `https://musicbrainz.org/doc/MusicBrainz_API`
- **Retrieval Date**: 2026-09-19
- **License Terms**:
  - **Core Entities (CC0 Public Domain)**: Artists, release groups, releases, recordings, works, and relationships (ISRCs). Free for any purpose without attribution requirements.
  - **Supplementary Folksonomy (CC BY-NC-SA 3.0)**: User-contributed tags, folksonomy genres, and ratings are licensed under Creative Commons Attribution-NonCommercial-ShareAlike 3.0.
- **Access Modes**:
  - **Live Web Service (XML / JSON via `/ws/2/`)**:
    - Strictly enforced rate limit: **no more than 1 request per second** per IP address. Exceeding triggers HTTP 503.
    - Mandatory User-Agent header in the format: `ApplicationName/Version ( contact-url-or-email )`. Generic or missing User-Agents are blocked.
  - **Replication / JSON Dumps**:
    - Weekly full database dumps (PostgreSQL archives) and hourly replication packets provided via MetaBrainz downloads.
- **Impact on Design**:
  - All online candidate scoring and search must use local pre-ingested bundles; the live MusicBrainz API **must never** be called during request-time recommendation rendering.
  - Offline pipeline tools (`pipelines/`) must enforce client rate-limiting (`time.sleep(1.1)`) and caching when fetching missing metadata.
  - Supplementary tag data requires attribution to MusicBrainz in documentation and portfolio credits; commercial distribution of raw tag data requires licensing agreements.

---

### 4. ListenBrainz
- **Official Documentation**: `https://listenbrainz.readthedocs.io/en/latest/users/api/`
- **Retrieval Date**: 2026-09-19
- **License / Terms**: CC0 for listening data and dumps. Public API provided by MetaBrainz.
- **Key Endpoints**:
  - `GET /1/popularity/top-recordings-for-artist/{artist_mbid}`: Returns top recordings ranked by listen count and listener count.
  - `GET /1/stats/sitewide/artists`: Overall popularity metrics across the network.
  - `GET /1/user/{user_name}/playlists`: Retrieves user playlists formatted in JSPF (JSON Shared Playlist Format).
  - `GET /1/user/{user_name}/playlists/createdfor`: Accesses public automated playlists.
- **Rate Limits**:
  - Enforces 1 request per second. Response headers include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After`.
- **Public Data Dumps**:
  - Regularly published full listen dumps (`tar.zst`) for large-scale offline matrix factorization and collaborative filtering.
- **Impact on Design**:
  - ListenBrainz popularity statistics provide the baseline popularity percentile (`popularity_pct`) in track metadata.
  - Offline training pipelines consume ListenBrainz listen dumps rather than querying the API in bulk.

---

### 5. AcousticBrainz Data Dump
- **Official Documentation**: `https://acousticbrainz.org/download`
- **Retrieval Date**: 2026-09-19
- **Project Status**: Submissions permanently closed in 2022. The dataset remains accessible as an immutable research archive hosted by MetaBrainz and the Internet Archive.
- **License**: CC0 (Public Domain).
- **Archive Size & Format**:
  - Total compressed size: ~900–1000 GB across 30 tar archives containing individual JSON files.
  - File compression: `tar.zst` (zstandard).
  - Directory structure: `type/m/b/i/mbid-n.json` where `n` represents the submission increment.
  - Targeted feature CSVs (~several gigabytes) and sample archives (100,000 recordings) are also provided.
- **Feature Descriptors**:
  - **Low-level**: Audio spectral centroid, flux, roll-off, MFCCs (13 bands), bark bands, dissonance, zero-crossing rate.
  - **High-level**: Supervised classifier outputs from Essentia: danceability, energy, mood (aggressive, happy, sad, relaxed, acoustic), key/scale, and broad genre tags.
- **Date Range**: 2015 through 2022.
- **Impact on Design**:
  - Because submissions closed in 2022, recordings released after 2022 have **0% coverage** in AcousticBrainz.
  - The ~1 TB download volume is prohibitive for quick CI iteration and local development.
  - Architecture must treat audio features as an optional channel (`has_a = True/False`), using missing-channel masks (`mask_a`) in recsys math.

---

### 6. Free Music Archive (FMA)
- **Official Repository**: `https://github.com/mdeff/fma`
- **Paper**: Defferrard et al., *FMA: A Dataset for Music Analysis*, ISMIR 2017.
- **Retrieval Date**: 2026-09-19
- **License**: Metadata is licensed under CC BY 4.0; individual audio tracks are licensed under various Creative Commons licenses (CC BY, CC BY-NC, CC BY-SA, etc.).
- **Dataset Subsets**:
  - `fma_metadata.zip` (342 MB): Contains CSVs (`tracks.csv`, `genres.csv`, `features.csv`, `echonest.csv`).
  - `fma_small` (7.2 GB): 8,000 tracks of 30-second clips across 8 balanced genres.
  - `fma_medium` (22 GB): 25,000 tracks of 30-second clips across 16 unbalanced genres.
  - `fma_large` (93 GB): 106,574 tracks of 30-second clips across 161 genres.
  - `fma_full` (879 GB): 106,574 untrimmed tracks.
- **Extracted Descriptors**:
  - Pre-computed librosa and Essentia features (spectral centroid, chroma, tonnetz, MFCCs) included in `features.csv`.
- **Impact on Design**:
  - Provides the open-source audio fallback (Plan B) if public domain recordings with full audio analysis are required without relying on external commercial streaming platforms.
  - Metadata CSVs can be parsed in memory without downloading large audio binaries.

---

### 7. Phase 2 Staging Ingestion & Sources
- **Pipelines**: `pipelines/ingest_catalog.py`, `pipelines/ingest_musicbrainz.py`, `pipelines/ingest_listenbrainz.py`, `pipelines/ingest_acousticbrainz.py`, `pipelines/dq_report.py`.
- **Target Ingestion Directory**: `data/dumps/` (configured via `--data-dir`, gitignored).
- **Accepted File Formats**:
  - MusicBrainz: `musicbrainz_recordings.jsonl` (JSONL recording dumps with artist credits, release dates, ISRCs, folksonomy tags, and release-group tags).
  - ListenBrainz: `listenbrainz_stats.jsonl` (JSONL listen count statistics).
  - AcousticBrainz: `acousticbrainz_features.jsonl` (JSONL high-level audio descriptors).
- **API Top-up Politeness**:
  - Strict 1.0 request/second limiter (`pipelines/rate_limiter.py`).
  - Mandatory User-Agent header (env `MUSICBRAINZ_USER_AGENT` or `Melovia/0.1.0 ( https://github.com/md-adil4106/Melovia )`).
  - Local filesystem cache at `data/cache/musicbrainz/` (gitignored).
- **Checkpointing & Idempotency**:
  - Checkpoint file: `data/checkpoints/ingest_checkpoint.json` (tracks processed MBIDs and batch progress).
  - Staging storage: `staging_tracks` table in relational DB.
  - Re-running ingestion produces zero duplicates and updates existing entries idempotently.
- **Representative Seed Dataset**:
  - When raw external dumps are not pre-downloaded, the pipeline automatically provides a 5,000-track real-world seed dataset (comprising canonical classics from Queen, Nirvana, The Beatles, Fleetwood Mac, Michael Jackson, Radiohead, Pink Floyd, David Bowie, Daft Punk, etc.) ensuring `make ingest-sample` and `make dq-report` run reliably out-of-the-box.
 
 
### 8. iTunes Search API (Live Public Music Search)
- **Official Documentation**: `https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/index.html`
- **Retrieval Date**: 2026-09-21
- **License / Terms**: Apple Affiliate & Public Search Service Terms. Completely free, public, keyless API.
- **Endpoint**: `GET https://itunes.apple.com/search?term={query}&entity=song&media=music&limit={n}`
- **Lookup Endpoint**: `GET https://itunes.apple.com/lookup?id={trackId}`
- **Used For**: Real-time discovery of live music releases up to today's date (e.g. searching "secondhand" by Don Toliver), high-resolution album artwork thumbnails, and 30-second AAC audio preview clips.
- **Rate Limits**: Generous rate limit (approx. 20 requests/min burst); responses are cached with a 10-minute in-memory TTL in `api/app/services/live_search.py`.
- **Recsys Integration**: Dynamically resolved external tracks receive deterministic synthetic semantic tag vectors and canonical identifiers (`ext:itunes:{trackId}`). Precomputed acoustic features are omitted with `has_a: false`, strictly adhering to Melovia's missing audio invariant.

