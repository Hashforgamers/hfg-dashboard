# Graph Report - hfg-dashboard-service  (2026-10-02)

## Corpus Check
- 167 files · ~79,555 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1335 nodes · 3565 edges · 78 communities (69 shown, 9 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 100 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5f6384f7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- Flask
- vendor.py
- pricingController.py
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- models/routes.py
- subscription_controller.py
- cafe_wallet_controller.py
- passModels.py
- review_controller.py
- console_catalog_service.py
- vendor_games.py
- _invalidate_vendor_caches
- package_controller.py
- GameService
- test_subscription_commerce.py
- console_service.py
- Package
- test_subscription_checkout.py
- test_cafe_wallet.py
- CloudinaryGameImageService
- datetime
- BridgeTests
- Kiosk backend contract — 22 September 2026
- ConsoleService
- get_vendor_notification_preferences
- 20260922_cafe_wallet.sql
- VendorGame
- add_or_update_bank_details
- tournament_matches
- is_subscription_active
- get_vendor_dashboard
- get_landing_page_vendor
- get_vendor_passes
- get_all_games
- Cafe wallets: read-only mobile app APIs
- subscription_commerce.py
- vendor_console_overrides
- transaction.py
- vendorDaySlotConfig.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- subscription_service.py
- extensions.py
- CloudinaryProfileImageService
- CafePass
- test_qr_input.py
- BankTransferDetails
- 20260923_unified_kiosk_qr.sql
- cafe_play_sessions
- RAWGSyncService
- change
- Subscription packages, purchases and kiosk licences
- UserPass
- Console and cafe-wallet pricing

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 45 edges
2. `Vendor` - 36 edges
3. `KioskError` - 28 edges
4. `staff_actor()` - 27 edges
5. `ConsoleService` - 26 edges
6. `auth()` - 26 edges
7. `_invalidate_vendor_caches()` - 22 edges
8. `KioskTests` - 22 edges
9. `fund()` - 20 edges
10. `audit()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `test_postgres_concurrent_checkout_and_legacy_guards()` --indirect_call--> `checkout()`  [INFERRED]
  tests/test_cafe_wallet.py → app/controllers/cafe_wallet_controller.py
- `env()` --calls--> `Console`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console.py
- `test_postgres_concurrent_links_cannot_exceed_purchased_limit()` --calls--> `Console`  [INFERRED]
  tests/test_subscription_commerce.py → app/models/console.py
- `env()` --calls--> `ConsoleLinkSession`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console_link_session.py
- `commerce()` --calls--> `Package`  [INFERRED]
  tests/test_subscription_commerce.py → app/models/package.py

## Import Cycles
- None detected.

## Communities (78 total, 9 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (58): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+50 more)

### Community 1 - "Flask"
Cohesion: 0.06
Nodes (75): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+67 more)

### Community 2 - "vendor.py"
Cohesion: 0.13
Nodes (12): BusinessRegistration, ContactInfo, Document, DocumentSubmitted, PhysicalAddress, Timing, Vendor, VendorAccount (+4 more)

### Community 3 - "pricingController.py"
Cohesion: 0.08
Nodes (42): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+34 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "app/routes.py"
Cohesion: 0.06
Nodes (52): VendorTaxProfile, add_console(), add_extra_service_category(), check_db_connection(), create_category(), create_menu_item(), create_payout(), delete_category() (+44 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (24): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_menu(), CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder (+16 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.06
Nodes (79): before_request, require_tournament_plan(), ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products… (+71 more)

### Community 8 - "KioskTests"
Cohesion: 0.06
Nodes (23): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+15 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.18
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "models/routes.py"
Cohesion: 0.18
Nodes (15): OpeningDay, add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor(), get_consoles(), get_device_for_console_type(), get_landing_page_vendor() (+7 more)

### Community 11 - "subscription_controller.py"
Cohesion: 0.10
Nodes (34): check_payment_status(), check_subscription_status(), debug_force_expire(), get_limit(), get_subscription(), get_subscription_history(), get_subscription_invoice(), _invoice_number() (+26 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.08
Nodes (92): adjust_wallet(), agent_ack(), agent_link(), agent_qr(), agent_session(), audit_history(), cafe_error(), checkout() (+84 more)

### Community 13 - "passModels.py"
Cohesion: 0.17
Nodes (5): PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type()

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "console_catalog_service.py"
Cohesion: 0.23
Nodes (19): _resolve_squad_group_for_game_name(), ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_type_overrides(), get_consoles(), ensure_default_console_catalog_seed() (+11 more)

### Community 16 - "vendor_games.py"
Cohesion: 0.20
Nodes (18): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games() (+10 more)

### Community 17 - "_invalidate_vendor_caches"
Cohesion: 0.19
Nodes (15): assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), get_device_for_console_type(), _invalidate_vendor_caches(), kiosk_start_session(), Start a session from kiosk using either booking_id (scan) or access_code.…, Rules: - Current IST time may be up to five minutes before scheduled start. -… (+7 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "GameService"
Cohesion: 0.19
Nodes (9): create_game(), route, Create a new game with optional image, update_game(), Game, GameService, Get all vendor games grouped by game. price_per_hour is dynamically computed…, Get all consoles for a specific platform (PC, PS5, Xbox, VR) (+1 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.13
Nodes (40): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+32 more)

### Community 21 - "console_service.py"
Cohesion: 0.20
Nodes (6): AdditionalDetails, AvailableGame, Booking, BookingSquadMember, HardwareSpecification, Slot

### Community 22 - "Package"
Cohesion: 0.33
Nodes (4): Package, SubscriptionStatus, create_package(), str

### Community 23 - "test_subscription_checkout.py"
Cohesion: 0.14
Nodes (15): BookingExtraService, MaintenanceStatus, PriceAndCost, Image, app(), order(), payment(), fixture (+7 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.05
Nodes (64): _vendor_slot_availability(), date, auth(), fund(), gamer(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, parametrize (+56 more)

### Community 25 - "CloudinaryGameImageService"
Cohesion: 0.18
Nodes (8): add_images_to_games(), CloudinaryGameImageService, Delete game cover image from Cloudinary, Service for handling game cover images Images are uploaded to the 'GAME_COVERS'…, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload game cover image to Cloudinary, Delete Cloudinary image

### Community 26 - "datetime"
Cohesion: 0.16
Nodes (6): PassRedemptionLog, PayAtCafeNotification, _get_next_slot_for_today(), datetime, EarlyStartTests, Check the dashboard's production eligibility rule without booting services.

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "ConsoleService"
Cohesion: 0.20
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 30 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "VendorGame"
Cohesion: 0.12
Nodes (9): ConsolePricingOffer, Time-based promotional pricing for console types (AvailableGames) Allows…, Check if this offer is active RIGHT NOW using IST. Returns True if current IST…, Calculate discount percentage, Convert to dictionary for API responses, Serialize VendorGame — price is always dynamically computed, Dynamically compute price from parent AvailableGame. - If an active…, Returns full pricing context: base price, offer price, offer details. Useful… (+1 more)

### Community 33 - "add_or_update_bank_details"
Cohesion: 0.25
Nodes (9): add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number(), _mask_upi_id(), Get vendor's bank transfer details, Get historized changes for vendor bank/UPI details. (+1 more)

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "is_subscription_active"
Cohesion: 0.38
Nodes (6): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), is_subscription_active(), Check if vendor has an active, non-expired subscription Returns: tuple: (bool:…

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

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_commerce.py"
Cohesion: 0.17
Nodes (17): Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, activate(), billing_datetime(), check_base(), paise(), preview(), public_quote() (+9 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 63 - "subscription_service.py"
Cohesion: 0.26
Nodes (16): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Subscription, change_subscription(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle() (+8 more)

### Community 64 - "extensions.py"
Cohesion: 0.24
Nodes (4): CafePass, PassType, ProvisionalResult, VerificationCheck

### Community 65 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 66 - "CafePass"
Cohesion: 0.20
Nodes (8): CafePass, create_hash_pass(), create_vendor_pass(), delete_vendor_pass(), Create new pass (date-based or hour-based), Deactivate a pass (soft delete), _sync_cafe_specific_pass_payment_method(), update_vendor_pass()

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "BankTransferDetails"
Cohesion: 0.22
Nodes (4): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters)

### Community 71 - "RAWGSyncService"
Cohesion: 0.25
Nodes (5): Create Game from RAWG API - image_url gets background_image automatically!, Sync single game from RAWG API, Fetch a single page of games from RAWG API, Sync games from RAWG API, RAWGSyncService

### Community 72 - "change"
Cohesion: 0.25
Nodes (8): change(), create_payment_order(), _parse_period_datetime(), provision_default(), post, Provision default subscription for new vendor, Change subscription package (admin use), Create Razorpay order for subscription purchase

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 75 - "Console and cafe-wallet pricing"
Cohesion: 0.50
Nodes (3): Compatibility and deployment, Console and cafe-wallet pricing, Rules

## Knowledge Gaps
- **34 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+29 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CloudinaryGameImageService` connect `CloudinaryGameImageService` to `GameService`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `KioskTests` connect `KioskTests` to `test_cafe_wallet.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `Vendor` connect `vendor.py` to `VendorGame`, `Flask`, `pricingController.py`, `BankTransferDetails`, `app/routes.py`, `ExtraServiceService`, `websocket_service.py`, `subscription_commerce.py`, `models/routes.py`, `cafe_wallet_controller.py`, `test_subscription_commerce.py`, `console_service.py`, `test_subscription_checkout.py`, `subscription_service.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_collections_date_boundaries_and_activity_scope()`) actually correct?**
  _`datetime` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeLedger`) actually correct?**
  _`CafeError` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Vendor` (e.g. with `Amenity` and `AvailableGame`) actually correct?**
  _`Vendor` has 18 INFERRED edges - model-reasoned connections that need verification._