# Graph Report - hfg-dashboard-service  (2026-10-09)

## Corpus Check
- 191 files · ~102,145 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1668 nodes · 4679 edges · 99 communities (89 shown, 10 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9905f71a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- access_controller.py
- vendor.py
- auth
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- kiosk_security.py
- KioskTests
- toggle_payment_method_for_vendor
- vendor_games.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- extensions.py
- review_controller.py
- test_shared_slot_capacity.py
- audit
- KioskError
- package_controller.py
- Owner PIN validation for native kiosk force exit
- test_subscription_commerce.py
- create_subscription
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
- subscription_commerce_controller.py
- is_subscription_active
- session_extensions_controller.py
- CafeError
- console_catalog_service.py
- Cafe wallets: read-only mobile app APIs
- subscription_service.py
- vendor_console_overrides
- BankTransferDetails
- Console
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- passModels.py
- ConsoleService
- get_landing_page_vendor
- Flask
- test_qr_input.py
- CloudinaryMenuImageService
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- get_vendor_dashboard
- env
- Subscription packages, purchases and kiosk licences
- get_vendor_notification_preferences
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- payload_formatters.py
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- get_all_games
- PhysicalAddress
- get_active_subscription
- get_extra_services
- update_menu_inventory
- CloudinaryProfileImageService
- package_service.py
- Transaction
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

## Communities (99 total, 10 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (61): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+53 more)

### Community 1 - "access_controller.py"
Cohesion: 0.05
Nodes (83): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+75 more)

### Community 2 - "vendor.py"
Cohesion: 0.10
Nodes (23): BusinessRegistration, Document, DocumentSubmitted, OpeningDay, add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor() (+15 more)

### Community 3 - "auth"
Cohesion: 0.15
Nodes (27): ContactInfo, test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages() (+19 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (45): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+37 more)

### Community 5 - "app/routes.py"
Cohesion: 0.07
Nodes (53): VendorDaySlotConfig, VendorTaxProfile, add_console(), assign_console_to_multiple_bookings(), _assign_console_to_multiple_bookings_core(), _booking_start_eligibility(), check_db_connection(), create_vendor_pass() (+45 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.08
Nodes (25): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_category(), add_extra_service_menu(), create_category(), create_menu_item() (+17 more)

### Community 7 - "kiosk_security.py"
Cohesion: 0.15
Nodes (30): ensure_ist(), internal_send_unlock(), internal_store_updated(), post, Ensure a datetime is timezone-aware in IST (idempotent)., Internal endpoint to notify dashboard clients that store inventory/products…, remaining(), kiosk_start_session() (+22 more)

### Community 8 - "KioskTests"
Cohesion: 0.06
Nodes (13): _vendor_slot_availability(), date, skipUnless, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), OwnerPinTests, KioskTests, load() (+5 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.20
Nodes (12): PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state. (+4 more)

### Community 10 - "vendor_games.py"
Cohesion: 0.08
Nodes (28): add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games() (+20 more)

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.10
Nodes (71): adjust_wallet(), agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation() (+63 more)

### Community 13 - "extensions.py"
Cohesion: 0.09
Nodes (9): PassRedemptionLog, PayAtCafeNotification, ProvisionalResult, Image, VerificationCheck, datetime, Adding hardware must not revive historical schedules or reset held capacity., EarlyStartTests (+1 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.11
Nodes (15): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+7 more)

### Community 16 - "audit"
Cohesion: 0.22
Nodes (20): CafeBookingClaim, install_cafe_audit_hooks(), Audit existing pricing/staff mutations in their database commit for configured…, acknowledge_booking(), existing_bookings(), _groups(), _payment_verified(), Existing paid bookings use the same PC QR and acknowledgement as wallet play. (+12 more)

### Community 17 - "KioskError"
Cohesion: 0.18
Nodes (18): get, post, Authorize a specific native owner action; never end or settle a gaming session., validate_owner_pin(), authorize(), before_request, authorize_subscription(), before_request (+10 more)

### Community 18 - "package_controller.py"
Cohesion: 0.24
Nodes (15): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+7 more)

