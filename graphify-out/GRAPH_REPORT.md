# Graph Report - hfg-dashboard-service  (2026-10-04)

## Corpus Check
- 179 files · ~88,506 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1471 nodes · 4020 edges · 100 communities (86 shown, 14 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 103 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f21a27eb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- access_controller.py
- vendor.py
- test_console_pricing.py
- tournament_engine_service.py
- add_or_update_bank_details
- ExtraServiceService
- KioskError
- KioskTests
- toggle_payment_method_for_vendor
- auth
- VendorGame
- CafeError
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
- test_cafe_continuations.py
- test_cafe_wallet.py
- get_active_subscription
- app/__init__.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- pricingController.py
- date
- 20260922_cafe_wallet.sql
- app/routes.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- terms
- get_vendor_dashboard
- CloudinaryMenuImageService
- .sync_games
- ConsoleService
- Cafe wallets: read-only mobile app APIs
- subscription_service.py
- vendor_console_overrides
- CloudinaryProfileImageService
- cafe_slot_reservations.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- subscription_controller.py
- cafePass.py
- extensions.py
- UserPass
- test_qr_input.py
- booking_bridge_controller.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- get_landing_page_vendor
- test_payment_methods.py
- Subscription packages, purchases and kiosk licences
- cafe_wallet_controller.py
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- test_kiosk_runtime.py
- cafe_play_sessions
- websocket_service.py
- get_vendor_notification_preferences
- console_catalog_service.py
- subscription_commerce_controller.py
- cafe_booking_service.py
- get_extra_services
- update_menu_inventory
- _invalidate_vendor_caches
- cafe_owner_email.py
- EarlyStartTests
- vendorDaySlotConfig.py
- payload_formatters.py
- websocket_controller.py
- accepted_methods
- internal_store_updated
- Transaction

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 59 edges
2. `Vendor` - 37 edges
3. `auth()` - 35 edges
4. `staff_actor()` - 31 edges
5. `KioskError` - 28 edges
6. `fund()` - 27 edges
7. `ConsoleService` - 26 edges
8. `KioskTests` - 26 edges
9. `audit()` - 25 edges
10. `_invalidate_vendor_caches()` - 24 edges

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

## Communities (100 total, 14 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (56): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+48 more)

### Community 1 - "access_controller.py"
Cohesion: 0.13
Nodes (38): migrate_rbac_legacy_command(), Backfill RBAC for legacy vendors: 1) Ensure one owner staff account exists per…, _auth_debug(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session() (+30 more)

### Community 2 - "vendor.py"
Cohesion: 0.07
Nodes (28): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted, OpeningDay (+20 more)

### Community 3 - "test_console_pricing.py"
Cohesion: 0.16
Nodes (10): offer(), pricing_api(), fixture, parametrize, Pricing and real wallet quote/reservation/capture regression tests., test_console_price_drives_quote_reservation_and_capture(), test_invalid_prices_rejected(), test_offer_window_midnight_boundaries_lowest_price_and_lowered_base() (+2 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "add_or_update_bank_details"
Cohesion: 0.25
Nodes (9): add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number(), _mask_upi_id(), Get vendor's bank transfer details, Get historized changes for vendor bank/UPI details. (+1 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.09
Nodes (22): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_menu(), create_category(), create_menu_item(), Create new service category (+14 more)

### Community 7 - "KioskError"
Cohesion: 0.16
Nodes (32): before_request, require_tournament_plan(), internal_send_unlock(), get, remaining(), authorize_subscription(), before_request, kiosk_unlink() (+24 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.20
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "auth"
Cohesion: 0.16
Nodes (28): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+20 more)

### Community 11 - "VendorGame"
Cohesion: 0.13
Nodes (9): ConsolePricingOffer, Time-based promotional pricing for console types (AvailableGames) Allows…, Check if this offer is active RIGHT NOW using IST. Returns True if current IST…, Calculate discount percentage, Convert to dictionary for API responses, Serialize VendorGame — price is always dynamically computed, Dynamically compute price from parent AvailableGame. - If an active…, Returns full pricing context: base price, offer price, offer details. Useful… (+1 more)

### Community 12 - "CafeError"
Cohesion: 0.16
Nodes (39): adjust_wallet(), food_order(), CafeAudit, CafeContinuation, CafeFoodOrder, CafeLedger, CafeOwnerEmail, CafePaymentPolicy (+31 more)

### Community 13 - "passModels.py"
Cohesion: 0.10
Nodes (11): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_vendor_pass(), delete_vendor_pass() (+3 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (13): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+5 more)

### Community 16 - "vendor_games.py"
Cohesion: 0.15
Nodes (21): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+13 more)

### Community 17 - "get"
Cohesion: 0.17
Nodes (37): agent_ack(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), agent_session(), audit_history() (+29 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "GameService"
Cohesion: 0.09
Nodes (19): create_game(), route, Create a new game with optional image, update_game(), Game, Create Game from RAWG API - image_url gets background_image automatically!, add_images_to_games(), CloudinaryGameImageService (+11 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.13
Nodes (39): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+31 more)

### Community 21 - "test_subscription_checkout.py"
Cohesion: 0.09
Nodes (25): ensure_ist(), Ensure a datetime is timezone-aware in IST (idempotent)., AdditionalDetails, AvailableGame, Booking, BookingExtraService, BookingSquadMember, Console (+17 more)

### Community 22 - "booking_bridge.py"
Cohesion: 0.18
Nodes (14): connect(), disconnect(), _emit_downstream(), ensure_upstream_vendor_join(), _handle_booking_event(), _join_upstream_vendor(), Any, Start the upstream bridge once (idempotent). (+6 more)

### Community 23 - "test_cafe_continuations.py"
Cohesion: 0.30
Nodes (19): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_collection_requires_completed_play_and_expected_amount(), test_competing_owner_approvals_create_one_credit_session(), test_continuation_migration_is_repeatable_and_preserves_live_play() (+11 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.13
Nodes (24): test_budget_duration_ignores_legacy_policy_limit_but_never_accepts_zero_price(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+16 more)

### Community 25 - "get_active_subscription"
Cohesion: 0.14
Nodes (16): create_payment_order(), debug_force_expire(), provision_default(), post, Provision default subscription for new vendor, Create Razorpay order for subscription purchase, Force expire subscription for testing - REMOVE IN PRODUCTION, Dashboard feature access is independent of staff permissions. (+8 more)

### Community 26 - "app/__init__.py"
Cohesion: 0.08
Nodes (33): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), Create test subscription for development Usage: flask test-subscription 1 base, Show subscription statistics Usage: flask subscription-stats (+25 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "pricingController.py"
Cohesion: 0.10
Nodes (33): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+25 more)

### Community 30 - "date"
Cohesion: 0.21
Nodes (6): _vendor_slot_availability(), date, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), ManualSessionEndTests, Scheduled end and midnight must not manufacture a completed session.

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "app/routes.py"
Cohesion: 0.06
Nodes (53): VendorTaxProfile, add_console(), add_extra_service_category(), check_db_connection(), create_hash_pass(), create_payout(), delete_category(), delete_console() (+45 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "terms"
Cohesion: 0.11
Nodes (25): change(), check_subscription_status(), get_limit(), get_subscription(), get_subscription_history(), get_subscription_invoice(), _invoice_number(), _parse_period_datetime() (+17 more)

### Community 36 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 37 - "CloudinaryMenuImageService"
Cohesion: 0.24
Nodes (6): CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload menu item image to Cloudinary

### Community 39 - "ConsoleService"
Cohesion: 0.23
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_service.py"
Cohesion: 0.15
Nodes (19): Package, Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, Subscription, SubscriptionStatus, create_package(), money(), activate() (+11 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "CloudinaryProfileImageService"
Cohesion: 0.27
Nodes (6): CloudinaryProfileImageService, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 44 - "cafe_slot_reservations.py"
Cohesion: 0.11
Nodes (30): CafeSlotReservation, affordable_duration(), Quote the linked console using Console Pricing, never wallet-policy amounts., Longest whole-minute session the available wallet covers, within cafe limits., session_prices(), covered_slots(), _day(), ensure_console_window() (+22 more)

### Community 63 - "subscription_controller.py"
Cohesion: 0.13
Nodes (26): check_payment_status(), Verify Razorpay payment signature and activate subscription Request body: {…, Check if a payment has been made for an order Used for QR code payments where…, verify_and_activate(), create_order(), get_order_details(), get_order_payments(), get_payment_details() (+18 more)

### Community 65 - "extensions.py"
Cohesion: 0.09
Nodes (11): PassRedemptionLog, PayAtCafeNotification, PaymentMethod, ProvisionalResult, VendorRolePermission, VerificationCheck, Cloudinary service for handling event banner images. Images are uploaded to the…, Cloudinary service for handling vendor profile images Images are uploaded to… (+3 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "booking_bridge_controller.py"
Cohesion: 0.48
Nodes (6): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status()

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 71 - "get_landing_page_vendor"
Cohesion: 0.29
Nodes (7): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, A clock boundary never completes a started session.

### Community 72 - "test_payment_methods.py"
Cohesion: 0.40
Nodes (3): methods(), fixture, Exercise the production payment-settings handlers in a disposable DB.

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 74 - "cafe_wallet_controller.py"
Cohesion: 0.17
Nodes (26): agent_continuation_quote(), cafe_customer_ids(), checkout(), checkout_details(), checkout_info(), continuation_quote(), food_context(), food_menu() (+18 more)

### Community 75 - "Console and cafe-wallet pricing"
Cohesion: 0.50
Nodes (3): Compatibility and deployment, Console and cafe-wallet pricing, Rules

### Community 78 - "Shared capacity for app, dashboard, kiosk and QR bookings"
Cohesion: 0.50
Nodes (3): Rollout, Shared capacity for app, dashboard, kiosk and QR bookings, Verification

### Community 81 - "websocket_service.py"
Cohesion: 0.27
Nodes (22): _connect_upstream(), _emit_downstream_to_vendor(), _get_next_slot_for_today(), _handle_upstream_booking(), _handle_upstream_booking_payment_update(), _handle_upstream_console_availability(), _handle_upstream_current_slot(), _handle_upstream_pay_at_cafe_event() (+14 more)

### Community 82 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

### Community 83 - "console_catalog_service.py"
Cohesion: 0.22
Nodes (20): _resolve_squad_group_for_game_name(), ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_type_overrides(), get_consoles(), _resolve_console_group_from_name() (+12 more)

### Community 85 - "subscription_commerce_controller.py"
Cohesion: 0.26
Nodes (13): authorize(), invalid(), invoice(), owned(), pay(), preview(), purchases(), before_request (+5 more)

### Community 86 - "cafe_booking_service.py"
Cohesion: 0.33
Nodes (13): CafeBookingClaim, acknowledge_booking(), existing_bookings(), _groups(), _payment_verified(), Existing paid bookings use the same PC QR and acknowledgement as wallet play., Called with the cafe/session locks held; no commit or wallet ledger writes., Keep the new and legacy views aligned, including cancellation during play. (+5 more)

### Community 87 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 88 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "_invalidate_vendor_caches"
Cohesion: 0.21
Nodes (13): assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), _invalidate_vendor_caches(), kiosk_start_session(), Start a session from kiosk using either booking_id (scan) or access_code.…, Rules: - Current IST time may be up to five minutes before scheduled start. -…, release_console() (+5 more)

### Community 90 - "cafe_owner_email.py"
Cohesion: 0.29
Nodes (7): cafe_error(), conflict(), errorhandler, register_cafe_runtime(), dispatch_owner_emails(), Transactional outbox: SMTP retries never undo an owner-approval request., send_owner_email()

### Community 94 - "payload_formatters.py"
Cohesion: 0.52
Nodes (6): format_current_slot_item(), format_upcoming_booking_from_upstream(), Any, Convert upstream booking payload into the upcomingBookings item shape, but ONLY…, _to_date_str(), _to_time_str()

### Community 95 - "websocket_controller.py"
Cohesion: 0.50
Nodes (3): handle_processed_slot(), Handle the processed event and emit a final event, on

### Community 96 - "accepted_methods"
Cohesion: 0.83
Nodes (3): accepted_methods(), canonical_method(), require_method()

### Community 98 - "internal_store_updated"
Cohesion: 0.67
Nodes (3): internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…

## Knowledge Gaps
- **41 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `KioskTests` connect `KioskTests` to `date`, `test_kiosk_runtime.py`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `Vendor` connect `vendor.py` to `app/routes.py`, `extensions.py`, `access_controller.py`, `ExtraServiceService`, `subscription_service.py`, `cafe_wallet_controller.py`, `auth`, `VendorGame`, `CafeError`, `test_subscription_commerce.py`, `test_subscription_checkout.py`, `pricingController.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `Console` connect `test_subscription_checkout.py` to `app/routes.py`, `ExtraServiceService`, `ConsoleService`, `cafe_wallet_controller.py`, `CafeError`, `vendor_games.py`, `GameService`, `test_subscription_commerce.py`, `cafe_booking_service.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._