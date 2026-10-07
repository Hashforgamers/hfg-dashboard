# Kiosk, dashboard and app integration guide: session extensions v1

**Prepared 7 October 2026.** Checked against the local dashboard-service implementation. Backend changes are **not yet certified deployed**. All IDs, times, balances and prices in examples are fictional; vendor 41 / console 269 illustrate field usage only. Prices must always come from the actual quote response.

## 1. Ownership and integration checklist

| Team | Required integration |
| --- | --- |
| Backend/deployment | Shared migration, matching booking/capacity helpers, dashboard service, reconciliation worker, Redis when using multiple workers |
| Kiosk | Enroll active session, heartbeat, quote/Continue, Stop, authenticate Socket.IO, apply authoritative snapshots, passive gamer UI |
| Dashboard | Configure Self QR credit policy, show requests/notices, resolve conflicts, owner decision, final settlement |
| App | Private gamer stream where required, public slot invalidations, refetch authoritative availability/wallet; preserve server pricing |

One runtime tracks one linked console's play, regardless of original booking source. Extension authorization reserves capacity shared with app, dashboard and Self QR purchases. Never implement local slot blocks, guessed prices, wallet deductions, or a separate extension booking on the client.

## 2. Connection and authentication

Use a configurable `BASE_URL`. The intended dashboard-service host is `https://hfg-dashboard.onrender.com`; confirm deployment before testing the new routes. All paths below are relative to that host. Socket.IO is hosted on the same service with the default `/socket.io` transport path. **Socket.IO is required; these are not raw WebSocket JSON messages.**

| Consumer | HTTP Authorization | Socket namespace/auth |
| --- | --- | --- |
| Linked PC | `Bearer <active console-link session token>` | `/cafe-agent`, `{ "token": "<link token>" }`, recommended for new integration |
| Linked PC using existing default connection | Same link token | `/`, `{ "session_token": "<link token>", "console_id": 269 }` |
| Dashboard staff | Existing named staff access JWT for selected cafe | `/`, `{ "token": "<staff access JWT>" }`; emit `dashboard_join_vendor` |
| Signed-in gamer | Cafe-checkout gamer JWT | `/cafe-gamer`, `{ "token": "<gamer JWT>" }` |
| Availability watcher | None for public invalidations | `/cafe-availability`; emit `watch` |

Keep link tokens and JWTs out of logs and URLs. A kiosk never needs a service secret, owner token, or a gamer's JWT to extend its own session. Server-derived link identity determines the cafe, PC and source ownership. Rooms are selected by the server, not supplied by clients.

Gamer JWTs must be issued through the existing cafe-checkout token flow and contain scope `cafe_gamer`, audience `cafe-checkout`, and valid `sub`, `iat`, `exp`. A generic app JWT cannot substitute for this token. Refresh expired tokens through the existing login exchange, then reconnect.

All extension HTTP responses have `Cache-Control: private, no-store` and vary on Authorization. Do not cache financial responses in local storage or a shared proxy.

## 3. REST endpoint map

| Method/path | Caller | Response |
| --- | --- | --- |
| GET `/api/kiosk/session` | PC | Wrapper `{session, capabilities}`; heartbeat |
| POST `/api/kiosk/session/extension/quote` | PC | Quote; creates/enrolls runtime when using `session_ref` |
| POST `/api/kiosk/session/continue` | PC | Bare snapshot, 200 granted / 202 pending |
| POST `/api/kiosk/session/stop` | PC | Bare snapshot |
| GET `/api/cafe/extensions/{runtime_id}` | Gamer | Own bare snapshot |
| GET `/api/cafe/{vendor}/extension-policy` | Staff with `dashboard.view` | Policy |
| PUT `/api/cafe/{vendor}/extension-policy` | Owner with `account.manage` | Updated policy |
| GET `/api/cafe/{vendor}/extensions` | Staff with `dashboard.view` | `{items, notices}`; maximum 100 each |
| GET `/api/cafe/{vendor}/extensions/{runtime_id}` | Staff with `dashboard.view` | Bare snapshot |
| POST `/api/cafe/{vendor}/extensions/{runtime_id}/decision` | Staff with `booking.manage`; owner for approval | Bare snapshot |
| POST `/api/cafe/{vendor}/extensions/{runtime_id}/end` | Staff with `booking.manage` | Bare snapshot |
| POST `/api/cafe/{vendor}/extensions/{runtime_id}/settle` | Staff with `wallet.topup`; `wallet.adjust` for waiver | Bare snapshot |
| POST `/api/cafe/{vendor}/extension-notices/{notice_id}/read` | Staff with `dashboard.view` | `{success:true}` |

There is no extension POST/Continue/Stop Socket.IO handler. **Mutations use REST. Sockets deliver committed state and invalidations.**

## 4. Source IDs and enrollment

Obtain the booking ID from existing assignment/unlock metadata. For Self QR obtain the existing active `CafePlaySession.id` from the cafe session metadata/agent API. The QR checkout token, access code, console ID and runtime ID are different identifiers; none can replace the source session ID.

