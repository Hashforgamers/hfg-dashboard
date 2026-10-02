# Graph Report - hfg-dashboard-service  (2026-10-02)

## Corpus Check
- 177 files · ~87,270 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1457 nodes · 3979 edges · 81 communities (70 shown, 11 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cef142b0`
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
- commands.py
- cafe_wallet_controller.py
- passModels.py
- review_controller.py
- test_shared_slot_capacity.py
- vendor_games.py
- get
- package_controller.py
- GameService
- test_subscription_commerce.py
- test_subscription_checkout.py
- booking_bridge.py
- test_console_pricing.py
- auth
- subscription_controller.py
- extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- console_catalog_service.py
- date
- 20260922_cafe_wallet.sql
- route
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- is_subscription_active
- get_vendor_dashboard
- CloudinaryMenuImageService
- _invalidate_vendor_caches
- ConsoleService
- Cafe wallets: read-only mobile app APIs
- subscription_commerce.py
- vendor_console_overrides
- update_menu_inventory
- UserPass
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- razorpay_service.py
- cafePass.py
- CloudinaryProfileImageService
- test_cafe_continuations.py
- test_qr_input.py
- booking_bridge_controller.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- VendorProfileImage
- Subscription packages, purchases and kiosk licences
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- test_kiosk_runtime.py
- cafe_play_sessions
- get_extra_services

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 58 edges
2. `Vendor` - 37 edges
3. `auth()` - 34 edges
4. `staff_actor()` - 31 edges
5. `KioskError` - 28 edges
6. `fund()` - 27 edges
7. `ConsoleService` - 26 edges
8. `KioskTests` - 26 edges
9. `audit()` - 25 edges
10. `serialize()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `test_postgres_concurrent_checkout_and_legacy_guards()` --indirect_call--> `checkout()`  [INFERRED]
  tests/test_cafe_wallet.py → app/controllers/cafe_wallet_controller.py
- `env()` --calls--> `Console`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console.py
- `test_postgres_concurrent_links_cannot_exceed_purchased_limit()` --calls--> `Console`  [INFERRED]
  tests/test_subscription_commerce.py → app/models/console.py
- `env()` --calls--> `ConsoleLinkSession`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console_link_session.py
- `env()` --calls--> `ExtraServiceCategory`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/extraServiceCategory.py

## Import Cycles
- None detected.

## Communities (81 total, 11 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (61): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+53 more)

### Community 1 - "access_controller.py"
Cohesion: 0.11
Nodes (38): _auth_debug(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session(), list_staff(), delete (+30 more)

### Community 2 - "vendor.py"
Cohesion: 0.07
Nodes (28): Amenity, BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted (+20 more)

### Community 3 - "pricingController.py"
Cohesion: 0.08
Nodes (41): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+33 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.08
Nodes (32): Transaction, VendorDaySlotConfig, VendorTaxProfile, add_or_update_bank_details(), _build_session_identifier(), _coerce_bool(), _default_vendor_notification_preferences(), _derive_booking_outcome() (+24 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.08
Nodes (24): ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), create_category(), create_menu_item(), delete_category() (+16 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.06
Nodes (88): Config, internal_send_unlock(), internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…, install_kiosk_errors(), get, remaining() (+80 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.20
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "test_cafe_wallet.py"
Cohesion: 0.13
Nodes (24): test_budget_duration_cannot_exceed_cafe_limit_or_turn_missing_price_into_zero(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+16 more)

### Community 11 - "commands.py"
Cohesion: 0.15
Nodes (28): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+20 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.05
Nodes (143): adjust_wallet(), agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation() (+135 more)

### Community 13 - "passModels.py"
Cohesion: 0.17
Nodes (5): PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type()

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (13): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+5 more)

### Community 16 - "vendor_games.py"
Cohesion: 0.08
Nodes (30): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+22 more)

### Community 17 - "get"
Cohesion: 0.17
Nodes (13): authorize_subscription(), get_limit(), get_subscription(), get_subscription_history(), get_subscription_invoice(), _invoice_number(), before_request, get (+5 more)

### Community 18 - "package_controller.py"
Cohesion: 0.17
Nodes (17): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+9 more)

### Community 19 - "GameService"
Cohesion: 0.08
Nodes (22): create_game(), route, Create a new game with optional image, update_game(), Game, Create Game from RAWG API - image_url gets background_image automatically!, add_images_to_games(), CloudinaryGameImageService (+14 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.15
Nodes (36): get_pcs(), link_pc(), get, post, unlink_pc(), vendor_required(), close_link(), create_link() (+28 more)

### Community 21 - "test_subscription_checkout.py"
Cohesion: 0.09
Nodes (24): ensure_ist(), Ensure a datetime is timezone-aware in IST (idempotent)., AdditionalDetails, AvailableGame, Booking, BookingExtraService, BookingSquadMember, Console (+16 more)

### Community 22 - "booking_bridge.py"
Cohesion: 0.18
Nodes (14): connect(), disconnect(), _emit_downstream(), ensure_upstream_vendor_join(), _handle_booking_event(), _join_upstream_vendor(), Any, Start the upstream bridge once (idempotent). (+6 more)

### Community 23 - "test_console_pricing.py"
Cohesion: 0.13
Nodes (13): User, env(), fixture, offer(), pricing_api(), fixture, parametrize, Pricing and real wallet quote/reservation/capture regression tests. (+5 more)

### Community 24 - "auth"
Cohesion: 0.13
Nodes (30): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+22 more)

### Community 25 - "subscription_controller.py"
Cohesion: 0.15
Nodes (29): create_payment_order(), debug_force_expire(), provision_default(), post, Provision default subscription for new vendor, Create Razorpay order for subscription purchase, Verify Razorpay payment signature and activate subscription Request body: {…, Force expire subscription for testing - REMOVE IN PRODUCTION (+21 more)

### Community 26 - "extensions.py"
Cohesion: 0.10
Nodes (8): ConsoleLinkStatus, PassRedemptionLog, PayAtCafeNotification, ProvisionalResult, VerificationCheck, datetime, EarlyStartTests, Check the dashboard's production eligibility rule without booting services.

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "console_catalog_service.py"
Cohesion: 0.20
Nodes (21): ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_pricing(), get_console_type_overrides(), get_console_types(), get_consoles() (+13 more)

### Community 30 - "date"
Cohesion: 0.21
Nodes (6): _vendor_slot_availability(), date, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), ManualSessionEndTests, Scheduled end and midnight must not manufacture a completed session.

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "route"
Cohesion: 0.06
Nodes (32): check_db_connection(), create_payout(), delete_vendor_profile_image(), get_all_device_for_vendor(), get_booking_details(), get_console(), get_master_stats(), get_payout_history() (+24 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "is_subscription_active"
Cohesion: 0.19
Nodes (12): change(), check_subscription_status(), _parse_period_datetime(), Check if vendor subscription is active (for dashboard lock), Change subscription package (admin use), _subscription_status_snapshot(), check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical… (+4 more)

### Community 36 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 37 - "CloudinaryMenuImageService"
Cohesion: 0.24
Nodes (6): CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload menu item image to Cloudinary

### Community 38 - "_invalidate_vendor_caches"
Cohesion: 0.11
Nodes (21): CafePass, add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), create_hash_pass(), create_vendor_pass(), delete_console() (+13 more)

### Community 39 - "ConsoleService"
Cohesion: 0.23
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_commerce.py"
Cohesion: 0.19
Nodes (16): Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, activate(), billing_datetime(), check_base(), paise(), preview(), public_quote() (+8 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 63 - "razorpay_service.py"
Cohesion: 0.15
Nodes (16): check_payment_status(), Check if a payment has been made for an order Used for QR code payments where…, create_order(), get_order_details(), get_order_payments(), get_payment_details(), get_razorpay_client(), get_test_price() (+8 more)

### Community 65 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 66 - "test_cafe_continuations.py"
Cohesion: 0.32
Nodes (18): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_collection_requires_completed_play_and_expected_amount(), test_competing_owner_approvals_create_one_credit_session(), test_continuation_migration_is_repeatable_and_preserves_live_play() (+10 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "booking_bridge_controller.py"
Cohesion: 0.48
Nodes (6): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status()

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 75 - "Console and cafe-wallet pricing"
Cohesion: 0.50
Nodes (3): Compatibility and deployment, Console and cafe-wallet pricing, Rules

### Community 78 - "Shared capacity for app, dashboard, kiosk and QR bookings"
Cohesion: 0.50
Nodes (3): Rollout, Shared capacity for app, dashboard, kiosk and QR bookings, Verification

### Community 83 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

## Knowledge Gaps
- **41 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `KioskTests` connect `KioskTests` to `date`, `test_kiosk_runtime.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `GameService` connect `GameService` to `vendor_games.py`, `test_subscription_checkout.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `Vendor` connect `vendor.py` to `access_controller.py`, `pricingController.py`, `app/routes.py`, `VendorProfileImage`, `subscription_commerce.py`, `commands.py`, `cafe_wallet_controller.py`, `vendor_games.py`, `test_subscription_commerce.py`, `test_subscription_checkout.py`, `test_console_pricing.py`, `auth`, `subscription_controller.py`, `extensions.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_collections_date_boundaries_and_activity_scope()`) actually correct?**
  _`datetime` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._