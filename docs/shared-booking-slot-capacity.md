# Shared capacity for app, dashboard, kiosk and QR bookings

All booking sources consume the same dated `VENDOR_<id>_SLOT` capacity. Slot templates describe timing; dated rows describe the inventory that can be sold. Reservations require a positive capacity and an available row, and the decrement is conditional and atomic.

- App checkout reserves dated capacity while payment verification or desk acceptance is pending. Confirmation and QR start of that paid booking reuse the reservation.
- Dashboard creation reserves capacity in the same transaction as payment and dashboard rows. Each selected slot uses a savepoint so a failed slot cannot roll back other accepted slots or leave orphan capacity.
- Direct dashboard booking uses the same conditional decrement, scopes selected timings to the vendor/game, and commits booking, payment and assignment together.
- QR wallet checkout creates `cafe_slot_reservations` for every dated interval it touches, including the 45-second PC acknowledgement window and midnight crossings. Its idempotency key returns the original reservation. A failed/expired start or completed session releases these claims once.
- Overtime charges reuse the booking for its actual reserved date. If the legacy overtime path creates a new booking, it reserves dated capacity and saves payment/dashboard rows together. Adding a charge to an existing booking does not reserve another unit.
- Kiosk continuations already lock and decrement the same dated rows. Database guards prevent negative capacity and overlapping assignments on a physical console.
- Slot edits move only that booking's original reserved units, preserving the booked date in transactions and booking metadata. The legacy editor now follows this path and accepts one booking slot per edit.
- Pending-payment workers lock the booking before releasing its persisted units/date. Capacity reconciliation counts pending, confirmed and checked-in bookings, squad units and unreleased QR claims. It locks inventory before taking its booking/claim snapshot.

QR start, acknowledgement and expiry publish `booking_slots_updated` and `console_availability` after commit. The dashboard's existing data bus refreshes its slot inventory from these events.

## Rollout

1. Apply `sql/20261002_shared_slot_reservations.sql` to the shared PostgreSQL database after the cafe-wallet and unified-QR migrations. It installs console/capacity guards for existing vendors and backfills remaining holds for live wallet sessions. A capacity conflict aborts the migration atomically; inspect and reconcile existing allocations before retrying. Rerunning the migration does not decrement a previously seeded claim again.
2. Deploy the dashboard service, booking service, onboarding service, and background processor together. The shared `slot_capacity.py` copies must remain identical. The onboarding service installs the guards when creating future vendor tables. A new dashboard worker also recovers a backfilled session that old code completed between migration and deployment.
3. For vendor 41 / console 269, reload QR checkout and verify a valid 60-minute price, then exercise an app booking and a desk booking in the same date range. All sources must see the same remaining dated capacity. A missing price remains unavailable; clients must never convert it to a purchasable zero.

No production database changes or deployment were performed during this implementation.

## Verification

Cross-flow integration tests use isolated PostgreSQL schemas and the production app/desk booking method, QR reservation code, assignment guards, slot-move code, reconciliation method and background release worker. They verify last-unit contention, rollback after a failed desk payment, duplicate QR requests/acknowledgements, overnight holds, live-session migration, exact release of squad capacity, and competing assignments of one PC.

Run from `hfg-dashboard-service` with a disposable database:

```sh
CAFE_TEST_DATABASE_URL=postgresql+psycopg2://... python -m pytest -q tests/test_shared_slot_capacity.py tests/test_console_pricing.py tests/test_cafe_wallet.py
```