For Self QR, only an active wallet-kind play session owned by this link is enrollable. An existing-booking QR claim uses the booking flow. An assigned normal booking must already be active. Enrollment must occur **before its original funded boundary**; settle already accrued legacy overtime first.

`GET /api/kiosk/session` does not enroll a legacy session. `session:null` means no *enrolled* runtime, not necessarily that the PC has no active legacy booking. Resolve the original source through existing APIs and enroll it using the quote endpoint. At session start, enroll and start heartbeat; display a newly fetched quote only when Continue is offered, because quotes expire.

Request, Self QR:
```http
POST /api/kiosk/session/extension/quote
Authorization: Bearer <PC_LINK_TOKEN>
Content-Type: application/json
```
```json
{
  "session_ref": {
    "kind": "self_qr",
    "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
  }
}
```

Normal dashboard/app booking request to the same endpoint:
```json
{
  "session_ref": {
    "kind": "booking",
    "id": "1084"
  }
}
```
Subsequent request, after storing returned runtime ID:
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23"
}
```
Example HTTP 200 quote response:
```json
{
  "quote_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
  "revision": 2,
  "expires_at": "2026-10-08T12:55:30Z",
  "interval_start": "2026-10-08T13:00:00Z",
  "interval_end": "2026-10-08T13:30:00Z",
  "price_paise": 3000,
  "wallet_funded_paise": 500,
  "credit_paise": 2500,
  "self_qr_credit_mode": "automatic",
  "credit_limit_paise": 10000,
  "requires_owner_approval": false,
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23"
}
```

A quote is informational: it does **not** reserve the next interval. Capacity and current pricing are rechecked on Continue/approval. Quotes expire after 30 seconds. `revision` is the runtime version to include with Continue. The owner-approval flag describes policy/funding, not whether the next slot is conflict-free.

For a normal booking, `wallet_funded_paise` is 0 and the price is an invoice due at the end. Self QR credit mode/limit does not impose an owner-approval requirement on normal invoices.

## 5. Continue and rolling authorization

```http
POST /api/kiosk/session/continue
Authorization: Bearer <PC_LINK_TOKEN>
Content-Type: application/json
```
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "quote_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
  "revision": 2,
  "credit_consent": true,
  "idempotency_key": "25a515cb-54b6-4d7d-8fb3-fa6170b3bffc"
}
```
Example HTTP 200 response, automatic mode:
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "session_ref": {
    "kind": "self_qr",
    "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
  },
  "console_id": 269,
  "vendor_id": 41,
  "revision": 3,
  "event_sequence": 2,
  "state": "active",
  "server_time": "2026-10-08T12:55:00Z",
  "started_at": "2026-10-08T12:00:00Z",
  "paid_until": "2026-10-08T13:00:00Z",
  "reserved_until": "2026-10-08T13:30:00Z",
  "stop_at": null,
  "auto_lock_at_end": false,
  "play_allowed": true,
  "last_seen_at": "2026-10-08T12:55:00Z",
  "ended_at": null,
  "extension": {
    "mode": "automatic",
    "rolling_enabled": true,
    "reason_code": null,
    "request_id": null,
    "status": "active",
    "requested_price_paise": null
  },
  "billing": {
    "currency": "INR",
    "total_paise": 0,
    "wallet_funded_paise": 0,
    "collected_paise": 0,
    "waived_paise": 0,
    "credit_due_paise": 0,
    "amount_due_paise": 0,
    "net_cafe_balance_paise": 500,
    "as_of": "2026-10-08T12:55:00Z",
    "is_final": false
  }
}
```

`credit_consent:true` must represent actual gamer acceptance of credit continuation. When credit is refused, send false. Normal invoice sessions do not use the cafe wallet. There is no separate “minutes” or “expected amount” input for this call: the server uses the accepted quote ID.

Continue enables rolling extension. The server tries the next interval around five minutes before `reserved_until`, provided heartbeat is current, price remains acceptable, and capacity/funding/policy allow it. Continue does not restart `started_at`. Stop-at-end disables rolling. A changed rate requires a fresh quote and gamer acceptance. Never extend local time merely because Continue was tapped.

### Owner approval with partial wallet funds

Alternative example: policy is `owner_approval`, quote costs ₹30, wallet has ₹5. The server grants the funded five-minute prefix immediately and creates an approval request for the remaining ₹25. HTTP **202** response:
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "session_ref": {
    "kind": "self_qr",
    "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
  },
  "console_id": 269,
  "vendor_id": 41,
  "revision": 4,
  "event_sequence": 3,
  "state": "approval_pending",
  "server_time": "2026-10-08T12:55:00Z",
  "started_at": "2026-10-08T12:00:00Z",
  "paid_until": "2026-10-08T13:00:00Z",
  "reserved_until": "2026-10-08T13:05:00Z",
  "stop_at": null,
  "auto_lock_at_end": false,
  "play_allowed": true,
  "last_seen_at": "2026-10-08T12:55:00Z",
  "ended_at": null,
  "extension": {
    "mode": "owner_approval",
    "rolling_enabled": true,
    "reason_code": "approval_pending",
    "request_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
    "status": "approval_pending",
    "requested_price_paise": 2500
  },
  "billing": {
    "currency": "INR",
    "total_paise": 0,
    "wallet_funded_paise": 0,
    "collected_paise": 0,
    "waived_paise": 0,
    "credit_due_paise": 0,
    "amount_due_paise": 0,
    "net_cafe_balance_paise": 500,
    "as_of": "2026-10-08T12:55:00Z",
    "is_final": false
  }
}
```

