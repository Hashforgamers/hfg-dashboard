# Kiosk session extensions v1 — implemented backend contract

Implementation date: 7 October 2026. These endpoints are implemented locally; this document does not certify production deployment. The native kiosk and mobile app must integrate them. Existing clients are not automatically enrolled.

## Rollout

1. Back up the shared PostgreSQL database and apply `sql/20261007_kiosk_extensions.sql` after the existing cafe-wallet and kiosk-runtime migrations. The migration includes an assignment guard covering primary PCs and assigned squad PCs. Do not bypass existing guard triggers.
2. Deploy the matching slot-capacity helpers in hfg-booking and hfg-background-processor. Deploy hfg-booking's duplicate overtime protection and remaining-capacity cancellation logic. Deploy the dashboard service and dashboard frontend.
3. For multiple Socket.IO workers/instances, configure the same `SOCKETIO_MESSAGE_QUEUE_URL` (or `REDIS_URL`) on all instances. Preserve existing Socket.IO client origin configuration and linked-device authentication. A single local worker can run without Redis.
4. The independent reconciliation worker runs every five seconds by default. `SESSION_EXTENSION_WORKER_ENABLED=false` disables it; do not disable it in production while enrolled sessions are running. New endpoints return 503 when the schema is missing. No schema is created automatically at startup.
5. Test a dedicated cafe, wallet and kiosk before enabling native clients. Existing active sessions must enroll before their original funded boundary; already accrued legacy overtime must be settled through its existing flow first. Never dual-write metered extension charges through the legacy extraBooking endpoint.

## Authorization and money

Device endpoints use `Authorization: Bearer <existing active console-link session token>`. Vendor, console, user and source ownership are resolved by the server; never send an arbitrary user/vendor to change billing. All timestamps are UTC ISO 8601, and all amounts below are integer INR paise. A quote uses the scanned console's server pricing and applicable offers, prorated to the next operating-hours slot boundary. The server checks physical-console conflicts and shared capacity atomically before granting time.

Original booking/payment and food billing remain in their existing system. `billing` in this protocol contains **extension charges only**, avoiding a second charge for prepaid time. Normal bookings accrue an invoice. Self QR extensions reserve spendable funds in the cafe-specific wallet, capture only played time, and release unused funds at Stop. Cafe credit mode is `automatic` or `owner_approval`, with an optional Self QR credit limit; zero disables credit. Gamer consent is required for credit. Partially funded time is granted while its unfunded remainder awaits consent, limit resolution or owner approval. A top-up pays existing cafe credit first; remaining wallet funds pay future play. Past credit charges are never retrospectively recategorized.

## Device API sequence

1. Enroll and get a quote before the original boundary:

```http
POST /api/kiosk/session/extension/quote
{"session_ref":{"kind":"self_qr","id":"<CafePlaySession id>"}}
```

For desk/app bookings use `{"session_ref":{"kind":"booking","id":"<booking id>"}}`. Keep the returned `runtime_id`. Subsequent quotes use `{"runtime_id":"..."}`. The linked PC must own that active source.

Quote response includes `runtime_id`, `quote_id`, `revision`, `expires_at`, `interval_start`, `interval_end`, `price_paise`, `wallet_funded_paise`, `credit_paise`, and `requires_owner_approval`. Quotes expire after 30 seconds. Display this actual price; do not infer prices from hourly labels.

2. Continue:

```http
POST /api/kiosk/session/continue
{"runtime_id":"...","quote_id":"...","revision":3,"credit_consent":true,"idempotency_key":"<unique UUID>"}
```

Set consent true only after the gamer accepts credit terms. HTTP 200 means the quote was granted; HTTP 202 means an action is pending and includes the authoritative snapshot. A pending response can also grant a wallet-funded prefix; obey `reserved_until`, not the HTTP status alone. Physical conflicts require staff resolution followed by Retry. Approval cannot displace a booking, exceed the credit limit, revive an ended session or authorize time retrospectively.

Continue enables rolling continuation: the server attempts the next interval five minutes before the reserved boundary while the kiosk is online. A changed price requires a fresh gamer quote/acceptance. Owner approval applies to new unfunded intervals. Never fabricate or optimistically extend the end timestamp.

3. State/heartbeat:

```http
GET /api/kiosk/session
```

Returns `{session:<snapshot>|null, capabilities:["session_extensions_v1"]}`. Poll every 15 seconds even when sockets work. Device polls update the heartbeat; after 60 seconds without a heartbeat, additional extensions are refused. Already reserved play remains authorized until its boundary. Reconnect and fetch this API before interpreting buffered events.

4. Stop:

```http
POST /api/kiosk/session/stop
{"runtime_id":"...","revision":4,"mode":"now","idempotency_key":"<unique UUID>"}
```

`now` freezes played charges at server time, frees tracked capacity, cancels pending extensions and ends play. An urgent Stop can use a stale revision; it still cannot stop another customer's runtime. `at_authorized_end` disables rolling and schedules Stop at the existing reserved boundary; it requires current revision. Opening a settlement dialog does not freeze time. Final charges are authoritative only after Stop.

