# Cafe display names

Account Settings → Business Details → Display name controls public cafe branding.
The registered business name remains in `vendors.cafe_name`; optional branding is
stored separately in `vendors.display_name` (maximum 120 characters). Whitespace
is normalized. Empty or null `displayName` restores the business-name fallback.
The existing `account.manage` permission protects the business-details PATCH.

`PATCH /api/vendor/{id}/business-details` accepts `displayName` and returns the
normalized `displayName`, unchanged `businessName`, and effective `publicName`.
Dashboard reads return `businessDetails.displayName` and `cafeProfile.name`.
The app-facing cafe list/search, booking cafe serializer, cafe wallet/QR context,
and cafe pass names use the effective public name. Legacy `cafe_name` response
keys remain compatible with installed app versions. The Flutter cafe-list
adapter also prefers `display_name` when present, so cards, maps and client-side
search share the same public name.

## Release order

1. Apply `sql/20261031_vendor_display_name.sql` to the shared PostgreSQL database.
   It is idempotent and does not rename existing businesses.
2. Deploy hfg-dashboard-service, hfg-onboard, hfg-booking and hfg-user-onboard.
3. Deploy hash-dashboard and ship the HFG-frontend update.

Already-open app screens need a refresh/refetch. The cafe search cache can keep
an earlier name for its configured TTL (60 seconds by default). Business documents
and financial snapshots continue to use the registered business name.

## Validation

- `python -m pytest tests/test_cafe_display_name.py -q` in hfg-dashboard-service.
- `node --test tests/cafe-display-name.test.cjs` in hash-dashboard.
- `flutter test test/cafe_display_name_test.dart` in HFG-frontend (Flutter SDK required).
