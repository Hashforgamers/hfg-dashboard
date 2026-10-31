# Graph Report - hfg-dashboard-service  (2026-10-31)

## Corpus Check
- 200 files · ~106,282 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1743 nodes · 4921 edges · 106 communities (94 shown, 12 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 111 edges (avg confidence: 0.61)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e64fe8d4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- Flask
- EarlyStartTests
- auth
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- commands.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- access_controller.py
- subscription_commerce.py
- test_shared_slot_capacity.py
- subscription_controller.py
- cafe_booking_service.py
- package_controller.py
- Owner PIN validation for native kiosk force exit
- test_subscription_commerce.py
- CloudinaryMenuImageService
- booking_bridge.py
- test_cafe_continuations.py
- test_cafe_wallet.py
- ConsoleService
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- _invalidate_vendor_caches
- review_controller.py
- 20260922_cafe_wallet.sql
- razorpay_service.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- test_subscription_checkout.py
- CloudinaryGameImageService
- session_extensions_controller.py
- CafeError
- subscription_service.py
- Cafe wallets: read-only mobile app APIs
- models/routes.py
- vendor_console_overrides
- extensions.py
- vendor_games.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- passModels.py
- console_catalog_service.py
- test_owner_security.py
- cafe_audit_reports.py
- test_qr_input.py
- test_console_pricing.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- get_vendor_dashboard
- vendor_pc_controller.py
- Subscription packages, purchases and kiosk licences
- BankTransferDetails
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- get_active_subscription
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- RAWGSyncService
- Booking verification and kiosk 401 review — 10 October 2026
- env
- get_extra_services
- update_menu_inventory
- CloudinaryProfileImageService
- UserPass
- register_cafe_runtime
- VendorStaff
- test_cafe_display_name.py
- Kiosk session extensions v1 — implemented backend contract
- ready
- Cafe display names
- PassRedemptionLog
- access_conflict
- private_access_response
- accepted_methods
- cafePass.py

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 86 edges
2. `staff_actor()` - 45 edges
3. `Vendor` - 43 edges
4. `auth()` - 40 edges
5. `KioskTests` - 38 edges
6. `KioskError` - 36 edges
7. `audit()` - 33 edges
8. `fund()` - 33 edges
9. `local_window()` - 29 edges
10. `staff_token()` - 28 edges

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

## Communities (106 total, 12 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (61): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+53 more)

### Community 1 - "Flask"
Cohesion: 0.15
Nodes (19): Config, create_app(), _is_insecure_secret(), _validate_production_config(), enforce_rbac_permissions(), _extract_vendor_id_from_request(), install_cafe_audit_hooks(), Audit existing pricing/staff mutations in their database commit for configured… (+11 more)

### Community 3 - "auth"
Cohesion: 0.14
Nodes (32): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+24 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.06
Nodes (54): Transaction, VendorDaySlotConfig, VendorTaxProfile, _build_session_identifier(), check_db_connection(), _coerce_bool(), _default_vendor_notification_preferences(), _derive_booking_outcome() (+46 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.08
Nodes (23): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), create_category(), create_menu_item() (+15 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.05
Nodes (96): ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products…, command_ack(), pending_commands() (+88 more)

### Community 8 - "KioskTests"
Cohesion: 0.05
Nodes (13): _vendor_slot_availability(), date, skipUnless, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), OwnerPinTests, KioskTests, load() (+5 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.20
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "commands.py"
Cohesion: 0.13
Nodes (29): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+21 more)

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.11
Nodes (65): agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), audit_history() (+57 more)

