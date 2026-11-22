# Hash Console Lock (Smart TV) on the shared kiosk backend

Status: implemented on branch `feature/console-lock-tv` (hfg-dashboard-service and
hash-dashboard). Not deployed. Apply `sql/20261123_console_tv_devices.sql` first;
until it runs, every new code path is dormant and the backend behaves exactly as
the PC-only build.

There is **one** backend. A Console Lock TV is one more device row in the table the
PC kiosk already uses (`console_link_sessions`), bound to one cafe station
(`consoles`). Sessions, timers, pricing, extensions, billing, audit and real-time
delivery all stay in the existing runtime engine (`session_extensions.py`,
`kiosk_runtime.py`). The TV module (`app/services/console_tv.py`) only adds pairing,
display-control commands, a versioned event contract, heartbeat/health and
backend-authoritative expiry for TV stations.

---

## 1. Audit of the existing backend

| # | Area | What exists today | Reused / extended |
|---|------|-------------------|-------------------|
| 1 | PC kiosk routes | `kiosk_controller.py` (`/api/kiosk/session/commands`, `/command-ack`, `/booking/verify`, `/owner-pin/validate`, `/api/bookings/<id>/remaining`), `session_extensions_controller.py` (`GET /api/kiosk/session`, `/extension/quote`, `/continue`, `/stop`), `routes.py` (`/api/kiosk/start-session`, `/api/kiosk/unlink`, `updateDeviceStatus`, `releaseDevice`), `cafe_wallet_controller.py` (`/api/cafe/agent/qr`, `/agent/session`, `/agent/ack`) | TV uses the same `/api/kiosk/session*` and `/api/cafe/agent/*` endpoints with its own bearer. New device-only routes are under `/api/kiosk/device/*`. |
| 2 | Session model + states | `kiosk_runtime_sessions` (`RuntimeSession`): `revision`, `event_sequence`, `reserved_until`, `stop_at`, `ended_at`, status `active / approval_pending / overtime_pending / offline / ended_unsettled / settled ...`; outbox `kiosk_session_outbox` | Unchanged. TV lifecycle (IDLE/ACTIVE/EXPIRING/EXPIRED/ENDED) is *derived* from it. `version` = `revision`. |
| 3 | Device registration / auth | Dashboard links a PC: `POST /api/vendors/<id>/pcs/link` → opaque `session_token` (`console_link_sessions`), revocable via `/pcs/unlink` or `/api/kiosk/unlink`. `linked_identity()` / `agent_link()` authenticate it. | Same table and token type. Added `device_type` (`PC_KIOSK` default, `CONSOLE_TV`) and metadata/capability columns. TVs pair via an approved code instead of a dashboard-issued token. |
| 4 | Cafe ↔ station | `consoles.vendor_id`, `consoles.console_type` (`pc`, `ps5`, …). Every kiosk call goes through `check_scope()`. | Reused. Added `consoles.configured_input_id` (HDMI source). |
| 5 | Socket events | Default namespace: device auth by `session_token` → room `kiosk_link_<link>`; vendor JWT → `vendor_<id>`. PC kiosk listens for `unlock_request`, `session.updated`; `/cafe-agent` namespace `session.prepare`. Dashboard listens for `session.updated`, `console_availability`, `booking_*`. | PC rooms and payloads untouched. TVs join `device_<link>` instead and get the v1 contract below. Dashboard gets one new refresh signal `console_device.updated`. |
| 6 | Start / stop / pause / extend | Start: `secure_start` + `kiosk_start_session` (code/QR), dashboard `updateDeviceStatus`/`kiosk/start-session` → `notify_console_runtime()` → `attach()`. End: `releaseDevice`, `/api/cafe/<v>/extensions/<rid>/end`, `/api/kiosk/session/stop`, `finish()`. Extend: quote/continue (rolling), owner approval, back-to-back adoption (`adopt_follow_on_bookings`). **No pause/resume exists.** | All reused. Pause/resume is not added (no engine support; see §10). |
| 7 | Lock / unlock | `pc_session_commands` (unlock/lock per booking, PC ack), `unlock_request` / `session_expired` socket events, PC locks itself at its local deadline. | PC table/events untouched. TV commands live in `device_commands` with device-reported results kept separate from delivery. |
| 8 | Booking + payment | Booking service tables (`bookings`, `VENDOR_<id>_DASHBOARD`), `transactions`, cafe wallet, pay-at-desk, QR checkout (`/api/cafe/checkout`). | Unchanged. |
| 9 | Pricing / billing | `cafe_session_pricing.session_prices()`, `next_price()`, `meter_overrun()`, `accrue()`, extension segments. | Unchanged. TV stations stop at the paid boundary so no overrun is metered (§6). |
| 10 | DB migrations | Hand-written, repeatable, transactional SQL files in `sql/` (`IF NOT EXISTS`, guarded constraints); code probes `to_regclass()` before using new tables. | Same convention: `sql/20261123_console_tv_devices.sql`, guarded by `console_tv.ready()`. |
| 11 | Authorization | `vendor_identity()` (owner JWT or staff `vendor_access` token with permission), `check_scope()`, `staff_actor()` for named staff sessions, `vendor_lock()` advisory lock per cafe. | Reused for all admin routes (`dashboard.view` to read, `gaming.manage` to act). Admin actions are also written to the cafe audit log. |
| 12 | Heartbeat / connectivity | Runtime `last_seen_at` refreshed by `seen()` from `/remaining` and `GET /api/kiosk/session`; tick marks `offline` after 60 s and refuses extension grants while offline. | TV heartbeat calls the same `seen()`. Added `last_heartbeat_at`/`last_heartbeat` on the link for dashboard health. |