The still-pending `request_id` is the quote/request UUID; `runtime_id` identifies the session. An HTTP 202 response can advance `reserved_until`. Apply the snapshot first and then show a passive “Waiting for cafe approval” message. Do not undo funded play or show the extension as fully granted.

If there are no usable wallet funds and credit consent is missing, the call can return 409 `Credit consent required`. If the configured credit ceiling is reached with no fundable prefix, it can return 409 `Cafe credit limit reached`. These errors do not grant time. Funded partial requests can instead have `consent_required` or `credit_limit` state.

### Already booked next window

HTTP 202 uses the same snapshot shape with `state:"conflict_pending"`, `extension.status:"conflict_pending"`, `extension.reason_code:"staff_resolution_required"` and a pending `extension.request_id`. `reserved_until` does not advance into conflicting time. Staff must resolve the other booking first, then Retry. Approval alone cannot displace it.

## 6. Current session and heartbeat

```http
GET /api/kiosk/session
Authorization: Bearer <PC_LINK_TOKEN>
```

Example HTTP 200 with an enrolled session:
```json
{
  "session": {
    "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
    "session_ref": {
      "kind": "self_qr",
      "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
    },
    "console_id": 269,
    "vendor_id": 41,
    "revision": 3,
    "event_sequence": 2,
    "state": "active",
    "server_time": "2026-10-08T12:55:00Z",
    "started_at": "2026-10-08T12:00:00Z",
    "paid_until": "2026-10-08T13:00:00Z",
    "reserved_until": "2026-10-08T13:30:00Z",
    "stop_at": null,
    "auto_lock_at_end": false,
    "play_allowed": true,
    "last_seen_at": "2026-10-08T12:55:00Z",
    "ended_at": null,
    "extension": {
      "mode": "automatic",
      "rolling_enabled": true,
      "reason_code": null,
      "request_id": null,
      "status": "active",
      "requested_price_paise": null
    },
    "billing": {
      "currency": "INR",
      "total_paise": 0,
      "wallet_funded_paise": 0,
      "collected_paise": 0,
      "waived_paise": 0,
      "credit_due_paise": 0,
      "amount_due_paise": 0,
      "net_cafe_balance_paise": 500,
      "as_of": "2026-10-08T12:55:00Z",
      "is_final": false
    }
  },
  "capabilities": [
    "session_extensions_v1"
  ]
}
```
Example with no active enrolled runtime:
```json
{
  "session": null,
  "capabilities": [
    "session_extensions_v1"
  ],
  "server_time": "2026-10-08T13:12:00Z"
}
```

Poll every 15 seconds throughout the session, including while a socket is connected. HTTP polling updates the kiosk heartbeat. Socket traffic or `ping_health` alone is **not** the extension heartbeat. The server refuses additional authorization after 60 seconds without a heartbeat; already reserved time remains usable to its boundary. The reconciliation interval is five seconds; realtime updates are eventual and subject to network delay.

After a reboot, socket reconnect, token refresh or uncertain mutation: fetch current state. There is no event-history replay API. Do not restore unlock permission solely from cached end times. A null result after an ended enrolled session is expected; use the last ended snapshot/authorized dashboard or gamer GET for its financial summary.

## 7. Snapshot fields and money semantics

| Field | Meaning |
| --- | --- |
| `runtime_id` | One server runtime for the linked console/source |
| `revision` | Authorization/state version; used for guarded mutations |
| `event_sequence` | Also changes for billing updates; order events by it |
| `state` | Runtime status, see state table below |
| `server_time` | UTC observation time; use to estimate client clock offset |
| `started_at` | Original play start; does not reset on extension |
| `paid_until` | Original source boundary; not a live funded-duration estimate |
| `reserved_until` | Current authorized shared reservation boundary |
| `stop_at` | Explicit scheduled/final Stop, or null |
| `play_allowed` | Current server permission; false on final end |
| `auto_lock_at_end` | False for original prepaid-end behavior; does not allow play beyond reserved authorization |
| `ended_at` | Final server Stop timestamp, or null |
| `extension.requested_price_paise` | Price of pending remainder/request, not already accrued debt |
| `billing.total_paise` | Played extension charges only |
| `billing.wallet_funded_paise` | Captured wallet payment only, not held funds |
| `billing.collected_paise` | Credit repayments/collections excluding waivers |
| `billing.waived_paise` | Authorized waiver total |
| `billing.amount_due_paise` / `credit_due_paise` | Net unpaid extension amount; equal in this contract |
| `billing.net_cafe_balance_paise` | Wallet book balance minus Self QR cafe credit debt; can be negative; not spendable availability |
| `billing.as_of` | Actual server accrual timestamp |
| `billing.is_final` | True only after play is ended |

