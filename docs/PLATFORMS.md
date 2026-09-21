# Music Platform & File Export Architecture (Phase 13)

Melovia provides portable, privacy-preserving playlist export across standard offline file formats and external music streaming providers.

---

## 1. Supported Export Targets

| Target | Identifier | Auth Flow | Offline Capable | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Offline File Formats** | `file` | None (Direct) | **Yes (100%)** | Active / Always Available |
| **Spotify Dev Mode** | `spotify` | OAuth 2.0 PKCE | No (Cloud API) | Active |
| **Apple Music** | `apple_music` | MusicKit User Auth | No (Cloud API) | Planned (Requires Apple Dev Program) |

---

## 2. Offline File Export Formats (`api/app/platforms/files.py`)

File export operates completely offline with zero network requests or third-party service accounts. Four standard formats are supported:

1. **CSV Spreadsheet (`.csv`)**:
   - RFC 4180 compliant with UTF-8 encoding.
   - Columns: `track_id`, `title`, `artist`, `isrc`, `year`, `tempo_bpm`, `energy`.
2. **JSON JSPF (`.json`)**:
   - JSON Shareable Playlist Format specification compliant (`https://melovia.local/jspf-ext`).
   - Includes track title, creator, duration, ISRC identifier (`urn:isrc:<isrc>`), and Melovia audio descriptors.
3. **Extended M3U (`.m3u8`)**:
   - Includes `#EXTM3U` and `#EXTINF:<duration>,<Artist> - <Title>` directives.
   - Includes `#EXT-X-ISRC:<isrc>` and safe audio filenames for media players (VLC, Winamp, Foobar2000).
4. **Plain Text (`.txt`)**:
   - Clean numbered tracklist (`1. Artist - Title`) for notes and copy-pasting.

---

## 3. Spotify Dev Mode Setup & Integration (`api/app/platforms/spotify.py`)

### Prerequisites & Limitations
- **Spotify Developer App**: Created at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).
- **Loopback Redirect URI**: `http://127.0.0.1:8000/export/spotify/callback`.
  > [!IMPORTANT]
  > Spotify strictly rejects `localhost` for redirect URIs. Always use `127.0.0.1`.
- **Developer Mode User Allowlist**: Under Dev Mode, up to 5 Spotify accounts added in your Spotify Developer Dashboard can authorize. The app owner must have a Spotify Premium account.

### Environment Configuration
Configure credentials in `.env` (never commit this file):
```env
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/export/spotify/callback
```

### OAuth 2.0 with PKCE & Token Security
- Authorization code flow with PKCE (`code_verifier` and `code_challenge` using S256).
- **Zero Token Persistence**: Access and refresh tokens are stored in-memory in the server session cache only. Tokens are never written to disk, database, or logs.
- Automatic token refresh on expiry.
- Disconnect endpoint clears session tokens immediately.

### Playlist Creation & Batch Insertion
- Creates private playlist via `POST /v1/me/playlists` with custom title and description.
- Adds matched track URIs (`spotify:track:...`) in batches of $\le 100$ items (Spotify Web API chunk limit).

---

## 4. Track Matching Cascade (`api/app/platforms/matching.py`)

When exporting catalog tracks to Spotify, a deterministic two-stage matching cascade is used:

```
Catalog Track
     │
     ├── 1. Has ISRC? ──► Exact ISRC Search (q=isrc:{isrc})
     │                         │
     │                         ├── Found? ──► MATCHED (Confidence = 1.0)
     │                         └── Not Found / No ISRC?
     │                                    │
     └── 2. Fuzzy Title + Artist ─────────┘
              (difflib SequenceMatcher on normalized strings)
              Score = 0.6 * title_sim + 0.4 * artist_sim
                   │
                   ├── Score >= 0.82 ─────────► MATCHED
                   ├── 0.65 <= Score < 0.82 ──► AMBIGUOUS
                   └── Score < 0.65 ──────────► UNMATCHED
```

- **Normalization**: Strips featured artists (`feat.`, `ft.`), remaster suffixes (`[Remastered]`), mix versions (`(Extended Mix)`), and punctuation.
- **In-Memory Cache**: Results are cached in memory to avoid duplicate platform API queries.
- **Unmatched Export**: Unmatched and ambiguous tracks can be downloaded as a CSV report via `GET /export/jobs/{job_id}/unmatched`.

---

## 5. Apple Music Adapter Requirements

The Apple Music adapter (`apple_music`) requires:
1. An active Apple Developer Program membership ($99/year).
2. MusicKit Developer Key (`.p8` private key) and Key ID.
3. Apple Developer Team ID.
4. Two-legged MusicKit authentication (Developer Token JWT signed via ES256 + User Token obtained via MusicKit JS on the client).

Because Spotify Dev Mode is available without an upfront developer fee, Spotify was implemented as the primary streaming platform adapter for Phase 13.
