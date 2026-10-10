# Graph Report - hfg-dashboard-service  (2026-10-10)

## Corpus Check
- 192 files · ~103,489 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1682 nodes · 4708 edges · 107 communities (96 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `866265b1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- commands.py
- datetime
- auth
- tournament_engine_service.py
- app/routes.py
- Flask
- KioskError
- KioskTests
- toggle_payment_method_for_vendor
- vendor_games.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- _require_permission
- review_controller.py
- test_shared_slot_capacity.py
- models/routes.py
- ConsoleLinkSession
- package_controller.py
- Owner PIN validation for native kiosk force exit
- test_subscription_commerce.py
- CloudinaryGameImageService
- booking_bridge.py
- test_cafe_continuations.py
- test_cafe_wallet.py
- extensions.py
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- local_window
- websocket_service.py
- 20260922_cafe_wallet.sql
- subscription_controller.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- subscription_commerce_controller.py
- get_active_subscription
- session_extensions_controller.py
- CafeError
- console_catalog_service.py
- Cafe wallets: read-only mobile app APIs
- subscription_commerce.py
- vendor_console_overrides
- vendor.py
- Game
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- passModels.py
- ConsoleService
- get_landing_page_vendor
- app/__init__.py
- test_qr_input.py
- cafe_booking_service.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- get_vendor_dashboard
- _invalidate_vendor_caches
- Subscription packages, purchases and kiosk licences
- add_or_update_bank_details
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- payload_formatters.py
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- test_owner_security.py
- Booking verification and kiosk 401 review — 10 October 2026
- subscription_service.py
- get_extra_services
- update_menu_inventory
- CloudinaryProfileImageService
- UserPass
- app
- rbac_guard.py
- models/__init__.py
- Kiosk session extensions v1 — implemented backend contract
- test_payment_methods.py
- staff_token
- websocket_controller.py
- access_controller.py
- cafe_owner_email.py
- ensure_ist
- accepted_methods
- cafePass.py
- internal_store_updated
- vendorDaySlotConfig.py

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 80 edges
2. `staff_actor()` - 41 edges
3. `Vendor` - 41 edges
4. `auth()` - 38 edges
5. `audit()` - 33 edges
6. `KioskError` - 32 edges
7. `KioskTests` - 32 edges
8. `fund()` - 29 edges
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

## Communities (107 total, 11 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (62): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+54 more)

### Community 1 - "commands.py"
Cohesion: 0.13
Nodes (29): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+21 more)

### Community 2 - "datetime"
Cohesion: 0.09
Nodes (9): PassRedemptionLog, PayAtCafeNotification, _get_next_slot_for_today(), datetime, test_activity_pages_filters_and_older_records(), test_collections_date_boundaries_and_activity_scope(), Adding hardware must not revive historical schedules or reset held capacity., EarlyStartTests (+1 more)

### Community 3 - "auth"
Cohesion: 0.25
Nodes (17): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+9 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.05
Nodes (63): Transaction, VendorTaxProfile, add_console(), add_extra_service_category(), add_pass_type(), check_db_connection(), _coerce_bool(), create_category() (+55 more)

### Community 6 - "Flask"
Cohesion: 0.08
Nodes (23): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_menu(), CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder (+15 more)

### Community 7 - "KioskError"
Cohesion: 0.19
Nodes (29): internal_send_unlock(), get, post, Authorize a specific native owner action; never end or settle a gaming session., remaining(), validate_owner_pin(), verify_kiosk_booking(), assigned_consoles() (+21 more)

### Community 8 - "KioskTests"
Cohesion: 0.05
Nodes (13): _vendor_slot_availability(), date, skipUnless, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), OwnerPinTests, KioskTests, load() (+5 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.18
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "vendor_games.py"
Cohesion: 0.08
Nodes (29): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+21 more)

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.11
Nodes (66): agent_ack(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), agent_session(), audit_history() (+58 more)

### Community 13 - "_require_permission"
Cohesion: 0.22
Nodes (20): _auth_debug(), change_owner_security(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session(), list_staff() (+12 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (14): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+6 more)

### Community 16 - "models/routes.py"
Cohesion: 0.18
Nodes (15): OpeningDay, add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor(), get_consoles(), get_device_for_console_type(), get_landing_page_vendor() (+7 more)

### Community 17 - "ConsoleLinkSession"
Cohesion: 0.25
Nodes (15): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+7 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "Owner PIN validation for native kiosk force exit"
Cohesion: 0.20
Nodes (9): Admin settings authorization (9 October 2026), Backend verification, Curl example, Error responses, Gaming session and money, Native integration sequence, Owner PIN validation for native kiosk force exit, Request (+1 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.21
Nodes (29): enforce_entitlements(), auth(), captured(), commerce(), finish(), pay(), preview(), fixture (+21 more)

### Community 21 - "CloudinaryGameImageService"
Cohesion: 0.17
Nodes (9): upload_game_image(), add_images_to_games(), CloudinaryGameImageService, Delete game cover image from Cloudinary, Service for handling game cover images Images are uploaded to the 'GAME_COVERS'…, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload game cover image to Cloudinary (+1 more)

### Community 22 - "booking_bridge.py"
Cohesion: 0.13
Nodes (20): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+12 more)

### Community 23 - "test_cafe_continuations.py"
Cohesion: 0.30
Nodes (19): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_collection_requires_completed_play_and_expected_amount(), test_competing_owner_approvals_create_one_credit_session(), test_continuation_migration_is_repeatable_and_preserves_live_play() (+11 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.13
Nodes (24): test_budget_duration_ignores_legacy_policy_limit_but_never_accepts_zero_price(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+16 more)

### Community 25 - "extensions.py"
Cohesion: 0.11
Nodes (17): AdditionalDetails, Booking, BookingExtraService, BookingSquadMember, Console, HardwareSpecification, MaintenanceStatus, PriceAndCost (+9 more)

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
Nodes (23): agent_continuation_quote(), continuation_quote(), affordable_duration(), console_durations(), Quote the linked console using Console Pricing, never wallet-policy amounts., Use the current dated console schedule as the only duration configuration., Longest whole-minute session the available wallet covers, within cafe limits., session_prices() (+15 more)

### Community 30 - "websocket_service.py"
Cohesion: 0.29
Nodes (21): _connect_upstream(), _emit_downstream_to_vendor(), _handle_upstream_booking(), _handle_upstream_booking_payment_update(), _handle_upstream_console_availability(), _handle_upstream_current_slot(), _handle_upstream_pay_at_cafe_event(), _health_check_loop() (+13 more)

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "subscription_controller.py"
Cohesion: 0.08
Nodes (42): authorize_subscription(), change(), check_payment_status(), check_subscription_status(), create_payment_order(), debug_force_expire(), get_limit(), get_subscription() (+34 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "subscription_commerce_controller.py"
Cohesion: 0.26
Nodes (14): authorize(), invalid(), invoice(), owned(), pay(), preview(), purchases(), before_request (+6 more)

### Community 36 - "get_active_subscription"
Cohesion: 0.21
Nodes (10): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), Dashboard feature access is independent of staff permissions., require_feature(), get_active_subscription(), is_subscription_active() (+2 more)

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.20
Nodes (27): answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue(), device_row() (+19 more)

### Community 38 - "CafeError"
Cohesion: 0.16
Nodes (40): adjust_wallet(), CafeAudit, CafeContinuation, CafeFoodOrder, CafeLedger, CafeOwnerEmail, CafePaymentPolicy, CafePlaySession (+32 more)

### Community 39 - "console_catalog_service.py"
Cohesion: 0.22
Nodes (20): _resolve_squad_group_for_game_name(), ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_type_overrides(), get_consoles(), _resolve_console_group_from_name() (+12 more)

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_commerce.py"
Cohesion: 0.14
Nodes (18): Package, Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, SubscriptionStatus, create_package(), money(), activate(), billing_datetime() (+10 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "vendor.py"
Cohesion: 0.10
Nodes (12): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted, PhysicalAddress (+4 more)

### Community 44 - "Game"
Cohesion: 0.15
Nodes (10): create_game(), route, Create a new game with optional image, update_game(), Game, Create Game from RAWG API - image_url gets background_image automatically!, Sync single game from RAWG API, Fetch a single page of games from RAWG API (+2 more)

### Community 63 - "passModels.py"
Cohesion: 0.11
Nodes (10): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, create_vendor_pass(), delete_vendor_pass(), Create new pass (date-based or hour-based) (+2 more)

### Community 64 - "ConsoleService"
Cohesion: 0.20
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 65 - "get_landing_page_vendor"
Cohesion: 0.22
Nodes (9): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, A clock boundary never completes a started session., financial_totals() (+1 more)

### Community 66 - "app/__init__.py"
Cohesion: 0.19
Nodes (12): Config, create_app(), _is_insecure_secret(), _validate_production_config(), kiosk_unlink(), start_expiry_worker(), linked_identity(), Independent of legacy expiry feature flags; multiple workers serialize rows. (+4 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "cafe_booking_service.py"
Cohesion: 0.33
Nodes (13): CafeBookingClaim, acknowledge_booking(), existing_bookings(), _groups(), _payment_verified(), Existing paid bookings use the same PC QR and acknowledgement as wallet play., Called with the cafe/session locks held; no commit or wallet ledger writes., Keep the new and legacy views aligned, including cancellation during play. (+5 more)

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 71 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 72 - "_invalidate_vendor_caches"
Cohesion: 0.21
Nodes (13): assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), _invalidate_vendor_caches(), kiosk_start_session(), Start a session from kiosk using either booking_id (scan) or access_code.…, Rules: - Current IST time may be up to five minutes before scheduled start. -…, release_console() (+5 more)

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

### Community 79 - "payload_formatters.py"
Cohesion: 0.52
Nodes (6): format_current_slot_item(), format_upcoming_booking_from_upstream(), Any, Convert upstream booking payload into the upcomingBookings item shape, but ONLY…, _to_date_str(), _to_time_str()

### Community 81 - "pricingController.py"
Cohesion: 0.07
Nodes (43): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+35 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.21
Nodes (27): reserve_slot(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner(), test_changed_quote_price_is_not_silently_charged() (+19 more)

### Community 83 - "test_owner_security.py"
Cohesion: 0.23
Nodes (14): install_kiosk_errors(), CafeStaffSession, VendorAccount, change(), test_account_password_synchronizes_linked_cafes_only(), test_closed_owner_session_cannot_change_credentials(), test_existing_pin_is_rotated_without_creating_duplicate(), test_other_cafe_pin_collision_is_readable() (+6 more)

### Community 85 - "Booking verification and kiosk 401 review — 10 October 2026"
Cohesion: 0.29
Nodes (6): Backend validation, Booking verification and kiosk 401 review — 10 October 2026, Confirmed failures in the supplied kiosk source, Errors, Team integration requirements (no kiosk code changed here), Unified device verification API

### Community 86 - "subscription_service.py"
Cohesion: 0.26
Nodes (16): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Subscription, change_subscription(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle() (+8 more)

### Community 87 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 88 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "CloudinaryProfileImageService"
Cohesion: 0.15
Nodes (11): delete_vendor_profile_image(), Upload profile image to Cloudinary and update VendorProfileImage table. Creates…, Delete vendor's profile image, update_profile_image(), CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in… (+3 more)

### Community 91 - "app"
Cohesion: 0.40
Nodes (6): app(), order(), payment(), fixture, parametrize, test_rejects_invalid_payment()

### Community 92 - "rbac_guard.py"
Cohesion: 0.60
Nodes (5): enforce_rbac_permissions(), _extract_vendor_id_from_request(), claim_vendor_id(), claims_permissions(), Match

### Community 95 - "Kiosk session extensions v1 — implemented backend contract"
Cohesion: 0.22
Nodes (8): Authoritative snapshot and realtime, Authorization and money, Dashboard management API, Device API sequence, Kiosk session extensions v1 — implemented backend contract, Native UX instructions, Rollout, Verification before production enablement

### Community 96 - "test_payment_methods.py"
Cohesion: 0.33
Nodes (4): methods(), fixture, Exercise the production payment-settings handlers in a disposable DB., test_all_six_methods_and_authenticated_idempotent_selection()

### Community 97 - "staff_token"
Cohesion: 0.12
Nodes (18): staff_token(), test_expired_jwt_cannot_renew_live_staff_session(), test_staff_renewal_preserves_session_and_logout_revokes_renewals(), test_staff_renewal_rechecks_scope_role_and_expiry(), offer(), pricing_api(), fixture, parametrize (+10 more)

### Community 98 - "websocket_controller.py"
Cohesion: 0.50
Nodes (3): handle_processed_slot(), Handle the processed event and emit a final event, on

### Community 99 - "access_controller.py"
Cohesion: 0.21
Nodes (16): access_conflict(), private_access_response(), after_request, errorhandler, patch, update_staff_member(), VendorStaff, create_staff() (+8 more)

### Community 100 - "cafe_owner_email.py"
Cohesion: 0.67
Nodes (3): dispatch_owner_emails(), Transactional outbox: SMTP retries never undo an owner-approval request., send_owner_email()

### Community 102 - "accepted_methods"
Cohesion: 0.83
Nodes (3): accepted_methods(), canonical_method(), require_method()

### Community 104 - "internal_store_updated"
Cohesion: 0.67
Nodes (3): internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…

## Knowledge Gaps
- **88 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `vendor.py` to `commands.py`, `auth`, `app/routes.py`, `Flask`, `KioskError`, `vendor_games.py`, `cafe_wallet_controller.py`, `models/routes.py`, `ConsoleLinkSession`, `test_subscription_commerce.py`, `extensions.py`, `session_extensions.py`, `session_extensions_controller.py`, `CafeError`, `subscription_commerce.py`, `pricingController.py`, `test_owner_security.py`, `subscription_service.py`, `app`, `models/__init__.py`, `access_controller.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `CafeError` connect `CafeError` to `event_controller.py`, `access_controller.py`, `cafe_booking_service.py`, `session_extensions_controller.py`, `app/routes.py`, `vendor.py`, `cafe_wallet_controller.py`, `_require_permission`, `ConsoleLinkSession`, `test_owner_security.py`, `extensions.py`, `session_extensions.py`, `local_window`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _88 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `event_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.055246913580246915 - nodes in this community are weakly interconnected._