# Subscription packages, purchases and kiosk licences

## Cafe flow

Open Account settings → Subscription Details → **Current plan · Upgrade · Add PCs · Invoices**, or `/subscription`.

1. View the purchased plan, renewal/end date and linked-PC usage.
2. Select a package and billing period; optionally select extra PCs when that package allows them.
3. Review the server-generated **Invoice preview — unpaid**. It shows the exact total and subscription period. This preview is not proof of payment and expires after 15 minutes.
4. Pay with Razorpay (or activate a zero-price plan). The backend verifies captured payment details and grants the saved entitlements and PC capacity.
5. Open the immutable payment invoice from Payments & invoices; use the browser's Print / Save as PDF action.
6. If checkout was interrupted, use Resume payment or Check payment. These reuse the same purchase/order; they do not create another order.

Payments are one-time purchases, not automatic recurring debits. Renewals extend the remaining period rather than throwing away unused days. Mid-period upgrades/additional PCs retain the end date and charge the positive price difference multiplied by remaining time / the original billing-cycle duration, rounded once to paise. Prepaid renewal time is included in the remaining time. Same-cycle upgrades cannot remove purchased features or PC capacity. Downgrades and billing-cycle changes during an active period require Hash support; after expiry a new plan/cycle can be selected.

Base plan prices support monthly, quarterly and yearly amounts. Extra-PC prices are monthly per PC and are multiplied by the number of months in the selected cycle. The configured totals are used directly; this implementation does not infer GST or fabricate a tax breakdown.

## Hash-team controls

In the super-admin website (`vendor-Onboard`), Subscription Models defines:

- Package code/name, active status and included PC/kiosk capacity.
- Monthly/quarterly/yearly prices and monthly extra-PC price (zero disables add-ons).
- Feature descriptions for display and separate switches for actual dashboard access.

Feature switches cover kiosk starts/link capacity, console pricing, cafe-wallet top-ups/new self-service charges, pass management, extras management, reports/statistics, tournaments and staff management. Billing, read-only customer wallet history, existing paid-booking actions, refunds and unlink/stop operations remain accessible through their existing authorization rules. Staff permissions still apply independently; buying a feature does not give every staff member permission to use it.

Purchases retain their limits, prices and feature snapshots after catalog edits. The migration also snapshots existing subscriptions. The super-admin subscription list reads purchased limits, including extra PCs. Catalog changes apply to future quotes; already-created quotes remain valid for their acceptance window.

The admin browser now requires HTTP Basic sign-in over the deployed HTTPS site. Credentials are checked server-side, including inside the proxy. The upstream admin API key stays on the server. This adds access protection to the previously unauthenticated proxy; all environments must configure browser credentials before release.

## Deployment order

1. Back up the database and apply `sql/20261001_subscription_commerce.sql` to the shared PostgreSQL database. It adds `subscriptions.commercial_terms`, snapshots old subscriptions, and creates `subscription_checkouts`. Rerunning preserves existing snapshots.
2. Deploy `hfg-dashboard-service`. Keep `SUBSCRIPTION_DEV_MODE=false` for catalog pricing in production. Configure the server's existing Razorpay key ID/secret and a new `SUBSCRIPTION_WEBHOOK_SECRET`.
3. In Razorpay, configure an HTTPS webhook to `<dashboard-service>/api/subscription-payments/webhook`, using the same webhook secret, for `payment.captured` and `order.paid`. This is required for activation when the browser closes. Test callback signing and provider capture in the target environment.
4. Deploy `hfg-onboard` and `vendor-Onboard`. Configure the same existing `SUPER_ADMIN_API_KEY` in dashboard-service and onboard, with the upstream proxy key in the admin website. Set server-only `SUPER_ADMIN_DASHBOARD_USERNAME` and a unique `SUPER_ADMIN_DASHBOARD_PASSWORD` of at least 16 characters in the admin website. Unconfigured authentication denies access.
5. Deploy `hash-dashboard` together with the new checkout endpoints. Legacy `/create-order` now returns 409 directing clients to the preview flow; old already-issued orders retain the legacy verify endpoint.
6. Sign in as Hash admin, define and save a plan, then test preview → payment → invoice → PC linking with a test cafe and Razorpay test keys before switching live configuration.

No live payment, production migration, webhook registration or deployment was performed by the coding task.

## APIs

All cafe subscription routes require a cafe JWT with `subscription.manage`; status checks accept `dashboard.view`. Cross-cafe access is rejected. Super-admin grants/catalog writes require the server admin credential.

| Method | Path suffix after `/api/vendors/{vendor_id}/subscription` | Purpose |
|---|---|---|
| GET | `/` | Current purchased terms, dates and PC usage |
| GET | `/status` | Active state and feature entitlements |
| POST | `/preview` | `{package_code, billing_cycle, extra_pcs}` → immutable 15-minute quote |
| POST | `/purchases/{quote_id}/pay` | Accept preview; create/reuse provider order or activate free plan |
| POST | `/purchases/{quote_id}/reconcile` | Fetch captured provider payment and atomically activate |
| GET | `/purchases` | Latest 100 pending/paid purchases and invoice references |
| GET | `/purchases/{quote_id}/invoice` | Printable HTML preview before payment, invoice after payment |

Money in these new quote APIs is integer paise (`amount_paise`). Catalog prices remain INR. The quote snapshots plan terms, customer, amount, period and base subscription state. Provider payment IDs/order IDs are unique. Vendor row locks serialize checkout activation and PC linking.

If an administrator independently changes a subscription while payment is in progress, or payment arrives after the purchased period ended, the captured payment is recorded as `paid_unapplied`. The cafe sees a payment receipt and a support message; access is not silently granted against the wrong subscription, and the customer is told not to pay again. Hash must review and resolve/refund such exceptions using the payment reference. Do not reset the row to unpaid or reuse a payment ID.

## Kiosk installer

Manage Consoles includes **Download HashDashPC v1.0.0 (.exe)** and the release folder:

- File: `https://drive.google.com/file/d/107quBG127Sg7lscQEusp_1vFqbvl1-CR/view`
- Folder: `https://drive.google.com/drive/folders/171RmdWLzuBhl0qE5xAhFvmtgyppmN0Cv`

The verified file is `HashDashPC_Setup_v1.0.0.exe` (34,804,132 bytes). The executable was not run or repackaged. Install it on a Windows PC, then use the existing link flow. A new release requires updating the direct link; the folder link remains available.

## Verification

`tests/test_subscription_commerce.py` and `tests/test_subscription_checkout.py` cover real Flask routes/models with mocked payment-provider responses. Set `SUBSCRIPTION_TEST_DATABASE_URL` to an isolated PostgreSQL database to include concurrent webhook/link and migration-rerun checks. Each test creates and removes its own schema. Never point test fixtures at production.

Frontend tests cover preview-before-payment, using the server order amount, invoice access and pending-payment recovery. Admin-auth tests cover missing credentials, malformed headers, invalid credentials and valid server-side sign-in. Production provider/webhook and physical Windows installation still require deployment smoke tests.
