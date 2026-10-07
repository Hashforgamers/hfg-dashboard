# Graph Report - hfg-dashboard-service  (2026-10-07)

## Corpus Check
- 188 files · ~100,329 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1626 nodes · 4588 edges · 88 communities (74 shown, 14 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 105 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0b66c26b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- event_controller.py
- Flask
- vendor.py
- auth
- tournament_engine_service.py
- app/routes.py
- ExtraServiceService
- websocket_service.py
- KioskTests
- models/__init__.py
- gamer
- Kiosk, dashboard and app integration guide: session extensions v1
- cafe_wallet_controller.py
- passModels.py
- review_controller.py
- test_shared_slot_capacity.py
- cafe_booking_service.py
- extensions.py
- package_controller.py
- models/routes.py
- test_subscription_commerce.py
- vendor_games.py
- booking_bridge.py
- test_cafe_continuations.py
- test_cafe_wallet.py
- ConsoleLinkSession
- session_extensions.py
- BridgeTests
- Kiosk backend contract — 22 September 2026
- cafe_wallet_service.py
- date
- 20260922_cafe_wallet.sql
- razorpay_service.py
- Self QR sessions, owner-approved continuation and balance due
- tournament_matches
- subscription_controller.py
- is_subscription_active
- session_extensions_controller.py
- CafeError
- ConsoleService
- Cafe wallets: read-only mobile app APIs
- subscription_commerce.py
- vendor_console_overrides
- CloudinaryProfileImageService
- test_console_schedule_bootstrap.py
- vendor_notification_preferences
- AGENTS.md
- extra_service_menus
- registrations
- cafePass.py
- subscription_service.py
- UserPass
- test_qr_input.py
- booking_bridge_controller.py
- 20260923_unified_kiosk_qr.sql
- 20261002_shared_slot_reservations.sql
- Subscription packages, purchases and kiosk licences
- Console and cafe-wallet pricing
- Shared capacity for app, dashboard, kiosk and QR bookings
- test_kiosk_runtime.py
- cafe_play_sessions
- pricingController.py
- test_session_extensions.py
- EarlyStartTests
- Kiosk session extensions v1 — implemented backend contract
- PassRedemptionLog
- PayAtCafeNotification
- accepted_methods

## God Nodes (most connected - your core abstractions)
1. `CafeError` - 78 edges
2. `staff_actor()` - 40 edges
3. `Vendor` - 38 edges
4. `auth()` - 38 edges
5. `audit()` - 31 edges
6. `KioskError` - 30 edges
7. `fund()` - 29 edges
8. `local_window()` - 28 edges
9. `wallet()` - 28 edges
10. `_invalidate_vendor_caches()` - 26 edges

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

## Communities (88 total, 14 thin omitted)

### Community 0 - "event_controller.py"
Cohesion: 0.06
Nodes (57): delete_banner(), _event_payload(), get_event(), get_event_detail(), get_events(), issue_jwt(), patch_event(), post_event() (+49 more)

### Community 1 - "Flask"
Cohesion: 0.05
Nodes (78): expire_subscriptions_command(), fix_expired_subscriptions_command(), init_pc_link_table_command(), init_rbac_tables_command(), init_review_table_command(), list_subscriptions_command(), migrate_rbac_legacy_command(), Create test subscription for development Usage: flask test-subscription 1 base (+70 more)

### Community 2 - "vendor.py"
Cohesion: 0.07
Nodes (20): AvailableGame, BankTransferDetails, PayoutTransaction, Return masked account number for UI display, Return masked UPI ID for UI display (mask first 4 characters), BusinessRegistration, Document, DocumentSubmitted (+12 more)

### Community 3 - "auth"
Cohesion: 0.10
Nodes (29): ContactInfo, auth(), test_topup_establishes_customer_contact_access(), test_topup_search_contact_privacy_and_customer_scope(), staff_token(), test_activity_pages_filters_and_older_records(), test_collections_date_boundaries_and_activity_scope(), test_expired_jwt_cannot_renew_live_staff_session() (+21 more)

### Community 4 - "tournament_engine_service.py"
Cohesion: 0.11
Nodes (47): admin_match_result(), close_event_check_in(), _emit(), _event_for_vendor(), generate_bracket(), get_event_bracket(), get_event_matches(), open_event_check_in() (+39 more)

### Community 5 - "app/routes.py"
Cohesion: 0.03
Nodes (95): PassType, VendorDaySlotConfig, VendorTaxProfile, add_console(), add_extra_service_category(), add_or_update_bank_details(), add_pass_type(), _build_session_identifier() (+87 more)

### Community 6 - "ExtraServiceService"
Cohesion: 0.07
Nodes (24): Amenity, ExtraServiceCategory, ExtraServiceMenu, ExtraServiceMenuImage, add_extra_service_menu(), CloudinaryMenuImageService, Delete menu item image from Cloudinary, Service for handling menu cover images Images are uploaded to the 'poc' folder (+16 more)

### Community 7 - "websocket_service.py"
Cohesion: 0.05
Nodes (93): before_request, require_tournament_plan(), internal_send_unlock(), internal_store_updated(), post, Internal endpoint to notify dashboard clients that store inventory/products…, get, remaining() (+85 more)

### Community 9 - "models/__init__.py"
Cohesion: 0.14
Nodes (13): PaymentMethod, PaymentVendorMap, _build_payment_method_response(), _ensure_payment_method_catalog(), get_all_payment_methods_for_vendor(), get_payment_method_stats(), _method_ids_for_canonical(), _normalize_payment_method_name() (+5 more)

### Community 10 - "gamer"
Cohesion: 0.22
Nodes (13): test_wallet_budget_can_buy_affordable_time_below_configured_duration(), gamer(), parametrize, Gamer wallet reads: tenant isolation, safe projection and cursor boundaries., test_balances_are_private_paginated_and_do_not_create_wallets(), test_cursor_validation_and_empty_pages(), test_gamer_cannot_use_staff_topup_or_wallet_routes(), test_history_is_scoped_filtered_and_stably_paginated() (+5 more)

### Community 11 - "Kiosk, dashboard and app integration guide: session extensions v1"
Cohesion: 0.06
Nodes (31): 10. Dashboard requests, approval and conflict resolution, 11. Final settlement, 12. Socket.IO setup and client emits, 13. Exact server event payloads, 14. Event ordering, reconnect and retries, 15. Errors and recovery, 16. Smooth gamer interaction, 17. Scenario acceptance checklist (+23 more)

### Community 12 - "cafe_wallet_controller.py"
Cohesion: 0.10
Nodes (69): adjust_wallet(), agent_end_qr_session(), agent_link(), agent_qr(), agent_realtime_snapshot(), agent_request_continuation(), agent_session(), audit_history() (+61 more)

### Community 13 - "passModels.py"
Cohesion: 0.17
Nodes (4): CafePass, PassRedemptionLog, Generate unique pass UID for hour-based passes, UserPass

### Community 14 - "review_controller.py"
Cohesion: 0.32
Nodes (15): list_reviews(), _proxy_get(), _proxy_headers(), _proxy_patch(), get, jwt_required, patch, respond_review() (+7 more)

### Community 15 - "test_shared_slot_capacity.py"
Cohesion: 0.12
Nodes (14): first_slot(), flows(), load_source(), overtime_route(), fixture, Cross-flow capacity regressions against isolated PostgreSQL schemas., Run the real overtime endpoint with unrelated mail/tax helpers stubbed., test_desk_failed_payment_rolls_back_capacity_and_booking() (+6 more)

### Community 16 - "cafe_booking_service.py"
Cohesion: 0.15
Nodes (21): CafeAudit, CafeBookingClaim, CafeFoodOrder, CafePlaySession, CafeShift, Cafe money is stored in integer paise; ledger and audit records are immutable., acknowledge_booking(), existing_bookings() (+13 more)

### Community 17 - "extensions.py"
Cohesion: 0.09
Nodes (18): ensure_ist(), Ensure a datetime is timezone-aware in IST (idempotent)., AdditionalDetails, Booking, BookingExtraService, BookingSquadMember, ConsoleLinkStatus, HardwareSpecification (+10 more)

### Community 18 - "package_controller.py"
Cohesion: 0.15
Nodes (19): _admin_authorized(), admin_catalog(), delete_admin_catalog_item(), _extract_admin_key(), get_package(), list_packages(), delete, get (+11 more)

### Community 19 - "models/routes.py"
Cohesion: 0.17
Nodes (15): OpeningDay, add_console(), check_db_connection(), delete_console(), get_all_device_for_vendor(), get_consoles(), get_device_for_console_type(), get_landing_page_vendor() (+7 more)

### Community 20 - "test_subscription_commerce.py"
Cohesion: 0.14
Nodes (38): app(), auth(), order(), payment(), fixture, parametrize, test_first_purchase_unlocks_and_duplicate_is_idempotent(), test_polled_payment_uses_provider_verification() (+30 more)

### Community 21 - "vendor_games.py"
Cohesion: 0.06
Nodes (43): create_game(), route, Create a new game with optional image, update_game(), add_game_to_consoles(), bulk_delete_game(), delete_game_image(), delete_vendor_game() (+35 more)

### Community 22 - "booking_bridge.py"
Cohesion: 0.18
Nodes (14): connect(), disconnect(), _emit_downstream(), ensure_upstream_vendor_join(), _handle_booking_event(), _join_upstream_vendor(), Any, Start the upstream bridge once (idempotent). (+6 more)

### Community 23 - "test_cafe_continuations.py"
Cohesion: 0.30
Nodes (19): approve(), request_more(), services(), started(), test_approval_never_starts_before_paid_expiry(), test_collection_requires_completed_play_and_expected_amount(), test_competing_owner_approvals_create_one_credit_session(), test_continuation_migration_is_repeatable_and_preserves_live_play() (+11 more)

### Community 24 - "test_cafe_wallet.py"
Cohesion: 0.13
Nodes (24): test_budget_duration_ignores_legacy_policy_limit_but_never_accepts_zero_price(), fund(), parametrize, Real transactional integration tests. Set CAFE_TEST_DATABASE_URL to a…, seed_booking(), test_active_booking_cancellation_or_refund_stops_session(), test_concurrent_duplicate_ack_does_not_double_capture(), test_disabled_cafe_wallet_does_not_reserve_or_debit() (+16 more)

### Community 25 - "ConsoleLinkSession"
Cohesion: 0.28
Nodes (14): get_pcs(), link_pc(), get, post, unlink_pc(), ConsoleLinkSession, vendor_required(), close_link() (+6 more)

### Community 26 - "session_extensions.py"
Cohesion: 0.13
Nodes (42): BaseSlotRelease, ExtensionQuote, ExtensionSegment, Shared kiosk continuation records. Money remains integer paise., RuntimeMutation, RuntimeSession, SessionCreditEntry, SessionNotice (+34 more)

### Community 27 - "BridgeTests"
Cohesion: 0.29
Nodes (5): BaseException, BridgeTests, load(), Run bridge functions with fake I/O so regressions cannot contact services., StopLoop

### Community 28 - "Kiosk backend contract — 22 September 2026"
Cohesion: 0.20
Nodes (9): 1. Credentials and lifetime, 2. Login investigation, 3. Server time and expiry, 4. Socket contract, 5. Redemption and unlink, 6. Response and retry contract, Kiosk backend contract — 22 September 2026, Rollout and validation (+1 more)

### Community 29 - "cafe_wallet_service.py"
Cohesion: 0.17
Nodes (26): agent_continuation_quote(), continuation_quote(), CafeSlotReservation, affordable_duration(), console_durations(), Quote the linked console using Console Pricing, never wallet-policy amounts., Use the current dated console schedule as the only duration configuration., Longest whole-minute session the available wallet covers, within cafe limits. (+18 more)

### Community 30 - "date"
Cohesion: 0.21
Nodes (6): _vendor_slot_availability(), date, test_dated_session_slots_cover_midnight_without_repeating_previous_day(), test_qr_quote_uses_dated_schedule_and_ignores_other_templates(), ManualSessionEndTests, Scheduled end and midnight must not manufacture a completed session.

### Community 31 - "20260922_cafe_wallet.sql"
Cohesion: 0.38
Nodes (3): cafe_audit_immutable, cafe_ledger_immutable, cafe_reject_history_mutation()

### Community 32 - "razorpay_service.py"
Cohesion: 0.19
Nodes (12): create_order(), get_order_details(), get_payment_details(), get_razorpay_client(), get_test_price(), Get order details from Razorpay Args: order_id: Razorpay order ID Returns:…, Create a Razorpay order for subscription payment Args: amount: Amount in INR…, Verify Razorpay payment signature for security Args: order_id: Razorpay order… (+4 more)

### Community 33 - "Self QR sessions, owner-approved continuation and balance due"
Cohesion: 0.29
Nodes (6): Billing and availability, Gamer / web QR endpoints, Kiosk / PC agent contract, Owner emails and runtime, Self QR sessions, owner-approved continuation and balance due, Staff endpoints and dashboard

### Community 34 - "tournament_matches"
Cohesion: 0.58
Nodes (8): events, map_veto_actions, match_disputes, match_participants, match_result_submissions, tournament_matches, tournament_seeds, teams

### Community 35 - "subscription_controller.py"
Cohesion: 0.12
Nodes (28): change(), check_payment_status(), check_subscription_status(), create_payment_order(), debug_force_expire(), get_limit(), get_subscription(), get_subscription_history() (+20 more)

### Community 36 - "is_subscription_active"
Cohesion: 0.38
Nodes (6): check_subscription_or_warn(), Soft check decorator - warns but doesn't block access Useful for non-critical…, Decorator to protect routes that require active subscription Usage:…, subscription_required(), is_subscription_active(), Check if vendor has an active, non-expired subscription Returns: tuple: (bool:…

### Community 37 - "session_extensions_controller.py"
Cohesion: 0.20
Nodes (27): after_request, answer(), body(), check_ready(), conflicting_mutation(), current_session(), decision(), device_continue() (+19 more)

### Community 38 - "CafeError"
Cohesion: 0.19
Nodes (29): agent_ack(), staff_end_qr_session(), CafeContinuation, CafeLedger, CafeOwnerEmail, CafeWallet, decide(), end_session() (+21 more)

### Community 39 - "ConsoleService"
Cohesion: 0.18
Nodes (5): Console, ConsoleService, Prefer cloning existing vendor slot date-coverage from other console types.…, Clear slot templates and dynamic vendor rows for one game type. Used when a…, Align new slot generation to the vendor's existing slot horizon. - If vendor…

### Community 40 - "Cafe wallets: read-only mobile app APIs"
Cohesion: 0.11
Nodes (16): 1. List my cafe wallets, 2. Balance at a specific cafe, 3. Cafe wallet transaction history, App screen flow, Authentication and hosts, Backend release, Cafe wallets: read-only mobile app APIs, Errors (+8 more)

### Community 41 - "subscription_commerce.py"
Cohesion: 0.16
Nodes (18): Immutable commercial snapshot for each subscription purchase., SubscriptionCheckout, activate(), billing_datetime(), check_base(), paise(), preview(), public_quote() (+10 more)

### Community 42 - "vendor_console_overrides"
Cohesion: 0.67
Nodes (3): console_catalog, vendors, vendor_console_overrides

### Community 43 - "CloudinaryProfileImageService"
Cohesion: 0.21
Nodes (7): CloudinaryProfileImageService, Cloudinary service for handling vendor profile images Images are uploaded to…, Delete profile image from Cloudinary, Service to handle vendor profile image uploads. Images are stored in…, Check if Cloudinary credentials are available, Initialize Cloudinary configuration, Upload profile image to Cloudinary in individual vendor folder

### Community 65 - "subscription_service.py"
Cohesion: 0.26
Nodes (16): Verify Razorpay payment signature and activate subscription Request body: {…, verify_and_activate(), Subscription, change_subscription(), create_subscription(), get_package_price_for_cycle(), get_subscription_duration(), normalize_billing_cycle() (+8 more)

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

### Community 81 - "pricingController.py"
Cohesion: 0.05
Nodes (66): calculate_controller_pricing(), _calculate_controller_total(), create_pricing_offer(), _default_squad_policy(), delete_pricing_offer(), get_active_pricing(), get_controller_pricing(), get_ist_now() (+58 more)

### Community 82 - "test_session_extensions.py"
Cohesion: 0.22
Nodes (26): reserve_slot(), active(), engine(), extend(), Real PostgreSQL transactions: no money or slot updates are mocked., test_billing_ticks_do_not_invalidate_quote_revision_and_stop_is_not_blocked(), test_capacity_exhaustion_cannot_be_overridden_by_owner(), test_changed_quote_price_is_not_silently_charged() (+18 more)

### Community 95 - "Kiosk session extensions v1 — implemented backend contract"
Cohesion: 0.22
Nodes (8): Authoritative snapshot and realtime, Authorization and money, Dashboard management API, Device API sequence, Kiosk session extensions v1 — implemented backend contract, Native UX instructions, Rollout, Verification before production enablement

### Community 102 - "accepted_methods"
Cohesion: 0.83
Nodes (3): accepted_methods(), canonical_method(), require_method()

## Knowledge Gaps
- **75 isolated node(s):** `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck`, `cafe_booking_claims`, `graphify` (+70 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Vendor` connect `vendor.py` to `Flask`, `subscription_service.py`, `auth`, `session_extensions_controller.py`, `ExtraServiceService`, `app/routes.py`, `CafeError`, `models/__init__.py`, `subscription_commerce.py`, `cafe_wallet_controller.py`, `pricingController.py`, `extensions.py`, `models/routes.py`, `test_subscription_commerce.py`, `ConsoleLinkSession`, `cafe_wallet_service.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `KioskTests` connect `KioskTests` to `date`, `test_kiosk_runtime.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `datetime` (e.g. with `debug_force_expire()` and `test_activity_pages_filters_and_older_records()`) actually correct?**
  _`datetime` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `CafeError` (e.g. with `CafeAudit` and `CafeContinuation`) actually correct?**
  _`CafeError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Flask` (e.g. with `env()` and `.setUp()`) actually correct?**
  _`Flask` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ConsoleLinkStatus`, `ProvisionalResult`, `VerificationCheck` to the rest of the system?**
  _75 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `event_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.061621621621621624 - nodes in this community are weakly interconnected._