Retry an uncertain mutation with the **same key and payload**. Reusing a key for a different action returns 409. On quote expiry, price/revision conflict, obtain a new snapshot and quote. Never repeat payment with a new key merely because a response was lost.

## Authoritative snapshot and realtime

Key fields: `runtime_id`, `session_ref`, `console_id`, `vendor_id`, `revision`, `event_sequence`, `started_at`, `paid_until`, `reserved_until`, `stop_at`, `ended_at`, `play_allowed`, `state`, `extension`, `billing`.

- `paid_until` records the original funded source boundary; it is not a permission deadline or a live wallet-duration estimate.
- `reserved_until` is the currently authorized/reserved play boundary. `stop_at`, when present, can shorten it.
- `play_allowed` and final `ended_at` control native lock state. Do not lock solely because the original prepaid end passed. At an unresolved reservation boundary, fetch state and stop further unauthorized use. There is no automatic grace credit beyond that boundary.
- `revision` changes authorization state and guards mutations. `event_sequence` also advances for billing updates. Deduplicate `event_id`; ignore lower sequence for the same runtime. Treat a different runtime as a different gamer.
- `billing.as_of` is the server's actual accrual timestamp, not a cached client estimate. `billing.is_final` is true only after Stop. `amount_due_paise` is extension debt; `net_cafe_balance_paise` can be negative. Original charges remain separate.

Committed events are stored in a durable outbox and retried. Delivery is at least once, not exactly once. `session.updated` carries `{event_id, revision, event_sequence, server_time, session_ref, snapshot}` to the existing linked-kiosk room on the default namespace and `/cafe-agent`. Preserve the existing authenticated link connection/room handshake. HTTP polling is the recovery path.

Staff vendor rooms receive thin `session.updated` invalidations containing runtime/vendor/console identifiers and versions, then fetch their permission-protected summaries. Dashboard notices cover low time, grants, owner requests, conflicts, wallet exhaustion, credit authorization, offline and session end. No email integration is claimed by this protocol.

The app can authenticate to `/cafe-gamer` with `{token:<cafe-checkout gamer JWT>}` to receive only its own full events. Expired connections are disconnected. GET `/api/cafe/extensions/<runtime_id>` returns the authenticated gamer's own snapshot.

Public availability namespace `/cafe-availability` accepts `watch` with `{vendor_id:41}` and returns `{ok:true}` for an existing cafe. It emits `slots.updated` with vendor ID, event ID and server time only when extension capacity changes. Subscribe again after reconnect, and refetch app availability on each event. It contains no gamer or financial details. Existing booking flows retain their existing availability events. Every purchase must still pass server-side conflict/capacity checks.

## Dashboard management API

Existing staff/vendor authentication and permissions apply:

- GET `/api/cafe/<vendor>/extension-policy`; PUT the same with `{"self_qr_credit_mode":"owner_approval","credit_limit_paise":10000}`. Owner only; use null for unlimited.
- GET `/api/cafe/<vendor>/extensions`: active/ended-unsettled sessions and unread notices (maximum 100 each).
- GET `/api/cafe/<vendor>/extensions/<runtime>`: authoritative summary.
- POST `.../<runtime>/decision` with `request_id`, `decision` (`approve`, `retry`, `reject`), `revision`, `idempotency_key`. Only owner authorizes credit; staff Retry requires the conflicting booking to have been resolved first.
- POST `.../<runtime>/end`: same Stop fields.
- POST `.../<runtime>/settle`: `amount_paise`, `method` (`cash`, `card`, `cafe_upi`, `upi`, `waiver`), `revision`, `idempotency_key`. Collect only finalized extension debt; partial collections supported. Money collection requires an open shift; waiver requires adjustment permission and a reason. Pay-at-cafe booking settings do not block extension settlement.
- POST `/api/cafe/<vendor>/extension-notices/<notice>/read` with `{}`.

## Native UX instructions

Use one small non-modal reminder around five minutes remaining. Do not steal keyboard focus, minimize a game, display a full-screen countdown or repeatedly interrupt the gamer. Offer Continue and Stop through the kiosk tray/overlay which the gamer explicitly opens. Show next-interval price and wallet/credit split before consent. Show a passive pending/conflict status with staff guidance. Keep notifications deduplicated by runtime and boundary. Staff sees requests on the dashboard while the existing authorized play continues.

Continue success updates the same session, never restarts its timer. Stop should explicitly confirm intentional ending and then use the returned snapshot. After a native restart/reconnect, rebuild state from GET; never unlock from an old cached timestamp or replayed prior customer's event. While offline, honor only already authorized time; do not reserve new slots locally.

## Verification before production enablement

Local tests use disposable PostgreSQL and cover shared reservations, physical conflicts, partial funding, owner approval, credit ceilings, metered captures, unused-fund release, negative credit, top-up repayment, future wallet capture, immutable financial entries, duplicate retries, concurrent Stop, revoked/offline links, schema installation, event retries/privacy and gamer authentication. Production acceptance still requires real kiosk/app integration, Redis delivery across instances, and a dedicated test cafe. No personal documents or production funds are needed for these tests.
