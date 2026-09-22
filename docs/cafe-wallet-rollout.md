# Cafe wallet and QR checkout

Implemented in the dashboard service, booking service and Hash dashboard. This is a cafe-scoped balance, independent of Hash Wallet. Amounts in all new APIs and tables are integer INR paise.

## Deployment order

1. Apply `sql/20260922_cafe_wallet.sql` to the shared PostgreSQL database before deploying either service, then apply `sql/20260923_unified_kiosk_qr.sql` for unified booking starts. Apply `hfg-booking/sql/20260922_cafe_login.sql` to the booking service's database (the same user/vendor database).
2. Deploy both services. They must use the same strong `JWT_SECRET_KEY`. Configure the dashboard service's `CAFE_CHECKOUT_URL` to the full HTTPS gamer page URL, e.g. `https://dashboard.example.com/play`. Keep `CAFE_RECONCILER_ENABLED=true` on at least one live dashboard process; it runs every five seconds. The `flask cafe-reconcile` command provides an external scheduler alternative.
3. Configure the booking service's existing Flask-Mail SMTP settings and `MAIL_DEFAULT_SENDER`. Gamer sign-in sends a single-use six-digit email code to an existing Hash account; no new account is silently created. Codes expire in ten minutes, have five verification attempts, and requests are limited by email and IP.
4. Deploy `hash-dashboard`, with its existing `NEXT_PUBLIC_DASHBOARD_URL` and `NEXT_PUBLIC_BOOKING_URL` pointing to those services. `/play` is public and does not initialize staff dashboard authentication or sockets. `/cafe-wallet` is the staff workspace.
5. Re-unlock staff sessions after deployment to create their auditable session records. Owners can enable the new wallet permissions in Employee Access for customized role matrices. Default staff can top up; managers can also reverse; manual adjustments default to owners.
6. In Cafe Wallet & Shifts, configure durations, prices, desk methods and food collection. Saving a cafe policy makes that cafe wallet-only for gaming; cafes with no saved policy retain legacy behavior. Enable QR self-service only after the real PC agent described below is connected. Enabling installs database guards on that cafe's existing console/booking tables.

Legacy gateway order creation, payment-link generation and capture must now include `vendor_id`, `game_id` or `booking_id`, so the server can enforce cafe payment policy before collecting money. Update older gateway clients accordingly. Wallet-only cafes must use QR checkout rather than the legacy booking checkout routes.

No migration was applied to a production database and no production cafe settings were changed by this implementation.

## PC agent integration — required before real PC rollout

This workspace does not contain a native PC agent. The backend and web checkout are implemented and tested with a simulated agent. Native OS lock/unlock, fullscreen QR rendering, tamper resistance and offline timer enforcement must be implemented by that agent. A browser acknowledgement is not proof that a Windows PC unlocked.

1. An authorized cafe staff/vendor credential links a PC using `POST /api/vendors/{vendor_id}/pcs/link` with `console_id`. Store the returned opaque `session_token` securely on that PC. Never put this credential in a QR code, URL or gamer page.
2. Connect Socket.IO to namespace `/cafe-agent`, with `auth: {token: session_token}`. The server joins only that credential's private PC room.
3. Call `POST /api/cafe/agent/qr` with `Authorization: Bearer <session_token>`. Render `checkout_url` as the **only gamer QR** on the locked PC. This same QR supports existing paid bookings and new wallet sessions; do not display a separate booking/payment QR. Refresh every 60–90 seconds; QR validity is 120 seconds. Scanning does not unlock anything.
4. Listen for `session.prepare`. Persist the command/session ID and process it idempotently. Also poll `GET /api/cafe/agent/session` on reconnect and periodically; this durable recovery path handles missed WebSocket messages and server restarts.
5. Prepare the local session and verify that the PC can run it. Send `POST /api/cafe/agent/ack` with `session_id`, `command_token` and boolean `success`. Do not expose the desktop while waiting for server confirmation. A failure or an acknowledgement after the 45-second deadline releases the reservation. The same acknowledgement may be retried safely.
6. Only an `active` server response authorizes play. Enforce its `ends_at` locally, including while offline. On restart, remain locked until the authenticated recovery endpoint confirms an active session. Ignore duplicated or expired commands. A failed/cancelled/completed/missing session must leave the PC locked. A PC must not remain unlocked after its deadline even if the network or server is unavailable.

Session state: `reserved → active → completed`, or `reserved → failed`. There is one live database claim per PC. Wallet balance and reservations are locked transactionally. A successful acknowledgement creates exactly one capture entry. Time begins at acknowledgement. Reconciliation releases expired reservations and completes expired sessions. It does not remotely enforce OS locking; the agent must do that.

## Gamer and staff APIs