### Community 19 - "Owner PIN validation for native kiosk force exit"
Cohesion: 0.20
Nodes (9): Admin settings authorization (9 October 2026), Backend verification, Curl example, Error responses, Gaming session and money, Native integration sequence, Owner PIN validation for native kiosk force exit, Request (+1 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.13
Nodes (41): get_pcs(), link_pc(), get, post, unlink_pc(), vendor_required(), close_link(), count_active_links() (+33 more)

### Community 21 - "create_subscription"
Cohesion: 0.15
Nodes (18): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), create_order(), get_order_details(), get_payment_details(), get_razorpay_client(), get_test_price(), Get order details from Razorpay Args: order_id: Razorpay order ID Returns:… (+10 more)

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
Nodes (19): AdditionalDetails, Booking, BookingExtraService, BookingSquadMember, HardwareSpecification, MaintenanceStatus, PriceAndCost, Slot (+11 more)

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
Cohesion: 0.20
Nodes (20): CafeSlotReservation, affordable_duration(), Quote the linked console using Console Pricing, never wallet-policy amounts., Longest whole-minute session the available wallet covers, within cafe limits., session_prices(), covered_slots(), _day(), ensure_console_window() (+12 more)

### Community 30 - "websocket_service.py"
Cohesion: 0.27
Nodes (22): _connect_upstream(), _emit_downstream_to_vendor(), _get_next_slot_for_today(), _handle_upstream_booking(), _handle_upstream_booking_payment_update(), _handle_upstream_console_availability(), _handle_upstream_current_slot(), _handle_upstream_pay_at_cafe_event() (+14 more)

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

### Community 35 - "subscription_commerce_controller.py"
Cohesion: 0.33
Nodes (11): invalid(), invoice(), owned(), pay(), preview(), purchases(), errorhandler, get (+3 more)

