# Graph Report - hfg-dashboard-service  (2026-10-08)

## Corpus Check
- 191 files · ~101,721 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1654 nodes · 4645 edges · 90 communities (80 shown, 10 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `91b55b06`
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
- websocket_service.py
- KioskTests
- toggle_payment_method_for_vendor
- registration_controller.py
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- datetime
- review_controller.py
- test_shared_slot_capacity.py
- cafe_booking_service.py
- event_service.py
- package_controller.py
- Owner PIN validation for native kiosk force exit
- test_subscription_commerce.py
- GameService
- booking_bridge.py
- test_cafe_continuations.py
- test_cafe_wallet.py
- team_controller.py
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- local_window
- cafe_audit_hooks.py
- 20260922_cafe_wallet.sql
- subscription_controller.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- post
- is_subscription_active
- session_extensions_controller.py
- CafeError
- extensions.py
- Cafe wallets: read-only mobile app APIs
- subscription_commerce.py
- vendor_console_overrides
- EarlyStartTests
- vendor_games.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- UserPass
- result_controller.py
- subscription_service.py
- Flask
- test_qr_input.py
- websocket_controller.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- Subscription packages, purchases and kiosk licences
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- CloudinaryEventImageService
- CloudinaryProfileImageService
- Kiosk session extensions v1 — implemented backend contract
- test_console_pricing.py
- accepted_methods
- cafePass.py
- UserPass

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 80 edges
2. `staff_actor()` - 41 edges
3. `Vendor` - 38 edges
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

## Communities (90 total, 10 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.19
Nodes (24): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+16 more)

### Community 1 - "access_controller.py"
Cohesion: 0.07
Nodes (67): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+59 more)

### Community 2 - "vendor.py"
Cohesion: 0.07
Nodes (31): BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, ContactInfo, Document, DocumentSubmitted (+23 more)