All money is integer paise: 500 = ₹5.00. Original booking, original QR purchase and food charges are excluded from `billing.total_paise`; retrieve their existing billing separately. Never collect `total_paise` again when wallet funding or prior credit collections already cover it. Spendable wallet balance remains its existing `balance - reserved` calculation; the net balance is for showing funds/debt, not authorizing purchases.

The server meters played time, rounds charges using its integer/second rules, and releases unused wallet holds at Stop. UI estimates must be labeled estimates. Always obtain the finalized server summary before collection. Top-ups repay outstanding cafe-specific credit first, then remaining funds cover future usage; no retrospective reclassification/double charge.

| State | Client action |
| --- | --- |
| `active` | Play only within authorization; keep heartbeat |
| `approval_pending` | Keep authorized play; owner must decide pending credit |
| `conflict_pending` | Staff must resolve upcoming booking then Retry |
| `consent_required` | Ask unobtrusively for credit acceptance and fresh quote/Continue |
| `credit_limit` | Show cafe policy limit; staff can alter policy or add wallet funds |
| `price_changed` | Fetch fresh quote and show changed price before acceptance |
| `offline` | Recover heartbeat; do not fabricate more time |
| `ended_unsettled` | Play ended; collect outstanding extension debt |
| `settled` | Play ended and extension debt cleared |

`play_allowed` and the minimum of `reserved_until` / non-null `stop_at` control permission, rather than state label alone. Pending/offline states can still permit already authorized play. A pending request does not grant a grace period beyond that boundary.

## 8. Stop immediately or at authorized end

Immediate Stop request:
```http
POST /api/kiosk/session/stop
Authorization: Bearer <PC_LINK_TOKEN>
Content-Type: application/json
```
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "revision": 3,
  "mode": "now",
  "idempotency_key": "85f74bc4-bbe1-44ed-8f6d-af66519764bc"
}
```
Example HTTP 200 finalized response after ten extra minutes:
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "session_ref": {
    "kind": "self_qr",
    "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
  },
  "console_id": 269,
  "vendor_id": 41,
  "revision": 4,
  "event_sequence": 22,
  "state": "ended_unsettled",
  "server_time": "2026-10-08T13:10:00Z",
  "started_at": "2026-10-08T12:00:00Z",
  "paid_until": "2026-10-08T13:00:00Z",
  "reserved_until": "2026-10-08T13:30:00Z",
  "stop_at": "2026-10-08T13:10:00Z",
  "auto_lock_at_end": false,
  "play_allowed": false,
  "last_seen_at": "2026-10-08T13:09:55Z",
  "ended_at": "2026-10-08T13:10:00Z",
  "extension": {
    "mode": "automatic",
    "rolling_enabled": false,
    "reason_code": null,
    "request_id": null,
    "status": "ended_unsettled",
    "requested_price_paise": null
  },
  "billing": {
    "currency": "INR",
    "total_paise": 1000,
    "wallet_funded_paise": 500,
    "collected_paise": 0,
    "waived_paise": 0,
    "credit_due_paise": 500,
    "amount_due_paise": 500,
    "net_cafe_balance_paise": -500,
    "as_of": "2026-10-08T13:10:00Z",
    "is_final": true
  }
}
```

