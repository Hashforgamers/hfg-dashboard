# Cafe wallets: read-only mobile app APIs

Implemented 2026-09-29 in the dashboard service. Deployment has not been verified.

Cafe wallets are separate from the global Hash Wallet. Each balance belongs to one gamer at one cafe (`vendor_id`). Money can only be added at the cafe by authorized staff through the dashboard. The app displays balances and history; do not show an online top-up action.

## Authentication and hosts

Use the environment's booking API origin as `BOOKING_BASE` and dashboard API origin as `DASHBOARD_BASE` (not the dashboard website URL). Obtain these from the deployment's `NEXT_PUBLIC_BOOKING_URL` and `NEXT_PUBLIC_DASHBOARD_URL` configuration.

First exchange the existing signed-in Hash app JWT:

```http
POST {BOOKING_BASE}/api/cafe-checkout/token
Authorization: Bearer <existing_hash_app_token>
```

No request body is required. Response:

```json
{ "token": "<cafe_gamer_token>", "expires_in": 1800 }
```

Use `Authorization: Bearer <cafe_gamer_token>` on all three GET endpoints below. The token lasts 30 minutes; exchange again after expiry. No QR scan is required. User identity comes from the verified token, never a user_id supplied by the app. Staff and kiosk credentials are not app credentials.

All money fields are integer INR paise: `10000 = ₹100`. All successful reads return `Cache-Control: private, no-store`. The reads never create wallets, write ledger entries, or change funds.

## 1. List my cafe wallets

```http
GET {DASHBOARD_BASE}/api/cafe/wallets?limit=20
Authorization: Bearer <cafe_gamer_token>
```

```json
{
  "items": [
    {
      "vendor_id": 12,
      "cafe_name": "Example Gaming Cafe",
      "currency": "INR",
      "balance": 50000,
      "reserved": 10000,
      "available_balance": 40000,
      "topup_at_cafe_only": true
    }
  ],
  "next_cursor": 12
}
```

Lists only this gamer's existing wallet records, including zero balances. A record can also have been created by prior cafe checkout/food activity; inclusion does not imply a previous top-up. Cafes without a wallet record are not listed. Sorted by ascending vendor_id.

- `limit`: optional, default 20, maximum 100, minimum 1.
- Next page: `GET /api/cafe/wallets?limit=20&after=12`.
- `after`: positive integer vendor ID; use the previous `next_cursor`.
- `next_cursor: null` means there are no more results.
- No wallets: `{ "items": [], "next_cursor": null }`.

## 2. Balance at a specific cafe

```http
GET {DASHBOARD_BASE}/api/cafe/12/wallet
Authorization: Bearer <cafe_gamer_token>
```

```json
{
  "vendor_id": 12,
  "cafe_name": "Example Gaming Cafe",
  "currency": "INR",
  "balance": 50000,
  "reserved": 10000,
  "available_balance": 40000,
  "topup_at_cafe_only": true
}
```

Display **Available balance ₹400** and, when nonzero, **Pending reservation ₹100**. `available_balance = balance - reserved`. A reservation is not yet a completed charge.

A valid cafe without a wallet returns zero for all three balance fields without inserting a wallet. An unknown cafe returns 404. Reads remain available when cafe self-service is disabled so historical funds remain visible.

## 3. Cafe wallet transaction history

```http
GET {DASHBOARD_BASE}/api/cafe/12/wallet/history?limit=20
Authorization: Bearer <cafe_gamer_token>
```

```json
{
  "vendor_id": 12,
  "currency": "INR",
  "items": [
    {
      "id": 105,
      "kind": "capture",
      "amount": -10000,
      "balance_after": 40000,
      "reserved_after": 0,
      "method": null,
      "session_id": "example-play-session-uuid",
      "reversal_of": null,
      "created_at": "2026-09-29T10:00:00Z"
    },
    {
      "id": 104,
      "kind": "topup",
      "amount": 50000,
      "balance_after": 50000,
      "reserved_after": 0,
      "method": "cash",
      "session_id": null,
      "reversal_of": null,
      "created_at": "2026-09-29T09:30:00Z"
    }
  ],
  "next_cursor": 104
}
```

Examples illustrate response shapes; IDs and values are placeholders. Responses are newest ledger ID first, scoped to both the selected cafe and authenticated gamer.

- `limit`: optional, default 20, range 1–100.
- Next page: `GET /api/cafe/12/wallet/history?limit=20&before=104`.
- `before`: positive integer ledger ID; results have IDs strictly below it.
- `next_cursor` is the last returned ID only when more rows exist; otherwise null.
- No history: `{ "vendor_id": 12, "currency": "INR", "items": [], "next_cursor": null }`.
- `created_at` is UTC ISO 8601; format it in the user's display timezone.
- Staff identity, internal notes, fingerprints and idempotency keys are intentionally omitted.
- Food collection records are excluded because they do not affect the gaming wallet.

| kind | Suggested app label | Interpretation |
|---|---|---|
| topup | Added at cafe | Positive credit; method is cash or cafe_upi |
| capture | Gaming charge | Negative debit after PC startup acknowledgement |
| refund | Transaction reversed | Signed amount; positive restores a gaming charge, negative reverses a desk top-up; reversal_of identifies original entry |
| adjustment | Cafe balance adjustment | Positive or negative staff correction |
| reserve | Session funds reserved | amount is zero; reserved_after shows held funds; do not display as money spent |
| release | Session reservation released | amount is zero; funds were released, not refunded after a charge |

Use amount's sign to display credit/debit, not the kind alone. The running balances are snapshots after each event; the current balance comes from endpoint 2. A paginated history is not an atomic snapshot with a separate balance request; refresh both after a new transaction.

## App screen flow

1. Keep the global Hash Wallet screen/API separate. Add a Cafe Wallets section.
2. Exchange the current app token and load `/api/cafe/wallets`.
3. Selecting a cafe loads its `/wallet` and `/wallet/history` in parallel.
4. Display available and reserved funds, history and “Top up at this cafe's reception.”
5. Use cursor pagination for more history. Refresh balance and the first history page on screen resume/pull-to-refresh, after a desk top-up or when returning from gaming checkout.
6. A cafe detail page can call `/api/cafe/{vendor_id}/wallet` directly even when the wallet list is empty.

No app-side POST/top-up API is part of this feature. Do not call staff `/wallets/{user_id}` or `/topups` routes from the app.

## Errors

| Status | Meaning | Action |
|---|---|---|
| 400 | Invalid limit/cursor | Send positive integers; limit cannot exceed 100 |
| 401 | Missing, invalid, expired or wrong-scope/audience token | Exchange a valid app token again; sign in if necessary |
| 404 | Unknown cafe | Remove/reload stale cafe selection |

Cafe errors use `{ "error": "message" }`. Token exchange can return `{ "message": "..." }` from existing app authentication. The new GET endpoints do not require a request body, QR, user ID, staff PIN or device token.

## Backend release

These routes reuse existing cafe wallet/ledger tables and cafe gamer authentication; this change needs no new migration. Existing cafe-wallet migrations must already be applied. Deploy the updated dashboard service; the booking service's token exchange must be deployed with matching JWT signing configuration. These APIs do not change global Hash Wallet or staff top-up behavior.
