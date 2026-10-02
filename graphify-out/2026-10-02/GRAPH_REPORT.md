# Graph Report - hfg-dashboard-service  (2026-10-02)

## Corpus Check
- 176 files · ~84,981 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1429 nodes · 3900 edges · 85 communities (74 shown, 11 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 101 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `04003ded`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- access_controller.py
- vendor.py
- pricingController.py
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- test_cafe_wallet.py
- change
- cafe_wallet_controller.py
- passModels.py
- review_controller.py
- test_shared_slot_capacity.py
- vendor_games.py
- subscription_controller.py
- package_controller.py
- Console
- test_subscription_commerce.py
- test_subscription_checkout.py
- booking_bridge.py
- test_console_pricing.py
- auth
- commands.py
- datetime
- BridgeTests
- Kiosk backend contract — 22 September 2026
- models/__init__.py
- date
- 20260922_cafe_wallet.sql
- route
- extensions.py
- tournament_matches
- is_subscription_active
- get_vendor_dashboard
- CloudinaryMenuImageService
- console_catalog_service.py
- ConsoleService
- Cafe wallets: read-only mobile app APIs
- subscription_service.py
- vendor_console_overrides
- Flask
- _invalidate_vendor_caches
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- create_subscription
- cafePass.py
- CloudinaryProfileImageService
- test_cafe_continuations.py
- test_qr_input.py
- booking_bridge_controller.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- add_or_update_bank_details
- test_payment_methods.py
- Subscription packages, purchases and kiosk licences
- UserPass
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- test_kiosk_runtime.py
- cafe_play_sessions
- rbac_guard.py
- websocket_controller.py
- get_extra_services

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 57 edges
2. `Vendor` - 37 edges
3. `staff_actor()` - 31 edges
4. `auth()` - 30 edges
5. `KioskError` - 28 edges
6. `ConsoleService` - 26 edges
7. `audit()` - 24 edges
8. `fund()` - 24 edges
9. `serialize()` - 23 edges
10. `_invalidate_vendor_caches()` - 22 edges

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

## Communities (85 total, 11 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (57): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+49 more)

### Community 1 - "access_controller.py"
Cohesion: 0.19
Nodes (30): _auth_debug(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session(), list_staff(), delete (+22 more)

### Community 2 - "vendor.py"
Cohesion: 0.07
Nodes (28): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted, OpeningDay (+20 more)

### Community 3 - "pricingController.py"
Cohesion: 0.08
Nodes (41): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+33 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "app/routes.py"
Cohesion: 0.09
Nodes (26): ContactInfo, Transaction, VendorDaySlotConfig, VendorTaxProfile, _build_session_identifier(), _coerce_bool(), _default_vendor_notification_preferences(), _derive_booking_outcome() (+18 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (23): add_extra_service_menu(), create_category(), create_menu_item(), delete_category(), delete_extra_service_category(), delete_extra_service_menu(), delete_menu_item(), Create new service category (+15 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.07
Nodes (75): before_request, require_tournament_plan(), internal_send_unlock(), internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…, get, remaining() (+67 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.20
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "test_cafe_wallet.py"
Cohesion: 0.15
Nodes (21): fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit(), test_disabled_wallet_hides_qr_payment_but_keeps_history_and_refunds() (+13 more)

### Community 11 - "change"
Cohesion: 0.25
Nodes (8): change(), create_payment_order(), _parse_period_datetime(), provision_default(), post, Provision default subscription for new vendor, Change subscription package (admin use), Create Razorpay order for subscription purchase

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.06
Nodes (134): adjust_wallet(), agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation() (+126 more)

### Community 13 - "passModels.py"
Cohesion: 0.11
Nodes (9): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass(), create_vendor_pass() (+1 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (13): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+5 more)

### Community 16 - "vendor_games.py"
Cohesion: 0.07
Nodes (30): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+22 more)

### Community 17 - "subscription_controller.py"
Cohesion: 0.10
Nodes (34): authorize_subscription(), check_payment_status(), check_subscription_status(), debug_force_expire(), get_limit(), get_subscription(), get_subscription_history(), get_subscription_invoice() (+26 more)

### Community 18 - "package_controller.py"
Cohesion: 0.17
Nodes (17): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+9 more)

### Community 19 - "Console"
Cohesion: 0.07
Nodes (23): create_game(), route, Create a new game with optional image, update_game(), Console, Game, Create Game from RAWG API - image_url gets background_image automatically!, add_images_to_games() (+15 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.13
Nodes (41): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+33 more)

### Community 21 - "test_subscription_checkout.py"
Cohesion: 0.11
Nodes (20): AdditionalDetails, Booking, BookingExtraService, BookingSquadMember, HardwareSpecification, MaintenanceStatus, PriceAndCost, Slot (+12 more)

### Community 22 - "booking_bridge.py"
Cohesion: 0.18
Nodes (14): connect(), disconnect(), _emit_downstream(), ensure_upstream_vendor_join(), _handle_booking_event(), _join_upstream_vendor(), Any, Start the upstream bridge once (idempotent). (+6 more)

### Community 23 - "test_console_pricing.py"
Cohesion: 0.16
Nodes (10): offer(), pricing_api(), fixture, parametrize, Pricing and real wallet quote/reservation/capture regression tests., test_console_price_drives_quote_reservation_and_capture(), test_invalid_prices_rejected(), test_offer_window_midnight_boundaries_lowest_price_and_lowered_base() (+2 more)

### Community 24 - "auth"
Cohesion: 0.17
Nodes (25): auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages(), test_gamer_cannot_use_staff_topup_or_wallet_routes(), test_history_is_scoped_filtered_and_stably_paginated() (+17 more)

### Community 25 - "commands.py"
Cohesion: 0.12
Nodes (27): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+19 more)

### Community 26 - "datetime"
Cohesion: 0.18
Nodes (5): PassRedemptionLog, PayAtCafeNotification, datetime, EarlyStartTests, Check the dashboard's production eligibility rule without booting services.

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 30 - "date"
Cohesion: 0.21
Nodes (6): _vendor_slot_availability(), date, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), ManualSessionEndTests, Scheduled end and midnight must not manufacture a completed session.

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "route"
Cohesion: 0.07
Nodes (30): add_extra_service_category(), check_db_connection(), create_payout(), delete_vendor_profile_image(), get_all_device_for_vendor(), get_booking_details(), get_console(), get_master_stats() (+22 more)

### Community 33 - "extensions.py"
Cohesion: 0.12
Nodes (11): ensure_ist(), Ensure a datetime is timezone-aware in IST (idempotent)., Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, ProvisionalResult, User (+3 more)

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "is_subscription_active"
Cohesion: 0.38
Nodes (6): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), is_subscription_active(), Check if vendor has an active, non-expired subscription Returns: tuple: (bool:…

### Community 36 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 37 - "CloudinaryMenuImageService"
Cohesion: 0.24
Nodes (6): CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload menu item image to Cloudinary

### Community 38 - "console_catalog_service.py"
Cohesion: 0.20
Nodes (21): ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_pricing(), get_console_type_overrides(), get_console_types(), get_consoles() (+13 more)

### Community 39 - "ConsoleService"
Cohesion: 0.18
Nodes (5): AvailableGame, ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_service.py"
Cohesion: 0.15
Nodes (23): Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, Subscription, SubscriptionStatus, activate(), billing_datetime(), check_base(), paise() (+15 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "Flask"
Cohesion: 0.18
Nodes (15): Register all Flask CLI commands, register_commands(), Config, register_cafe_runtime(), install_kiosk_errors(), create_app(), _is_insecure_secret(), _validate_production_config() (+7 more)

### Community 44 - "_invalidate_vendor_caches"
Cohesion: 0.14
Nodes (20): add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), delete_console(), delete_vendor_pass(), get_device_for_console_type(), _invalidate_vendor_caches() (+12 more)

### Community 63 - "create_subscription"
Cohesion: 0.31
Nodes (10): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle(), Create a new subscription after successful payment Args: vendor_id: Vendor ID…, Renew existing subscription (keeps same package) Args: vendor_id: Vendor ID… (+2 more)

### Community 65 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 66 - "test_cafe_continuations.py"
Cohesion: 0.42
Nodes (12): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_credit_due_only_after_ack_and_collection_does_not_change_wallet(), test_failed_credit_start_no_debt_or_stuck_capacity(), test_low_time_warning_once_expiry_stop_and_reconnect() (+4 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "booking_bridge_controller.py"
Cohesion: 0.48
Nodes (6): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status()

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 71 - "add_or_update_bank_details"
Cohesion: 0.25
Nodes (9): add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number(), _mask_upi_id(), Get vendor's bank transfer details, Get historized changes for vendor bank/UPI details. (+1 more)

### Community 72 - "test_payment_methods.py"
Cohesion: 0.40
Nodes (3): methods(), fixture, Exercise the production payment-settings handlers in a disposable DB.

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 75 - "Console and cafe-wallet pricing"
Cohesion: 0.50
Nodes (3): Compatibility and deployment, Console and cafe-wallet pricing, Rules

### Community 78 - "Shared capacity for app, dashboard, kiosk and QR bookings"
Cohesion: 0.50
Nodes (3): Rollout, Shared capacity for app, dashboard, kiosk and QR bookings, Verification

### Community 81 - "rbac_guard.py"
Cohesion: 0.60
Nodes (5): enforce_rbac_permissions(), _extract_vendor_id_from_request(), claim_vendor_id(), claims_permissions(), Match

### Community 82 - "websocket_controller.py"
Cohesion: 0.50
Nodes (3): handle_processed_slot(), Handle the processed event and emit a final event, on

### Community 83 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

## Knowledge Gaps
- **36 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+31 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ConsoleService` connect `ConsoleService` to `Console`, `vendor.py`, `test_subscription_checkout.py`, `app/routes.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `Vendor` connect `vendor.py` to `access_controller.py`, `extensions.py`, `pricingController.py`, `app/routes.py`, `ConsoleService`, `subscription_service.py`, `cafe_wallet_controller.py`, `vendor_games.py`, `test_subscription_commerce.py`, `test_subscription_checkout.py`, `commands.py`, `models/__init__.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `KioskError` connect `websocket_service.py` to `event_controller.py`, `extensions.py`, `app/routes.py`, `subscription_controller.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_collections_date_boundaries_and_activity_scope()`) actually correct?**
  _`datetime` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeLedger`) actually correct?**
  _`CafeError` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _36 weakly-connected nodes found - possible documentation gaps or missing edges._