### Community 3 - "auth"
Cohesion: 0.14
Nodes (27): test_wallet_budget_can_buy_affordable_time_below_configured_duration(), auth(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages(), test_gamer_cannot_use_staff_topup_or_wallet_routes() (+19 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "app/routes.py"
Cohesion: 0.03
Nodes (99): PassType, VendorDaySlotConfig, add_console(), add_extra_service_category(), add_or_update_bank_details(), add_pass_type(), _build_session_identifier(), check_db_connection() (+91 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (24): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_menu(), CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder (+16 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.06
Nodes (94): before_request, require_tournament_plan(), internal_send_unlock(), internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…, get, post (+86 more)

### Community 8 - "KioskTests"
Cohesion: 0.06
Nodes (13): _vendor_slot_availability(), date, skipUnless, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), OwnerPinTests, KioskTests, load() (+5 more)

### Community 9 - "toggle_payment_method_for_vendor"
Cohesion: 0.27
Nodes (11): _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name(), Get supported payment methods and vendor enablement state., Toggle manually managed payment methods for vendor. (+3 more)

### Community 10 - "registration_controller.py"
Cohesion: 0.31
Nodes (8): list_registrations(), get, jwt_required, patch, update_payment_status(), _vendor_id(), Registration, Team

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.11
Nodes (68): agent_ack(), agent_continuation_quote(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), agent_session() (+60 more)

### Community 13 - "datetime"
Cohesion: 0.06
Nodes (11): CafePass, PassRedemptionLog, PassRedemptionLog, PayAtCafeNotification, PaymentMethod, PaymentVendorMap, Transaction, Image (+3 more)

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (14): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+6 more)

### Community 16 - "cafe_booking_service.py"
Cohesion: 0.17
Nodes (20): CafeBookingClaim, CafeFoodOrder, CafeOwnerEmail, CafePlaySession, Cafe money is stored in integer paise; ledger and audit records are immutable., acknowledge_booking(), existing_bookings(), _groups() (+12 more)

### Community 17 - "event_service.py"
Cohesion: 0.30
Nodes (7): Event, EventStatus, create_event(), _as_aware_datetime(), create_event(), derive_event_status(), _normalize_datetime_fields()

### Community 18 - "package_controller.py"
Cohesion: 0.15
Nodes (19): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+11 more)

### Community 19 - "Owner PIN validation for native kiosk force exit"
Cohesion: 0.22
Nodes (8): Backend verification, Curl example, Error responses, Gaming session and money, Native integration sequence, Owner PIN validation for native kiosk force exit, Request, Success: HTTP 200

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.08
Nodes (57): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, ConsoleLinkStatus, vendor_required() (+49 more)

### Community 21 - "GameService"
Cohesion: 0.07
Nodes (27): create_game(), route, Create a new game with optional image, update_game(), delete_game_image(), get_all_games(), upload_game_image(), Game (+19 more)

### Community 22 - "booking_bridge.py"
Cohesion: 0.13
Nodes (20): join_vendor_room(), leave_vendor_room(), get, post, status(), bridge_status(), connect(), disconnect() (+12 more)

### Community 23 - "test_cafe_continuations.py"
Cohesion: 0.30
Nodes (19): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_collection_requires_completed_play_and_expected_amount(), test_competing_owner_approvals_create_one_credit_session(), test_continuation_migration_is_repeatable_and_preserves_live_play() (+11 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.13
Nodes (24): test_budget_duration_ignores_legacy_policy_limit_but_never_accepts_zero_price(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+16 more)

### Community 25 - "team_controller.py"
Cohesion: 0.46
Nodes (6): list_members(), list_teams(), get, jwt_required, _vendor_id(), TeamMember

### Community 26 - "session_extensions.py"
Cohesion: 0.12
Nodes (42): BaseSlotRelease, ExtensionQuote, ExtensionSegment, Shared kiosk continuation records. Money remains integer paise., RuntimeMutation, RuntimeSession, SessionCreditEntry, SessionNotice (+34 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "local_window"
Cohesion: 0.21
Nodes (19): CafeSlotReservation, affordable_duration(), Quote the linked console using Console Pricing, never wallet-policy amounts., Longest whole-minute session the available wallet covers, within cafe limits., session_prices(), covered_slots(), _day(), ensure_console_window() (+11 more)

### Community 30 - "cafe_audit_hooks.py"
Cohesion: 0.33
Nodes (5): put, set_policy(), CafePaymentPolicy, install_cafe_audit_hooks(), Audit existing pricing/staff mutations in their database commit for configured…

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "subscription_controller.py"
Cohesion: 0.12
Nodes (26): check_payment_status(), debug_force_expire(), get_limit(), get_subscription_history(), get_subscription_invoice(), _invoice_number(), get, Get PC limit for vendor (+18 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "post"
Cohesion: 0.40
Nodes (5): create_payment_order(), provision_default(), post, Provision default subscription for new vendor, Create Razorpay order for subscription purchase

### Community 36 - "is_subscription_active"
Cohesion: 0.19
Nodes (12): change(), check_subscription_status(), _parse_period_datetime(), Check if vendor subscription is active (for dashboard lock), Change subscription package (admin use), _subscription_status_snapshot(), check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical… (+4 more)

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.20
Nodes (27): after_request, answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue() (+19 more)

### Community 38 - "CafeError"
Cohesion: 0.22
Nodes (33): adjust_wallet(), CafeAudit, CafeContinuation, CafeLedger, CafeShift, CafeWallet, decide(), end_session() (+25 more)

### Community 39 - "extensions.py"
Cohesion: 0.08
Nodes (20): ensure_ist(), Ensure a datetime is timezone-aware in IST (idempotent)., AdditionalDetails, AvailableGame, Booking, BookingExtraService, BookingSquadMember, Console (+12 more)

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_commerce.py"
Cohesion: 0.16
Nodes (21): get_subscription(), Get current subscription status for vendor, Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, activate(), billing_datetime(), check_base(), paise() (+13 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 44 - "vendor_games.py"
Cohesion: 0.09
Nodes (25): add_game_to_consoles(), bulk_delete_game(), delete_vendor_game(), get_available_games(), get_consoles_by_platform(), get_game_details(), list_vendor_games(), _offer_is_active_now() (+17 more)

### Community 64 - "result_controller.py"
Cohesion: 0.40
Nodes (8): list_winners(), publish_winners(), get, jwt_required, post, _snapshot_url(), _vendor_id(), Winner

### Community 65 - "subscription_service.py"
Cohesion: 0.26
Nodes (16): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Subscription, change_subscription(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle() (+8 more)

### Community 66 - "Flask"
Cohesion: 0.24
Nodes (11): Config, install_kiosk_errors(), create_app(), _is_insecure_secret(), _validate_production_config(), start_expiry_worker(), Independent of legacy expiry feature flags; multiple workers serialize rows., start_worker() (+3 more)

### Community 67 - "test_qr_input.py"
Cohesion: 0.22
Nodes (7): Error, Exception, fixture, parametrize, resolver(), test_bad_input_never_resolves_device(), test_thirty_minute_expiry()

### Community 68 - "websocket_controller.py"
Cohesion: 0.50
Nodes (3): handle_processed_slot(), Handle the processed event and emit a final event, on

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

### Community 81 - "pricingController.py"
Cohesion: 0.07
Nodes (57): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+49 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.22
Nodes (26): reserve_slot(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner(), test_changed_quote_price_is_not_silently_charged() (+18 more)

### Community 83 - "CloudinaryEventImageService"
Cohesion: 0.31
Nodes (4): CloudinaryEventImageService, Cloudinary service for handling event banner images. Images are uploaded to the…, Upload event banner image to Cloudinary — EVENT_BANNERS folder, Delete event banner from Cloudinary

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
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `vendor.py` to `access_controller.py`, `subscription_service.py`, `session_extensions_controller.py`, `ExtraServiceService`, `extensions.py`, `app/routes.py`, `CafeError`, `subscription_commerce.py`, `cafe_wallet_controller.py`, `datetime`, `vendor_games.py`, `pricingController.py`, `test_subscription_commerce.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `CafeError` connect `CafeError` to `access_controller.py`, `vendor.py`, `app/routes.py`, `session_extensions_controller.py`, `extensions.py`, `websocket_service.py`, `cafe_wallet_controller.py`, `cafe_booking_service.py`, `test_subscription_commerce.py`, `session_extensions.py`, `local_window`, `cafe_audit_hooks.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _82 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `access_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07063063063063063 - nodes in this community are weakly interconnected._