Stop at existing authorized end, same endpoint:
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "revision": 3,
  "mode": "at_authorized_end",
  "idempotency_key": "11ef42ea-fc94-488f-8fa0-d3c6e4dac3ae"
}
```
The response is a bare snapshot: rolling becomes false, `stop_at` equals the existing `reserved_until`, `ended_at` remains null, and current play can continue until that point. Pending extensions are cancelled. Server reconciliation finalizes at that timestamp.

Urgent `mode:now` can accept a stale revision. It cannot target a different customer's session on the same PC. `at_authorized_end` requires the latest revision. Opening a settlement dialog does not pause or freeze billing; only server Stop finalizes charges. Explicitly ask the gamer to confirm Stop through a user-opened control so an accidental click cannot end a game.

## 9. Cafe policy configuration

GET `/api/cafe/41/extension-policy`, staff JWT. Example HTTP 200:
```json
{
  "self_qr_credit_mode": "automatic",
  "credit_limit_paise": 10000,
  "reminder_seconds": 300
}
```
Owner PUT to the same endpoint:
```json
{
  "self_qr_credit_mode": "owner_approval",
  "credit_limit_paise": 10000
}
```
HTTP 200 returns the updated policy with `reminder_seconds:300`. `credit_limit_paise:null` means unlimited; 0 disables additional Self QR credit. The default when no policy row exists is automatic mode, unlimited credit, 300-second reminder. Configure each cafe intentionally before rollout. Changes govern subsequent grants; they do not cancel previously authorized segments. `reminder_seconds` is currently server-fixed, not an editable field.

## 10. Dashboard requests, approval and conflict resolution

GET `/api/cafe/41/extensions` with staff JWT returns enriched snapshots and unread notices. Example (items abridged to show added fields):
```json
{
  "items": [
    {
      "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
      "revision": 4,
      "state": "approval_pending",
      "gamer_name": "Test Gamer",
      "console_name": "PC 3",
      "request_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
      "extension": {
        "mode": "owner_approval",
        "rolling_enabled": true,
        "reason_code": "approval_pending",
        "request_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
        "status": "approval_pending",
        "requested_price_paise": 2500
      },
      "billing": {
        "currency": "INR",
        "total_paise": 0,
        "wallet_funded_paise": 0,
        "collected_paise": 0,
        "waived_paise": 0,
        "credit_due_paise": 0,
        "amount_due_paise": 0,
        "net_cafe_balance_paise": 500,
        "as_of": "2026-10-08T12:55:00Z",
        "is_final": false
      }
    }
  ],
  "notices": [
    {
      "id": "776ed0bf-efca-45f2-b495-5ee3c43d9e78",
      "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
      "kind": "approval_required",
      "details": {
        "request_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
        "amount": 2500
      },
      "created_at": "2026-10-08T12:55:00Z"
    }
  ]
}
```
Actual items include all snapshot fields. Top-level `request_id` in this staff list is populated for approval/conflict requests; `extension.request_id` can additionally refer to consent/credit-limit pending quotes. The list is capped at 100 each and has no pagination cursor. Fetch an individual summary with GET `/api/cafe/41/extensions/{runtime_id}` before a decision or collection.

Owner approve:
```http
POST /api/cafe/41/extensions/7a3df154-33ea-4eae-a9e0-9c56c075bc23/decision
Authorization: Bearer <OWNER_STAFF_ACCESS_JWT>
Content-Type: application/json
```
```json
{
  "request_id": "11d3d198-4261-44c4-a7f3-9c1483c15a23",
  "decision": "approve",
  "revision": 4,
  "idempotency_key": "18ea952c-f1d7-405c-a523-d2a94ea68a19"
}
```
HTTP 200 returns a bare snapshot. If granted, `state` becomes active, its reservation advances, and the pending request clears. The returned state is authoritative: wallet changes may leave only a funded prefix authorized. There is no separate `approved` socket event.

To reject, send `decision:"reject"` with current revision and a new key. Rejection disables rolling; existing authorized time remains. It does not retroactively cancel funded/approved play.

For a conflicting booking, resolve it in the existing scheduling system, then POST the same decision endpoint with `decision:"retry"`, its conflict `request_id`, current revision and a new key. A staff member needs booking-management permission. Retry does not bypass owner approval if the rechecked grant requires credit. Never cancel someone else's booking automatically from the kiosk.

Mark a notice read:
```http
POST /api/cafe/41/extension-notices/776ed0bf-efca-45f2-b495-5ee3c43d9e78/read
Authorization: Bearer <STAFF_ACCESS_JWT>
Content-Type: application/json

