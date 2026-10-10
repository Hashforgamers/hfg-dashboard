# Booking verification and kiosk 401 review — 10 October 2026

Kiosk source was reviewed **read-only** in `hashdashpc`; no kiosk files were changed. Backend changes are local and require deployment.

## Confirmed failures in the supplied kiosk source

1. `lib/features/kiosk/data/kiosk_backend_repository.dart`, `startSessionWithAccessCode()` posts to onboarding `/api/bookingQueue` with Content-Type only. It supplies neither a device token nor a login token. The onboarding proxy forwards Authorization to dashboard `/api/kiosk/start-session`; the downstream backend correctly rejects an empty header with 401.
2. `lib/features/timer/presentation/cubit/timer_cubit.dart`, `_startRemoteIfNeeded()` supplies `config.authToken` to the legacy updateDeviceStatus route. The lock cubit explicitly permits this login JWT to be missing/expired while continuing kiosk operation. Consequently that remote start can return 401 even though `config.sessionToken` is still active.
3. Runtime heartbeat, owner PIN and sockets already use the separately stored active PC link token `config.sessionToken`. Booking-start calls must follow the same identity contract.
4. `_throwIfError()` reads message/error rather than code. Backend errors now include a readable message alongside the stable code, so the native client can explain missing/expired authentication without a source change for error parsing.

The exact string “Failed to verify booking” and a separate booking-QR scanner/verification request were not found in this supplied branch. Confirm the installed kiosk/app build and failed request path before attributing that exact message to a specific method. The QR displayed by the lock page is the gamer-facing PC checkout QR; it is distinct from a booking ticket containing an access code.

## Team integration requirements (no kiosk code changed here)

- For bookingQueue/access-code requests, send `Authorization: Bearer <config.sessionToken>`.
- Use that same active link credential for start/updateDeviceStatus, booking remaining, extension and release operations. Owner/login/gamer JWTs are different credentials; do not depend on the owner login JWT staying alive during kiosk operation.
- A PC-token release through the legacy releaseDevice path must include the exact `booking_id` in the JSON body, or use the modern runtime Stop API. Do not derive a booking from the PC alone: a stale retry must not terminate a later customer's session.
- Do not store a token in a URL, logs, or a public QR. Never have the backend look up and insert a PC's secret just from console_id. A booking code proves the ticket, not physical PC ownership.
- Do not begin local play after an unsuccessful remote authorization. The supplied timer code currently logs remote-start failure and keeps the local play path alive. Native behavior must distinguish an already-authorized server session from a failed authorization.
- The lock cubit also has hardcoded admin/test-code branches. These are separate native paths and must not bypass owner PIN authorization or production booking authorization. No changes were made to them during this review.

## Unified device verification API

```http
POST https://hfg-dashboard.onrender.com/api/kiosk/booking/verify
Authorization: Bearer <ACTIVE_PC_LINK_TOKEN>
Content-Type: application/json

{"access_code":"MKY628"}
```

Or a booking-ticket QR payload:

```json
{"qr":{"booking_id":1094,"access_code":"MKY628"}}
```

The QR value can also be that JSON encoded as a string, or the six-character access code itself. The code is normalized to uppercase and stripped of surrounding whitespace. Numeric codes remain supported. `console_id` is optional for a linked PC; if supplied it must match the token. Plain guessed booking IDs are not a kiosk ticket credential. A gamer-facing signed PC checkout QR must continue through the existing gamer `/api/cafe/checkout` flow, not this ticket-verification API.

Example successful accepted/upcoming booking, within its start window:

```json
{
  "status":"success",
  "verified":true,
  "can_start":true,
  "data":{
    "booking_id":1094,
    "console_id":269,
    "vendor_id":41,
    "game_id":100,
    "status":"ready",
    "start_time":"2026-10-10T10:00:00+00:00",
    "end_time":"2026-10-10T11:00:00+00:00",
    "server_time":"2026-10-10T10:05:00+00:00"
  }
}
```

IDs/times are illustrative, not production booking 1094 data. Active bookings can return the existing active booking-window fields instead. Verify does not redeem the code, assign a PC, unlock, or collect payment. On success call the existing start endpoint with the same ticket/code and active PC Authorization:

```http
POST /api/kiosk/start-session
Authorization: Bearer <ACTIVE_PC_LINK_TOKEN>
Content-Type: application/json

{"console_id":269,"access_code":"MKY628"}
```

Alternatively keep the onboarding `/api/bookingQueue` proxy with the same header/body. The start endpoint rechecks state, time and capacity; a verification response is not a reservation. Wait for committed authorization before native unlock.

Both verification and start use the same backend parser, identity checks, acceptance rules, console scope and rate limits. An accepted pay-at-cafe booking (`confirmed`) can verify/start without a gamer app session, wallet, or already-collected cash payment. Desk collection remains separate. Pending/unaccepted bookings cannot start. Payment at the desk must not be fabricated by unlocking.

## Errors

```json
{
  "status":"error",
  "code":"token_required",
  "message":"PC authentication is required. Send the active PC link token in the Authorization Bearer header."
}
```

- 401 token_required: header missing; kiosk team must supply the active PC token.
- 401 invalid_session_token: missing/inactive/revoked link credential; relink/recover device identity.
- 401 token_expired: expired login JWT was used; runtime requests need the active PC link credential.
- 403 kiosk_token_required: verification requires a linked PC, not a dashboard token.
- 400 access_code_required / invalid_booking_qr / invalid_access_code: send the ticket credential in its supported format.
- 403 booking_scope_mismatch / booking_console_mismatch: ticket and device must belong to the same cafe/assigned PC.
- 409 booking_not_accepted: cafe must accept the pay-at-cafe request first.
- 409 session_not_active / session_ended / access_code_used: respect scheduled/terminal/redemption state.
- 429 rate_limited: Retry-After 60, no rapid repeated guesses.

A 401 is not caused by the customer having no wallet or by pay-at-cafe being unpaid. Do not remove authentication or inject server credentials to hide it.

## Backend validation

PostgreSQL regressions cover device verification with both QR/access-code inputs, accepted pay-at-cafe start without any wallet table, rejection before acceptance, no redemption/assignment during Verify, wrong PC/cafe, invalid/expired credentials and duplicate redemption. Native release/start/overlay behavior still requires the kiosk team's changes and a real-device test. The kiosk repository remained unchanged throughout this review.
