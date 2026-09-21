# ADR 005: Client-Side Privacy, Ephemeral Sessions & Zero PII

## Status
Accepted

## Date
2026-09-21

---

## Context
Commercial streaming services surveil user listening habits, build persistent behavioral tracking profiles, and monetize user telemetry. For an exploratory discovery prototype like Melovia:
1. Mandatory account creation creates friction that discourages casual exploration.
2. Storing user listening histories centrally introduces severe privacy risks, GDPR/CCPA compliance liabilities, and database attack surfaces.
3. Third-party social sharing features often transmit telemetry or upload user images to centralized servers.

## Decision
We enforce a privacy-first, zero-surveillance architecture across backend and frontend:
1. **No Mandatory Registration**: Full discovery features (steerability, 3D universe, why drawer, conversational steering, export) require zero account creation.
2. **Anonymous Session Cookies**: Taste profiles and session states are maintained via ephemeral UUIDs stored in browser cookies or `localStorage`.
3. **Pure Client-Side Taste Sharing**: The "Share as Image" feature renders a $1200\times 630\text{ px}$ PNG card directly via HTML5 Canvas in the browser. Zero image uploads, zero analytics pings, zero server-side telemetry.
4. **Session-Only Platform Tokens**: Spotify OAuth PKCE tokens exist solely in volatile server memory for the duration of the export action and are never persisted to disk or database.
5. **Anonymous Evaluation Trials (`/study`)**: Double-blind A/B evaluation collects only cryptographic hash participant IDs, Likert scores, and anonymized feedback.

## Consequences
### Positive
- Maximum user trust and agency.
- Zero liability for storing personal listening data or third-party credentials.
- Instant user onboarding with zero sign-up wall.

### Negative
- Users lose profile continuity if they switch browsers or clear cookies (mitigated by exportable session backups).
- No cross-device profile synchronization without explicit file export/import.
