# Graph Report - hfg-dashboard-service  (2026-10-10)

## Corpus Check
- 194 files · ~104,100 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1696 nodes · 4755 edges · 94 communities (84 shown, 10 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0bc4c561`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- commands.py
- datetime
- auth
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- Flask
- KioskTests
- toggle_payment_method_for_vendor
- vendor_games.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- access_controller.py
- review_controller.py
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
- extensions.py
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- cafe_slot_reservations.py
- env
- 20260922_cafe_wallet.sql
- subscription_controller.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- Website
- get_vendor_notification_preferences
- session_extensions_controller.py
- cafe_wallet_service.py
- get_vendor_passes
- Cafe wallets: read-only mobile app APIs
- subscription_service.py
- vendor_console_overrides
- vendor.py
- GameService
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- passModels.py
- ConsoleService
- get_landing_page_vendor
- cafe_audit_reports.py
- test_qr_input.py
- transaction.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- get_vendor_dashboard
- Subscription packages, purchases and kiosk licences
- add_or_update_bank_details
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- Booking verification and kiosk 401 review — 10 October 2026
- get_extra_services
- update_menu_inventory
- VendorProfileImage
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
6. `KioskError` - 32 edges
7. `fund()` - 32 edges
8. `KioskTests` - 32 edges
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

## Communities (94 total, 10 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (61): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+53 more)

### Community 1 - "commands.py"
Cohesion: 0.15
Nodes (28): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+20 more)

### Community 2 - "datetime"
Cohesion: 0.13
Nodes (7): PassRedemptionLog, PayAtCafeNotification, _get_next_slot_for_today(), datetime, Adding hardware must not revive historical schedules or reset held capacity., EarlyStartTests, Check the dashboard's production eligibility rule without booting services.

### Community 3 - "auth"
Cohesion: 0.14
Nodes (28): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+20 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.07
Nodes (54): VendorTaxProfile, add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), check_db_connection(), create_or_update_console_type_override(), create_payout() (+46 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (25): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), create_category(), create_menu_item() (+17 more)

### Community 7 - "Flask"
Cohesion: 0.05
Nodes (96): Config, ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products…, install_kiosk_errors() (+88 more)

### Community 8 - "KioskTests"
Cohesion: 0.05
Nodes (13): _vendor_slot_availability(), date, skipUnless, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), OwnerPinTests, KioskTests, load() (+5 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.18
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "vendor_games.py"
Cohesion: 0.13
Nodes (22): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_all_games(), get_available_games(), get_consoles_by_platform(), get_game_details() (+14 more)

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.10
Nodes (73): adjust_wallet(), agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation() (+65 more)

### Community 13 - "access_controller.py"
Cohesion: 0.07
Nodes (56): access_conflict(), _auth_debug(), change_owner_security(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session() (+48 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (18): local_window(), scheduled_slots(), first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas. (+10 more)

### Community 16 - "VendorGame"
Cohesion: 0.12
Nodes (9): ConsolePricingOffer, Time-based promotional pricing for console types (AvailableGames) Allows…, Check if this offer is active RIGHT NOW using IST. Returns True if current IST…, Calculate discount percentage, Convert to dictionary for API responses, Serialize VendorGame — price is always dynamically computed, Dynamically compute price from parent AvailableGame. - If an active…, Returns full pricing context: base price, offer price, offer details. Useful… (+1 more)

### Community 17 - "razorpay_service.py"
Cohesion: 0.17
Nodes (14): create_order(), get_order_details(), get_order_payments(), get_payment_details(), get_razorpay_client(), get_test_price(), Get order details from Razorpay Args: order_id: Razorpay order ID Returns:…, Get payments attached to an order from Razorpay. Returns list of payment items. (+6 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "Owner PIN validation for native kiosk force exit"
Cohesion: 0.20
Nodes (9): Admin settings authorization (9 October 2026), Backend verification, Curl example, Error responses, Gaming session and money, Native integration sequence, Owner PIN validation for native kiosk force exit, Request (+1 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.12
Nodes (43): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+35 more)

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
Cohesion: 0.14
Nodes (23): test_budget_duration_ignores_legacy_policy_limit_but_never_accepts_zero_price(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+15 more)

### Community 25 - "extensions.py"
Cohesion: 0.10
Nodes (23): AdditionalDetails, AvailableGame, Booking, BookingExtraService, BookingSquadMember, MaintenanceStatus, PriceAndCost, ProvisionalResult (+15 more)

### Community 26 - "session_extensions.py"
Cohesion: 0.12
Nodes (44): BaseSlotRelease, ExtensionQuote, ExtensionSegment, Shared kiosk continuation records. Money remains integer paise., RuntimeMutation, RuntimeSession, SessionCreditEntry, SessionNotice (+36 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "cafe_slot_reservations.py"
Cohesion: 0.19
Nodes (20): CafeSlotReservation, affordable_duration(), Quote the linked console using Console Pricing, never wallet-policy amounts., Longest whole-minute session the available wallet covers, within cafe limits., session_prices(), covered_slots(), _day(), ensure_console_window() (+12 more)

### Community 30 - "env"
Cohesion: 0.24
Nodes (6): reports(), test_console_history_includes_qr_actual_session_and_blocks_other_cafe(), test_report_filters_validate_ranges(), test_topup_and_collection_are_visible_once_with_credit_movement(), env(), fixture

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "subscription_controller.py"
Cohesion: 0.09
Nodes (38): authorize_subscription(), change(), check_payment_status(), check_subscription_status(), create_payment_order(), debug_force_expire(), get_limit(), get_subscription() (+30 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "Website"
Cohesion: 0.25
Nodes (4): PhysicalAddress, Website, Update vendor business details including website, phone, email, and address, update_business_details()

### Community 36 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.20
Nodes (27): answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue(), device_row() (+19 more)

### Community 38 - "cafe_wallet_service.py"
Cohesion: 0.11
Nodes (54): put, set_policy(), CafeAudit, CafeBookingClaim, CafeContinuation, CafeLedger, CafeOwnerEmail, CafePaymentPolicy (+46 more)

### Community 39 - "get_vendor_passes"
Cohesion: 0.33
Nodes (6): get_vendor_passes(), get_vendor_passes_by_mode(), _parse_bool_flag(), Get vendor passes grouped for frontend (hour/date based)., Backward-compatible alias of /vendor/<vendor_id>/passes., _vendor_exists()

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_service.py"
Cohesion: 0.11
Nodes (33): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Package, Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, Subscription, SubscriptionStatus, create_package() (+25 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "vendor.py"
Cohesion: 0.09
Nodes (24): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted, OpeningDay (+16 more)

### Community 44 - "GameService"
Cohesion: 0.09
Nodes (21): create_game(), route, Create a new game with optional image, update_game(), Game, Create Game from RAWG API - image_url gets background_image automatically!, add_images_to_games(), CloudinaryGameImageService (+13 more)

### Community 63 - "passModels.py"
Cohesion: 0.12
Nodes (7): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass()

### Community 64 - "ConsoleService"
Cohesion: 0.16
Nodes (6): Console, HardwareSpecification, ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

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

### Community 81 - "pricingController.py"
Cohesion: 0.08
Nodes (51): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+43 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.21
Nodes (27): reserve_slot(), test_credit_movement_and_runtime_history_do_not_duplicate_qr(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner() (+19 more)

### Community 85 - "Booking verification and kiosk 401 review — 10 October 2026"
Cohesion: 0.29
Nodes (6): Backend validation, Booking verification and kiosk 401 review — 10 October 2026, Confirmed failures in the supplied kiosk source, Errors, Team integration requirements (no kiosk code changed here), Unified device verification API

### Community 87 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 88 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "VendorProfileImage"
Cohesion: 0.12
Nodes (12): VendorProfileImage, delete_vendor_profile_image(), Upload profile image to Cloudinary and update VendorProfileImage table. Creates…, Delete vendor's profile image, update_profile_image(), CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary (+4 more)

### Community 95 - "Kiosk session extensions v1 — implemented backend contract"
Cohesion: 0.22
Nodes (8): Authoritative snapshot and realtime, Authorization and money, Dashboard management API, Device API sequence, Kiosk session extensions v1 — implemented backend contract, Native UX instructions, Rollout, Verification before production enablement

### Community 97 - "test_console_pricing.py"
Cohesion: 0.12
Nodes (14): offer(), pricing_api(), fixture, parametrize, Pricing and real wallet quote/reservation/capture regression tests., test_base_price_api_updates_wallet_quote_and_rejects_invalid(), test_console_price_drives_quote_reservation_and_capture(), test_controller_save_calculate_reject_invalid_and_squad_defaults() (+6 more)

### Community 102 - "accepted_methods"
Cohesion: 0.83
Nodes (3): accepted_methods(), canonical_method(), require_method()

## Knowledge Gaps
- **88 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `vendor.py` to `VendorProfileImage`, `commands.py`, `auth`, `Website`, `session_extensions_controller.py`, `ExtraServiceService`, `Flask`, `app/routes.py`, `subscription_service.py`, `cafe_wallet_service.py`, `cafe_wallet_controller.py`, `access_controller.py`, `VendorGame`, `pricingController.py`, `test_subscription_commerce.py`, `extensions.py`, `session_extensions.py`, `env`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `CafeError` connect `cafe_wallet_controller.py` to `ConsoleService`, `cafe_audit_reports.py`, `app/routes.py`, `session_extensions_controller.py`, `cafe_wallet_service.py`, `Flask`, `vendor.py`, `access_controller.py`, `test_subscription_commerce.py`, `extensions.py`, `session_extensions.py`, `cafe_slot_reservations.py`?**
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
  _Cohesion score 0.057124310288867254 - nodes in this community are weakly interconnected._