---

## 2. Minimal modification plan (what changed)

**hfg-dashboard-service**

| File | Change |
|------|--------|
| `sql/20261123_console_tv_devices.sql` | New, additive, repeatable migration. |
| `app/services/console_tv.py` | New. Pairing, commands, lifecycle, events, heartbeat, admin actions. |
| `app/controllers/console_tv_controller.py` | New. Device and admin routes. |
| `app/__init__.py` | Registers the blueprint. |
| `app/config.py` | Optional `CONSOLE_TV_*` settings. |
| `app/services/session_extensions.py` | `tick()`: TV rows end at `reserved_until` (one guarded check, PC rows unaffected). `dispatch()`: after the existing PC/dashboard/gamer emits, a guarded hook emits the TV contract and issues UNLOCK/LOCK. |
| `app/controllers/session_extensions_controller.py` | `GET /api/kiosk/session` adds `timer`, `display`, `station`, `pending_commands` and capability `console_tv_v1` **only for TV bearers**. PC response unchanged. |
| `app/services/websocket_service.py` | TV bearer joins `device_<link>`; `device.heartbeat` and `device.control.result` handlers; disconnect bookkeeping; `_emit_to_kiosk` additionally bridges `unlock_request`/`session_expired` to a paired TV on a background task (never the caller's transaction). |
| `app/services/link_service.py`, `subscription_commerce.py`, `vendor_pc_controller.py` | PC licence counts count `PC_KIOSK` links only, so a paired TV never takes a PC kiosk seat. Same numbers as today when no TV is paired. |
| `tests/test_console_tv.py` | New integration + regression tests (real PostgreSQL). |

**hash-dashboard**

| File | Change |
|------|--------|
| `app/components/console-lock-panel.tsx` | New. Pair TV, health, session/expiry, lock state, capabilities, Lock/Unlock/HDMI test, staff confirmation, HDMI source, move, unpair, end session, event log. |
| `app/components/console-list.tsx` | Console (non-PC) cards show `TV online` / `TV offline` / `Not securely locked`, and a "Console Lock TV" menu item opening the panel. Hidden while the server returns 503 (migration not applied). |
| `tests/console-lock-panel.test.cjs` | New badge tests. |

HFG-frontend and hashdashpc are not touched.

---

## 3. Database migration (`sql/20261123_console_tv_devices.sql`)

* `console_link_sessions` + `device_type` (`PC_KIOSK` default, check constraint), `device_metadata` jsonb, `reported_capabilities` jsonb, `capability_verification` jsonb, `last_heartbeat_at`, `last_heartbeat` jsonb, `token_rotated_at`, `paired_by`; partial index on active links by type.
* `consoles` + `configured_input_id` (HDMI source).
* `device_pairing_challenges`: code and claim secret stored only as HMAC-SHA256 (keyed by `SECRET_KEY`); status `pending → approved → claimed` (or `expired` / `rejected`); unique open code.
* `device_commands`: `LOCK / UNLOCK / HDMI_TEST`, status `PENDING / SUCCEEDED / FAILED / UNSUPPORTED / UNVERIFIED / SUPERSEDED / EXPIRED`, `session_version`, `issued_at`, `expires_at`, `received_at` (delivery only), `completed_at`, `failure_reason`, `result` (device report), `staff_verification`, unique `dedupe_key`.
* `device_events`: append-only audit (`out` / `in` / `admin` / `system`).

No column is dropped, renamed or rewritten. Existing PC rows get `device_type='PC_KIOSK'` from the default. The ORM models are intentionally **not** changed, so the new code can deploy before or after the migration.

---

## 4. Lifecycle and display-control state

Session (derived from the shared runtime row):

| Status | Meaning |
|--------|---------|
| `IDLE` | No session on the station (or the last one ended over 30 min ago). |
| `ACTIVE` | Play allowed; more than 5 minutes left (same 5-minute boundary the engine uses for `time_low`). |
| `EXPIRING` | Play allowed; 5 minutes or less to `expiresAt`. |
| `EXPIRED` | Reached its paid end (`ended_at >= reserved_until`, or `stop_at` passed). |
| `ENDED` | Ended early (staff end, stop now, release). |

Display control (latest LOCK/UNLOCK for the TV): `NOT_REQUESTED`, `PENDING`, `SUCCEEDED`, `FAILED`, `UNSUPPORTED`, `UNVERIFIED` (`EXPIRED` commands show as `FAILED` with `failureReason: no_result_before_expiry`).

`display.security`:

* `SESSION_ACTIVE`: a paid session is running.
* `SECURE`: last LOCK reported `SUCCEEDED` **and** the TV claims `lockEnforcement`.
* `NOT_SECURE`: anything else (no lock result yet, failed, unsupported, TV offline). The dashboard shows "Station is not securely locked".

Every `SUCCEEDED` is labelled `evidence: device_reported`. A `RECEIVED` report only sets `received_at`; it never changes status. Capabilities move from `UNVERIFIED` to `DEVICE_REPORTED_SUCCESS/FAILURE`/`UNSUPPORTED` from results, and only staff watching an HDMI test can set `STAFF_CONFIRMED` / `STAFF_REJECTED`.

---

## 5. Device API (Flutter TV contract)

Base URL: the dashboard service (`DASHBOARD_URL`). JSON everywhere, UTC ISO-8601 with `Z`. Device calls send `Authorization: Bearer <deviceToken>`. Errors: `{"status":"error","code":"<code>","message":"…"}`; `429` carries `Retry-After: 60`.

### 5.1 Pairing

`POST /api/kiosk/device/pairing/challenges` (no auth; 10/min per IP)

```json
{"deviceType":"CONSOLE_TV","tvPlatform":"ANDROID_TV","tvManufacturer":"Sony","tvModel":"Example Model",
 "appVersion":"1.0.0","consoleType":"PS5","hdmiInput":"HDMI_1",
 "controlCapabilities":{"switchToApp":false,"switchToHdmi":false,"lockEnforcement":false}}
```
`tvPlatform` ∈ `ANDROID_TV, GOOGLE_TV, TIZEN, WEBOS`. `201`:
```json
{"challengeId":"5b0c…","pairingCode":"KQ7M-3XHP","claimSecret":"<keep in memory only>",
 "expiresAt":"2026-11-22T10:05:00Z","serverTime":"2026-11-22T10:00:00Z","pollIntervalSeconds":3,"deviceType":"CONSOLE_TV"}
```
Show `pairingCode`. Never display `claimSecret`. The device does not and cannot name a cafe or station.

`POST /api/kiosk/device/pairing/challenges/<challengeId>/claim` body `{"claimSecret":"…"}` (40/min per challenge, 120/min per IP)

* `202 {"status":"pending", "expiresAt", "pollIntervalSeconds":3}`: keep polling.
* `200` once, after a cafe admin approved:
```json
{"status":"paired","deviceToken":"<bearer>","deviceId":41,"vendorId":7,
 "station":{"stationId":12,"stationNumber":3,"stationName":"PS5 Bay","consoleType":"PS5","hdmiInput":"HDMI_1"},
 "device":{"deviceId":41,"controlCapabilities":{…},"capabilityVerification":{…},…},
 "wsUrl":"https://…","socketPath":"/socket.io","heartbeatIntervalSeconds":15,"serverTime":"…"}
```
* `410 pairing_already_claimed` / `410 pairing_expired`, `404 pairing_not_found` (wrong id or secret), `409 station_already_paired`.

Store `deviceToken` in platform secure storage (Android Keystore / Tizen / webOS secure storage).

### 5.2 State and reconciliation

`GET /api/kiosk/device/state` (also returned by every heartbeat):
```json
{"serverTime":"2026-11-22T10:35:00Z",
 "device":{"deviceId":41,"deviceType":"CONSOLE_TV","online":true,"lastHeartbeatAt":"…","controlCapabilities":{…},"capabilityVerification":{…}},
 "station":{"stationId":12,"consoleType":"PS5","hdmiInput":"HDMI_1",…},
 "session":{"sessionId":"session_example","sessionRef":{"kind":"booking","id":"981"},"status":"ACTIVE",
   "startedAt":"2026-11-22T10:00:00Z","expiresAt":"2026-11-22T11:00:00Z","endedAt":null,
   "serverTime":"2026-11-22T10:35:00Z","version":3,"eventSequence":5,"playAllowed":true,"secondsRemaining":1500,
   "runtimeState":"active","bookingIds":[981],"stationId":12,"deviceId":41},
 "display":{"controlStatus":"SUCCEEDED","lockState":"UNLOCKED","security":"SESSION_ACTIVE",…},
 "pendingCommands":[],"heartbeatIntervalSeconds":15,"eventVersion":1}
```
`session` is `null` when idle. The existing `GET /api/kiosk/session` also works with the TV bearer and returns the same `timer` (= `session` above), `display`, `station`, `pending_commands`, plus the original `session` runtime snapshot and capabilities including `console_tv_v1`.

**Timer rule:** countdown locally as `expiresAt − (now + (serverTime − localTimeAtResponse))`. Reconcile on every event, every heartbeat response and at least every 60 s. Never extend locally. If the backend says `playAllowed:false`, show the lock screen.

### 5.3 Heartbeat

`POST /api/kiosk/device/heartbeat` every `heartbeatIntervalSeconds` (or socket `device.heartbeat` with an ack callback):
```json
{"appVersion":"1.0.0","currentInput":"HDMI_1","lockScreenVisible":false,"appInForeground":false,
 "networkType":"wifi","uptimeSeconds":3600,"controlCapabilities":{"switchToHdmi":true}}
```
Response = state (§5.2) + `ok:true`. Offline is shown after `CONSOLE_TV_OFFLINE_AFTER_SECONDS` (45 s). The heartbeat is also the runtime liveness signal: extensions are refused while the TV is offline, so a disconnected TV can never be auto-extended.

### 5.4 Commands

Delivered as socket events (§6) and recoverable with `GET /api/kiosk/device/commands` → `{"commands":[<command>], "serverTime"}` (pending, unexpired only).

Command payload:
```json
{"v":1,"eventId":"…","type":"device.lock.requested","commandId":"0d6c…","commandType":"LOCK","commandStatus":"PENDING",
 "deviceId":41,"stationId":12,"vendorId":7,"sessionId":"session_example","sessionVersion":4,
 "issuedAt":"2026-11-22T11:00:01Z","expiresAt":"2026-11-22T11:01:01Z","reason":"session_expired","serverTime":"…",
 "hdmiInput":"HDMI_1","session":{…timer contract…}}
```
`hdmiInput` is present on `UNLOCK` and `HDMI_TEST`.

Report: `POST /api/kiosk/device/commands/<commandId>/result` (or socket `device.control.result` with `commandId` in the body)
```json
{"status":"SUCCEEDED","sessionVersion":4,"observedInput":"HASH_APP","lockScreenVisible":true,"detail":"input switched via TvInputManager"}
```
`status` ∈ `RECEIVED` (delivery only), `SUCCEEDED`, `FAILED`, `UNSUPPORTED`, `UNVERIFIED` (attempted, cannot confirm). Response `{"commandId","commandStatus","evidence":"device_reported","followUpCommands":[…]}`.

Rejections: `409 stale_command` (superseded by a newer LOCK/UNLOCK), `409 command_expired`, `409 result_conflict` (different final result for the same command), `409 session_version_mismatch`, `403 command_scope_mismatch`. Same result twice → `200` with `duplicate:true`. If an `UNLOCK` result arrives after the session stopped being authorized, the backend answers with a `LOCK` in `followUpCommands` and on the socket.

**Device rules:** execute a command only if `commandId` is new, `expiresAt` is in the future (server clock) and `sessionVersion` is not older than the newest version you hold. Before switching to HDMI for `UNLOCK`, check `session.playAllowed` (fetch state if unsure). After `HDMI_TEST`, report the result and return to the lock screen if no session is running.

### 5.5 Credentials

* `POST /api/kiosk/device/credentials/rotate` → `{"deviceToken","deviceId","rotatedAt"}`. Old token stops working immediately; the running session and device id are kept. Reconnect the socket with the new token.
* `POST /api/kiosk/unlink` (existing) lets the TV unpair itself.
* Revoked by the cafe → `device.revoked` event, then every call returns `401 invalid_session_token`: wipe the token and restart pairing.

### 5.6 Session extension by QR (existing flow)

When `session.status` is `EXPIRING`, `EXPIRED` or `ENDED`, call the existing `POST /api/cafe/agent/qr` with the device bearer → `{"token","checkout_url","expires_in":1800,"console_id","vendor_id"}` and render `checkout_url` as a QR. The URL holds only a signed, 30-minute station reference (`cafe-pc-qr-v1`), never the device token. The gamer signs in on their phone; the existing checkout applies cafe wallet / existing booking / owner-approval rules, idempotency and replay protection. A purchase starts a new session on this station through the shared engine; the TV receives `session.prepare` on the `/cafe-agent` namespace (existing), acknowledges with `POST /api/cafe/agent/ack` after it has shown the session start, and then gets `session.started` + `device.unlock.requested`. While a session is still `EXPIRING`, the in-session paths `POST /api/kiosk/session/extension/quote` and `/continue` work with the TV bearer exactly as on the PC.

---

## 6. Socket.IO contract

Connect to `wsUrl` (path `/socket.io`) with `auth: {"session_token": "<deviceToken>"}`. A TV bearer joins room `device_<deviceId>` only; it does not receive PC kiosk events. For QR sessions also connect to namespace `/cafe-agent` with `auth: {"token": "<deviceToken>"}` (existing).

Server → TV (every payload has `v:1`, `eventId`, `type`, `deviceId`, `stationId`, `vendorId`, `sessionId`, `sessionVersion`, `eventSequence`, `issuedAt`, `serverTime`, `session`):

| Event | When |
|-------|------|
| `session.started` | First event for a session on this TV. |
| `session.updated` | Any other change (billing, state, reconnection). |
| `session.expiring` | Entered the last 5 minutes. |
| `session.extended` | `expiresAt` moved later. |
| `session.expired` | Paid end reached (backend decided). |
| `session.ended` | Ended early by staff/stop/release. |
| `device.unlock.requested` | Session became authorized (once per session) or staff Unlock. |
| `device.lock.requested` | Session expired/ended (once per session end), staff Lock, or stale-unlock relock. |
| `device.hdmi_test.requested` | Staff HDMI test. |
| `device.config.updated` / `device.reassigned` | Station HDMI source changed / TV moved to another station (`station` included). |
| `device.revoked` | Cafe unpaired the TV. |

TV → server (ack callback returns `{"ok":true,…}` or `{"ok":false,"code":…}`): `device.heartbeat` (body §5.3), `device.control.result` (body §5.4 + `commandId`).

Dedup: ignore an `eventId` or `commandId` you have seen; ignore session events whose `sessionVersion`/`eventSequence` is lower than what you hold. After reconnecting, call `GET /api/kiosk/device/state`; it is the source of truth.

Dashboard rooms get `console_device.updated {vendor_id, console_id, device_id, reason, server_time}` (refresh signal only).

---

## 7. Expiry (backend-authoritative)

1. The extension worker (`tick()`, every 5 s, runs whether or not the TV is connected) sees a TV station's runtime past `reserved_until`.
2. It calls the shared `finish(row, reserved_until)`: bookings complete, capacity and console are released, the outbox records the change. Because play stops at the boundary, no overtime is metered (PC kiosks keep their current overtime handling).
3. Dispatch emits `session.expired` and issues one deduplicated `LOCK` (`reason: session_expired`) to `device_<id>`.
4. The TV opens the Hash lock screen and reports the result.
5. The result is stored on `device_commands` and in `device_events`; the dashboard shows it. If the TV is offline, failed, or does not claim lock enforcement, the station shows **Not securely locked**.

Back-to-back bookings the gamer bought are still joined in advance by the existing `adopt_follow_on_bookings`, so they extend `reserved_until` before the boundary.

---

## 8. Cafe dashboard API

Owner JWT, or staff access token with `dashboard.view` (read) / `gaming.manage` (actions). The cafe always comes from the token (`check_scope`); every device and station is checked against it.

| Method & path | Purpose |
|---------------|---------|
| `GET /api/vendors/<v>/console-devices` | All stations with `consoleType` (PC/PS5/PS4/XBOX/…), `hdmiInput`, `deviceKind`, `device` (TV health, capabilities, verification), `session` (timer contract), `display`. |
| `POST /api/vendors/<v>/console-devices/pairing/approve` | `{"pairingCode":"KQ7M-3XHP","consoleId":12,"hdmiInput":"HDMI_1"}` (20/min per cafe; needs the `kiosk` subscription entitlement; PC stations refused). |
| `POST …/<deviceId>/commands` | `{"commandType":"LOCK"|"UNLOCK"|"HDMI_TEST"}` → `202` command. `UNLOCK` → `409 session_not_authorized` without a running paid session. |
| `POST …/<deviceId>/commands/<commandId>/verify` | `{"observed":true|false}`: staff saw the TV switch (or not). |
| `PUT …/stations/<consoleId>/display` | `{"hdmiInput":"HDMI_2"}` or `null`. |
| `POST …/<deviceId>/reassign` | `{"consoleId":14,"hdmiInput":"HDMI_1"}`; refused while a session runs on the TV or the target. |
| `POST …/<deviceId>/revoke` | Unpair; `409 end_session_first` while a session or QR checkout is live. |
| `GET …/<deviceId>/events?limit=100` | Device health / audit log. |

Start, end and extend use the existing dashboard flows (booking start, `releaseDevice`, `/api/cafe/<v>/extensions/<runtime>/end`, extension approvals). The panel's "End session" calls the existing extensions end endpoint.

---

## 9. Security summary

* Every device call authenticates the link bearer and re-reads its station and cafe; socket events re-check the link is still active.
* Pairing codes: 8 characters from a 31-symbol alphabet, 5-minute lifetime, single use, HMAC-stored, rate-limited at creation, polling and approval. The TV gets a credential only by presenting its claim secret after an admin of the station's own cafe approved.
* Admins can act only on their cafe (`check_scope`, cafe from token). PC stations cannot be paired as TVs.
* Credentials are rotatable in place and revocable; revocation supersedes pending commands.
* QR codes carry a signed station reference only; payment/approval stays in the existing checkout.
* Commands are versioned, expiring, deduplicated and superseded; stale or expired results cannot reopen a station; a late UNLOCK after the end triggers a LOCK.
* Device-reported capabilities are stored with verification status and never shown as verified unless staff confirm.
* Transport: TLS is terminated at the existing edge (wss/https). No change.

---

## 10. Backward compatibility, tests and open points

* PC kiosk: no change to endpoints, payloads, rooms, events, lock/unlock semantics, overtime, pricing or payments. `GET /api/kiosk/session` returns the same body for PC bearers. Licence counting is identical while no TV is paired.
* `tests/test_console_tv.py` (real PostgreSQL via `CAFE_TEST_DATABASE_URL`): pairing approval/expiry/single-use/rate limit/cafe scoping/rotation; start → UNLOCK; offline backend expiry → LOCK with no overtime; replayed dispatch issues no second lock; RECEIVED ≠ success; stale/superseded/expired results; late UNLOCK relock; heartbeat liveness; admin scoping, HDMI test + staff verification, reassign, revoke; Socket.IO rooms keep PC and TV traffic apart; PC regression (overtime unchanged, no TV commands/events/rooms, no `timer` in PC session response, TV not counted as a PC seat).
* Full backend suite on PostgreSQL: 411 passed, 12 failed. The same 12 fail on the base branch without these changes (cross-repo files absent from this checkout, password verifier, pricing contract fixtures).
* Dashboard: no new TypeScript errors (same 228 pre-existing lines with and without the change); node tests 86 pass / 8 fail, the same 8 failing before.

Open points for the product owner:

1. **Pause / resume**: the engine has no pause. Not added.
2. **TV licensing**: paired TVs do not consume PC kiosk seats; pairing requires the `kiosk` entitlement. Change `count_pc_links` / the approval check if TVs should be billed differently.
3. **Expiry policy for TV stations** is a hard stop at the paid end (no metered overtime). PC stations keep metered overtime.
4. **What a TV can really do** varies by platform: most consumer TVs cannot force an input switch or block the remote from a third-party app. Expect many stations to report `UNSUPPORTED`/`UNVERIFIED`; the dashboard will show them as not securely locked, by design.

---

## 11. Environment configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `CONSOLE_TV_PAIRING_TTL_SECONDS` | 300 | Pairing code lifetime. |
| `CONSOLE_TV_CLAIM_WINDOW_SECONDS` | 120 | Minimum time the TV has to claim after approval. |
| `CONSOLE_TV_COMMAND_TTL_SECONDS` | 60 | Command expiry. |
| `CONSOLE_TV_HEARTBEAT_SECONDS` | 15 | Interval told to the TV. |
| `CONSOLE_TV_OFFLINE_AFTER_SECONDS` | 45 | Dashboard offline threshold. |
| `KIOSK_WS_URL` (existing) | request host | Socket URL returned to TVs at pairing. |
| `CAFE_CHECKOUT_URL` (existing) | — | Required for the QR extension code. |
| `SECRET_KEY` (existing) | — | Also keys the pairing code/secret HMACs; rotating it invalidates open pairing codes only. |
| `SESSION_EXTENSION_WORKER_ENABLED` (existing) | true | Must stay on: it enforces TV expiry. |

Deploy order: run the migration, deploy hfg-dashboard-service, then hash-dashboard. No other service changes.
