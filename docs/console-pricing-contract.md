# Console and cafe-wallet pricing

Console Pricing owns prices. Cafe Wallet → Payment settings only controls available self-service session lengths and payment methods. It is not a second price list.

## Rules

- Base price is INR **per configured slot**, not per hour. The existing database stores whole rupees (0–10,000); fractional base prices are rejected rather than truncated. Offers and controller rates support two decimals.
- Offers are continuous intervals in Asia/Kolkata time. An offer spanning several dates includes the full intervening days. A scheduled slot receives an offer only if the entire slot fits inside that interval, including overnight slots. Lowest eligible offer wins and never exceeds the current base price. Current-price previews exclude the exact end instant. New overlapping active offers are rejected; adjacent intervals are allowed.
- New cafe-wallet QR sessions derive prices from the linked physical console's configured slots. Partial slots are prorated; the combined amount rounds once to integer paise. For example, two half-hour slots at ₹50 cost ₹100 for 60 minutes. A ₹30 offer covering the first slot reduces that to ₹80.
- A physical console must map to exactly one pricing record. Missing or overlapping slot coverage disables the affected duration with an explanation. Missing mappings block new charges but do not hide the customer's balance or existing booking actions.
- Checkout recomputes the price before reservation. A changed amount returns HTTP 409 and requires a refreshed quote. Successful idempotent retries reuse the reservation. Price edits after reservation do not change the reserved amount or final capture.
- Controller charges are server-calculated using the cheapest combination of base charges and configured bundle tiers. Quantities are bounded to 0–64 and tier quantities to 2–64. Client-provided fares cannot override pricing. Missing controller rules block chargeable controller bookings; they do not make controllers free.
- Squad discounts apply to supported multiplayer groups using slot price × players × (1 − discount/100). Controller-priced consoles use their controller policy. Dashboard preview rounds the whole group total once. Once a group's rules have been customized, missing/deactivated player-count rules mean zero discount, not a resurrected default discount.
- New QR duration sessions start one console for one gamer. For squad/controller bookings, create the configured booking first and use the QR's existing-booking action.
- Pricing writes require an authenticated owner/staff identity for the same cafe with `pricing.manage` permission. Enabled payment methods remain independent of the pricing source.

## Compatibility and deployment

Deploy `hfg-dashboard-service`, `hfg-booking`, and `hash-dashboard` together. Stored wallet policy durations with legacy `amount` fields are accepted, but those amounts are ignored; policy saves retain only `minutes`. No JSON-policy database migration is required. Older clients sending a flat legacy `expected_amount` can receive 409 and must refresh checkout. Clients must handle unavailable durations (`amount: null` with `unavailable_reason`) and top-level `pricing_error`.

Local verification covers pricing API validation/permissions, shared arithmetic, PostgreSQL console-price → quote → reserve → capture, unavailable mappings, controller bundles, squad defaults, and existing payment regressions. This does not confirm a production deployment or physical kiosk execution.