- Gamer auth: existing Hash token → `POST /api/cafe-checkout/token` on booking service; web sign-in → `/api/cafe-checkout/login/request` and `/verify`. Use the resulting scoped token only with cafe gamer endpoints.
- `GET /api/cafe/checkout?qr=...`: cafe, PC, price options, available balance, existing bookings with eligibility reasons, and the gamer’s active session ID on this PC.
- `POST /api/cafe/checkout`: `qr`, `minutes`, `expected_amount`, `payment_method: "cafe_wallet"`, `idempotency_key`. A changed price requires checkout reload and confirmation. The web UI retains its request key across refreshes.
- `GET /api/cafe/sessions/{id}`: owner-only status, timing and current checkout/balance information. Session recovery remains available after the original QR expires.
- `GET/PUT /api/cafe/{vendor}/policy`: current settings / authorized replacement. Initial release implements only cafe wallet, desk top-ups and cash/cafe UPI collection. Other Hash payment rails remain available to cafes without a policy.
- Staff: `/{vendor}/wallets/{user}`, `/topups`, `/adjustments`, `/{vendor}/ledger/{entry}/refund`, `/{vendor}/shifts`, `/shifts/open`, `/shifts/{id}/close`, `/audit`, `/report`, `/logout` under `/api/cafe`.
- Food: `/api/cafe/food/menu` and `/food/orders` accept QR context, or `session_id` owned by the gamer. Food snapshots and inventory changes are separate from gaming. Vendor-collected food cannot be paid from the cafe wallet or marked collected by cafe staff. Cafe-collected food has a separate staff collection endpoint and report category; no wallet credit/debit is created for food collection.

## One QR for existing bookings and wallet play

After sign-in, `/play` lists the gamer’s bookings at this cafe first. Eligible paid solo bookings show **Start my booking**, with no additional payment. **Buy a new session instead** exposes the existing wallet duration/payment flow on the same page. Without bookings, wallet time selection appears immediately. Food remains a separate checkout.

For an existing booking, send `POST /api/cafe/checkout` with `qr`, `booking_id` (the returned group anchor), `payment_method: "existing_booking"` and a unique `idempotency_key`. The backend rechecks ownership, cafe, payment, booking window, PC compatibility and availability. Group/squad bookings require desk assignment. Contiguous slots purchased with the same access code are grouped. Only verified paid bookings can start; unpaid bookings require desk assistance.

Both flows use the same `session.prepare`, acknowledgement and recovery APIs. Agent commands include `kind`, `booking_ids`, `booking_end` and `amount`; existing bookings have `kind: "existing_booking"` and amount zero. Existing bookings end at their original scheduled end, even if started late. No wallet reserve/capture ledger entry is written for them. Failed startup releases the PC and booking claim so another attempt is possible. Successful claims prevent booking reuse on another PC. Cancellation or payment reversal during play is reflected by reconciliation and agent polling.

The migration guards legacy assignment updates while a QR booking is reserved or active. Apply the additive migration before deploying the updated service. Tests use simulated PC acknowledgements; the actual kiosk must replace its existing displayed gamer QR with the returned `checkout_url` and implement this agent contract.

## Audit and reconciliation

Ledger entries cannot be edited or deleted through the ORM or PostgreSQL. Corrections append a reversal or an authorized adjustment with a reason. Reversal is full-transaction, once only. Staff identity and name are snapshotted from verified credentials, never accepted from the request body.

Login, explicit logout, recorded JWT expiry, shift open/close, payment-policy changes and configured-cafe staff/pricing mutations are audited. Closing a browser does not close a cash shift. Offline logout is locally immediate; if the API cannot be reached, the server records session expiry at the token deadline.

Shift expected cash = opening cash + recorded cash top-ups - cash top-up reversals + cafe-collected cash food payments. UPI receipts are shown separately. Gaming consumption, top-ups, adjustments, reversals and food collections remain separate totals. Gaming-charge reversals restore cafe balance; they are not a cash payout. A top-up reversal records a desk payout using the original collection method and requires an open shift.

Food-store payments remain `pay_at_store` in this release; there is no separate food-vendor sign-in/payment confirmation portal in this workspace.

## Verification

The new integration suite uses real PostgreSQL row locks and migrations, with temporary schemas and fixture versions of existing catalog tables. It covers concurrency, retry safety, private agent rooms, wrong-PC acknowledgements, timeout releases, immutable history, permissions, shift arithmetic, OTP replay/limits, food separation and legacy policy enforcement.

```sh
CAFE_TEST_DATABASE_URL=postgresql://localhost/test_database python -m pytest tests/test_cafe_wallet.py -q
```

Do not point tests at production. Tests create/drop dedicated random schemas. The browser workflow was exercised against an isolated PostgreSQL fixture with email delivery mocked and a simulated PC acknowledgement. Real SMTP delivery and native PC control need environment integration validation.
