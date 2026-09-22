# Graph Report - hfg-dashboard-service  (2026-09-22)

## Corpus Check
- 148 files · ~70,899 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1147 nodes · 3022 edges · 71 communities (59 shown, 12 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aac74d88`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- access_controller.py
- vendor.py
- pricingController.py
- tournament_engine_service.py
- route
- ExtraServiceService
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- models/routes.py
- subscription_controller.py
- cafe_wallet_controller.py
- passModels.py
- review_controller.py
- razorpay_service.py
- vendor_games.py
- _invalidate_vendor_caches
- subscription_service.py
- datetime
- link_service.py
- extensions.py
- verify_and_activate
- CloudinaryMenuImageService
- test_cafe_wallet.py
- BankTransferDetails
- CloudinaryProfileImageService
- BridgeTests
- Kiosk backend contract — 22 September 2026
- ConsolePricingOffer
- PassRedemptionLog.py
- 20260922_cafe_wallet.sql
- AvailableGame
- add_or_update_bank_details
- tournament_matches
- is_subscription_active
- get_vendor_dashboard
- app/routes.py
- UserPass
- RAWGSyncService
- Cafe wallet and QR checkout
- get_extra_services
- vendor_console_overrides
- update_menu_inventory
- CloudinaryGameImageService
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- GameService
- .update_game_image
- OpeningDay
- payAtCafeNotification.py
- VendorProfileImage
- Website
- 20260923_unified_kiosk_qr.sql
- cafe_play_sessions

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 40 edges
2. `Vendor` - 32 edges
3. `ConsoleService` - 26 edges
4. `_invalidate_vendor_caches()` - 22 edges
5. `KioskError` - 22 edges
6. `KioskTests` - 22 edges
7. `staff_actor()` - 20 edges
8. `audit()` - 19 edges
9. `normalize_console_slug()` - 19 edges
10. `ExtraServiceService` - 18 edges

## Surprising Connections (you probably didn't know these)
- `test_postgres_concurrent_checkout_and_legacy_guards()` --indirect_call--> `checkout()`  [INFERRED]
  tests/test_cafe_wallet.py → app/controllers/cafe_wallet_controller.py
- `env()` --calls--> `Console`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console.py
- `env()` --calls--> `ConsoleLinkSession`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console_link_session.py
- `env()` --calls--> `User`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/user.py
- `env()` --calls--> `Vendor`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/vendor.py

## Import Cycles
- None detected.

## Communities (71 total, 12 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.12
Nodes (32): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+24 more)

### Community 1 - "access_controller.py"
Cohesion: 0.07
Nodes (63): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+55 more)

### Community 2 - "vendor.py"
Cohesion: 0.21
Nodes (7): BusinessRegistration, Document, DocumentSubmitted, PhysicalAddress, Timing, Vendor, VendorAccount

### Community 3 - "pricingController.py"
Cohesion: 0.08
Nodes (46): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+38 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.06
Nodes (70): list_registrations(), get, jwt_required, patch, update_payment_status(), _vendor_id(), list_winners(), publish_winners() (+62 more)

### Community 5 - "route"
Cohesion: 0.06
Nodes (35): check_db_connection(), create_category(), create_payout(), delete_vendor_profile_image(), get_all_device_for_vendor(), get_booking_details(), get_console(), get_console_pricing() (+27 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.08
Nodes (23): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), create_menu_item(), delete_category() (+15 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.07
Nodes (69): Config, ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products…, install_kiosk_errors() (+61 more)

### Community 8 - "KioskTests"
Cohesion: 0.06
Nodes (25): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+17 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.15
Nodes (15): PaymentMethod, _build_payment_method_response(), delete_vendor_pass(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name() (+7 more)

### Community 10 - "models/routes.py"
Cohesion: 0.24
Nodes (14): add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor(), get_consoles(), get_device_for_console_type(), get_landing_page_vendor(), get_transaction_report() (+6 more)

### Community 11 - "subscription_controller.py"
Cohesion: 0.17
Nodes (18): change(), check_subscription_status(), debug_force_expire(), get_limit(), get_subscription_history(), get_subscription_invoice(), _invoice_number(), _parse_period_datetime() (+10 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.09
Nodes (82): adjust_wallet(), agent_ack(), agent_link(), agent_qr(), agent_session(), audit_history(), cafe_error(), checkout() (+74 more)

### Community 13 - "passModels.py"
Cohesion: 0.11
Nodes (9): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass(), create_vendor_pass() (+1 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "razorpay_service.py"
Cohesion: 0.15
Nodes (16): check_payment_status(), Check if a payment has been made for an order Used for QR code payments where…, create_order(), get_order_details(), get_order_payments(), get_payment_details(), get_razorpay_client(), get_test_price() (+8 more)

### Community 16 - "vendor_games.py"
Cohesion: 0.20
Nodes (16): add_game_to_consoles(), bulk_delete_game(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games(), _offer_is_active_now() (+8 more)

### Community 17 - "_invalidate_vendor_caches"
Cohesion: 0.14
Nodes (19): add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), delete_console(), get_device_for_console_type(), _invalidate_vendor_caches(), kiosk_start_session() (+11 more)

### Community 18 - "subscription_service.py"
Cohesion: 0.16
Nodes (20): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+12 more)

### Community 19 - "datetime"
Cohesion: 0.27
Nodes (7): create_game(), route, Create a new game with optional image, update_game(), Game, _get_next_slot_for_today(), datetime

### Community 20 - "link_service.py"
Cohesion: 0.18
Nodes (16): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, PaymentVendorMap (+8 more)

### Community 21 - "extensions.py"
Cohesion: 0.06
Nodes (28): AdditionalDetails, Booking, BookingExtraService, BookingSquadMember, CafePass, HardwareSpecification, MaintenanceStatus, PassType (+20 more)

### Community 22 - "verify_and_activate"
Cohesion: 0.24
Nodes (13): create_payment_order(), post, Create Razorpay order for subscription purchase, Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration() (+5 more)

### Community 23 - "CloudinaryMenuImageService"
Cohesion: 0.24
Nodes (6): CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload menu item image to Cloudinary

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.16
Nodes (25): auth(), fund(), gamer(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), staff_token(), test_active_booking_cancellation_or_refund_stops_session() (+17 more)

### Community 25 - "BankTransferDetails"
Cohesion: 0.22
Nodes (4): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters)

### Community 26 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "ConsolePricingOffer"
Cohesion: 0.28
Nodes (5): ConsolePricingOffer, Time-based promotional pricing for console types (AvailableGames) Allows…, Check if this offer is active RIGHT NOW using IST. Returns True if current IST…, Calculate discount percentage, Convert to dictionary for API responses

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
Cohesion: 0.15
Nodes (15): get_subscription(), provision_default(), Provision default subscription for new vendor, Get current subscription status for vendor, check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required() (+7 more)

### Community 36 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 37 - "app/routes.py"
Cohesion: 0.08
Nodes (31): ContactInfo, Transaction, VendorDaySlotConfig, VendorTaxProfile, _build_session_identifier(), _coerce_bool(), create_or_update_console_type_override(), deactivate_console_type_override() (+23 more)

### Community 39 - "RAWGSyncService"
Cohesion: 0.25
Nodes (5): Create Game from RAWG API - image_url gets background_image automatically!, Sync single game from RAWG API, Fetch a single page of games from RAWG API, Sync games from RAWG API, RAWGSyncService

### Community 40 - "Cafe wallet and QR checkout"
Cohesion: 0.25
Nodes (7): Audit and reconciliation, Cafe wallet and QR checkout, Deployment order, Gamer and staff APIs, One QR for existing bookings and wallet play, PC agent integration — required before real PC rollout, Verification

### Community 41 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 44 - "CloudinaryGameImageService"
Cohesion: 0.25
Nodes (6): add_images_to_games(), CloudinaryGameImageService, Service for handling game cover images Images are uploaded to the 'GAME_COVERS'…, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload game cover image to Cloudinary

### Community 63 - "GameService"
Cohesion: 0.24
Nodes (6): get_all_games(), GameService, Get all games ordered by name, Search games by name (case-insensitive, partial match), Get all vendor games grouped by game. price_per_hour is dynamically computed…, Get all consoles for a specific platform (PC, PS5, Xbox, VR)

### Community 64 - ".update_game_image"
Cohesion: 0.25
Nodes (5): delete_game_image(), upload_game_image(), Delete game cover image from Cloudinary, Delete Cloudinary image, Update game cover image using Cloudinary

## Knowledge Gaps
- **19 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CloudinaryGameImageService` connect `CloudinaryGameImageService` to `.update_game_image`, `datetime`, `GameService`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `Vendor` connect `vendor.py` to `AvailableGame`, `access_controller.py`, `OpeningDay`, `pricingController.py`, `VendorProfileImage`, `app/routes.py`, `ExtraServiceService`, `websocket_service.py`, `Website`, `models/routes.py`, `cafe_wallet_controller.py`, `subscription_service.py`, `link_service.py`, `BankTransferDetails`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeLedger`) actually correct?**
  _`CafeError` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Vendor` (e.g. with `Amenity` and `AvailableGame`) actually correct?**
  _`Vendor` has 18 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `event_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12010796221322537 - nodes in this community are weakly interconnected._