{}
```
HTTP 200:
```json
{
  "success": true
}
```

## 11. Final settlement

Dashboard can POST `/api/cafe/41/extensions/{runtime_id}/end` using the same Stop body (runtime ID is in the path; body can contain revision/mode/key) to finalize play. GET the summary after ending. Do not present cached zero/old debt as a ready-to-pay total.

After receiving actual ₹5 payment:
```http
POST /api/cafe/41/extensions/7a3df154-33ea-4eae-a9e0-9c56c075bc23/settle
Authorization: Bearer <STAFF_ACCESS_JWT>
Content-Type: application/json
```
```json
{
  "amount_paise": 500,
  "method": "cash",
  "revision": 4,
  "idempotency_key": "8dfb8c54-7c43-4bc8-85e3-5a648445ee84"
}
```
Example HTTP 200 response:
```json
{
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
  "session_ref": {
    "kind": "self_qr",
    "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
  },
  "console_id": 269,
  "vendor_id": 41,
  "revision": 5,
  "event_sequence": 23,
  "state": "settled",
  "server_time": "2026-10-08T13:12:00Z",
  "started_at": "2026-10-08T12:00:00Z",
  "paid_until": "2026-10-08T13:00:00Z",
  "reserved_until": "2026-10-08T13:30:00Z",
  "stop_at": "2026-10-08T13:10:00Z",
  "auto_lock_at_end": false,
  "play_allowed": false,
  "last_seen_at": "2026-10-08T13:09:55Z",
  "ended_at": "2026-10-08T13:10:00Z",
  "extension": {
    "mode": "automatic",
    "rolling_enabled": false,
    "reason_code": null,
    "request_id": null,
    "status": "settled",
    "requested_price_paise": null
  },
  "billing": {
    "currency": "INR",
    "total_paise": 1000,
    "wallet_funded_paise": 500,
    "collected_paise": 500,
    "waived_paise": 0,
    "credit_due_paise": 0,
    "amount_due_paise": 0,
    "net_cafe_balance_paise": 0,
    "as_of": "2026-10-08T13:10:00Z",
    "is_final": true
  }
}
```
Supported methods: `cash`, `card`, `cafe_upi`, `upi`, `waiver`. Cash/card/UPI are records of money already received, not calls to an external payment gateway. Collection requires a named authorized staff session and an open shift. Partial payment is allowed with a positive amount up to outstanding due. If ₹2 of ₹5 is collected, the remaining debt is ₹3 and state stays ended_unsettled; get the new revision before another collection.

A waiver requires `wallet.adjust`, method waiver and a 3–500 character `reason`, for example `"Approved goodwill waiver"`. The initial pay-at-cafe booking toggle does not disable extra-play settlement. Original/food obligations are still separate; “extension settled” is not proof every original charge was paid.

## 12. Socket.IO setup and client emits

JavaScript reference syntax is shown for clarity. Native Windows/Dart clients must use equivalent Socket.IO namespace/auth/event APIs.

### Recommended kiosk connection

```javascript
import { io } from "socket.io-client";
const BASE_URL = "https://hfg-dashboard.onrender.com";
const agent = io(`${BASE_URL}/cafe-agent`, {
  path: "/socket.io",
  auth: { token: PC_LINK_TOKEN },
  transports: ["polling", "websocket"],
  reconnection: true
});
agent.on("connect", () => refreshCurrentSession()); // REST heartbeat/state
agent.on("session.updated", event => applyCommittedSnapshot(event));
agent.on("connect_error", error => showPassiveConnectionStatus(error.message));
// Independently poll GET /api/kiosk/session every 15 seconds.
```

No join emit is required on `/cafe-agent`; server automatically joins the link's room. Do not connect to both kiosk namespaces unless your deduplication supports duplicate delivery.

### Existing default kiosk connection

```javascript
const kiosk = io(BASE_URL, {
  path: "/socket.io",
  auth: { session_token: PC_LINK_TOKEN, console_id: 269 },
  reconnection: true
});
kiosk.on("connect", () => {
  // Optional; connect already joins the authenticated link room.
  kiosk.emit("kiosk_join", { console_id: 269 });
  refreshCurrentSession();
});
kiosk.on("session.updated", applyCommittedSnapshot);
// Existing assignment/unlock events remain part of the existing start flow.
```

`kiosk_id` is accepted as a legacy alias in kiosk_join but is validated as a console ID; use `console_id` explicitly. This event has no contract ACK payload.

### Dashboard connection/emits

```javascript
const dashboard = io(BASE_URL, {auth: {token: STAFF_ACCESS_JWT}});
dashboard.on("connect", () => {
  dashboard.emit("dashboard_join_vendor", {vendor_id: 41});
  refreshExtensionList();
});
dashboard.on("session.updated", event => {
  if (event.vendor_id === 41) refreshExtensionList();
});
// When leaving this cafe:
dashboard.emit("dashboard_leave_vendor", {vendor_id: 41});
```

Join the cafe belonging to the staff token. Changing cafe requires that cafe's valid staff token/connection. Dashboard join/leave do not return a defined ACK payload.

### Gamer connection

```javascript
const gamer = io(`${BASE_URL}/cafe-gamer`, {auth: {token: CAFE_GAMER_JWT}});
gamer.on("connect", () => refreshOwnRuntime());
gamer.on("session.updated", applyCommittedSnapshot);
// GET /api/cafe/extensions/{runtime_id}, Authorization Bearer CAFE_GAMER_JWT
```

Server joins the signed-in user room and disconnects expired gamer connections. No client room/user ID emit is supported.

### Public availability connection/emits

```javascript
const availability = io(`${BASE_URL}/cafe-availability`);
availability.on("connect", () => {
  availability.emit("watch", {vendor_id: 41}, ack => {
    if (ack?.ok) refreshAuthoritativeAvailability();
  });
});
availability.on("slots.updated", event => {
  if (event.vendor_id === 41) refreshAuthoritativeAvailability();
});
```

`watch` ACK: `{"ok":true}` for an existing positive integer vendor ID, `{"ok":false}` for an invalid/nonexistent one. Re-watch after reconnect. This namespace exposes only invalidations; keep existing app booking-availability APIs. There is no defined unwatch event; reconnect/destroy the watcher when changing its lifecycle. Purchase always rechecks database capacity even if the visible slot list is stale.

## 13. Exact server event payloads

### Kiosk and private gamer: `session.updated`

Emitted after committed state/financial changes to linked-PC rooms on `/` and `/cafe-agent`, and the gamer's room on `/cafe-gamer`. Example:
```json
{
  "event_id": "ebfe046c-3a9c-4b96-b227-4d1f1ff5c9ab",
  "session_ref": {
    "kind": "self_qr",
    "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
  },
  "revision": 3,
  "server_time": "2026-10-08T12:55:01Z",
  "event_sequence": 2,
  "snapshot": {
    "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23",
    "session_ref": {
      "kind": "self_qr",
      "id": "84243dc8-ab91-4359-a985-2f9210b2c473"
    },
    "console_id": 269,
    "vendor_id": 41,
    "revision": 3,
    "event_sequence": 2,
    "state": "active",
    "server_time": "2026-10-08T12:55:00Z",
    "started_at": "2026-10-08T12:00:00Z",
    "paid_until": "2026-10-08T13:00:00Z",
    "reserved_until": "2026-10-08T13:30:00Z",
    "stop_at": null,
    "auto_lock_at_end": false,
    "play_allowed": true,
    "last_seen_at": "2026-10-08T12:55:00Z",
    "ended_at": null,
    "extension": {
      "mode": "automatic",
      "rolling_enabled": true,
      "reason_code": null,
      "request_id": null,
      "status": "active",
      "requested_price_paise": null
    },
    "billing": {
      "currency": "INR",
      "total_paise": 0,
      "wallet_funded_paise": 0,
      "collected_paise": 0,
      "waived_paise": 0,
      "credit_due_paise": 0,
      "amount_due_paise": 0,
      "net_cafe_balance_paise": 500,
      "as_of": "2026-10-08T12:55:00Z",
      "is_final": false
    },
    "availability_changed": true
  }
}
```

`snapshot.availability_changed` is an additional event-snapshot field used for publication. REST snapshots do not include it. Permit additional fields for forward compatibility. Envelope server_time is dispatch time; snapshot.server_time is snapshot creation time, and billing.as_of is actual accrual time. Outbox delivery can be delayed.

### Dashboard: `session.updated`

Default namespace, selected vendor room, thin invalidation:
```json
{
  "event_id": "ebfe046c-3a9c-4b96-b227-4d1f1ff5c9ab",
  "revision": 3,
  "event_sequence": 2,
  "server_time": "2026-10-08T12:55:01Z",
  "vendor_id": 41,
  "console_id": 269,
  "runtime_id": "7a3df154-33ea-4eae-a9e0-9c56c075bc23"
}
```
It has no snapshot/financial payload. Refetch permission-protected summaries/notices, coalescing bursts of events. The same event name has different payload shapes depending on the recipient/namespace; do not use the kiosk parser for dashboard invalidations.

### Public app: `slots.updated`

Namespace `/cafe-availability`, only when extension reservation/release changes capacity:
```json
{
  "vendor_id": 41,
  "event_id": "ebfe046c-3a9c-4b96-b227-4d1f1ff5c9ab",
  "server_time": "2026-10-08T12:55:01Z"
}
```
No gamer/session/payment information is included. Existing booking events continue separately; this public event covers extension changes, not every legacy booking mutation.

### Existing dashboard invalidations retained

Default vendor room:
- `booking_slots_updated`: `{"vendor_id":41,"console_id":269}`
- `console_availability`: `{"vendor_id":41,"console_id":269,"is_available":false}` on occupied reservation; true on finish
- `cafe_session_updated`: existing legacy Self QR snapshot; do not use it instead of modern `session.updated` for metered extensions

No `continue`, `approve`, `wallet_exhausted` or `stop` socket emit endpoint is implemented. Notices are records returned by GET extensions; their creation produces session.updated invalidations. No separate native-popup command or email delivery guarantee is included.

## 14. Event ordering, reconnect and retries

1. Keep the active runtime ID and latest event_sequence. When source/PC assignment changes, fetch HTTP state before replacing active identity.
2. Deduplicate event_id and ignore an older/equal sequence for that runtime. Revision alone is insufficient because billing can change without authorization revision changing.
3. Apply HTTP snapshots through the same ordering rules. An older socket packet after a newer HTTP response must not revert end time, unlock a completed session or reduce the displayed debt.
4. On reconnect, refresh state before acting on queued packets. Outbox is at-least-once; replay of missed events is not guaranteed to reconnecting clients.
5. Retry uncertain POSTs using the same idempotency_key **and identical semantic payload**. Persist outstanding action keys until the result is known. Never reuse a key for a different request; never switch keys just because a timeout occurred.
6. On stale revision, expired quote or changed price: get current state/quote and ask for any changed consent before a new action/key. Immediate Stop can tolerate stale revision, but cannot target a prior gamer once a new runtime occupies the link.
7. Do not repeatedly beep or display a popup per five-second billing event. Throttle rendering and group dashboard refreshes, without discarding final Stop or permission changes.

A snapshot before a deadline is not permission to exceed it while offline. At the minimum of reserved_until/stop_at, fetch current state and honor only authorized play. Do not lock at paid_until if reserved_until extends it. Implement this separately from any legacy kiosk countdown auto-lock rule.

## 15. Errors and recovery

Typical business error body:
```json
{
  "error": "Quote expired"
}
```
| HTTP | Example message | Required action |
| --- | --- | --- |
| 400 | Supply a JSON object / Invalid integer amount, duration or identifier | Fix request shape/types; paise is integer, consent is boolean |
| 401 | PC authentication required / PC authentication failed | Relink/refresh valid link; do not retry with owner secrets |
| 403 | Only owner can authorize credit / Permission denied | Correct named staff role/permission |
| 404 | Session not found / Request not found | Refresh identity; check ownership |
| 409 | Quote expired / Stale session revision | Fetch state and fresh quote |
| 409 | Price changed; accept a fresh quote | Show fresh price and obtain acceptance |
| 409 | Credit consent required / Cafe credit limit reached | Consent/top-up/policy resolution; no authorized grace time |
| 409 | Kiosk is offline; reconnect before extending | Resume valid heartbeat and fresh state |
| 409 | Authorization boundary passed | Do not revive retrospectively; staff handles ended debt/new booking |
| 409 | Open your shift before collecting payment | Staff opens shift, fetches final summary and retries appropriately |
| 409 | Collection exceeds remaining due | Fetch latest remaining debt |
| 409 | Idempotency conflict | Investigate changed payload/key reuse |
| 503 | Session extension migration is required | Deploy/apply migration; do not silently pretend modern continuation works |

Integrity conflicts can return `{"error":"Conflicting mutation; retry with the same idempotency key."}`. JWT/framework failures can use their existing error shape (such as msg); generic failures must not be interpreted as payment success. Physical conflicts often appear as a 202 conflict_pending snapshot rather than an HTTP error.

## 16. Smooth gamer interaction

At approximately five minutes remaining show one small passive cue: “Continue playing? Next interval ₹X.” Continue opens a user-invoked tray/overlay with server quote, wallet contribution and unpaid credit terms. For rolling play show a persistent unobtrusive status rather than prompting every billing tick. A changed price/credit consent may require another explicit acceptance. Warn staff early for approval/conflict so they can act before the reservation boundary.

Do not steal focus, minimize fullscreen games, intercept gameplay keys or use a modal every minute. Stop and settlement controls must be intentional. Display pending/offline status passively; do not report Continue successful until a returned snapshot authorizes its time. The backend does not implement the native overlay or know whether gameplay is at a crucial moment.

## 17. Scenario acceptance checklist

| Scenario | Verify |
| --- | --- |
| Normal dashboard/app booking | Same started_at, new reservation, invoice due; no wallet debit |
| Self QR sufficient funds | Funds held, only played time captured, unused remainder released |
| Automatic credit + consent | Same session continues; negative cafe net balance and staff notice |
| Owner approval + ₹5 wallet | Funded prefix granted, pending ₹25 request, approval before its boundary |
| Owner rejects | Rolling disabled, previously granted time retained, no unapproved slot occupation |
| Next slot booked | conflict_pending; owner approval cannot override; Retry only after staff resolution |
| Credit limit 0 | No credit authorization; usable wallet prefix only |
| Wallet top-up during credit play | Existing credit paid first, remaining funds pay future play; no duplicate captures |
| Partial/final collection | Server final amount only; payment recorded once; second collection uses new revision |
| Socket disconnect/reboot | GET recovery; no unlock from old runtime event; heartbeat resumes |
| No heartbeat >60 seconds | No additional automatic grant; existing authorized window retained |
| Price changes | Fresh quote and consent; no silent new rate |
| Midnight/squad/cancellation | UTC timeline, per-console guards, no duplicate capacity release |
| Lost POST response / duplicate event | Same mutation key, dedupe event_id/sequence, no double charge |
| Permission/token failure | Wrong PC/user/vendor blocked; no public financial data |

Use a dedicated cafe/test gamer, never the personal documents or real payment details in screenshots.

## 18. Deployment prerequisites and current limits

Apply `hfg-dashboard-service/sql/20261007_kiosk_extensions.sql` after existing cafe-wallet/kiosk migrations. Deploy matching booking/background slot helpers and duplicate legacy-overtime protection, then dashboard service/frontend. Use shared Redis message queue (`SOCKETIO_MESSAGE_QUEUE_URL` or `REDIS_URL`) for multiple socket workers. Reconciliation is enabled by default and runs every five seconds; keep it enabled for running enrolled sessions.

The current protocol is opt-in via enrollment; old clients are not silently migrated. The native Continue/Stop UI and mobile listeners are integration work for their teams. Emails are not guaranteed by this extension contract. Extension billing is separate from original booking/food obligations. Public invalidation is for extension capacity changes. Quotes are short-lived; final money is fetched, never inferred from cached UI.

Local backend/transaction and existing kiosk tests passed in the implementation handoff. These examples are schema-checked documentation, not a production traffic capture or proof of real-device end-to-end acceptance. Confirm deployment and run the scenarios above on an actual linked kiosk before enabling cafes.

## 19. Postman collection

Import `kiosk-session-extensions-v1.postman_collection.json` from the accompanying handoff. Set base_url, tokens, source IDs, and a unique UUID for each intended mutation. Quote tests populate runtime_id, quote_id and revision; mutation tests refresh revision/request_id. For GET summaries, copy the latest revision manually before a guarded action. Amount/revision variables are numeric JSON. Quotes expire after 30 seconds.

**Do not run the entire collection as a batch.** Approve/Retry/Reject and Stop modes are alternative scenarios. Settlement records payment already received; use a dedicated test cafe. Keep the same action key for retries and replace it only for a new intended action. No credentials are included in the collection.
