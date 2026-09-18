# Graph Report - hfg-dashboard-service  (2026-09-18)

## Corpus Check
- 131 files · ~57,427 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 933 nodes · 2326 edges · 61 communities (53 shown, 8 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 60 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dbb19472`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Flask
- access_controller.py
- extensions.py
- pricingController.py
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- websocket_service.py
- booking_bridge.py
- toggle_payment_method_for_vendor
- ConsoleService
- subscription_controller.py
- subscription_service.py
- passModels.py
- review_controller.py
- razorpay_service.py
- vendor_games.py
- _invalidate_vendor_caches
- package_controller.py
- CloudinaryGameImageService
- vendor_pc_controller.py
- test_subscription_checkout.py
- verify_and_activate
- game_service.py
- console_service.py
- GameService
- CloudinaryProfileImageService
- internal_ws_controller.py
- AvailableGame
- ConsolePricingOffer
- datetime
- RAWGSyncService
- VendorGame
- add_or_update_bank_details
- tournament_matches
- is_subscription_active
- get_vendor_dashboard
- get_landing_page_vendor
- UserPass
- get_vendor_notification_preferences
- get_vendor_passes
- vendorTaxProfile.py
- vendor_console_overrides
- transaction.py
- vendorDaySlotConfig.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations

## God Nodes (most connected - your core abstractions)
1. `Vendor` - 27 edges
2. `ConsoleService` - 26 edges
3. `normalize_console_slug()` - 19 edges
4. `ExtraServiceService` - 18 edges
5. `AvailableGame` - 17 edges
6. `GameService` - 17 edges
7. `resolve_console_capabilities()` - 15 edges
8. `register_commands()` - 14 edges
9. `Package` - 14 edges
10. `VendorGame` - 14 edges

## Surprising Connections (you probably didn't know these)
- `app()` --calls--> `Package`  [EXTRACTED]
  tests/test_subscription_checkout.py → app/models/package.py
- `get_landing_page_vendor()` --indirect_call--> `status()`  [INFERRED]
  app/routes.py → app/controllers/booking_bridge_controller.py
- `ConsoleService` --uses--> `AdditionalDetails`  [INFERRED]
  app/services/console_service.py → app/models/additionalDetails.py
- `Vendor` --uses--> `Amenity`  [INFERRED]
  app/models/vendor.py → app/models/amenity.py
- `Vendor` --uses--> `AvailableGame`  [INFERRED]
  app/models/vendor.py → app/models/availableGame.py

## Import Cycles
- None detected.

## Communities (61 total, 8 thin omitted)

### Community 0 - "Flask"
Cohesion: 0.06
Nodes (63): Config, delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event() (+55 more)

### Community 1 - "access_controller.py"
Cohesion: 0.07
Nodes (63): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+55 more)

### Community 2 - "extensions.py"
Cohesion: 0.06
Nodes (33): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, CafePass, ContactInfo, Document (+25 more)

### Community 3 - "pricingController.py"
Cohesion: 0.08
Nodes (48): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+40 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.07
Nodes (51): add_console(), add_extra_service_category(), check_db_connection(), create_category(), create_menu_item(), create_or_update_console_type_override(), create_payout(), deactivate_console_type_override() (+43 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (22): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_menu(), CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder (+14 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.15
Nodes (33): handle_processed_slot(), Handle the processed event and emit a final event, format_current_slot_item(), format_upcoming_booking_from_upstream(), Any, Convert upstream booking payload into the upcomingBookings item shape, but ONLY…, _to_date_str(), _to_time_str() (+25 more)

### Community 8 - "booking_bridge.py"
Cohesion: 0.13
Nodes (20): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+12 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.13
Nodes (14): PaymentMethod, PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name() (+6 more)

### Community 10 - "ConsoleService"
Cohesion: 0.19
Nodes (5): add_console(), ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 11 - "subscription_controller.py"
Cohesion: 0.17
Nodes (18): change(), check_subscription_status(), debug_force_expire(), get_limit(), get_subscription(), get_subscription_history(), get_subscription_invoice(), _invoice_number() (+10 more)

### Community 12 - "subscription_service.py"
Cohesion: 0.19
Nodes (13): Package, Subscription, SubscriptionStatus, create_package(), change_subscription(), get_active_subscription(), get_vendor_pc_limit(), provision_default_subscription() (+5 more)

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
Cohesion: 0.22
Nodes (16): add_game_to_consoles(), bulk_delete_game(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games(), _offer_is_active_now() (+8 more)

### Community 17 - "_invalidate_vendor_caches"
Cohesion: 0.14
Nodes (17): assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), delete_console(), delete_vendor_pass(), get_device_for_console_type(), _invalidate_vendor_caches(), kiosk_start_session() (+9 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "CloudinaryGameImageService"
Cohesion: 0.17
Nodes (9): upload_game_image(), add_images_to_games(), CloudinaryGameImageService, Delete game cover image from Cloudinary, Service for handling game cover images Images are uploaded to the 'GAME_COVERS'…, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload game cover image to Cloudinary (+1 more)

### Community 20 - "vendor_pc_controller.py"
Cohesion: 0.28
Nodes (13): _auth_vendor(), get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus (+5 more)

### Community 21 - "test_subscription_checkout.py"
Cohesion: 0.21
Nodes (13): BookingExtraService, Image, fixture, parametrize, app(), order(), payment(), Isolated checkout tests with real subscription rows and provider responses. (+5 more)

### Community 22 - "verify_and_activate"
Cohesion: 0.20
Nodes (15): create_payment_order(), provision_default(), post, Provision default subscription for new vendor, Create Razorpay order for subscription purchase, Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), create_subscription() (+7 more)

### Community 23 - "game_service.py"
Cohesion: 0.23
Nodes (6): create_game(), route, Create a new game with optional image, update_game(), Console, Game

### Community 24 - "console_service.py"
Cohesion: 0.19
Nodes (5): AdditionalDetails, HardwareSpecification, MaintenanceStatus, PriceAndCost, update_console()

### Community 25 - "GameService"
Cohesion: 0.18
Nodes (8): delete_game_image(), get_all_games(), GameService, Delete Cloudinary image, Get all games ordered by name, Search games by name (case-insensitive, partial match), Get all vendor games grouped by game. price_per_hour is dynamically computed…, Get all consoles for a specific platform (PC, PS5, Xbox, VR)

### Community 26 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 27 - "internal_ws_controller.py"
Cohesion: 0.24
Nodes (8): ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to broadcast unlock events to a specific kiosk (console) for…, Internal endpoint to notify dashboard clients that store inventory/products…, User

### Community 28 - "AvailableGame"
Cohesion: 0.33
Nodes (4): AvailableGame, Booking, BookingSquadMember, Slot

### Community 29 - "ConsolePricingOffer"
Cohesion: 0.24
Nodes (5): ConsolePricingOffer, Time-based promotional pricing for console types (AvailableGames) Allows…, Check if this offer is active RIGHT NOW using IST. Returns True if current IST…, Calculate discount percentage, Convert to dictionary for API responses

### Community 30 - "datetime"
Cohesion: 0.20
Nodes (4): PassRedemptionLog, PayAtCafeNotification, _get_next_slot_for_today(), datetime

### Community 31 - "RAWGSyncService"
Cohesion: 0.25
Nodes (5): Create Game from RAWG API - image_url gets background_image automatically!, Sync single game from RAWG API, Fetch a single page of games from RAWG API, Sync games from RAWG API, RAWGSyncService

### Community 32 - "VendorGame"
Cohesion: 0.22
Nodes (4): Serialize VendorGame — price is always dynamically computed, Dynamically compute price from parent AvailableGame. - If an active…, Returns full pricing context: base price, offer price, offer details. Useful…, VendorGame

### Community 33 - "add_or_update_bank_details"
Cohesion: 0.25
Nodes (9): add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number(), _mask_upi_id(), Get vendor's bank transfer details, Get historized changes for vendor bank/UPI details. (+1 more)

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "is_subscription_active"
Cohesion: 0.32
Nodes (7): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), _as_utc(), is_subscription_active(), Check if vendor has an active, non-expired subscription Returns: tuple: (bool:…

### Community 36 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 37 - "get_landing_page_vendor"
Cohesion: 0.29
Nodes (7): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, Keep lifecycle monotonic for API output: - future date can never be…

### Community 39 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

### Community 40 - "get_vendor_passes"
Cohesion: 0.33
Nodes (6): get_vendor_passes(), get_vendor_passes_by_mode(), _parse_bool_flag(), Get vendor passes grouped for frontend (hour/date based)., Backward-compatible alias of /vendor/<vendor_id>/passes., _vendor_exists()

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

## Knowledge Gaps
- **4 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `graphify`
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GameService` connect `GameService` to `VendorGame`, `vendor_games.py`, `CloudinaryGameImageService`, `game_service.py`, `AvailableGame`, `RAWGSyncService`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `ConsoleService` connect `ConsoleService` to `extensions.py`, `app/routes.py`, `game_service.py`, `console_service.py`, `AvailableGame`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `Vendor` connect `extensions.py` to `VendorGame`, `access_controller.py`, `pricingController.py`, `app/routes.py`, `ExtraServiceService`, `subscription_service.py`, `internal_ws_controller.py`, `AvailableGame`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `Vendor` (e.g. with `Amenity` and `AvailableGame`) actually correct?**
  _`Vendor` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `ConsoleService` (e.g. with `AdditionalDetails` and `AvailableGame`) actually correct?**
  _`ConsoleService` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Flask` be split into smaller, more focused modules?**
  _Cohesion score 0.055651176133103844 - nodes in this community are weakly interconnected._