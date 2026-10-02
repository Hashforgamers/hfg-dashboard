# Self QR sessions, owner-approved continuation and balance due

Deploy the shared capacity changes in all four services described in
`shared-booking-slot-capacity.md`. Then apply
`sql/20261002_cafe_continuations.sql` before deploying this dashboard backend
and the `hash-dashboard` web client. Both migrations are transactional and
repeatable. No production data, deployment or email delivery was changed by
local development.

## Billing and availability

Existing cafe-wallet checkout buys a **fixed duration**. Wallet money is reserved
until PC acknowledgement, then captured once. A zero remaining wallet balance
immediately after capture does not stop the purchased duration. The warning
appears during its last five minutes; play stops at `ends_at`.

A gamer requests a configured continuation duration and reviews its console
price. Requests themselves hold no capacity and cannot authorize play. The
owner may reject immediately, or approve after funded time ends. Approval checks
the current price, dated capacity, physical console and future bookings again,
then reserves a new `kind: owner_credit` session. It has the same 45-second PC
acknowledgement timeout as prepaid play. Only a successful acknowledgement creates
the fixed-duration balance due. Failed startup releases every hold without debt.
Early ending releases capacity; the explicitly agreed fixed-duration price remains
due, as with prepaid time. This is **not** a metered per-minute or negative-wallet
billing system.

Play stops at the approved duration limit too. Additional play needs another
request and a new approval, after settling outstanding approved play. New
self-service wallet checkouts cannot bypass an unpaid balance at that cafe.
Other cafes retain their separate balances. Pending requests expire 15 minutes
after funded time ends (or after the request if it is already over). Approval
never displaces an app/desk booking. Capacity is released on stop independently
of invoice settlement, so unpaid debt never blocks an otherwise free slot.

## Gamer / web QR endpoints

All use the existing exchanged `cafe_gamer` JWT, restricted to the session owner.

- `GET /api/cafe/checkout/affordable?qr=<token>`: longest affordable whole-minute duration (minimum five minutes), capped at the cafe's longest configured duration. Start through normal checkout with `use_available_balance: true`, quoted minutes and amount. Pricing and funds are rechecked; leftover paise stay in the wallet.
- `GET /api/cafe/sessions/<id>`: session snapshot, `remaining_seconds`,
  `play_allowed`, `stop_at`, `server_time`, `payment_due`, `continuation_request`,
  `last_continuation`, `next_session_id` and checkout details.
- `GET /api/cafe/sessions/<id>/continuation/quote`: configured durations with
  integer paise price, or `amount: null` plus unavailability reason. This is an
  indicative quote; capacity is reserved only on approval.
- `POST /api/cafe/sessions/<id>/continuation`:
  `{minutes, expected_amount, idempotency_key}`. Returns a durable request.
  Reusing a key with different input returns 409; retries do not resend email.

The web `/play` page displays low-time warnings, requests continuation, polls the
owner decision, follows `next_session_id`, and displays debt. Rejection and expiry
keep play stopped; the gamer may ask again within the continuation window.
Native Flutter sources, including `cafe_play_api.dart`, are absent from this
workspace and still need these client integrations. Never convert null pricing
to a purchasable zero price.

## Staff endpoints and dashboard

These require an unexpired named `vendor_access` staff session for the cafe.

- `GET /api/cafe/<vendor>/sessions/live`: running/reserved QR sessions, completed
  unpaid sessions and pending requests. Includes gamer name, PC number and owner
  email delivery status (no recipient address). Dashboard Live Sessions and the
  notification bell refresh from this snapshot and authenticated vendor events.
- `POST /api/cafe/<vendor>/continuations/<request>/decision`:
  `{decision: "approve" | "reject", expected_amount}`. Only the owner may decide;
  custom employee permissions cannot grant credit approval. Approving retries
  return the same child session. Price change/conflict returns 409 for review.
