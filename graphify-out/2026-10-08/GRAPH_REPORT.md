# Graph Report - hfg-dashboard-service  (2026-10-08)

## Corpus Check
- 191 files · ~101,933 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1664 nodes · 4673 edges · 97 communities (86 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7daaad30`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- access_controller.py
- extensions.py
- auth
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- kiosk_security.py
- KioskTests
- toggle_payment_method_for_vendor
- commands.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- datetime
- review_controller.py
- test_shared_slot_capacity.py
- cafe_booking_service.py
- KioskError
- package_controller.py
- Owner PIN validation for native kiosk force exit
- test_subscription_commerce.py
- GameService
- booking_bridge.py
- test_cafe_continuations.py
- test_cafe_wallet.py
- test_subscription_checkout.py
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- local_window
- websocket_service.py
- 20260922_cafe_wallet.sql
- subscription_controller.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- console_catalog_service.py
- CloudinaryGameImageService
- session_extensions_controller.py
- CafeError
- ConsoleService
- Cafe wallets: read-only mobile app APIs
- subscription_service.py
- vendor_console_overrides
- BankTransferDetails
- vendor_games.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- passModels.py
- _invalidate_vendor_caches
- get_landing_page_vendor
- app/__init__.py
- test_qr_input.py
- Flask
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- console_link_session.py
- .sync_games
- Subscription packages, purchases and kiosk licences
- get_vendor_dashboard
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- payload_formatters.py
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- get_all_games
- PassRedemptionLog.py
- get_extra_services
- update_menu_inventory
- ensure_ist
- CloudinaryProfileImageService
- Kiosk session extensions v1 — implemented backend contract
- test_console_pricing.py
- accepted_methods
- cafePass.py
- UserPass

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 80 edges
2. `staff_actor()` - 41 edges
3. `Vendor` - 40 edges
4. `auth()` - 38 edges
5. `audit()` - 33 edges
6. `KioskError` - 31 edges
7. `fund()` - 29 edges
8. `local_window()` - 28 edges
9. `wallet()` - 28 edges
10. `KioskTests` - 28 edges

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

## Communities (97 total, 11 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (57): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+49 more)

### Community 1 - "access_controller.py"
Cohesion: 0.08
Nodes (53): access_conflict(), _auth_debug(), change_owner_security(), create_staff_member(), delete_staff_member(), _ensure_vendor_exists(), get_permissions(), issue_owner_session() (+45 more)

### Community 2 - "extensions.py"
Cohesion: 0.06
Nodes (31): PayoutTransaction, BusinessRegistration, Document, DocumentSubmitted, OpeningDay, PhysicalAddress, ProvisionalResult, add_console() (+23 more)

### Community 3 - "auth"
Cohesion: 0.20
Nodes (23): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+15 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "app/routes.py"
Cohesion: 0.05
Nodes (64): Transaction, VendorDaySlotConfig, VendorTaxProfile, check_db_connection(), _coerce_bool(), create_category(), create_menu_item(), create_or_update_console_type_override() (+56 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (25): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), delete_category(), delete_extra_service_category() (+17 more)

### Community 7 - "kiosk_security.py"
Cohesion: 0.18
Nodes (27): internal_send_unlock(), internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…, get, post, Authorize immediate native kiosk exit; never end or settle a gaming session., remaining() (+19 more)

### Community 8 - "KioskTests"
Cohesion: 0.06
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
Cohesion: 0.10
Nodes (68): agent_ack(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), agent_session(), audit_history() (+60 more)

### Community 13 - "datetime"
Cohesion: 0.18
Nodes (6): PayAtCafeNotification, _get_next_slot_for_today(), datetime, Adding hardware must not revive historical schedules or reset held capacity., EarlyStartTests, Check the dashboard's production eligibility rule without booting services.

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (14): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+6 more)

### Community 16 - "cafe_booking_service.py"
Cohesion: 0.17
Nodes (20): CafeBookingClaim, CafeFoodOrder, CafeOwnerEmail, CafePlaySession, Cafe money is stored in integer paise; ledger and audit records are immutable., acknowledge_booking(), existing_bookings(), _groups() (+12 more)

### Community 17 - "KioskError"
Cohesion: 0.14
Nodes (26): before_request, require_tournament_plan(), authorize(), invalid(), invoice(), owned(), pay(), preview() (+18 more)

### Community 18 - "package_controller.py"
Cohesion: 0.15
Nodes (19): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+11 more)

### Community 19 - "Owner PIN validation for native kiosk force exit"
Cohesion: 0.22
Nodes (8): Backend verification, Curl example, Error responses, Gaming session and money, Native integration sequence, Owner PIN validation for native kiosk force exit, Request, Success: HTTP 200

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.13
Nodes (42): get_pcs(), link_pc(), get, post, unlink_pc(), vendor_required(), close_link(), count_active_links() (+34 more)

### Community 21 - "GameService"
Cohesion: 0.21
Nodes (9): create_game(), route, Create a new game with optional image, update_game(), Game, GameService, Get all vendor games grouped by game. price_per_hour is dynamically computed…, Get all consoles for a specific platform (PC, PS5, Xbox, VR) (+1 more)

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
Cohesion: 0.12
Nodes (16): AdditionalDetails, BookingExtraService, MaintenanceStatus, PriceAndCost, Image, app(), order(), payment() (+8 more)

### Community 26 - "session_extensions.py"
Cohesion: 0.13
Nodes (42): BaseSlotRelease, ExtensionQuote, ExtensionSegment, Shared kiosk continuation records. Money remains integer paise., RuntimeMutation, RuntimeSession, SessionCreditEntry, SessionNotice (+34 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "local_window"
Cohesion: 0.21
Nodes (19): agent_continuation_quote(), CafeSlotReservation, console_durations(), Quote the linked console using Console Pricing, never wallet-policy amounts., Use the current dated console schedule as the only duration configuration., session_prices(), covered_slots(), _day() (+11 more)

### Community 30 - "websocket_service.py"
Cohesion: 0.29
Nodes (21): _connect_upstream(), _emit_downstream_to_vendor(), _handle_upstream_booking(), _handle_upstream_booking_payment_update(), _handle_upstream_console_availability(), _handle_upstream_current_slot(), _handle_upstream_pay_at_cafe_event(), _health_check_loop() (+13 more)

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "subscription_controller.py"
Cohesion: 0.07
Nodes (47): change(), check_payment_status(), check_subscription_status(), create_payment_order(), debug_force_expire(), get_limit(), get_subscription(), get_subscription_history() (+39 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "console_catalog_service.py"
Cohesion: 0.20
Nodes (19): _resolve_squad_group_for_game_name(), ConsoleCatalog, VendorConsoleOverride, get_console_pricing(), get_consoles(), get_device_for_console_type(), _resolve_console_group_from_name(), update_console_pricing() (+11 more)

### Community 36 - "CloudinaryGameImageService"
Cohesion: 0.17
Nodes (9): upload_game_image(), add_images_to_games(), CloudinaryGameImageService, Delete game cover image from Cloudinary, Service for handling game cover images Images are uploaded to the 'GAME_COVERS'…, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload game cover image to Cloudinary (+1 more)

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.20
Nodes (27): answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue(), device_row() (+19 more)

### Community 38 - "CafeError"
Cohesion: 0.17
Nodes (37): adjust_wallet(), put, set_policy(), CafeAudit, CafeContinuation, CafeLedger, CafePaymentPolicy, CafeShift (+29 more)

### Community 39 - "ConsoleService"
Cohesion: 0.11
Nodes (12): AvailableGame, Booking, BookingSquadMember, HardwareSpecification, Slot, add_console(), get_console(), update_console() (+4 more)

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_service.py"
Cohesion: 0.13
Nodes (32): Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, Subscription, activate(), billing_datetime(), check_base(), paise(), preview() (+24 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "BankTransferDetails"
Cohesion: 0.14
Nodes (12): BankTransferDetails, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), add_or_update_bank_details(), _ensure_bank_details_audit_table(), get_bank_details(), get_bank_details_history(), _mask_account_number() (+4 more)

### Community 44 - "vendor_games.py"
Cohesion: 0.18
Nodes (18): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games() (+10 more)

### Community 63 - "passModels.py"
Cohesion: 0.12
Nodes (7): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass()

### Community 64 - "_invalidate_vendor_caches"
Cohesion: 0.21
Nodes (13): assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), _invalidate_vendor_caches(), kiosk_start_session(), Start a session from kiosk using either booking_id (scan) or access_code.…, Rules: - Current IST time may be up to five minutes before scheduled start. -…, release_console() (+5 more)

### Community 65 - "get_landing_page_vendor"
Cohesion: 0.22
Nodes (9): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, A clock boundary never completes a started session., financial_totals() (+1 more)

### Community 66 - "app/__init__.py"
Cohesion: 0.24
Nodes (9): Config, create_app(), _is_insecure_secret(), _validate_production_config(), start_expiry_worker(), Independent of legacy expiry feature flags; multiple workers serialize rows., start_worker(), Authenticated app session stream; user room is derived from signed claims. (+1 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "Flask"
Cohesion: 0.12
Nodes (11): handle_processed_slot(), Handle the processed event and emit a final event, User, Flask, on, env(), fixture, methods() (+3 more)

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 72 - ".sync_games"
Cohesion: 0.25
Nodes (4): Create Game from RAWG API - image_url gets background_image automatically!, Sync single game from RAWG API, Fetch a single page of games from RAWG API, Sync games from RAWG API

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 74 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

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
Nodes (44): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+36 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.21
Nodes (27): reserve_slot(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner(), test_changed_quote_price_is_not_silently_charged() (+19 more)

### Community 83 - "get_all_games"
Cohesion: 0.50
Nodes (3): get_all_games(), Get all games ordered by name, Search games by name (case-insensitive, partial match)

### Community 86 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 87 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

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
- **82 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+77 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `extensions.py` to `access_controller.py`, `auth`, `Flask`, `session_extensions_controller.py`, `ExtraServiceService`, `kiosk_security.py`, `console_link_session.py`, `ConsoleService`, `commands.py`, `BankTransferDetails`, `cafe_wallet_controller.py`, `subscription_service.py`, `app/routes.py`, `CafeError`, `pricingController.py`, `test_subscription_commerce.py`, `test_subscription_checkout.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `CafeError` connect `CafeError` to `access_controller.py`, `extensions.py`, `Flask`, `app/routes.py`, `session_extensions_controller.py`, `kiosk_security.py`, `cafe_wallet_controller.py`, `cafe_booking_service.py`, `session_extensions.py`, `local_window`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _82 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `event_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.061621621621621624 - nodes in this community are weakly interconnected._