### Community 13 - "access_controller.py"
Cohesion: 0.19
Nodes (30): _auth_debug(), change_owner_security(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session(), list_staff() (+22 more)

### Community 14 - "subscription_commerce.py"
Cohesion: 0.14
Nodes (18): Package, Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, SubscriptionStatus, create_package(), money(), activate(), billing_datetime() (+10 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.11
Nodes (15): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+7 more)

### Community 16 - "subscription_controller.py"
Cohesion: 0.14
Nodes (25): invoice(), change(), check_subscription_status(), get_limit(), get_subscription(), get_subscription_history(), get_subscription_invoice(), _invoice_number() (+17 more)

### Community 17 - "cafe_booking_service.py"
Cohesion: 0.33
Nodes (13): CafeBookingClaim, acknowledge_booking(), existing_bookings(), _groups(), _payment_verified(), Existing paid bookings use the same PC QR and acknowledgement as wallet play., Called with the cafe/session locks held; no commit or wallet ledger writes., Keep the new and legacy views aligned, including cancellation during play. (+5 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

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

### Community 25 - "ConsoleService"
Cohesion: 0.23
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 26 - "session_extensions.py"
Cohesion: 0.11
Nodes (49): CafeSlotReservation, BaseSlotRelease, ExtensionQuote, ExtensionSegment, Shared kiosk continuation records. Money remains integer paise., RuntimeSession, SessionCreditEntry, SessionNotice (+41 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "_invalidate_vendor_caches"
Cohesion: 0.13
Nodes (21): add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), delete_console(), delete_vendor_pass(), get_device_for_console_type(), _invalidate_vendor_caches() (+13 more)

### Community 30 - "review_controller.py"
Cohesion: 0.27
Nodes (16): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+8 more)

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "razorpay_service.py"
Cohesion: 0.15
Nodes (16): check_payment_status(), Check if a payment has been made for an order Used for QR code payments where…, create_order(), get_order_details(), get_order_payments(), get_payment_details(), get_razorpay_client(), get_test_price() (+8 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "test_subscription_checkout.py"
Cohesion: 0.12
Nodes (19): AdditionalDetails, Booking, BookingExtraService, BookingSquadMember, HardwareSpecification, MaintenanceStatus, PriceAndCost, Slot (+11 more)

### Community 36 - "CloudinaryGameImageService"
Cohesion: 0.14
Nodes (13): create_game(), route, Create a new game with optional image, update_game(), upload_game_image(), add_images_to_games(), CloudinaryGameImageService, Delete game cover image from Cloudinary (+5 more)

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.18
Nodes (31): answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue(), device_row() (+23 more)

### Community 38 - "CafeError"
Cohesion: 0.12
Nodes (53): adjust_wallet(), food_order(), put, set_policy(), CafeAudit, CafeContinuation, CafeFoodOrder, CafeLedger (+45 more)

### Community 39 - "subscription_service.py"
Cohesion: 0.26
Nodes (16): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Subscription, change_subscription(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle() (+8 more)

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "models/routes.py"
Cohesion: 0.18
Nodes (15): OpeningDay, add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor(), get_consoles(), get_device_for_console_type(), get_landing_page_vendor() (+7 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "extensions.py"
Cohesion: 0.07
Nodes (15): BusinessRegistration, Document, DocumentSubmitted, PayAtCafeNotification, PhysicalAddress, ProvisionalResult, Timing, Image (+7 more)

### Community 44 - "vendor_games.py"
Cohesion: 0.07
Nodes (31): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+23 more)

### Community 63 - "passModels.py"
Cohesion: 0.11
Nodes (9): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass(), create_vendor_pass() (+1 more)

### Community 64 - "console_catalog_service.py"
Cohesion: 0.25
Nodes (18): ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_type_overrides(), get_consoles(), ensure_default_console_catalog_seed(), get_merged_console_catalog() (+10 more)

### Community 65 - "test_owner_security.py"
Cohesion: 0.25
Nodes (13): install_kiosk_errors(), CafeStaffSession, change(), test_account_password_synchronizes_linked_cafes_only(), test_closed_owner_session_cannot_change_credentials(), test_existing_pin_is_rotated_without_creating_duplicate(), test_other_cafe_pin_collision_is_readable(), test_owner_password_requires_current_password() (+5 more)

### Community 66 - "cafe_audit_reports.py"
Cohesion: 0.60
Nodes (5): bounds(), console_history(), ledger_report(), page_query(), Read-only movement ledger and per-console usage history; no synthetic payments.

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "test_console_pricing.py"
Cohesion: 0.16
Nodes (10): offer(), pricing_api(), fixture, parametrize, Pricing and real wallet quote/reservation/capture regression tests., test_console_price_drives_quote_reservation_and_capture(), test_invalid_prices_rejected(), test_offer_window_midnight_boundaries_lowest_price_and_lowered_base() (+2 more)

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 71 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 72 - "vendor_pc_controller.py"
Cohesion: 0.29
Nodes (12): get_pcs(), link_pc(), get, post, unlink_pc(), vendor_required(), close_link(), create_link() (+4 more)

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 74 - "BankTransferDetails"
Cohesion: 0.11
Nodes (15): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), add_or_update_bank_details(), create_payout(), _ensure_bank_details_audit_table(), get_bank_details() (+7 more)

### Community 75 - "Console and cafe-wallet pricing"
Cohesion: 0.50
Nodes (3): Compatibility and deployment, Console and cafe-wallet pricing, Rules

### Community 78 - "Shared capacity for app, dashboard, kiosk and QR bookings"
Cohesion: 0.50
Nodes (3): Rollout, Shared capacity for app, dashboard, kiosk and QR bookings, Verification

### Community 79 - "get_active_subscription"
Cohesion: 0.18
Nodes (11): create_payment_order(), debug_force_expire(), provision_default(), post, Provision default subscription for new vendor, Create Razorpay order for subscription purchase, Force expire subscription for testing - REMOVE IN PRODUCTION, Dashboard feature access is independent of staff permissions. (+3 more)

### Community 81 - "pricingController.py"
Cohesion: 0.07
Nodes (46): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+38 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.21
Nodes (27): reserve_slot(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner(), test_changed_quote_price_is_not_silently_charged() (+19 more)

### Community 83 - "RAWGSyncService"
Cohesion: 0.25
Nodes (5): Create Game from RAWG API - image_url gets background_image automatically!, Sync single game from RAWG API, Fetch a single page of games from RAWG API, Sync games from RAWG API, RAWGSyncService

### Community 85 - "Booking verification and kiosk 401 review — 10 October 2026"
Cohesion: 0.29
Nodes (6): Backend validation, Booking verification and kiosk 401 review — 10 October 2026, Confirmed failures in the supplied kiosk source, Errors, Team integration requirements (no kiosk code changed here), Unified device verification API

### Community 86 - "env"
Cohesion: 0.15
Nodes (10): reports(), test_console_history_includes_qr_actual_session_and_blocks_other_cafe(), test_credit_movement_and_runtime_history_do_not_duplicate_qr(), test_report_filters_validate_ranges(), test_topup_and_collection_are_visible_once_with_credit_movement(), env(), fixture, methods() (+2 more)

### Community 87 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 88 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "CloudinaryProfileImageService"
Cohesion: 0.15
Nodes (11): delete_vendor_profile_image(), Upload profile image to Cloudinary and update VendorProfileImage table. Creates…, Delete vendor's profile image, update_profile_image(), CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in… (+3 more)

### Community 91 - "register_cafe_runtime"
Cohesion: 0.33
Nodes (6): cafe_error(), conflict(), errorhandler, register_cafe_runtime(), dispatch_owner_emails(), send_owner_email()

### Community 92 - "VendorStaff"
Cohesion: 0.28
Nodes (3): PaymentMethod, VendorStaff, verify_staff_pin()

### Community 94 - "test_cafe_display_name.py"
Cohesion: 0.32
Nodes (5): production_public_name(), parametrize, Exercise the production business-details handler against isolated SQL storage., test_all_public_name_consumers_have_the_same_fallback(), test_invalid_display_name_does_not_change_business_or_public_name()

### Community 95 - "Kiosk session extensions v1 — implemented backend contract"
Cohesion: 0.22
Nodes (8): Authoritative snapshot and realtime, Authorization and money, Dashboard management API, Device API sequence, Kiosk session extensions v1 — implemented backend contract, Native UX instructions, Rollout, Verification before production enablement

### Community 96 - "ready"
Cohesion: 0.50
Nodes (4): agent_session(), dispatch(), ready(), Read-only canonical session view; never infer device acknowledgement from…

### Community 97 - "Cafe display names"
Cohesion: 0.50
Nodes (3): Cafe display names, Release order, Validation

### Community 102 - "accepted_methods"
Cohesion: 0.83
Nodes (3): accepted_methods(), canonical_method(), require_method()

## Knowledge Gaps
- **90 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+85 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `KioskTests` connect `KioskTests` to `websocket_service.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `CafeError` connect `CafeError` to `test_owner_security.py`, `cafe_audit_reports.py`, `app/routes.py`, `session_extensions_controller.py`, `websocket_service.py`, `extensions.py`, `cafe_wallet_controller.py`, `access_controller.py`, `vendor_games.py`, `cafe_booking_service.py`, `session_extensions.py`, `review_controller.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `Vendor` connect `extensions.py` to `Flask`, `auth`, `app/routes.py`, `ExtraServiceService`, `websocket_service.py`, `commands.py`, `cafe_wallet_controller.py`, `access_controller.py`, `subscription_commerce.py`, `test_subscription_commerce.py`, `session_extensions.py`, `test_subscription_checkout.py`, `session_extensions_controller.py`, `CafeError`, `subscription_service.py`, `models/routes.py`, `vendor_games.py`, `test_owner_security.py`, `BankTransferDetails`, `pricingController.py`, `env`, `VendorStaff`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Flask` (e.g. with `api()` and `env()`) actually correct?**
  _`Flask` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _90 weakly-connected nodes found - possible documentation gaps or missing edges._