- `POST /api/cafe/<vendor>/sessions/<id>/end`: `booking.manage`, or owner.
  Existing paid booking QR sessions retain their normal booking controls.
- `POST /api/cafe/<vendor>/sessions/<id>/settle`:
  `{method: "cash" | "cafe_upi", expected_amount, idempotency_key}`. Requires
  `wallet.topup`, an open staff shift and a completed unpaid credit session.
  The staff member confirms actual receipt; the server records a
  `session_collection` ledger entry, shift reconciliation and audit without
  adding money to or subtracting money from the gamer wallet. Duplicate receipt
  retries cannot collect twice. Full settlement only; partial credit payments
  are not supported.

## Kiosk / PC agent contract

Native kiosk sources are absent. The backend provides these authenticated
integration points; the kiosk must implement the UI and local stop enforcement.

Use the active PC link token as Bearer auth and in Socket.IO `/cafe-agent`
connect auth `{token}`. Rooms remain `cafe-agent:<link_id>`.

- `session.prepare`: reserved command and secret `command_token`; start only
  after acknowledging the exact command through the existing `/agent/ack`.
- `session.updated`: authoritative timer/debt/request snapshot.
- `session.warning`: last-five-minutes warning; show a kiosk notice and the
  option to ask the owner for priced additional time.
- `session.stop`: completed/failed session. Lock gameplay and display any debt.
- `GET /api/cafe/agent/status`: reconnect/poll fallback includes the last stopped
  session, decision, next session command, `play_allowed` and `server_time`.
  `/agent/session` continues to provide live/reserved commands for old clients.
- `GET /api/cafe/agent/continuation/quote?session_id=<id>`: PC token plus
  `X-Session-Command: <command_token>`.
- `POST /api/cafe/agent/continuation`: `{session_id, command_token, minutes,
  expected_amount, idempotency_key}`. The user comes from the authenticated PC
  session, never from a caller-supplied user id.
- `POST /api/cafe/agent/session/end`: `{session_id, command_token}`.

The kiosk must keep a local timer from `stop_at` and `server_time`, stop exactly
at expiry even while disconnected, reconcile snapshots on reconnect, ignore
messages for old session IDs when a newer session is running, and acknowledge
reserved commands once. `play_allowed: false` means never unlock gameplay.
Socket events are invalidations/snapshots, not a durable queue; periodic
snapshot reconciliation is required. Booking stop and continuation requests
should not depend on receiving every individual event.

## Owner emails and runtime

Owner recipient is the cafe's `VendorAccount.email`, with vendor contact email
as fallback; it never comes from request JSON. Configure dashboard `MAIL_SERVER`,
`MAIL_PORT`, `MAIL_DEFAULT_SENDER`, optional `MAIL_USERNAME` / `MAIL_PASSWORD`, and
`MAIL_USE_TLS` / `MAIL_USE_SSL` for the same existing SMTP service. No credentials
are checked into code. Missing SMTP/address leaves the dashboard request usable
and displays an email delivery issue. Local tests mock delivery; real owner
email delivery is not verified.

`CAFE_RECONCILER_ENABLED=true` (the existing default) starts independent timer and
email workers. SMTP cannot delay timer expiry. For external scheduling use
`flask cafe-reconcile` and `flask cafe-email-dispatch`. The outbox uses row locks
with SKIP LOCKED, bounded SMTP timeouts, exponential retries (up to 8), stable
Message-ID and discards notifications after request expiry/decision. SMTP is
at-least-once: a crash after acceptance but before commit can resend the same
Message-ID. Dashboard decisions and payments remain idempotent regardless.

Tests run against a disposable local PostgreSQL database. They cover startup
failure, debt, expiry warnings, reconnect snapshots, wrong owner/vendor/gamer/PC,
failed email retries, simultaneous approvals, future booking conflicts, slot
release, receipt retries and attempts to bypass unpaid credit using the original
session or a new wallet checkout.