### Community 36 - "is_subscription_active"
Cohesion: 0.38
Nodes (6): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), is_subscription_active(), Check if vendor has an active, non-expired subscription Returns: tuple: (bool:…

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.20
Nodes (27): answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue(), device_row() (+19 more)

### Community 38 - "CafeError"
Cohesion: 0.15
Nodes (35): CafeAudit, CafeContinuation, CafeLedger, CafeOwnerEmail, CafePaymentPolicy, CafePlaySession, CafeShift, CafeWallet (+27 more)

### Community 39 - "console_catalog_service.py"
Cohesion: 0.23
Nodes (19): _resolve_squad_group_for_game_name(), ConsoleCatalog, VendorConsoleOverride, create_or_update_console_type_override(), deactivate_console_type_override(), get_console_type_overrides(), get_consoles(), ensure_default_console_catalog_seed() (+11 more)

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_service.py"
Cohesion: 0.14
Nodes (26): Package, Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, Subscription, SubscriptionStatus, activate(), billing_datetime(), check_base() (+18 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "BankTransferDetails"
Cohesion: 0.11
Nodes (15): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), add_or_update_bank_details(), create_payout(), _ensure_bank_details_audit_table(), get_bank_details() (+7 more)

### Community 44 - "Console"
Cohesion: 0.08
Nodes (23): create_game(), route, Create a new game with optional image, update_game(), upload_game_image(), Console, Game, Create Game from RAWG API - image_url gets background_image automatically! (+15 more)

### Community 63 - "passModels.py"
Cohesion: 0.12
Nodes (7): CafePass, PassRedemptionLog, PassType, Generate unique pass UID for hour-based passes, UserPass, add_pass_type(), create_hash_pass()

### Community 64 - "ConsoleService"
Cohesion: 0.20
Nodes (4): ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 65 - "get_landing_page_vendor"
Cohesion: 0.22
Nodes (9): _build_session_identifier(), _derive_booking_outcome(), get_landing_page_vendor(), _normalize_lifecycle(), _normalize_status_key(), Fetches vendor dashboard data including stats, booking stats, upcoming…, A clock boundary never completes a started session., financial_totals() (+1 more)

### Community 66 - "Flask"
Cohesion: 0.16
Nodes (15): Config, install_kiosk_errors(), handle_processed_slot(), Handle the processed event and emit a final event, create_app(), _is_insecure_secret(), _validate_production_config(), start_expiry_worker() (+7 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "CloudinaryMenuImageService"
Cohesion: 0.24
Nodes (6): CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder, Checking if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload menu item image to Cloudinary

### Community 70 - "20261002_shared_slot_reservations.sql"
Cohesion: 0.29
Nodes (4): pg_tables, cafe_guard_assignment(), cafe_install_console_guards(), cafe_play_sessions

### Community 71 - "get_vendor_dashboard"
Cohesion: 0.25
Nodes (7): coerce_duration(), get_extra_services_low_stock_alerts(), get_vendor_dashboard(), Force duration to a single int or None., Return low-stock alerts for extra service menu items., to_24h(), Return low-stock menu items for notification surfaces.

### Community 72 - "env"
Cohesion: 0.29
Nodes (3): User, env(), fixture

### Community 73 - "Subscription packages, purchases and kiosk licences"
Cohesion: 0.25
Nodes (7): APIs, Cafe flow, Deployment order, Hash-team controls, Kiosk installer, Subscription packages, purchases and kiosk licences, Verification

### Community 74 - "get_vendor_notification_preferences"
Cohesion: 0.40
Nodes (6): _coerce_bool(), _default_vendor_notification_preferences(), _ensure_vendor_notification_preferences_table(), get_vendor_notification_preferences(), Any, upsert_vendor_notification_preferences()

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
Cohesion: 0.09
Nodes (37): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+29 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.21
Nodes (27): reserve_slot(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner(), test_changed_quote_price_is_not_silently_charged() (+19 more)

### Community 83 - "get_all_games"
Cohesion: 0.50
Nodes (3): get_all_games(), Get all games ordered by name, Search games by name (case-insensitive, partial match)

### Community 85 - "PhysicalAddress"
Cohesion: 0.40
Nodes (3): PhysicalAddress, Update vendor business details including website, phone, email, and address, update_business_details()

### Community 86 - "get_active_subscription"
Cohesion: 0.50
Nodes (4): Dashboard feature access is independent of staff permissions., require_feature(), get_active_subscription(), Get currently active subscription for a vendor Checks status AND period validity

### Community 87 - "get_extra_services"
Cohesion: 0.50
Nodes (3): get_extra_services(), Get all categories and menu items, Get all active categories with their menu items for a vendor

### Community 88 - "update_menu_inventory"
Cohesion: 0.50
Nodes (3): Set/increment/decrement stock for a menu item., update_menu_inventory(), Set or increment stock quantity for a menu item.

### Community 89 - "CloudinaryProfileImageService"
Cohesion: 0.15
Nodes (11): delete_vendor_profile_image(), Upload profile image to Cloudinary and update VendorProfileImage table. Creates…, Delete vendor's profile image, update_profile_image(), CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in… (+3 more)

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
- **83 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `vendor.py` to `access_controller.py`, `auth`, `session_extensions_controller.py`, `ExtraServiceService`, `kiosk_security.py`, `app/routes.py`, `subscription_service.py`, `vendor_games.py`, `BankTransferDetails`, `cafe_wallet_controller.py`, `CafeError`, `env`, `pricingController.py`, `test_subscription_commerce.py`, `PhysicalAddress`, `test_subscription_checkout.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `CafeError` connect `CafeError` to `access_controller.py`, `vendor.py`, `app/routes.py`, `session_extensions_controller.py`, `kiosk_security.py`, `env`, `cafe_wallet_controller.py`, `Console`, `audit`, `session_extensions.py`, `local_window`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _83 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `event_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.057124310288867254 - nodes in this community are weakly interconnected._