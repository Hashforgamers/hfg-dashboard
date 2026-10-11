# Graph Report - hfg-dashboard-service  (2026-10-10)

## Corpus Check
- 194 files · ~104,124 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1697 nodes · 4757 edges · 98 communities (87 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ebcb0f2c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- Flask
- extensions.py
- auth
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- vendor_games.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- access_controller.py
- subscription_commerce.py
- test_shared_slot_capacity.py
- VendorGame
- razorpay_service.py
- package_controller.py
- Owner PIN validation for native kiosk force exit
- test_subscription_commerce.py
- CloudinaryMenuImageService
- booking_bridge.py
- test_cafe_continuations.py
- test_cafe_wallet.py
- test_subscription_checkout.py
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- local_window
- env
- 20260922_cafe_wallet.sql
- subscription_controller.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- PhysicalAddress
- get_vendor_notification_preferences
- session_extensions_controller.py
- CafeError
- get_vendor_passes
- Cafe wallets: read-only mobile app APIs
- subscription_service.py
- vendor_console_overrides
- vendor.py
- Console
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- passModels.py
- ConsoleService
- get_landing_page_vendor
- cafe_audit_reports.py
- test_qr_input.py
- Transaction
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- get_vendor_dashboard
- ConsoleLinkSession
- Subscription packages, purchases and kiosk licences
- add_or_update_bank_details
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- is_subscription_active
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- PayoutTransaction
- Booking verification and kiosk 401 review — 10 October 2026
- vendorTaxProfile.py
- get_extra_services
- update_menu_inventory
- CloudinaryProfileImageService
- UserPass
- Kiosk session extensions v1 — implemented backend contract
- test_console_pricing.py
- accepted_methods
- cafePass.py
- vendorDaySlotConfig.py

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 83 edges
2. `staff_actor()` - 43 edges
3. `Vendor` - 41 edges
4. `auth()` - 38 edges
5. `audit()` - 33 edges
6. `KioskTests` - 33 edges
7. `KioskError` - 32 edges
8. `fund()` - 32 edges
9. `local_window()` - 28 edges
10. `_invalidate_vendor_caches()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `security()` --indirect_call--> `cafe_error()`  [INFERRED]
  tests/test_owner_security.py → app/controllers/cafe_wallet_controller.py
- `test_postgres_concurrent_checkout_and_legacy_guards()` --indirect_call--> `checkout()`  [INFERRED]
  tests/test_cafe_wallet.py → app/controllers/cafe_wallet_controller.py
- `env()` --calls--> `Console`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console.py
- `test_postgres_concurrent_links_cannot_exceed_purchased_limit()` --calls--> `Console`  [INFERRED]
  tests/test_subscription_commerce.py → app/models/console.py
- `env()` --calls--> `ConsoleLinkSession`  [INFERRED]
  tests/test_cafe_wallet.py → app/models/console_link_session.py

## Import Cycles
- None detected.

## Communities (98 total, 11 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (56): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+48 more)

### Community 1 - "Flask"
Cohesion: 0.15
Nodes (14): Config, create_app(), _is_insecure_secret(), _validate_production_config(), install_cafe_audit_hooks(), Cloudinary service for handling event banner images. Images are uploaded to the…, Cloudinary service for handling vendor profile images Images are uploaded to…, start_expiry_worker() (+6 more)

### Community 2 - "extensions.py"
Cohesion: 0.09
Nodes (9): PassRedemptionLog, PayAtCafeNotification, ProvisionalResult, VerificationCheck, Transactional outbox: SMTP retries never undo an owner-approval request., datetime, Adding hardware must not revive historical schedules or reset held capacity., EarlyStartTests (+1 more)

### Community 3 - "auth"
Cohesion: 0.15
Nodes (30): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+22 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "app/routes.py"
Cohesion: 0.08
Nodes (50): add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), check_db_connection(), create_or_update_console_type_override(), create_vendor_pass(), deactivate_console_type_override() (+42 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (25): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), create_category(), create_menu_item() (+17 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.06
Nodes (89): before_request, require_tournament_plan(), ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products… (+81 more)

### Community 8 - "KioskTests"
Cohesion: 0.06
Nodes (12): _vendor_slot_availability(), date, skipUnless, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), OwnerPinTests, KioskTests, load() (+4 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.20
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "vendor_games.py"
Cohesion: 0.15
Nodes (21): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+13 more)

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.10
Nodes (71): agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), agent_session() (+63 more)

### Community 13 - "access_controller.py"
Cohesion: 0.05
Nodes (84): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+76 more)

### Community 14 - "subscription_commerce.py"
Cohesion: 0.17
Nodes (17): Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, activate(), billing_datetime(), check_base(), paise(), preview(), public_quote() (+9 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (14): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+6 more)

### Community 16 - "VendorGame"
Cohesion: 0.13
Nodes (9): ConsolePricingOffer, Time-based promotional pricing for console types (AvailableGames) Allows…, Check if this offer is active RIGHT NOW using IST. Returns True if current IST…, Calculate discount percentage, Convert to dictionary for API responses, Serialize VendorGame — price is always dynamically computed, Dynamically compute price from parent AvailableGame. - If an active…, Returns full pricing context: base price, offer price, offer details. Useful… (+1 more)

### Community 17 - "razorpay_service.py"
Cohesion: 0.19
Nodes (12): create_order(), get_order_details(), get_payment_details(), get_razorpay_client(), get_test_price(), Get order details from Razorpay Args: order_id: Razorpay order ID Returns:…, Create a Razorpay order for subscription payment Args: amount: Amount in INR…, Verify Razorpay payment signature for security Args: order_id: Razorpay order… (+4 more)

### Community 18 - "package_controller.py"
Cohesion: 0.15
Nodes (19): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+11 more)

### Community 19 - "Owner PIN validation for native kiosk force exit"
Cohesion: 0.20
Nodes (9): Admin settings authorization (9 October 2026), Backend verification, Curl example, Error responses, Gaming session and money, Native integration sequence, Owner PIN validation for native kiosk force exit, Request (+1 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.21
Nodes (29): enforce_entitlements(), auth(), captured(), commerce(), finish(), pay(), preview(), fixture (+21 more)

### Community 21 - "CloudinaryMenuImageService"
Cohesion: 0.24
Nodes (6): CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload menu item image to Cloudinary

### Community 22 - "booking_bridge.py"
Cohesion: 0.13
Nodes (20): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+12 more)

### Community 23 - "test_cafe_continuations.py"
Cohesion: 0.30
Nodes (19): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_collection_requires_completed_play_and_expected_amount(), test_competing_owner_approvals_create_one_credit_session(), test_continuation_migration_is_repeatable_and_preserves_live_play() (+11 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.13
Nodes (24): test_budget_duration_ignores_legacy_policy_limit_but_never_accepts_zero_price(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+16 more)

### Community 25 - "test_subscription_checkout.py"
Cohesion: 0.10
Nodes (21): AdditionalDetails, AvailableGame, Booking, BookingExtraService, BookingSquadMember, HardwareSpecification, MaintenanceStatus, PriceAndCost (+13 more)

### Community 26 - "session_extensions.py"
Cohesion: 0.12
Nodes (43): BaseSlotRelease, ExtensionQuote, ExtensionSegment, Shared kiosk continuation records. Money remains integer paise., RuntimeMutation, RuntimeSession, SessionCreditEntry, SessionNotice (+35 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "local_window"
Cohesion: 0.19
Nodes (21): CafeSlotReservation, affordable_duration(), Quote the linked console using Console Pricing, never wallet-policy amounts., Longest whole-minute session the available wallet covers, within cafe limits., session_prices(), covered_slots(), _day(), ensure_console_window() (+13 more)

### Community 30 - "env"
Cohesion: 0.15
Nodes (9): reports(), test_console_history_includes_qr_actual_session_and_blocks_other_cafe(), test_report_filters_validate_ranges(), test_topup_and_collection_are_visible_once_with_credit_movement(), env(), fixture, methods(), fixture (+1 more)

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "subscription_controller.py"
Cohesion: 0.12
Nodes (28): change(), check_payment_status(), check_subscription_status(), create_payment_order(), debug_force_expire(), get_limit(), get_subscription(), get_subscription_history() (+20 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "PhysicalAddress"
Cohesion: 0.40
Nodes (3): PhysicalAddress, Update vendor business details including website, phone, email, and address, update_business_details()

### Community 36 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.12
Nodes (43): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+35 more)

### Community 38 - "CafeError"
Cohesion: 0.13
Nodes (54): adjust_wallet(), collect_food(), food_order(), CafeAudit, CafeBookingClaim, CafeContinuation, CafeFoodOrder, CafeLedger (+46 more)

### Community 39 - "get_vendor_passes"
Cohesion: 0.33
Nodes (6): get_vendor_passes(), get_vendor_passes_by_mode(), _parse_bool_flag(), Get vendor passes grouped for frontend (hour/date based)., Backward-compatible alias of /vendor/<vendor_id>/passes., _vendor_exists()

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_service.py"
Cohesion: 0.26
Nodes (16): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Subscription, change_subscription(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle() (+8 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "vendor.py"
Cohesion: 0.08
Nodes (26): BankTransferDetails, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted, OpeningDay, add_console() (+18 more)

### Community 44 - "Console"
Cohesion: 0.08
Nodes (23): create_game(), route, Create a new game with optional image, update_game(), Console, Game, Create Game from RAWG API - image_url gets background_image automatically!, add_images_to_games() (+15 more)

### Community 63 - "passModels.py"
Cohesion: 0.12
Nodes (7): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass()

### Community 64 - "ConsoleService"
Cohesion: 0.20
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 65 - "get_landing_page_vendor"
Cohesion: 0.22
Nodes (9): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, A clock boundary never completes a started session., financial_totals() (+1 more)

### Community 66 - "cafe_audit_reports.py"
Cohesion: 0.60
Nodes (5): bounds(), console_history(), ledger_report(), page_query(), Read-only movement ledger and per-console usage history; no synthetic payments.

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 71 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 72 - "ConsoleLinkSession"
Cohesion: 0.25
Nodes (15): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+7 more)

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 74 - "add_or_update_bank_details"
Cohesion: 0.25
Nodes (9): add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number(), _mask_upi_id(), Get vendor's bank transfer details, Get historized changes for vendor bank/UPI details. (+1 more)

### Community 75 - "Console and cafe-wallet pricing"
Cohesion: 0.50
Nodes (3): Compatibility and deployment, Console and cafe-wallet pricing, Rules

### Community 78 - "Shared capacity for app, dashboard, kiosk and QR bookings"
Cohesion: 0.50
Nodes (3): Rollout, Shared capacity for app, dashboard, kiosk and QR bookings, Verification

### Community 79 - "is_subscription_active"
Cohesion: 0.38
Nodes (6): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), is_subscription_active(), Check if vendor has an active, non-expired subscription Returns: tuple: (bool:…

### Community 81 - "pricingController.py"
Cohesion: 0.07
Nodes (54): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+46 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.22
Nodes (26): reserve_slot(), test_credit_movement_and_runtime_history_do_not_duplicate_qr(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner() (+18 more)

### Community 83 - "PayoutTransaction"
Cohesion: 0.50
Nodes (3): PayoutTransaction, create_payout(), Create a new payout transaction

### Community 85 - "Booking verification and kiosk 401 review — 10 October 2026"
Cohesion: 0.29
Nodes (6): Backend validation, Booking verification and kiosk 401 review — 10 October 2026, Confirmed failures in the supplied kiosk source, Errors, Team integration requirements (no kiosk code changed here), Unified device verification API

### Community 87 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 88 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "CloudinaryProfileImageService"
Cohesion: 0.18
Nodes (10): delete_vendor_profile_image(), Upload profile image to Cloudinary and update VendorProfileImage table. Creates…, Delete vendor's profile image, update_profile_image(), CloudinaryProfileImageService, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available (+2 more)

### Community 95 - "Kiosk session extensions v1 — implemented backend contract"
Cohesion: 0.22
Nodes (8): Authoritative snapshot and realtime, Authorization and money, Dashboard management API, Device API sequence, Kiosk session extensions v1 — implemented backend contract, Native UX instructions, Rollout, Verification before production enablement

### Community 97 - "test_console_pricing.py"
Cohesion: 0.16
Nodes (10): offer(), pricing_api(), fixture, parametrize, Pricing and real wallet quote/reservation/capture regression tests., test_console_price_drives_quote_reservation_and_capture(), test_invalid_prices_rejected(), test_offer_window_midnight_boundaries_lowest_price_and_lowered_base() (+2 more)

### Community 102 - "accepted_methods"
Cohesion: 0.83
Nodes (3): accepted_methods(), canonical_method(), require_method()

## Knowledge Gaps
- **88 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `KioskTests` connect `KioskTests` to `Flask`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Vendor` connect `vendor.py` to `auth`, `app/routes.py`, `ExtraServiceService`, `websocket_service.py`, `cafe_wallet_controller.py`, `access_controller.py`, `subscription_commerce.py`, `VendorGame`, `test_subscription_commerce.py`, `test_subscription_checkout.py`, `session_extensions.py`, `env`, `PhysicalAddress`, `session_extensions_controller.py`, `CafeError`, `subscription_service.py`, `ConsoleLinkSession`, `pricingController.py`, `PayoutTransaction`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `CafeError` connect `CafeError` to `cafe_audit_reports.py`, `app/routes.py`, `session_extensions_controller.py`, `ConsoleLinkSession`, `vendor.py`, `cafe_wallet_controller.py`, `access_controller.py`, `Console`, `session_extensions.py`, `local_window`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _88 weakly-connected nodes found - possible documentation gaps or missing edges._