# Graph Report - hfg-dashboard-service  (2026-09-28)

## Corpus Check
- 150 files · ~71,552 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1171 nodes · 3092 edges · 66 communities (56 shown, 10 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 91 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b2a56699`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- access_controller.py
- extensions.py
- pricingController.py
- tournament_engine_service.py
- app/routes.py
- test_subscription_checkout.py
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- models/routes.py
- subscription_controller.py
- cafe_wallet_controller.py
- passModels.py
- review_controller.py
- command
- vendor_games.py
- _invalidate_vendor_caches
- package_controller.py
- GameService
- link_service.py
- console_service.py
- commands.py
- booking_bridge.py
- test_cafe_wallet.py
- CloudinaryGameImageService
- datetime
- BridgeTests
- Kiosk backend contract — 22 September 2026
- ConsoleService
- get_vendor_notification_preferences
- 20260922_cafe_wallet.sql
- AvailableGame
- add_or_update_bank_details
- tournament_matches
- is_subscription_active
- get_vendor_dashboard
- get_landing_page_vendor
- get_vendor_passes
- get_all_games
- Cafe wallet and QR checkout
- vendorTaxProfile.py
- vendor_console_overrides
- transaction.py
- vendorDaySlotConfig.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- cafePass.py
- 20260923_unified_kiosk_qr.sql
- cafe_play_sessions

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 42 edges
2. `Vendor` - 32 edges
3. `ConsoleService` - 26 edges
4. `staff_actor()` - 25 edges
5. `_invalidate_vendor_caches()` - 22 edges
6. `KioskError` - 22 edges
7. `KioskTests` - 22 edges
8. `audit()` - 19 edges
9. `normalize_console_slug()` - 19 edges
10. `serialize()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `test_postgres_concurrent_checkout_and_legacy_guards()` --indirect_call--> `checkout()`  [INFERRED]
  tests/test_cafe_wallet.py → app/controllers/cafe_wallet_controller.py
- `env()` --calls--> `Console`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console.py
- `env()` --calls--> `ConsoleLinkSession`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console_link_session.py
- `env()` --calls--> `Vendor`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/vendor.py
- `env()` --calls--> `ExtraServiceCategory`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/extraServiceCategory.py

## Import Cycles
- None detected.

## Communities (66 total, 10 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (58): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+50 more)

### Community 1 - "access_controller.py"
Cohesion: 0.13
Nodes (37): _auth_debug(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session(), list_staff(), delete (+29 more)

### Community 2 - "extensions.py"
Cohesion: 0.08
Nodes (16): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted, OpeningDay (+8 more)

### Community 3 - "pricingController.py"
Cohesion: 0.06
Nodes (53): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+45 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.06
Nodes (53): add_console(), add_extra_service_category(), check_db_connection(), create_category(), create_menu_item(), create_or_update_console_type_override(), create_payout(), deactivate_console_type_override() (+45 more)

### Community 6 - "test_subscription_checkout.py"
Cohesion: 0.05
Nodes (37): Amenity, BookingExtraService, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, Image, add_extra_service_menu(), CloudinaryMenuImageService (+29 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.07
Nodes (69): Config, ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products…, install_kiosk_errors() (+61 more)

### Community 8 - "KioskTests"
Cohesion: 0.08
Nodes (7): _vendor_slot_availability(), date, skipUnless, KioskTests, Run with KIOSK_TEST_DATABASE_URL pointing to a disposable PostgreSQL DB. Loads…, ManualSessionEndTests, Scheduled end and midnight must not manufacture a completed session.

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.12
Nodes (16): PaymentMethod, PaymentVendorMap, _build_payment_method_response(), delete_vendor_pass(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical() (+8 more)

### Community 10 - "models/routes.py"
Cohesion: 0.24
Nodes (14): add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor(), get_consoles(), get_device_for_console_type(), get_landing_page_vendor(), get_transaction_report() (+6 more)

### Community 11 - "subscription_controller.py"
Cohesion: 0.08
Nodes (43): change(), check_payment_status(), check_subscription_status(), create_payment_order(), debug_force_expire(), get_limit(), get_subscription_history(), get_subscription_invoice() (+35 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.09
Nodes (82): adjust_wallet(), agent_ack(), agent_link(), agent_qr(), agent_session(), audit_history(), cafe_error(), checkout() (+74 more)

### Community 13 - "passModels.py"
Cohesion: 0.11
Nodes (9): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass(), create_vendor_pass() (+1 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "command"
Cohesion: 0.14
Nodes (26): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+18 more)

### Community 16 - "vendor_games.py"
Cohesion: 0.18
Nodes (18): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games() (+10 more)

### Community 17 - "_invalidate_vendor_caches"
Cohesion: 0.16
Nodes (17): assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), get_device_for_console_type(), _invalidate_vendor_caches(), kiosk_start_session(), Start a session from kiosk using either booking_id (scan) or access_code.…, Rules: - Current IST time may be up to five minutes before scheduled start. -… (+9 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "GameService"
Cohesion: 0.12
Nodes (15): create_game(), route, Create a new game with optional image, update_game(), upload_game_image(), Game, Create Game from RAWG API - image_url gets background_image automatically!, GameService (+7 more)

### Community 20 - "link_service.py"
Cohesion: 0.25
Nodes (15): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+7 more)

### Community 21 - "console_service.py"
Cohesion: 0.15
Nodes (7): AdditionalDetails, Booking, BookingSquadMember, HardwareSpecification, MaintenanceStatus, PriceAndCost, Slot

### Community 22 - "commands.py"
Cohesion: 0.16
Nodes (17): Package, Subscription, SubscriptionStatus, create_package(), change_subscription(), create_subscription(), expire_subscriptions(), get_active_subscription() (+9 more)

### Community 23 - "booking_bridge.py"
Cohesion: 0.13
Nodes (20): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+12 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.14
Nodes (31): ContactInfo, auth(), fund(), gamer(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), staff_token() (+23 more)

### Community 25 - "CloudinaryGameImageService"
Cohesion: 0.22
Nodes (7): add_images_to_games(), CloudinaryGameImageService, Delete game cover image from Cloudinary, Service for handling game cover images Images are uploaded to the 'GAME_COVERS'…, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload game cover image to Cloudinary

### Community 26 - "datetime"
Cohesion: 0.07
Nodes (15): PassRedemptionLog, PayAtCafeNotification, Generate unique pass UID for hour-based passes, UserPass, CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in… (+7 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "ConsoleService"
Cohesion: 0.18
Nodes (5): Console, ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 30 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "AvailableGame"
Cohesion: 0.20
Nodes (5): AvailableGame, Serialize VendorGame — price is always dynamically computed, Dynamically compute price from parent AvailableGame. - If an active…, Returns full pricing context: base price, offer price, offer details. Useful…, VendorGame

### Community 33 - "add_or_update_bank_details"
Cohesion: 0.25
Nodes (9): add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number(), _mask_upi_id(), Get vendor's bank transfer details, Get historized changes for vendor bank/UPI details. (+1 more)

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "is_subscription_active"
Cohesion: 0.24
Nodes (9): get_subscription(), Get current subscription status for vendor, check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), _as_utc(), is_subscription_active() (+1 more)

### Community 36 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 37 - "get_landing_page_vendor"
Cohesion: 0.29
Nodes (7): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, A clock boundary never completes a started session.

### Community 38 - "get_vendor_passes"
Cohesion: 0.33
Nodes (6): get_vendor_passes(), get_vendor_passes_by_mode(), _parse_bool_flag(), Get vendor passes grouped for frontend (hour/date based)., Backward-compatible alias of /vendor/<vendor_id>/passes., _vendor_exists()

### Community 39 - "get_all_games"
Cohesion: 0.50
Nodes (3): get_all_games(), Get all games ordered by name, Search games by name (case-insensitive, partial match)

### Community 40 - "Cafe wallet and QR checkout"
Cohesion: 0.25
Nodes (7): Audit and reconciliation, Cafe wallet and QR checkout, Deployment order, Gamer and staff APIs, One QR for existing bookings and wallet play, PC agent integration — required before real PC rollout, Verification

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

## Knowledge Gaps
- **19 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `extensions.py` to `AvailableGame`, `access_controller.py`, `pricingController.py`, `app/routes.py`, `test_subscription_checkout.py`, `websocket_service.py`, `models/routes.py`, `cafe_wallet_controller.py`, `link_service.py`, `commands.py`, `test_cafe_wallet.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `CloudinaryGameImageService` connect `CloudinaryGameImageService` to `GameService`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_collections_date_boundaries_and_activity_scope()`) actually correct?**
  _`datetime` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeLedger`) actually correct?**
  _`CafeError` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Vendor` (e.g. with `Amenity` and `AvailableGame`) actually correct?**
  _`Vendor` has 18 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._