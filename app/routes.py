from flask import Blueprint, request, jsonify, current_app
from datetime import datetime,timedelta
from typing import Dict
import re
import time
import threading
import hashlib
from .models.transaction import Transaction
from app.extension.extensions import db
from sqlalchemy import cast, Date, text, func
from sqlalchemy import case
from app.services.console_service import ConsoleService

from .models.console import Console
from .models.availableGame import AvailableGame, available_game_console
from .models.booking import Booking
from .models.passModels import CafePass
from .models.passModels import PassType
from .models.passModels import UserPass
from .models.physicalAddress import PhysicalAddress
from .models.contactInfo import ContactInfo
from .models.vendorDaySlotConfig import VendorDaySlotConfig
from .models.amenity import Amenity
from app.models.vendorProfileImage import VendorProfileImage
from app.services.cloudinary_profile_service import CloudinaryProfileImageService
from app.models.website import Website 
from app.models.bankTransferDetails import BankTransferDetails, PayoutTransaction
# Add these imports with your existing model imports
from app.models.paymentMethod import PaymentMethod
from app.models.paymentVendorMap import PaymentVendorMap
from app.models.bookingExtraService import BookingExtraService
from app.models.bookingSquadMember import BookingSquadMember
from app.models.vendorTaxProfile import VendorTaxProfile

from .models.hardwareSpecification import HardwareSpecification
from .models.maintenanceStatus import MaintenanceStatus
from .models.priceAndCost import PriceAndCost
from .models.slot import Slot
from .models.user import User
from .models.additionalDetails import AdditionalDetails
from sqlalchemy.orm import joinedload
from collections import defaultdict
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError

from app.services.payload_formatters import format_current_slot_item
 
from collections import Counter

from datetime import datetime, timedelta, date
from app.services.websocket_service import socketio
from zoneinfo import ZoneInfo

from app.models.vendor import Vendor  # adjust import as per your structure
from app.models.uploadedImage import Image
from app.models.documentSubmitted import DocumentSubmitted
from app.models.timing import Timing
from app.models.openingDay import OpeningDay
from app.models.businessRegistration import BusinessRegistration
from app.models.vendorAccount import VendorAccount
from app.models.extraServiceCategory import ExtraServiceCategory
from app.models.bookingExtraService import BookingExtraService
from app.models.extraServiceMenu import ExtraServiceMenu
from app.services.extra_service_service import ExtraServiceService

WEEKDAY_ORDER = ["mon","tue","wed","thu","fri","sat","sun"]
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
STATE_CODE_REGEX = re.compile(r"^[0-9A-Z]{2}$")
LANDING_PAGE_CACHE_TTL_SEC = 5
_landing_page_cache = {}
_landing_page_cache_lock = threading.Lock()
LANDING_HISTORY_DAYS = 1
CONSOLES_CACHE_TTL_SEC = 10
_vendor_consoles_cache = {}
_vendor_consoles_cache_lock = threading.Lock()


def _invalidate_vendor_caches(vendor_id: int):
    key = f"vendor:{int(vendor_id)}"
    with _landing_page_cache_lock:
        _landing_page_cache.pop(key, None)
    with _vendor_consoles_cache_lock:
        _vendor_consoles_cache.pop(key, None)

dashboard_service = Blueprint("dashboard_service", __name__)
IST = ZoneInfo("Asia/Kolkata")
LIFECYCLE_ORDER = {
    "upcoming": 1,
    "current": 2,
    "completed": 3,
    "discarded": 3,
    "cancelled": 3,
    "canceled": 3,
    "rejected": 3,
}


def _resolve_console_group_from_name(console_name: str) -> str:
    value = str(console_name or "").strip().lower()
    if "pc" in value:
        return "pc"
    if "ps" in value:
        return "ps"
    if "xbox" in value:
        return "xbox"
    if "vr" in value:
        return "vr"
    return "unknown"


def _booking_start_eligibility(slot_date, start_time, end_time):
    """
    Rules:
    - Booking date must be today (IST)
    - Current IST time must be between start_time and end_time (inclusive)
    """
    now_ist = datetime.now(IST).replace(tzinfo=None)
    if not slot_date or not start_time or not end_time:
        return False, "Booking schedule is incomplete."

    slot_day = slot_date if isinstance(slot_date, date) else None
    if slot_day != now_ist.date():
        return False, "Session can only be started on its booking date."

    start_dt = datetime.combine(slot_day, start_time)
    end_dt = datetime.combine(slot_day, end_time)
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    if now_ist < start_dt:
        return False, "Session can be started only when slot time begins."
    if now_ist > end_dt:
        return False, "Slot end time has passed. Cannot start session."
    return True, ""


def _build_session_identifier(booking_id, slot_date, start_time, end_time):
    raw = f"{booking_id}|{slot_date}|{start_time}|{end_time}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"sess-{booking_id}-{digest}"


def _normalize_lifecycle(book_status: str, row_date, start_time=None, end_time=None):
    """
    Keep lifecycle monotonic for API output:
    - future date can never be current/completed
    - past date can never be upcoming/current
    """
    status = str(book_status or "upcoming").strip().lower()
    if status not in LIFECYCLE_ORDER:
        status = "upcoming"
    today_ist = datetime.now(IST).date()
    if isinstance(row_date, date) and row_date > today_ist:
        return "upcoming"
    if isinstance(row_date, date) and row_date < today_ist:
        return "completed"
    # For today's rows, trust persisted status unless slot end has already passed.
    # This prevents stale "upcoming" rows from showing after their end time.
    if (
        isinstance(row_date, date)
        and row_date == today_ist
        and start_time
        and end_time
    ):
        now_ist = datetime.now(IST).replace(tzinfo=None)
        start_dt = datetime.combine(row_date, start_time)
        end_dt = datetime.combine(row_date, end_time)
        if end_dt <= start_dt:
            end_dt = end_dt + timedelta(days=1)
        if now_ist > end_dt:
            return "completed"
    return status

@dashboard_service.route('/transactionReport/<int:vendor_id>/<string:to_date>/<string:from_date>', methods=['GET'])
def get_transaction_report(to_date, from_date, vendor_id):
    try:
        to_date = datetime.strptime(to_date, "%Y%m%d").date()
        if not from_date or from_date.lower() == "null":
            from_date = datetime.utcnow().date()
        else:
            from_date = datetime.strptime(from_date, "%Y%m%d").date()

        rows = (
            db.session.query(Transaction, User.name.label("user_name"))
            .outerjoin(User, User.id == Transaction.user_id)
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date.between(from_date, to_date),
            )
            .order_by(
                Transaction.booking_date.desc(),
                Transaction.booking_time.desc(),
                Transaction.id.desc(),
            )
            .all()
        )

        result = []
        for txn, user_name in rows:
            base_amount = float(txn.base_amount or 0)
            meals_amount = float(txn.meals_amount or 0)
            controller_amount = float(txn.controller_amount or 0)
            waive_off_amount = float(txn.waive_off_amount or 0)
            gst_rate = float(txn.gst_rate or 0)

            taxable_amount = float(txn.taxable_amount or 0)
            if taxable_amount <= 0:
                derived_taxable = base_amount + meals_amount + controller_amount - waive_off_amount
                taxable_amount = round(derived_taxable if derived_taxable > 0 else float(txn.amount or 0), 2)

            cgst_amount = float(txn.cgst_amount or 0)
            sgst_amount = float(txn.sgst_amount or 0)
            igst_amount = float(txn.igst_amount or 0)
            total_tax_amount = cgst_amount + sgst_amount + igst_amount

            if total_tax_amount <= 0 and gst_rate > 0 and taxable_amount > 0:
                estimated_tax = round((taxable_amount * gst_rate) / 100.0, 2)
                if igst_amount > 0:
                    igst_amount = estimated_tax
                else:
                    cgst_amount = round(estimated_tax / 2.0, 2)
                    sgst_amount = round(estimated_tax - cgst_amount, 2)
                total_tax_amount = cgst_amount + sgst_amount + igst_amount

            total_with_tax = float(txn.total_with_tax or 0)
            if total_with_tax <= 0:
                total_with_tax = round(taxable_amount + total_tax_amount, 2)
                if total_with_tax <= 0:
                    total_with_tax = float(txn.amount or 0)

            result.append({
                "id": txn.id,
                "bookingId": txn.booking_id,
                "slotDate": txn.booking_date.strftime("%Y-%m-%d") if txn.booking_date else None,
                "playDate": txn.booked_date.strftime("%Y-%m-%d") if txn.booked_date else None,
                "slotTime": txn.booking_time.strftime("%I:%M %p") if txn.booking_time else None,
                "userName": user_name,
                "amount": txn.amount,
                "originalAmount": txn.original_amount,
                "discountedAmount": txn.discounted_amount,
                "modeOfPayment": txn.mode_of_payment,
                "paymentUseCase": txn.payment_use_case,
                "bookingType": txn.booking_type,
                "settlementStatus": txn.settlement_status,
                "userId": txn.user_id,
                "bookedOn": txn.booking_date,
                "sourceChannel": txn.source_channel,
                "staffId": txn.initiated_by_staff_id,
                "staffName": txn.initiated_by_staff_name,
                "staffRole": txn.initiated_by_staff_role,
                "baseAmount": base_amount,
                "mealsAmount": meals_amount,
                "controllerAmount": controller_amount,
                "waiveOffAmount": waive_off_amount,
                "taxableAmount": taxable_amount,
                "gstRate": gst_rate,
                "cgstAmount": cgst_amount,
                "sgstAmount": sgst_amount,
                "igstAmount": igst_amount,
                "totalWithTax": total_with_tax,
            })

        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_service.route('/vendor/<int:vendor_id>/tax-profile', methods=['GET', 'PUT'])
def vendor_tax_profile(vendor_id):
    try:
        profile = VendorTaxProfile.query.filter_by(vendor_id=vendor_id).first()

        if request.method == 'GET':
            if not profile:
                return jsonify({
                    "success": True,
                    "profile": {
                        "vendor_id": vendor_id,
                        "gst_registered": False,
                        "gst_enabled": False,
                        "gst_rate": 18.0,
                        "tax_inclusive": False
                    }
                }), 200
            return jsonify({"success": True, "profile": profile.to_dict()}), 200

        body = request.get_json(silent=True) or {}
        if not profile:
            profile = VendorTaxProfile(vendor_id=vendor_id)
            db.session.add(profile)

        gst_registered = bool(body.get("gst_registered", profile.gst_registered))
        gst_enabled = bool(body.get("gst_enabled", profile.gst_enabled))
        tax_inclusive = bool(body.get("tax_inclusive", profile.tax_inclusive))
        gst_rate = float(body.get("gst_rate", profile.gst_rate or 18.0))

        gstin_raw = body.get("gstin", profile.gstin)
        gstin = str(gstin_raw).strip().upper() if gstin_raw else None

        state_code_raw = body.get("state_code", profile.state_code)
        state_code = str(state_code_raw).strip().upper() if state_code_raw else None

        place_raw = body.get("place_of_supply_state_code", profile.place_of_supply_state_code)
        place_code = str(place_raw).strip().upper() if place_raw else None

        if gst_rate < 0 or gst_rate > 100:
            return jsonify({"success": False, "error": "gst_rate must be between 0 and 100"}), 400

        if gst_registered and not gstin:
            return jsonify({"success": False, "error": "gstin is required when gst_registered is true"}), 400

        if gstin and not GSTIN_REGEX.match(gstin):
            return jsonify({"success": False, "error": "Invalid GSTIN format"}), 400

        if state_code and not STATE_CODE_REGEX.match(state_code):
            return jsonify({"success": False, "error": "state_code must be exactly 2 alphanumeric characters"}), 400

        if place_code and not STATE_CODE_REGEX.match(place_code):
            return jsonify({"success": False, "error": "place_of_supply_state_code must be exactly 2 alphanumeric characters"}), 400

        profile.gst_registered = gst_registered
        profile.gstin = gstin
        profile.legal_name = body.get("legal_name", profile.legal_name)
        profile.state_code = state_code
        profile.place_of_supply_state_code = place_code
        profile.gst_enabled = gst_enabled
        profile.gst_rate = gst_rate
        profile.tax_inclusive = tax_inclusive

        db.session.commit()
        return jsonify({"success": True, "profile": profile.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@dashboard_service.route('/db-check', methods=['GET'])
def check_db_connection():
    try:
        # Try executing a simple query
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "success", "message": "Database connection is working!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@dashboard_service.route('/addConsole', methods=['POST'])
def add_console():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid input data"}), 400

        response, status = ConsoleService.add_console(data)
        if status < 400:
            vendor_id = data.get("vendorId") or data.get("vendor_id") or data.get("vendorID")
            if vendor_id is not None:
                try:
                    _invalidate_vendor_caches(int(vendor_id))
                except Exception:
                    pass
        return jsonify(response), status

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route("/console/<int:console_id>", methods=["GET"])
def get_console(console_id):
    result, status_code = ConsoleService.get_console_details(console_id)
    return jsonify(result), status_code

@dashboard_service.route("/vendor/<int:vendor_id>/console-pricing", methods=["GET"])
def get_console_pricing(vendor_id):
    try:
        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()

        if not available_games:
            return jsonify({"message": "No games found for this vendor"}), 404

        pricing_data = {}
        for game in available_games:
            pricing_data[game.game_name] = game.single_slot_price  # Use correct field name and just value

        return jsonify(pricing_data), 200  # return dict directly (matches frontend expectation)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route("/vendor/<int:vendor_id>/console-pricing", methods=["POST"])
def update_console_pricing(vendor_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Expecting data like: { "ps5": 20, "xbox": 15, "pc": 10 }
        updated_prices = data

        updated_count = 0

        for game_name, new_price in updated_prices.items():
            game = AvailableGame.query.filter_by(vendor_id=vendor_id, game_name=game_name).first()
            if game:
                game.single_slot_price = new_price
                updated_count += 1

        db.session.commit()
        return jsonify({"success": True, "message": f"{updated_count} pricing records updated."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getConsoles/vendor/<int:vendor_id>', methods=['GET'])
def get_consoles(vendor_id):
    started_at = time.perf_counter()
    cache_key = f"vendor:{vendor_id}"
    now_ts = time.time()

    with _vendor_consoles_cache_lock:
        cached_entry = _vendor_consoles_cache.get(cache_key)
    if cached_entry and cached_entry["expires_at"] > now_ts:
        response = jsonify(cached_entry["payload"])
        response.headers["X-Cache"] = "HIT"
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started_at) * 1000:.2f}"
        return response, 200

    try:
        availability_table = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table = f"VENDOR_{vendor_id}_DASHBOARD"
        sql_query = text(f"""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.console_type,
                c.model_number,
                c.console_number,
                c.brand,
                hs.processor_type,
                hs.graphics_card,
                hs.ram_size,
                hs.storage_capacity,
                hs.console_model_type,
                ms.available_status,
                ca.is_available,
                ca.game_id,
                cur.book_id AS current_booking_id,
                cur.user_id AS current_user_id,
                cur.username AS current_username,
                cur.start_time AS current_start_time,
                cur.end_time AS current_end_time,
                cur.date AS current_date,
                due.pending_due
            FROM available_games ag
            JOIN available_game_console agc ON agc.available_game_id = ag.id
            JOIN consoles c ON c.id = agc.console_id
            LEFT JOIN hardware_specifications hs ON hs.console_id = c.id
            LEFT JOIN maintenance_status ms ON ms.console_id = c.id
            LEFT JOIN {availability_table} ca ON ca.console_id = c.id AND ca.vendor_id = :vendor_id
            LEFT JOIN LATERAL (
                SELECT b.book_id, b.user_id, b.username, b.start_time, b.end_time, b.date
                FROM {booking_table} b
                WHERE b.console_id = c.id
                  AND b.book_status = 'current'
                  AND COALESCE(ca.is_available, TRUE) = FALSE
                ORDER BY b.date DESC, b.start_time DESC
                LIMIT 1
            ) cur ON TRUE
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(
                    CASE
                        WHEN t.total_with_tax IS NOT NULL AND t.total_with_tax > 0 THEN t.total_with_tax
                        ELSE t.amount
                    END
                ), 0.0) AS pending_due
                FROM transactions t
                WHERE t.booking_id = cur.book_id
                  AND t.vendor_id = :vendor_id
                  AND t.settlement_status = 'pending'
            ) due ON TRUE
            WHERE ag.vendor_id = :vendor_id
              AND c.vendor_id = :vendor_id
            ORDER BY c.id
        """)

        rows = db.session.execute(sql_query, {"vendor_id": vendor_id}).fetchall()
        payload = []
        for row in rows:
            normalized_type = str(row.console_type or "pc").strip().lower()
            is_pc = normalized_type == "pc"
            raw_maintenance = str(row.available_status or "").strip().lower()
            is_maintenance = raw_maintenance in {"under maintenance", "maintenance"}
            has_live_booking = bool(row.current_booking_id) and (row.is_available is False)
            occupancy_state = "maintenance" if is_maintenance else ("occupied" if has_live_booking else "free")
            pending_due = float(row.pending_due or 0.0)
            pending_due = round(pending_due, 2)
            payload.append({
                "id": row.id,
                "type": normalized_type,
                "name": row.model_number,
                "number": row.console_number,
                "icon": "Monitor" if normalized_type == "pc" else "Tv" if normalized_type == "ps5" else "Gamepad",
                "brand": row.brand,
                "processor": row.processor_type if is_pc and row.processor_type else None,
                "gpu": row.graphics_card if is_pc and row.graphics_card else None,
                "ram": row.ram_size if is_pc and row.ram_size else None,
                "storage": row.storage_capacity if row.storage_capacity else None,
                "status": occupancy_state == "free",
                "statusLabel": "Under Maintenance" if is_maintenance else ("Occupied" if has_live_booking else "Free"),
                "occupancyState": occupancy_state,
                "gameId": row.game_id,
                "currentBookingId": row.current_booking_id,
                "currentUserId": row.current_user_id,
                "currentUsername": row.current_username,
                "currentStartTime": row.current_start_time.strftime('%I:%M %p') if row.current_start_time else None,
                "currentEndTime": row.current_end_time.strftime('%I:%M %p') if row.current_end_time else None,
                "currentDate": row.current_date.isoformat() if row.current_date else None,
                "collectibleAmount": pending_due,
                "hasPendingCollection": pending_due > 0,
                "consoleModelType": row.console_model_type if row.console_model_type else None,
            })

        with _vendor_consoles_cache_lock:
            _vendor_consoles_cache[cache_key] = {
                "payload": payload,
                "expires_at": time.time() + CONSOLES_CACHE_TTL_SEC,
            }

        response = jsonify(payload)
        response.headers["X-Cache"] = "MISS"
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started_at) * 1000:.2f}"
        return response, 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/console/<int:vendor_id>/<int:console_id>', methods=['DELETE'])
def delete_console(vendor_id, console_id):
    try:
        console = Console.query.get(console_id)
        if not console:
            return jsonify({"error": "Console not found"}), 404

        # Fetch the associated available_game_id
        available_game_entry = db.session.execute(
            available_game_console.select().where(available_game_console.c.console_id == console_id)
        ).fetchone()
        available_game_id = available_game_entry[0] if available_game_entry else None

        # Delete related entries from dependent tables (if cascade is not applied)
        if console.hardware_specifications:
            db.session.delete(console.hardware_specifications)
        if console.maintenance_status:
            db.session.delete(console.maintenance_status)
        if console.price_and_cost:
            db.session.delete(console.price_and_cost)
        if console.additional_details:
            db.session.delete(console.additional_details)

        # Remove Console Associations from available_game_console
        db.session.execute(
            available_game_console.delete().where(available_game_console.c.console_id == console_id)
        )

        # Update slots associated with the available_game_id
        if available_game_id:
            slots_to_update = Slot.query.filter_by(gaming_type_id=available_game_id).all()
            for slot in slots_to_update:
                if slot.available_slot > 0:
                    slot.available_slot -= 1  # Decrement available_slot
                if slot.available_slot == 0:  # If no available slots, mark as unavailable
                    slot.is_available = False
                db.session.add(slot)

            available_game = AvailableGame.query.get(available_game_id)
            if available_game and available_game.total_slot > 0:
                available_game.total_slot -= 1

            # Commit slot updates first
            db.session.commit()

            remaining_mapping_count = (
                db.session.query(available_game_console.c.console_id)
                .filter(available_game_console.c.available_game_id == available_game_id)
                .count()
            )

            # Update the standard table VENDOR_{vendor_id}_SLOT
            table_name = f"VENDOR_{vendor_id}_SLOT"
            update_query = text(f"""
                UPDATE {table_name}
                SET available_slot = GREATEST(COALESCE(available_slot, 0) - 1, 0),
                    is_available = CASE
                        WHEN GREATEST(COALESCE(available_slot, 0) - 1, 0) > 0 THEN TRUE
                        ELSE FALSE
                    END
                WHERE slot_id IN (
                    SELECT id FROM slots WHERE gaming_type_id = :available_game_id
                );
            """)
            db.session.execute(update_query, {"available_game_id": available_game_id})
            db.session.commit()

            # If this was the last console for this game type, remove stale slot templates/rows
            # so re-adding the type starts from current day-wise configuration only.
            if remaining_mapping_count == 0:
                stale_slot_ids = [
                    int(row[0])
                    for row in db.session.query(Slot.id)
                    .filter(Slot.gaming_type_id == available_game_id)
                    .all()
                ]
                if stale_slot_ids:
                    referenced_slot_ids = {
                        int(row[0])
                        for row in db.session.query(Booking.slot_id)
                        .filter(Booking.slot_id.in_(stale_slot_ids))
                        .distinct()
                        .all()
                    }
                    deletable_slot_ids = [
                        sid for sid in stale_slot_ids if sid not in referenced_slot_ids
                    ]
                else:
                    deletable_slot_ids = []

                # Always clear vendor date-slot rows for this game type when count reaches zero.
                # (Safe: dynamic table has no FK to bookings.)
                if stale_slot_ids:
                    db.session.execute(
                        text(f"""
                            DELETE FROM {table_name}
                            WHERE slot_id IN (SELECT unnest(:slot_ids))
                        """),
                        {"slot_ids": stale_slot_ids},
                    )

                if deletable_slot_ids:
                    Slot.query.filter(
                        Slot.gaming_type_id == available_game_id,
                        Slot.id.in_(deletable_slot_ids),
                    ).delete(synchronize_session=False)
                db.session.commit()

        # ✅ Remove Console from the dynamic VENDOR_{vendor_id}_CONSOLE_AVAILABILITY table
        availability_table = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        delete_availability_query = text(f"""
            DELETE FROM {availability_table}
            WHERE console_id = :console_id
        """)
        db.session.execute(delete_availability_query, {"console_id": console_id})
        db.session.commit()

        # Delete Console
        db.session.delete(console)

        # Commit all changes
        db.session.commit()
        _invalidate_vendor_caches(vendor_id)

        return jsonify({"message": "Console deleted successfully, availability updated"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/console/update/vendor/<int:vendor_id>', methods=['PUT'])
def update_console(vendor_id):
    started_at = time.perf_counter()
    try:
        data = request.get_json(silent=True) or {}
        console_id_raw = data.get("consoleId")
        console_details = data.get("consoleDetails") or {}

        try:
            console_id = int(console_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid consoleId"}), 400

        if not console_id or not console_details:
            return jsonify({"error": "Missing required fields"}), 400

        # Scoped fetch with eager-loaded relations to avoid lazy-load round-trips.
        console = (
            Console.query
            .options(
                joinedload(Console.hardware_specifications),
                joinedload(Console.maintenance_status),
            )
            .filter(Console.id == console_id, Console.vendor_id == vendor_id)
            .first()
        )
        if not console:
            return jsonify({"error": "Console not found"}), 404

        brand = console_details.get("brand")
        if brand is not None:
            console.brand = brand
        console_name = console_details.get("name")
        if console_name is None:
            # Backward/alternate key support
            console_name = console_details.get("modelNumber")
        if console_name is not None:
            clean_name = str(console_name).strip()
            if clean_name:
                console.model_number = clean_name

        # Fetch or create hardware relation.
        hardware_spec = console.hardware_specifications
        if hardware_spec is None:
            hardware_spec = HardwareSpecification(console_id=console.id)
            db.session.add(hardware_spec)

        normalized_hw = ConsoleService.normalize_hardware_spec(
            console.console_type,
            {
                "processorType": console_details.get("processor"),
                "graphicsCard": console_details.get("gpu"),
                "ramSize": console_details.get("ram"),
                "storageCapacity": console_details.get("storage"),
                "connectivity": console_details.get("connectivity"),
                "consoleModelType": console_details.get("consoleModelType"),
            },
        )
        hardware_spec.processor_type = normalized_hw.get("processorType")
        hardware_spec.graphics_card = normalized_hw.get("graphicsCard")
        hardware_spec.ram_size = normalized_hw.get("ramSize")
        hardware_spec.storage_capacity = normalized_hw.get("storageCapacity")
        hardware_spec.connectivity = normalized_hw.get("connectivity")
        hardware_spec.console_model_type = normalized_hw.get("consoleModelType")

        maintenance = console.maintenance_status
        status_value = console_details.get("status")
        if status_value is not None:
            console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
            normalized_status = str(status_value).strip().lower()
            if isinstance(status_value, bool):
                target_is_available = bool(status_value)
                normalized_status = "available" if target_is_available else "in use"
            else:
                target_is_available = normalized_status in {"available", "true", "1", "yes"}

            if maintenance:
                if normalized_status in {"under maintenance", "maintenance"}:
                    maintenance.available_status = "Under Maintenance"
                    target_is_available = False
                elif target_is_available:
                    maintenance.available_status = "Available"
                else:
                    maintenance.available_status = "In Use"

            sql_update_status = text(f"""
                UPDATE {console_table_name}
                SET is_available = :is_available
                WHERE vendor_id = :vendor_id AND console_id = :console_id
            """)
            db.session.execute(
                sql_update_status,
                {
                    "is_available": target_is_available,
                    "vendor_id": vendor_id,
                    "console_id": console_id,
                },
            )

        db.session.commit()
        _invalidate_vendor_caches(vendor_id)
        response = jsonify({"message": "Console updated successfully"})
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started_at) * 1000:.2f}"
        return response, 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getAllDevice/consoleTypeId/<gameid>/vendor/<vendor_id>', methods=['GET'])
def get_device_for_console_type(gameid, vendor_id):
    try:
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"
        vendor_id_int = int(vendor_id)
        game_id_int = int(gameid)

        requested_game = AvailableGame.query.filter_by(id=game_id_int).first()
        requested_group = _resolve_console_group_from_name(requested_game.game_name if requested_game else "")

        # For PC bookings, keep availability rows aligned with full PC inventory.
        # This avoids modal showing fewer PCs than Console Control when some
        # VENDOR_X_CONSOLE_AVAILABILITY rows are missing for given game_id.
        if requested_group == "pc":
            pc_console_rows = (
                db.session.query(Console.id)
                .filter(Console.vendor_id == vendor_id_int)
                .filter(func.lower(func.coalesce(Console.console_type, "")) == "pc")
                .all()
            )
            pc_console_ids = [int(r.id) for r in pc_console_rows]
            if pc_console_ids:
                existing_for_game = db.session.execute(
                    text(f"""
                        SELECT console_id
                        FROM {console_table_name}
                        WHERE game_id = :game_id
                          AND console_id = ANY(:console_ids)
                    """),
                    {"game_id": game_id_int, "console_ids": pc_console_ids},
                ).fetchall()
                existing_ids = {int(r.console_id) for r in existing_for_game if r and r.console_id is not None}
                missing_ids = [cid for cid in pc_console_ids if cid not in existing_ids]

                for cid in missing_ids:
                    any_busy_row = db.session.execute(
                        text(f"""
                            SELECT 1
                            FROM {console_table_name}
                            WHERE console_id = :console_id
                              AND is_available = FALSE
                            LIMIT 1
                        """),
                        {"console_id": cid},
                    ).fetchone()
                    inferred_available = False if any_busy_row else True
                    db.session.execute(
                        text(f"""
                            INSERT INTO {console_table_name} (vendor_id, console_id, game_id, is_available)
                            VALUES (:vendor_id, :console_id, :game_id, :is_available)
                        """),
                        {
                            "vendor_id": vendor_id_int,
                            "console_id": cid,
                            "game_id": game_id_int,
                            "is_available": inferred_available,
                        },
                    )
                if missing_ids:
                    db.session.commit()
                    _invalidate_vendor_caches(vendor_id_int)

        # Reconcile stale availability flags: if a console has no current session,
        # mark all its availability rows as available.
        stale_rows = db.session.execute(
            text(f"""
                SELECT DISTINCT ca.console_id
                FROM {console_table_name} ca
                WHERE ca.game_id = :game_id
                  AND ca.is_available = FALSE
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {booking_table_name} b
                      WHERE b.console_id = ca.console_id
                        AND b.book_status = 'current'
                  )
            """),
            {"game_id": game_id_int},
        ).fetchall()
        stale_console_ids = [int(r.console_id) for r in stale_rows if r and r.console_id is not None]
        if stale_console_ids:
            db.session.execute(
                text(f"""
                    UPDATE {console_table_name}
                    SET is_available = TRUE
                    WHERE console_id = ANY(:console_ids)
                """),
                {"console_ids": stale_console_ids},
            )
            db.session.commit()
            _invalidate_vendor_caches(vendor_id_int)

        # ✅ SQL query to fetch console details
        sql_query = text(f"""
            SELECT
                ca.console_id,
                c.model_number,
                c.brand,
                MIN(CASE WHEN ca_all.is_available THEN 1 ELSE 0 END) AS is_available_int,
                :game_id AS game_id
            FROM {console_table_name} ca
            JOIN consoles c ON ca.console_id = c.id
            JOIN {console_table_name} ca_all ON ca_all.console_id = ca.console_id
            WHERE ca.game_id = :game_id
            GROUP BY ca.console_id, c.model_number, c.brand
        """)

        # ✅ Execute the query
        result = db.session.execute(sql_query, {"game_id": game_id_int}).fetchall()

        # ✅ Format the response
        devices = []
        for row in result:
            # Fetch the related AvailableGame instance by game_id
            game = AvailableGame.query.filter_by(id=row.game_id).first()
            
            devices.append({
                "consoleId": row.console_id,
                "consoleModelNumber": row.model_number,
                "brand": row.brand,
                "is_available": bool(int(row.is_available_int or 0) == 1),
                "consoleTypeName": game.game_name if game else "Unknown",  # If game exists, use game_name
                "consolePrice": game.single_slot_price
            })

        return jsonify(devices), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/updateDeviceStatus/consoleTypeId/<gameid>/console/<console_id>/bookingId/<booking_id>/vendor/<vendor_id>', methods=['POST'])
def update_console_status(gameid, console_id, booking_id, vendor_id):
    try:
        body = request.get_json(silent=True) or {}
        requested_additional_console_ids = body.get("additional_console_ids") or []
        if requested_additional_console_ids and not isinstance(requested_additional_console_ids, list):
            return jsonify({"error": "additional_console_ids must be a list"}), 400

        current_app.logger.debug(
            "Starting update_console_status | gameid=%s console_id=%s booking_id=%s vendor_id=%s",
            gameid, console_id, booking_id, vendor_id
        )

        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"
        current_app.logger.debug("Resolved table names: %s, %s", console_table_name, booking_table_name)

        # Validate booking start eligibility before occupying console.
        sql_booking_for_start = text(f"""
            SELECT date, start_time, end_time, book_status
            FROM {booking_table_name}
            WHERE book_id = :booking_id AND game_id = :game_id
        """)
        booking_row = db.session.execute(sql_booking_for_start, {
            "booking_id": booking_id,
            "game_id": gameid
        }).fetchone()
        if not booking_row:
            return jsonify({"error": "Booking not found"}), 404
        if booking_row.book_status != "upcoming":
            return jsonify({"error": "Only upcoming bookings can be started"}), 400

        allowed, reason = _booking_start_eligibility(booking_row.date, booking_row.start_time, booking_row.end_time)
        if not allowed:
            return jsonify({"error": reason}), 400

        booking_detail = Booking.query.filter_by(id=int(booking_id)).first()
        squad_details = booking_detail.squad_details if booking_detail and isinstance(booking_detail.squad_details, dict) else {}

        game = AvailableGame.query.filter_by(id=int(gameid)).first()
        console_group = _resolve_console_group_from_name(game.game_name if game else "")
        is_pc_squad = bool(
            console_group == "pc"
            and bool(squad_details.get("enabled"))
            and int(squad_details.get("player_count") or 1) > 1
        )
        required_console_count = int(squad_details.get("player_count") or 1) if is_pc_squad else 1

        selected_console_ids = [int(console_id)]
        for raw_id in requested_additional_console_ids:
            try:
                cid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if cid not in selected_console_ids:
                selected_console_ids.append(cid)

        if is_pc_squad and len(selected_console_ids) < required_console_count:
            return jsonify({
                "error": f"PC squad booking requires {required_console_count} consoles. "
                         f"Selected {len(selected_console_ids)}."
            }), 400
        if is_pc_squad and len(selected_console_ids) > required_console_count:
            selected_console_ids = selected_console_ids[:required_console_count]

        for selected_console_id in selected_console_ids:
            stale_current = db.session.execute(
                text(f"""
                    SELECT 1
                    FROM {booking_table_name}
                    WHERE console_id = :console_id
                      AND book_status = 'current'
                    LIMIT 1
                """),
                {"console_id": selected_console_id},
            ).fetchone()
            if not stale_current:
                db.session.execute(
                    text(f"""
                        UPDATE {console_table_name}
                        SET is_available = TRUE
                        WHERE console_id = :console_id
                    """),
                    {"console_id": selected_console_id},
                )

            sql_check_availability = text(f"""
                SELECT MIN(CASE WHEN is_available THEN 1 ELSE 0 END) AS is_available_int
                FROM {console_table_name}
                WHERE console_id = :console_id
            """)
            result = db.session.execute(sql_check_availability, {
                "console_id": selected_console_id,
            }).fetchone()
            current_app.logger.debug("Console availability query result: %s", result)

            if not result or result.is_available_int is None:
                current_app.logger.warning("Console not found in availability table")
                return jsonify({"error": f"Console {selected_console_id} not found in availability table"}), 404

            if int(result.is_available_int) != 1:
                current_app.logger.warning("Console already in use | console_id=%s", selected_console_id)
                return jsonify({"error": f"Console {selected_console_id} is already in use"}), 400

        for selected_console_id in selected_console_ids:
            sql_update_status = text(f"""
                UPDATE {console_table_name}
                SET is_available = FALSE
                WHERE console_id = :console_id
            """)
            db.session.execute(sql_update_status, {
                "console_id": selected_console_id,
            })
        current_app.logger.debug("Updated console statuses to occupied: %s", selected_console_ids)

        # Update booking status
        sql_update_booking_status = text(f"""
            UPDATE {booking_table_name}
            SET book_status = 'current', console_id = :console_id
            WHERE book_id = :booking_id AND game_id = :game_id AND book_status = 'upcoming'
        """)
        upd_res = db.session.execute(sql_update_booking_status, {
            "console_id": console_id,
            "game_id": gameid,
            "booking_id": booking_id
        })
        current_app.logger.debug("Booking update executed | rowcount=%s", getattr(upd_res, "rowcount", None))
        if getattr(upd_res, "rowcount", 0) != 1:
            db.session.rollback()
            return jsonify({"error": "Booking is no longer eligible to start"}), 400

        db.session.execute(
            text("UPDATE bookings SET status = 'checked_in' WHERE id = :booking_id AND status IN ('confirmed','pending_verified','pending_acceptance','checked_in')"),
            {"booking_id": booking_id}
        )

        assigned_console_labels = []
        member_console_map = []
        if selected_console_ids:
            label_rows = (
                db.session.query(Console.id, Console.console_number, Console.model_number)
                .filter(Console.id.in_(selected_console_ids))
                .all()
            )
            label_map = {}
            for lr in label_rows:
                preferred = str(lr.console_number or "").strip() or str(lr.model_number or "").strip()
                label_map[int(lr.id)] = preferred or f"Console-{int(lr.id)}"
            assigned_console_labels = [label_map.get(int(cid), f"Console-{int(cid)}") for cid in selected_console_ids]
            if is_pc_squad:
                squad_members = (
                    BookingSquadMember.query
                    .filter(BookingSquadMember.booking_id == int(booking_id))
                    .order_by(BookingSquadMember.member_position.asc())
                    .all()
                )
                for idx, member in enumerate(squad_members):
                    if idx >= len(selected_console_ids):
                        break
                    cid = int(selected_console_ids[idx])
                    member_console_map.append({
                        "member_position": int(member.member_position),
                        "member_user_id": int(member.member_user_id) if member.member_user_id else None,
                        "member_name": member.name_snapshot,
                        "console_id": cid,
                        "console_label": label_map.get(cid, f"Console-{cid}")
                    })

        if booking_detail:
            updated_squad_details = dict(squad_details) if isinstance(squad_details, dict) else {}
            if is_pc_squad:
                updated_squad_details["assigned_console_ids"] = selected_console_ids
            else:
                updated_squad_details["assigned_console_ids"] = [int(console_id)]
            if assigned_console_labels:
                updated_squad_details["assigned_console_labels"] = assigned_console_labels
            if member_console_map:
                updated_squad_details["member_console_map"] = member_console_map
            updated_squad_details["assigned_at"] = datetime.utcnow().isoformat()
            booking_detail.squad_details = updated_squad_details

        db.session.commit()
        current_app.logger.debug("DB commit successful")
        _invalidate_vendor_caches(int(vendor_id))

        # ======= Fetch and emit slot update =======
        if getattr(upd_res, "rowcount", None) is None or upd_res.rowcount != 0:
            sql_fetch_booking = text(f"""
                SELECT
                    COALESCE(b.username, u.name) AS username,
                    b.user_id,
                    b.start_time,
                    b.end_time,
                    b.date,
                    b.book_id,
                    b.game_id,
                    b.game_name,
                    b.console_id,
                    b.status,
                    b.book_status,
                    ag.single_slot_price,
                    d.slot_id,
                    d.squad_details,
                    c.model_number AS console_name,
                    c.console_number AS console_number
                FROM {booking_table_name} b
                JOIN available_games ag ON b.game_id = ag.id
                JOIN bookings d ON b.book_id = d.id
                LEFT JOIN users u ON b.user_id = u.id
                LEFT JOIN consoles c ON c.id = b.console_id
                WHERE b.book_id = :booking_id AND b.game_id = :game_id
            """)
            b_row = db.session.execute(sql_fetch_booking, {
                "booking_id": booking_id,
                "game_id": gameid
            }).mappings().fetchone()
            current_app.logger.debug("Fetched booking row: %s", dict(b_row) if b_row else None)

            if b_row and b_row.get("book_status") == "current":
                squad_members = (
                    BookingSquadMember.query
                    .filter(BookingSquadMember.booking_id == int(b_row["book_id"]))
                    .order_by(BookingSquadMember.member_position.asc())
                    .all()
                )
                squad_member_payload = [
                    {
                        "id": int(member.id),
                        "member_user_id": int(member.member_user_id) if member.member_user_id else None,
                        "member_position": int(member.member_position),
                        "is_captain": bool(member.is_captain),
                        "name": member.name_snapshot,
                        "phone": member.phone_snapshot,
                    }
                    for member in squad_members
                ]
                squad_details = b_row.get("squad_details") if isinstance(b_row.get("squad_details"), dict) else {}
                current_item = format_current_slot_item(row={
                    "slot_id": b_row["slot_id"],
                    "book_id": b_row["book_id"],
                    "start_time": b_row["start_time"],
                    "end_time": b_row["end_time"],
                    "status": b_row["status"],
                    "console_id": b_row["console_id"],
                    "username": b_row["username"],
                    "user_id": b_row["user_id"],
                    "game_id": b_row["game_id"],
                    "date": b_row["date"],
                    "single_slot_price": b_row["single_slot_price"],
                    "console_name": b_row.get("console_name"),
                    "console_number": b_row.get("console_number"),
                    "squad_enabled": bool(squad_details.get("enabled")) or len(squad_member_payload) > 1,
                    "squad_player_count": int(
                        squad_details.get("player_count")
                        or squad_details.get("playerCount")
                        or (len(squad_member_payload) if squad_member_payload else 1)
                    ),
                    "squad_members": squad_member_payload,
                    "squad_details": squad_details,
                })
                room = f"vendor_{int(vendor_id)}"
                socketio.emit("current_slot", current_item, room=room)
                current_app.logger.debug("Emitted current_slot event to room=%s | data=%s", room, current_item)

                sql_remaining = text(f"""
                    SELECT COUNT(*) AS remaining
                    FROM {console_table_name}
                    WHERE game_id = :game_id AND is_available = TRUE
                """)
                rem_row = db.session.execute(sql_remaining, {"game_id": gameid}).fetchone()
                remaining = int(rem_row.remaining) if rem_row and rem_row.remaining is not None else None
                current_app.logger.debug("Remaining consoles available for game_id=%s: %s", gameid, remaining)

                socketio.emit("console_availability", {
                    "vendorId": int(vendor_id),
                    "game_id": int(gameid),
                    "console_id": int(console_id),
                    "is_available": False,
                    "remaining_available_for_game": remaining
                }, room=room)
                current_app.logger.debug("Emitted console_availability event to room=%s", room)
                for sid in selected_console_ids:
                    if int(sid) == int(console_id):
                        continue
                    socketio.emit("console_availability", {
                        "vendorId": int(vendor_id),
                        "game_id": int(gameid),
                        "console_id": int(sid),
                        "is_available": False,
                        "remaining_available_for_game": remaining
                    }, room=room)
        # ======= END =======

        current_app.logger.debug("Successfully completed update_console_status")
        return jsonify({
            "message": "Console status and booking status updated successfully!",
            "assigned_console_ids": selected_console_ids,
            "assigned_console_labels": assigned_console_labels,
            "member_console_map": member_console_map,
            "required_console_count": required_console_count,
            "is_pc_squad": is_pc_squad,
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Failed update_console_status | error=%s", str(e))
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/assignConsoleToMultipleBookings', methods=['POST'])
def assign_console_to_multiple_bookings():
    try:
        data = request.get_json()
        console_id = data.get('console_id')
        additional_console_ids = data.get('additional_console_ids') or []
        game_id = data.get('game_id')
        booking_ids = data.get('booking_ids')  # List[int]
        vendor_id = data.get('vendor_id')

        if not all([console_id, game_id, booking_ids, vendor_id]):
            return jsonify({"error": "Missing required fields"}), 400

        if not isinstance(booking_ids, list) or not all(isinstance(bid, int) for bid in booking_ids):
            return jsonify({"error": "booking_ids must be a list of integers"}), 400
        if additional_console_ids and not isinstance(additional_console_ids, list):
            return jsonify({"error": "additional_console_ids must be a list"}), 400

        # Dynamic table names
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"

        # Validate all bookings before occupying console.
        sql_bookings_for_start = text(f"""
            SELECT book_id, date, start_time, end_time, book_status
            FROM {booking_table_name}
            WHERE book_id = ANY(:booking_ids) AND game_id = :game_id
        """)
        booking_rows = db.session.execute(sql_bookings_for_start, {
            "booking_ids": booking_ids,
            "game_id": game_id
        }).fetchall()
        if len(booking_rows) != len(booking_ids):
            return jsonify({"error": "One or more bookings were not found"}), 404

        invalid_status = [r.book_id for r in booking_rows if r.book_status != "upcoming"]
        if invalid_status:
            return jsonify({"error": f"Bookings not in upcoming state: {invalid_status}"}), 400

        not_eligible = []
        for r in booking_rows:
            allowed, reason = _booking_start_eligibility(r.date, r.start_time, r.end_time)
            if not allowed:
                not_eligible.append({"booking_id": r.book_id, "reason": reason})
        if not_eligible:
            return jsonify({"error": "Some bookings are not eligible to start", "details": not_eligible}), 400

        first_booking = Booking.query.filter_by(id=int(booking_ids[0])).first()
        first_squad = first_booking.squad_details if first_booking and isinstance(first_booking.squad_details, dict) else {}
        game = AvailableGame.query.filter_by(id=int(game_id)).first()
        console_group = _resolve_console_group_from_name(game.game_name if game else "")
        is_pc_squad = bool(
            console_group == "pc"
            and bool(first_squad.get("enabled"))
            and int(first_squad.get("player_count") or 1) > 1
        )
        required_console_count = int(first_squad.get("player_count") or 1) if is_pc_squad else 1
        selected_console_ids = [int(console_id)]
        for raw_id in additional_console_ids:
            try:
                cid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if cid not in selected_console_ids:
                selected_console_ids.append(cid)
        if is_pc_squad and len(selected_console_ids) < required_console_count:
            return jsonify({"error": f"PC squad booking requires {required_console_count} consoles"}), 400
        if is_pc_squad and len(selected_console_ids) > required_console_count:
            selected_console_ids = selected_console_ids[:required_console_count]

        for selected_console_id in selected_console_ids:
            stale_current = db.session.execute(
                text(f"""
                    SELECT 1
                    FROM {booking_table_name}
                    WHERE console_id = :console_id
                      AND book_status = 'current'
                    LIMIT 1
                """),
                {"console_id": selected_console_id},
            ).fetchone()
            if not stale_current:
                db.session.execute(
                    text(f"""
                        UPDATE {console_table_name}
                        SET is_available = TRUE
                        WHERE console_id = :console_id
                    """),
                    {"console_id": selected_console_id},
                )

            sql_check_availability = text(f"""
                SELECT MIN(CASE WHEN is_available THEN 1 ELSE 0 END) AS is_available_int
                FROM {console_table_name}
                WHERE console_id = :console_id
            """)

            result = db.session.execute(sql_check_availability, {
                "console_id": selected_console_id,
            }).fetchone()

            if not result or result.is_available_int is None:
                return jsonify({"error": f"Console {selected_console_id} not found"}), 404

            if int(result.is_available_int) != 1:
                return jsonify({"error": f"Console {selected_console_id} is already in use"}), 400

        for selected_console_id in selected_console_ids:
            sql_update_console_status = text(f"""
                UPDATE {console_table_name}
                SET is_available = FALSE
                WHERE console_id = :console_id
            """)

            db.session.execute(sql_update_console_status, {
                "console_id": selected_console_id,
            })

        # ✅ Update multiple bookings to status 'current' and assign the console
        sql_update_bookings = text(f"""
            UPDATE {booking_table_name}
            SET book_status = 'current', console_id = :console_id
            WHERE book_id = ANY(:booking_ids) AND game_id = :game_id AND book_status = 'upcoming'
        """)

        upd_multi = db.session.execute(sql_update_bookings, {
            "console_id": console_id,
            "game_id": game_id,
            "booking_ids": booking_ids
        })
        if getattr(upd_multi, "rowcount", 0) != len(booking_ids):
            db.session.rollback()
            return jsonify({"error": "One or more bookings are no longer eligible to start"}), 400

        db.session.execute(
            text("UPDATE bookings SET status = 'checked_in' WHERE id = ANY(:booking_ids) AND status IN ('confirmed','pending_verified','pending_acceptance','checked_in')"),
            {"booking_ids": booking_ids}
        )

        assigned_console_labels = []
        if selected_console_ids:
            label_rows = (
                db.session.query(Console.id, Console.console_number, Console.model_number)
                .filter(Console.id.in_(selected_console_ids))
                .all()
            )
            label_map = {}
            for lr in label_rows:
                preferred = str(lr.console_number or "").strip() or str(lr.model_number or "").strip()
                label_map[int(lr.id)] = preferred or f"Console-{int(lr.id)}"
            assigned_console_labels = [label_map.get(int(cid), f"Console-{int(cid)}") for cid in selected_console_ids]

        booking_models = Booking.query.filter(Booking.id.in_(booking_ids)).all()
        for booking_model in booking_models:
            current_squad = booking_model.squad_details if isinstance(booking_model.squad_details, dict) else {}
            updated_squad = dict(current_squad)
            updated_squad["assigned_console_ids"] = selected_console_ids if is_pc_squad else [int(console_id)]
            if assigned_console_labels:
                updated_squad["assigned_console_labels"] = assigned_console_labels
            if is_pc_squad:
                members = (
                    BookingSquadMember.query
                    .filter(BookingSquadMember.booking_id == int(booking_model.id))
                    .order_by(BookingSquadMember.member_position.asc())
                    .all()
                )
                member_console_map = []
                for idx, member in enumerate(members):
                    if idx >= len(selected_console_ids):
                        break
                    cid = int(selected_console_ids[idx])
                    member_console_map.append({
                        "member_position": int(member.member_position),
                        "member_user_id": int(member.member_user_id) if member.member_user_id else None,
                        "member_name": member.name_snapshot,
                        "console_id": cid,
                        "console_label": label_map.get(cid, f"Console-{cid}")
                    })
                if member_console_map:
                    updated_squad["member_console_map"] = member_console_map
            updated_squad["assigned_at"] = datetime.utcnow().isoformat()
            booking_model.squad_details = updated_squad

        db.session.commit()
        _invalidate_vendor_caches(int(vendor_id))

        return jsonify({
            "message": "Console assigned to multiple bookings successfully.",
            "assigned_console_ids": selected_console_ids,
            "assigned_console_labels": assigned_console_labels,
            "required_console_count": required_console_count,
            "is_pc_squad": is_pc_squad,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/releaseDevice/consoleTypeId/<gameid>/console/<console_id>/vendor/<vendor_id>', methods=['POST'])
def release_console(gameid, console_id, vendor_id):
    try:
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"

        # ✅ Check if the console exists in the table
        sql_check_console = text(f"""
            SELECT MIN(CASE WHEN is_available THEN 1 ELSE 0 END) AS is_available_int
            FROM {console_table_name}
            WHERE console_id = :console_id
        """)

        result = db.session.execute(sql_check_console, {
            "console_id": console_id,
        }).fetchone()

        if not result or result.is_available_int is None:
            return jsonify({"error": "Console not found in the availability table"}), 404

        is_available = int(result.is_available_int) == 1

        if is_available:
            # Self-heal stale dashboard linkage if console is already free but
            # booking table still has dangling 'current' rows.
            healed = db.session.execute(
                text(f"""
                    UPDATE {booking_table_name}
                    SET book_status = 'completed'
                    WHERE console_id = :console_id
                      AND book_status = 'current'
                    RETURNING book_id
                """),
                {"console_id": console_id}
            ).fetchall()

            if healed:
                healed_ids = [int(r[0]) for r in healed if r and r[0] is not None]
                if healed_ids:
                    db.session.execute(
                        text("UPDATE bookings SET status = 'completed' WHERE id = ANY(:booking_ids)"),
                        {"booking_ids": healed_ids}
                    )
                    db.session.commit()
                    _invalidate_vendor_caches(int(vendor_id))
                    return jsonify({"message": "Console already free; stale session link cleaned."}), 200

            return jsonify({"message": "Console is already available"}), 200

        # ✅ Update the status to TRUE (available)
        sql_update_status = text(f"""
            UPDATE {console_table_name}
            SET is_available = TRUE
            WHERE console_id = :console_id
        """)

        db.session.execute(sql_update_status, {
            "console_id": console_id,
        })

        # For PC squad sessions, a single booking may own multiple consoles.
        # Releasing one console should only partially end session until all assigned
        # consoles are released.
        active_rows = db.session.execute(
            text(f"""
                SELECT DISTINCT book_id
                FROM {booking_table_name}
                WHERE game_id = :game_id AND book_status = 'current'
            """),
            {"game_id": gameid}
        ).fetchall()
        active_booking_ids = [int(r.book_id) for r in active_rows if r and r.book_id is not None]

        partial_release = False
        completed_booking_ids = []
        matched_pc_squad_booking_id = None

        if active_booking_ids:
            booking_models = Booking.query.filter(Booking.id.in_(active_booking_ids)).all()
            for booking_model in booking_models:
                details = booking_model.squad_details if isinstance(booking_model.squad_details, dict) else {}
                assigned_ids = details.get("assigned_console_ids") if isinstance(details.get("assigned_console_ids"), list) else []
                normalized_assigned = []
                for cid in assigned_ids:
                    try:
                        normalized_assigned.append(int(cid))
                    except (TypeError, ValueError):
                        continue
                is_pc_squad = bool(
                    details.get("enabled")
                    and str(details.get("console_group") or "").lower() == "pc"
                    and len(normalized_assigned) > 0
                )
                if not is_pc_squad:
                    continue
                if int(console_id) not in normalized_assigned:
                    continue

                matched_pc_squad_booking_id = int(booking_model.id)
                remaining_ids = [cid for cid in normalized_assigned if cid != int(console_id)]
                released_ids = details.get("released_console_ids") if isinstance(details.get("released_console_ids"), list) else []
                normalized_released = []
                for rid in released_ids:
                    try:
                        normalized_released.append(int(rid))
                    except (TypeError, ValueError):
                        continue
                if int(console_id) not in normalized_released:
                    normalized_released.append(int(console_id))

                updated = dict(details)
                updated["assigned_console_ids"] = remaining_ids
                updated["released_console_ids"] = normalized_released
                booking_model.squad_details = updated

                if remaining_ids:
                    partial_release = True
                    db.session.execute(
                        text(f"""
                            UPDATE {booking_table_name}
                            SET console_id = :next_console_id
                            WHERE book_id = :booking_id
                              AND game_id = :game_id
                              AND book_status = 'current'
                        """),
                        {
                            "next_console_id": int(remaining_ids[0]),
                            "booking_id": int(booking_model.id),
                            "game_id": gameid,
                        }
                    )
                else:
                    db.session.execute(
                        text(f"""
                            UPDATE {booking_table_name}
                            SET book_status = 'completed'
                            WHERE book_id = :booking_id
                              AND game_id = :game_id
                              AND book_status = 'current'
                        """),
                        {"booking_id": int(booking_model.id), "game_id": gameid}
                    )
                    booking_model.status = "completed"
                    completed_booking_ids.append(int(booking_model.id))
                break

        if not matched_pc_squad_booking_id:
            # ✅ Move lifecycle one-way: current -> completed only
            sql_update_booking_status = text(f"""
                UPDATE {booking_table_name}
                SET book_status = 'completed'
                WHERE console_id = :console_id AND game_id = :game_id AND book_status = 'current'
                RETURNING book_id
            """)

            upd_release = db.session.execute(sql_update_booking_status, {
                "console_id": console_id,
                "game_id": gameid
            }).fetchall()
            if not upd_release:
                db.session.rollback()
                return jsonify({"error": "No active current session found to release"}), 400
            completed_booking_ids = [int(r.book_id) for r in upd_release if r and r.book_id is not None]

            if completed_booking_ids:
                db.session.execute(
                    text("""
                        UPDATE bookings
                        SET status = 'completed'
                        WHERE id = ANY(:booking_ids)
                    """),
                    {"booking_ids": completed_booking_ids}
                )

        # Commit the changes
        db.session.commit()
        _invalidate_vendor_caches(int(vendor_id))
        # ADDED: Calculate remaining available consoles after release
        sql_remaining = text(f"""
            SELECT COUNT(*) AS remaining
            FROM {console_table_name}
            WHERE game_id = :game_id AND is_available = TRUE
        """)
        rem_row = db.session.execute(sql_remaining, {"game_id": gameid}).fetchone()
        remaining = int(rem_row.remaining) if rem_row and rem_row.remaining is not None else None
        current_app.logger.debug("Remaining consoles available for game_id=%s: %s", gameid, remaining)
        
        #  ADDED: Emit console_availability event (same as session start but with is_available: True)
        room = f"vendor_{int(vendor_id)}"
        socketio.emit("console_availability", {
            "vendorId": int(vendor_id),
            "game_id": int(gameid),
            "console_id": int(console_id),
            "is_available": True,  #  Console is now AVAILABLE (opposite of session start)
            "remaining_available_for_game": remaining
        }, room=room)
        current_app.logger.debug("Emitted console_availability event to room=%s - console now available", room)
        

        if partial_release:
            return jsonify({
                "message": "Console released for squad member. Session remains active for remaining consoles.",
                "partial_release": True,
                "booking_id": matched_pc_squad_booking_id,
            }), 200

        return jsonify({
            "message": "Console released successfully!",
            "partial_release": False,
            "completed_booking_ids": completed_booking_ids,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getAllDevice/vendor/<int:vendor_id>', methods=['GET'])
def get_all_device_for_vendor(vendor_id):
    try:
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"

        sql_query = text(f"""
            SELECT ca.console_id, c.model_number, c.brand, ca.is_available, ca.game_id
            FROM {console_table_name} ca
            JOIN consoles c ON ca.console_id = c.id
            WHERE ca.vendor_id = :vendor_id
        """)

        result = db.session.execute(sql_query, {"vendor_id": vendor_id}).fetchall()
        game_ids = {row.game_id for row in result if row.game_id is not None}
        games = (
            AvailableGame.query
            .filter(AvailableGame.id.in_(game_ids))
            .all()
            if game_ids else []
        )
        game_lookup = {game.id: game for game in games}

        devices = []
        for row in result:
            game = game_lookup.get(row.game_id)

            devices.append({
                "consoleId": row.console_id,
                "consoleModelNumber": row.model_number,
                "brand": row.brand,
                "is_available": row.is_available,
                "consoleTypeName": game.game_name if game else "Unknown",
                "console_type_id": row.game_id,
                "consolePrice": game.single_slot_price if game else None
            })

        return jsonify(devices), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getLandingPage/vendor/<int:vendor_id>', methods=['GET'])
def get_landing_page_vendor(vendor_id):
    """Fetches vendor dashboard data including stats, booking stats, upcoming bookings, and current slots."""
    started_at = time.perf_counter()
    cache_key = f"vendor:{vendor_id}"
    now_ts = time.time()

    with _landing_page_cache_lock:
        cached_entry = _landing_page_cache.get(cache_key)
    if cached_entry and cached_entry["expires_at"] > now_ts:
        response = jsonify(cached_entry["payload"])
        response.headers["X-Cache"] = "HIT"
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started_at) * 1000:.2f}"
        return response, 200

    try:
        table_name = f"VENDOR_{vendor_id}_DASHBOARD"
        availability_table = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        today = datetime.utcnow().date()
        now_ist_dt = datetime.now(IST).replace(tzinfo=None)
        today_ist = now_ist_dt.date()
        now_ist_time = now_ist_dt.time()
        # Optional history controls:
        # - history_date=YYYY-MM-DD (exact date)
        # - history_days=N (rolling window, capped)
        history_days = LANDING_HISTORY_DAYS
        history_days_raw = request.args.get("history_days")
        if history_days_raw:
            try:
                history_days = max(0, min(60, int(history_days_raw)))
            except (TypeError, ValueError):
                history_days = LANDING_HISTORY_DAYS

        history_date_raw = (request.args.get("history_date") or "").strip()
        exact_history_date = None
        if history_date_raw:
            try:
                exact_history_date = datetime.strptime(history_date_raw, "%Y-%m-%d").date()
            except ValueError:
                exact_history_date = None

        if exact_history_date is not None:
            history_from_date = exact_history_date
            history_to_date = exact_history_date
        else:
            history_from_date = today_ist - timedelta(days=history_days)
            history_to_date = today_ist

        terminal_booking_statuses = (
            "completed",
            "cancelled",
            "canceled",
            "rejected",
            "discarded",
            "verification_failed",
        )

        # Self-heal stale current rows: only sessions with an occupied console can remain current.
        # If no occupied availability row exists for the same console, mark as completed.
        stale_current_rows = db.session.execute(
            text(f"""
                UPDATE {table_name} b
                SET book_status = 'completed'
                WHERE b.book_status = 'current'
                  AND b.console_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {availability_table} ca
                      WHERE ca.vendor_id = :vendor_id
                        AND ca.console_id = b.console_id
                        AND COALESCE(ca.is_available, TRUE) = FALSE
                  )
                RETURNING b.book_id
            """),
            {"vendor_id": vendor_id},
        ).fetchall()
        if stale_current_rows:
            healed_ids = [int(r[0]) for r in stale_current_rows if r and r[0] is not None]
            if healed_ids:
                db.session.execute(
                    text("""
                        UPDATE bookings
                        SET status = 'completed'
                        WHERE id = ANY(:booking_ids)
                    """),
                    {"booking_ids": healed_ids},
                )
                db.session.commit()

        # Keep dashboard lifecycle aligned with canonical bookings.status for terminal states.
        db.session.execute(
            text(f"""
                UPDATE {table_name} b
                SET book_status = 'completed'
                FROM bookings d
                WHERE d.id = b.book_id
                  AND LOWER(COALESCE(d.status, '')) IN (
                      'completed', 'cancelled', 'canceled', 'rejected', 'discarded', 'verification_failed'
                  )
                  AND b.book_status <> 'completed'
            """),
            {},
        )
        db.session.commit()

        # Self-heal overdue upcoming rows as "discarded" (no-show), not completed.
        overdue_upcoming_rows = db.session.execute(
            text(f"""
                UPDATE {table_name} b
                SET book_status = 'discarded'
                WHERE b.book_status = 'upcoming'
                  AND (
                      b.date < :today_ist
                      OR (
                          b.date = :today_ist
                          AND b.end_time > b.start_time
                          AND b.end_time < :now_ist_time
                      )
                  )
                RETURNING b.book_id
            """),
            {"today_ist": today_ist, "now_ist_time": now_ist_time},
        ).fetchall()
        if overdue_upcoming_rows:
            discarded_ids = [int(r[0]) for r in overdue_upcoming_rows if r and r[0] is not None]
            if discarded_ids:
                db.session.execute(
                    text("""
                        UPDATE bookings
                        SET status = 'discarded'
                        WHERE id = ANY(:booking_ids)
                          AND LOWER(COALESCE(status, '')) NOT IN
                              ('completed', 'cancelled', 'canceled', 'rejected', 'discarded', 'verification_failed')
                    """),
                    {"booking_ids": discarded_ids},
                )
                db.session.commit()

        # Self-heal overdue current rows to completed only if console is no longer occupied.
        overdue_current_rows = db.session.execute(
            text(f"""
                UPDATE {table_name} b
                SET book_status = 'completed'
                WHERE b.book_status = 'current'
                  AND (
                      b.date < :today_ist
                      OR (
                          b.date = :today_ist
                          AND b.end_time > b.start_time
                          AND b.end_time < :now_ist_time
                      )
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {availability_table} ca
                      WHERE ca.vendor_id = :vendor_id
                        AND ca.console_id = b.console_id
                        AND COALESCE(ca.is_available, TRUE) = FALSE
                  )
                RETURNING b.book_id
            """),
            {"today_ist": today_ist, "now_ist_time": now_ist_time, "vendor_id": vendor_id},
        ).fetchall()
        if overdue_current_rows:
            completed_ids = [int(r[0]) for r in overdue_current_rows if r and r[0] is not None]
            if completed_ids:
                db.session.execute(
                    text("""
                        UPDATE bookings
                        SET status = 'completed'
                        WHERE id = ANY(:booking_ids)
                          AND LOWER(COALESCE(status, '')) NOT IN
                              ('completed', 'cancelled', 'canceled', 'rejected', 'discarded', 'verification_failed')
                    """),
                    {"booking_ids": completed_ids},
                )
                db.session.commit()

        # Vendor-scoped transaction summary in one query.
        transaction_summary = (
            db.session.query(
                func.coalesce(
                    func.sum(case((Transaction.booked_date == today, Transaction.amount), else_=0.0)),
                    0.0
                ).label("today_earnings"),
                func.coalesce(
                    func.sum(case((Transaction.booked_date == today, 1), else_=0)),
                    0
                ).label("today_bookings"),
                func.coalesce(
                    func.sum(case((Transaction.settlement_status == 'pending', Transaction.amount), else_=0.0)),
                    0.0
                ).label("pending_amount"),
            )
            .filter(Transaction.vendor_id == vendor_id)
            .one()
        )

        today_earnings = float(transaction_summary.today_earnings or 0)
        today_bookings = int(transaction_summary.today_bookings or 0)
        pending_amount = float(transaction_summary.pending_amount or 0)
        cleared_amount = today_earnings - pending_amount

        # Fetch bookings from vendor-specific dashboard table (single query).
        sql_fetch_bookings = text(f"""
            SELECT 
                COALESCE(b.username, u.name) AS username, 
                b.user_id, 
                b.start_time, 
                b.end_time, 
                b.date, 
                b.book_id, 
                b.game_id, 
                b.game_name, 
                b.console_id, 
                b.status, 
                b.book_status,
                ag.single_slot_price,
                d.slot_id,
                d.squad_details,
                ca.is_available AS console_is_available,
                c.model_number AS console_name,
                c.brand AS console_brand,
                c.console_number AS console_number,
                c.console_type AS console_type
            FROM {table_name} b
            JOIN available_games ag ON b.game_id = ag.id
            JOIN bookings d ON b.book_id = d.id
            LEFT JOIN users u ON b.user_id = u.id
            LEFT JOIN {availability_table} ca
              ON ca.vendor_id = :vendor_id
             AND ca.console_id = b.console_id
             AND ca.game_id = b.game_id
            LEFT JOIN consoles c ON c.id = b.console_id
            WHERE b.date BETWEEN :history_from_date AND :history_to_date
            ORDER BY b.date ASC, b.start_time ASC, b.book_id ASC
        """)
        result = db.session.execute(
            sql_fetch_bookings,
            {
                "vendor_id": vendor_id,
                "history_from_date": history_from_date,
                "history_to_date": history_to_date,
            },
        ).fetchall()

        upcoming_bookings = []
        current_slots = []
        history_bookings = []

        booking_ids = [row.book_id for row in result]
        assigned_console_labels: Dict[int, str] = {}
        if booking_ids:
            meals_lookup = set(
                r[0] for r in db.session.query(BookingExtraService.booking_id)
                .filter(BookingExtraService.booking_id.in_(booking_ids))
                .distinct()
                .all()
            )
            assigned_console_ids = set()
            for r in result:
                details = r.squad_details if isinstance(r.squad_details, dict) else {}
                ids = details.get("assigned_console_ids")
                if isinstance(ids, list):
                    for cid in ids:
                        try:
                            assigned_console_ids.add(int(cid))
                        except (TypeError, ValueError):
                            continue
            if assigned_console_ids:
                console_rows = (
                    db.session.query(Console.id, Console.console_number, Console.model_number, Console.brand)
                    .filter(Console.id.in_(assigned_console_ids))
                    .all()
                )
                for console_row in console_rows:
                    label_bits = [
                        str(console_row.console_number or "").strip(),
                        str(console_row.model_number or "").strip(),
                    ]
                    preferred = next((bit for bit in label_bits if bit), None)
                    fallback = f"Console-{console_row.id}"
                    assigned_console_labels[int(console_row.id)] = preferred or fallback
            squad_member_rows = (
                BookingSquadMember.query
                .filter(BookingSquadMember.booking_id.in_(booking_ids))
                .order_by(BookingSquadMember.booking_id.asc(), BookingSquadMember.member_position.asc())
                .all()
            )
            squad_members_by_booking = defaultdict(list)
            for member in squad_member_rows:
                squad_members_by_booking[int(member.booking_id)].append({
                    "id": int(member.id),
                    "member_user_id": int(member.member_user_id) if member.member_user_id else None,
                    "member_position": int(member.member_position),
                    "is_captain": bool(member.is_captain),
                    "name": member.name_snapshot,
                    "phone": member.phone_snapshot,
                })
        else:
            meals_lookup = set()
            squad_members_by_booking = defaultdict(list)
        
        for row in result:
            has_meals = row.book_id in meals_lookup
            is_console_occupied = bool(row.console_id is not None and row.console_is_available is False)

            lifecycle_status = _normalize_lifecycle(
                row.book_status,
                row.date,
                row.start_time,
                row.end_time,
            )
            # Occupied current sessions must remain live even if scheduled end passed (extra-time play).
            if str(row.book_status or "").strip().lower() == "current" and is_console_occupied:
                lifecycle_status = "current"
            session_identifier = _build_session_identifier(row.book_id, row.date, row.start_time, row.end_time)
            lifecycle_step = LIFECYCLE_ORDER.get(lifecycle_status, 1)
            squad_details = row.squad_details if isinstance(row.squad_details, dict) else {}
            squad_members = squad_members_by_booking.get(int(row.book_id), [])
            squad_enabled = bool(squad_details.get("enabled")) or len(squad_members) > 1
            squad_player_count = int(
                squad_details.get("player_count")
                or squad_details.get("playerCount")
                or (len(squad_members) if squad_members else 1)
            )
            assigned_ids = squad_details.get("assigned_console_ids") if isinstance(squad_details.get("assigned_console_ids"), list) else []
            assigned_label_list = []
            for assigned_id in assigned_ids:
                try:
                    parsed_id = int(assigned_id)
                except (TypeError, ValueError):
                    continue
                if parsed_id in assigned_console_labels:
                    assigned_label_list.append(assigned_console_labels[parsed_id])
                else:
                    assigned_label_list.append(f"Console-{parsed_id}")
            if assigned_label_list:
                squad_details = dict(squad_details)
                squad_details["assigned_console_labels"] = assigned_label_list
            squad_member_names = [m.get("name") for m in squad_members if m.get("name")]

            booking_data = {
                "slotId": row.slot_id,
                "bookingId": row.book_id,
                "username": row.username,
                "userId":row.user_id,
                "game": row.game_name,
                "consoleType": row.console_name or f"Console-{row.console_id}",
                "consoleId": row.console_id,
                "consoleName": row.console_name,
                "consoleBrand": row.console_brand,
                "consoleNumber": row.console_number,
                "consoleCategory": row.console_type,
                "time": f"{row.start_time.strftime('%I:%M %p')} - {row.end_time.strftime('%I:%M %p')}",
                "status": "Confirmed" if row.status != 'pending_verified' else "Pending",
                "game_id":row.game_id,
                "date":row.date,
                "slot_price": row.single_slot_price,
                "hasMeals": has_meals,
                "lifecycleStatus": lifecycle_status,
                "lifecycleStep": lifecycle_step,
                "sessionIdentifier": session_identifier,
                "bookingRecordStatus": str(getattr(row, "status", "") or "").strip().lower(),
                "squadEnabled": squad_enabled,
                "squadPlayerCount": max(1, squad_player_count),
                "squadMembers": squad_members,
                "squadMemberNames": squad_member_names,
                "squadDetails": squad_details,
            }
            
            slot_data = {
                "slotId": row.slot_id,
                "bookId" : row.book_id,
                "startTime": row.start_time.strftime('%I:%M %p'),
                "endTime": row.end_time.strftime('%I:%M %p'),
                "status": "Booked" if row.status != 'pending_verified' else "Available",
                "consoleType": row.console_name or (f"HASH{row.console_id}" if row.console_id is not None else "Console"),
                "consoleId": row.console_id,
                "consoleName": row.console_name,
                "consoleBrand": row.console_brand,
                "consoleNumber": str(row.console_number or row.console_id),
                "consoleCode": row.console_number,
                "consoleCategory": row.console_type,
                "username": row.username,
                "userId":row.user_id,
                "game_id":row.game_id,
                "date":row.date,
                "slot_price": row.single_slot_price,
                "hasMeals": has_meals,
                "lifecycleStatus": lifecycle_status,
                "lifecycleStep": lifecycle_step,
                "sessionIdentifier": session_identifier,
                "bookingRecordStatus": str(getattr(row, "status", "") or "").strip().lower(),
                "squadEnabled": squad_enabled,
                "squadPlayerCount": max(1, squad_player_count),
                "squadMembers": squad_members,
                "squadMemberNames": squad_member_names,
                "squadDetails": squad_details,
            }

            booking_record_status = str(getattr(row, "status", "") or "").strip().lower()
            is_terminal = booking_record_status in terminal_booking_statuses

            if is_terminal:
                history_bookings.append(booking_data)
            elif lifecycle_status == "upcoming":
                upcoming_bookings.append(booking_data)
            elif lifecycle_status == "current" and is_console_occupied:
                current_slots.append(slot_data)
            elif lifecycle_status == "current":
                # If slot time says "current" but console is not occupied yet,
                # keep it visible in upcoming queue instead of dropping it.
                # This avoids disappearing bookings when occupancy sync is late.
                upcoming_bookings.append(booking_data)
            else:
                history_bookings.append(booking_data)

        # Vendor-scoped booking stats in one aggregate query.
        booking_summary = (
            db.session.query(
                func.count(Booking.id).label("total_bookings"),
                func.coalesce(func.sum(case((Booking.status == 'completed', 1), else_=0)), 0).label("completed_bookings"),
                func.coalesce(func.sum(case((Booking.status == 'cancelled', 1), else_=0)), 0).label("cancelled_bookings"),
                func.coalesce(func.sum(case((Booking.status == 'rescheduled', 1), else_=0)), 0).label("rescheduled_bookings"),
            )
            .join(AvailableGame, Booking.game_id == AvailableGame.id)
            .filter(AvailableGame.vendor_id == vendor_id)
            .one()
        )

        total_bookings = int(booking_summary.total_bookings or 0)
        completed_bookings = int(booking_summary.completed_bookings or 0)
        cancelled_bookings = int(booking_summary.cancelled_bookings or 0)
        rescheduled_bookings = int(booking_summary.rescheduled_bookings or 0)

        # Average duration from vendor slots (instead of a fixed synthetic value).
        avg_slot_minutes = (
            db.session.query(
                func.avg(
                    case(
                        (Slot.end_time > Slot.start_time, func.extract('epoch', Slot.end_time) - func.extract('epoch', Slot.start_time)),
                        else_=(func.extract('epoch', Slot.end_time) + 86400 - func.extract('epoch', Slot.start_time))
                    )
                )
            )
            .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)
            .filter(AvailableGame.vendor_id == vendor_id)
            .scalar()
        )
        average_booking_duration = f"{round((float(avg_slot_minutes or 1800) / 60.0))} min"

        # Peak booking hours from this vendor only.
        peak_hours = (
            db.session.query(func.to_char(Transaction.booking_time, 'HH24'), func.count(Transaction.id))
            .filter(Transaction.vendor_id == vendor_id)
            .group_by(func.to_char(Transaction.booking_time, 'HH24'))
            .order_by(func.count(Transaction.id).desc())
            .limit(3)
            .all()
        )
        peak_booking_hours = [f"{int(hour)}:00 - {int(hour)+1}:00" for hour, _ in peak_hours]

        payload = {
            "vendorId":vendor_id,
            "stats": {
                "todayEarnings": today_earnings,
                "todayEarningsChange": -12,  # Placeholder value
                "todayBookings": today_bookings,
                "todayBookingsChange": 8,  # Placeholder value
                "pendingAmount": pending_amount,
                "clearedAmount": cleared_amount
            },
            "bookingStats": {
                "totalBookings": total_bookings,
                "completedBookings": completed_bookings,
                "cancelledBookings": cancelled_bookings,
                "rescheduledBookings": rescheduled_bookings,
                "averageBookingDuration": average_booking_duration,
                "peakBookingHours": peak_booking_hours
            },
            "upcomingBookings": upcoming_bookings,
            "currentSlots": current_slots,
            "historyBookings": history_bookings,
        }

        with _landing_page_cache_lock:
            _landing_page_cache[cache_key] = {
                "payload": payload,
                "expires_at": time.time() + LANDING_PAGE_CACHE_TTL_SEC,
            }

        response = jsonify(payload)
        response.headers["X-Cache"] = "MISS"
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started_at) * 1000:.2f}"
        return response, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def to_24h(s: str) -> str:
    if not s:
        return ""
    try:
        return datetime.strptime(s, "%I:%M %p").strftime("%H:%M")
    except Exception:
        return s  # assume already "HH:MM"

def coerce_duration(value):
    """Force duration to a single int or None."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        return int(value[0])
    return int(value)

@dashboard_service.route('/vendor/<int:vendor_id>/dashboard', methods=['GET'])
def get_vendor_dashboard(vendor_id):
    # 1) Load vendor and related objects
    vendor = (
        db.session.query(Vendor)
        .options(
            joinedload(Vendor.physical_address),
            joinedload(Vendor.contact_info),
            joinedload(Vendor.business_registration),
            joinedload(Vendor.timing),            # not used for hours
            joinedload(Vendor.opening_days),
            joinedload(Vendor.images),
            joinedload(Vendor.documents),
            joinedload(Vendor.available_games)
        )
        .filter_by(id=vendor_id)
        .first()
    )
    vendor = db.session.query(Vendor).options(
        joinedload(Vendor.physical_address),
        joinedload(Vendor.contact_info),
        joinedload(Vendor.business_registration),
        joinedload(Vendor.timing),
        joinedload(Vendor.opening_days),
        joinedload(Vendor.images),
        joinedload(Vendor.documents),
        joinedload(Vendor.profile_image)
    ).filter_by(id=vendor_id).first()

    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404
    
    profile_image_url = vendor.profile_image.image_url if vendor.profile_image else None

    # 2) Load per-day vendor config (preferred if present)
    config_rows = db.session.execute(
        text("""
            SELECT day, opening_time, closing_time, slot_duration
            FROM vendor_day_slot_config
            WHERE vendor_id = :vendor_id
        """),
        {"vendor_id": vendor_id}
    ).fetchall()

    config_map = {}
    for r in (config_rows or []):
        dkey = (r.day or "").strip().lower()
        config_map[dkey] = {
            "open": to_24h(r.opening_time),
            "close": to_24h(r.closing_time),
            "duration": coerce_duration(r.slot_duration)
        }

    # 3) Fallback inference from Slot table (used only where config is missing)
    all_slots = (
        db.session.query(Slot)
        .join(AvailableGame, AvailableGame.id == Slot.gaming_type_id)
        .filter(AvailableGame.vendor_id == vendor_id)
        .all()
    )

    def infer_hours_and_duration(slots):
        if not slots:
            return None, None, None

        starts, ends, durations_min = [], [], []

        for s in slots:
            if not (s.start_time and s.end_time):
                continue
            starts.append(s.start_time)
            ends.append(s.end_time)

            dt_start = datetime.combine(date.today(), s.start_time)
            dt_end = datetime.combine(date.today(), s.end_time)
            if dt_end <= dt_start:
                dt_end += timedelta(days=1)
            dur_min = int((dt_end - dt_start).total_seconds() // 60)
            if dur_min > 0:
                durations_min.append(dur_min)

        if not starts or not ends:
            return None, None, None

        opening_24 = min(starts).strftime("%H:%M")
        closing_24 = max(ends).strftime("%H:%M")

        duration_value = None
        if durations_min:
            cnt = Counter(durations_min)
            duration_value = cnt.most_common(1)[0]  # mode as a single int

        return opening_24, closing_24, duration_value

    fallback_open, fallback_close, fallback_duration = infer_hours_and_duration(all_slots)

    # 4) Build operatingHours in a consistent weekday order or using vendor.opening_days
    opening_days_list = [od.day for od in (vendor.opening_days or [])] or WEEKDAY_ORDER
    opening_day_enabled_map = {}
    for od in (vendor.opening_days or []):
        raw = (od.day or "").strip().lower()
        key = raw if raw in WEEKDAY_ORDER else raw[:3]
        if key:
            opening_day_enabled_map[key] = bool(od.is_open)

    operating_hours = []
    for day_key in opening_days_list:
        dkey = (day_key or "").strip().lower()
        if dkey not in WEEKDAY_ORDER:
            dkey = dkey[:3] if dkey else ""

        cfg = config_map.get(dkey)
        if cfg:
            open_str = cfg["open"] or ""
            close_str = cfg["close"] or ""
            duration_int = coerce_duration(cfg["duration"])
        else:
            open_str = fallback_open or ""
            close_str = fallback_close or ""
            duration_int = coerce_duration(fallback_duration)

        operating_hours.append({
            "day": dkey,
            "open": open_str,
            "close": close_str,
            "slotDurationMinutes": duration_int,  # always int or None
            "isEnabled": opening_day_enabled_map.get(dkey, True),
            "is24Hours": bool(open_str and close_str and open_str == close_str),
        })

    # 5) Images
    avatar = ""
    if vendor.images:
       first_img = vendor.images[0]
       avatar = getattr(first_img, "path", None) or getattr(first_img, "url", "") or ""


    gallery_images = []
    if vendor.images:
       for img in vendor.images:
           image_url = getattr(img, "path", None) or getattr(img, "url", "") or ""
           gallery_images.append({
               "id": img.id,
               "url": image_url,
               "public_id": img.public_id,
               "uploaded_at": img.uploaded_at.isoformat() if img.uploaded_at else None
        })

    # 6) Construct response
    payload = {
        "navigation": [
            {"icon": "User", "label": "Profile"},
            {"icon": "Building2", "label": "Business Details"},
            {"icon": "Wallet", "label": "Billing"},
            {"icon": "FileCheck", "label": "Verified Documents"},
        ],
        "cafeProfile": {
            "name": vendor.cafe_name,
            "avatar": avatar,
            "membershipStatus": "Premium Member",
            "avatar": vendor.images[0].path if vendor.images else "",
            "profileImage": profile_image_url,  
            "membershipStatus": "Premium Member",  # hardcoded; change if needed
             "website": vendor.website.url if vendor.website else "",
            "email": vendor.contact_info.email if vendor.contact_info else "",
        },
        "cafeGallery": {
            "images": gallery_images  # Now returns objects instead of just URLs
        },
        "businessDetails": {
            "businessName": vendor.cafe_name,
            "businessType": "Gaming Cafe",
            "phone": vendor.contact_info.phone if vendor.contact_info else "",
            "website": vendor.website.url if vendor.website else "",
            "address": vendor.physical_address.addressLine1 if vendor.physical_address else ""
        },
        "operatingHours": operating_hours,
        "billingDetails": {
            "plan": "Premium Plan",
            "price": "$49/month, billed annually",
            "status": "Active",
            "metrics": {
                "monthlyViews": "150k",
                "ordersPerMonth": "2.5k",
                "uptime": "99.9%"
            },
            "paymentMethod": "•••• •••• •••• 4242"
        },
        "verifiedDocuments": [
            {
                "name": doc.document_type,
                "status": doc.status,
                "expiry": None
            } for doc in (vendor.documents or [])
        ]
    }

    return jsonify(payload), 200

@dashboard_service.route('/vendor/<int:vendor_id>/knowYourGamer', methods=['GET'])
def get_your_gamers(vendor_id):
    try:
        transactions = Transaction.query.filter_by(vendor_id=vendor_id).all()
        if not transactions:
            return jsonify([])

        # Prepare sets for bulk fetch
        user_ids = list({t.user_id for t in transactions})
        booking_ids = list({t.booking_id for t in transactions})
        trans_ids = list({t.id for t in transactions})
        promo_table = f"VENDOR_{vendor_id}_PROMO_DETAIL"

        # Bulk fetch users and bookings
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        bookings = {b.id: b for b in Booking.query.filter(Booking.id.in_(booking_ids)).all()}

        # Bulk fetch promo data
        promo_results = db.session.execute(text(f"""
            SELECT transaction_id, discount_applied
            FROM {promo_table}
            WHERE transaction_id IN :ids
        """), {"ids": tuple(trans_ids)}).fetchall()

        promo_dict = {row.transaction_id: row.discount_applied for row in promo_results}

        # Start building user summary
        user_summary = {}

        for trans in transactions:
            user_id = trans.user_id
            booking_id = trans.booking_id
            amount = trans.amount or 0.0
            booked_date = trans.booked_date

            user_obj = users.get(user_id)
            booking = bookings.get(booking_id)

            if not user_obj or not booking:
                continue

            phone = user_obj.contact_info.phone if user_obj.contact_info else "N/A"

            if user_id not in user_summary:
                user_summary[user_id] = {
                    "id": user_id,
                    "name": user_obj.name,
                    "contact": phone,
                    "totalSlots": 0,
                    "totalAmount": 0.0,
                    "promoCodesUsed": 0,
                    "discountAvailed": 0.0,
                    "lastVisit": booked_date,
                    "membershipTier": "Silver",
                    "notes": "N/A"
                }

            summary = user_summary[user_id]
            summary["totalSlots"] += 1
            summary["totalAmount"] += amount
            summary["lastVisit"] = max(summary["lastVisit"], booked_date)

            discount = promo_dict.get(trans.id)
            if discount:
                summary["promoCodesUsed"] += 1
                summary["discountAvailed"] += float(discount)

        # Final formatting
        result = []
        for user in user_summary.values():
            total_amount = user["totalAmount"]
            total_slots = user["totalSlots"]
            discount = user["discountAvailed"]
            net = total_amount - discount

            user["averagePerSlot"] = round(total_amount / total_slots) if total_slots else 0
            user["netRevenue"] = round(net)

            if total_slots > 10:
                user["membershipTier"] = "Platinum"
            elif total_slots > 5:
                user["membershipTier"] = "Gold"

            result.append(user)

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Error generating Know Your Gamer: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@dashboard_service.route('/vendor/<int:vendor_id>/knowYourGamer/stats', methods=['GET'])
def get_your_gamers_stats(vendor_id):
    try:
        promo_table = f"VENDOR_{vendor_id}_PROMO_DETAIL"
        today = datetime.utcnow().date()
        current_start = today.replace(day=1)
        current_end_exclusive = today + timedelta(days=1)

        previous_start = (current_start - timedelta(days=1)).replace(day=1)
        days_elapsed = (today - current_start).days + 1
        previous_end_exclusive = min(previous_start + timedelta(days=days_elapsed), current_start)

        def _pct_change(current_value, previous_value):
            if previous_value == 0:
                return "+0.00%" if current_value == 0 else "+100.00%"
            pct = ((current_value - previous_value) / previous_value) * 100
            return f"+{pct:.2f}%" if pct >= 0 else f"{pct:.2f}%"

        def _avg_session_hours(period_start, period_end_exclusive):
            rows = (
                db.session.query(Slot.start_time, Slot.end_time)
                .join(Booking, Booking.slot_id == Slot.id)
                .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)
                .join(Transaction, Transaction.booking_id == Booking.id)
                .filter(
                    AvailableGame.vendor_id == vendor_id,
                    Transaction.booking_date >= period_start,
                    Transaction.booking_date < period_end_exclusive,
                )
                .all()
            )
            if not rows:
                return 0.0

            total_minutes = 0.0
            for row in rows:
                start_dt = datetime.combine(date.today(), row.start_time)
                end_dt = datetime.combine(date.today(), row.end_time)
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                total_minutes += (end_dt - start_dt).total_seconds() / 60.0

            return (total_minutes / len(rows)) / 60.0

        total_gamers = (
            db.session.query(func.count(func.distinct(Transaction.user_id)))
            .filter(Transaction.vendor_id == vendor_id)
            .scalar()
            or 0
        )

        current_gamers = (
            db.session.query(func.count(func.distinct(Transaction.user_id)))
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date >= current_start,
                Transaction.booking_date < current_end_exclusive,
            )
            .scalar()
            or 0
        )
        previous_gamers = (
            db.session.query(func.count(func.distinct(Transaction.user_id)))
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date >= previous_start,
                Transaction.booking_date < previous_end_exclusive,
            )
            .scalar()
            or 0
        )

        average_revenue = (
            db.session.query(func.avg(Transaction.amount))
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date >= current_start,
                Transaction.booking_date < current_end_exclusive,
            )
            .scalar()
            or 0
        )
        previous_average_revenue = (
            db.session.query(func.avg(Transaction.amount))
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date >= previous_start,
                Transaction.booking_date < previous_end_exclusive,
            )
            .scalar()
            or 0
        )

        lifetime_premium_subq = (
            db.session.query(Transaction.user_id)
            .filter(Transaction.vendor_id == vendor_id)
            .group_by(Transaction.user_id)
            .having(func.sum(Transaction.amount) >= 1000)
            .subquery()
        )
        premium_members = db.session.query(func.count()).select_from(lifetime_premium_subq).scalar() or 0

        current_premium_subq = (
            db.session.query(Transaction.user_id)
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date >= current_start,
                Transaction.booking_date < current_end_exclusive,
            )
            .group_by(Transaction.user_id)
            .having(func.sum(Transaction.amount) >= 1000)
            .subquery()
        )
        current_premium = db.session.query(func.count()).select_from(current_premium_subq).scalar() or 0

        previous_premium_subq = (
            db.session.query(Transaction.user_id)
            .filter(
                Transaction.vendor_id == vendor_id,
                Transaction.booking_date >= previous_start,
                Transaction.booking_date < previous_end_exclusive,
            )
            .group_by(Transaction.user_id)
            .having(func.sum(Transaction.amount) >= 1000)
            .subquery()
        )
        previous_premium = db.session.query(func.count()).select_from(previous_premium_subq).scalar() or 0

        avg_session_time = _avg_session_hours(current_start, current_end_exclusive)
        previous_avg_session_time = _avg_session_hours(previous_start, previous_end_exclusive)

        revenue_growth = _pct_change(float(average_revenue), float(previous_average_revenue))
        total_gamers_growth = _pct_change(float(current_gamers), float(previous_gamers))
        premium_members_growth = _pct_change(float(current_premium), float(previous_premium))
        session_growth = _pct_change(float(avg_session_time), float(previous_avg_session_time))

        try:
            promo_discount = db.session.execute(
                text(f"SELECT COALESCE(SUM(discount_applied), 0) FROM {promo_table}")
            ).scalar() or 0
        except Exception:
            promo_discount = 0

        available_slots = (
            db.session.query(func.sum(Slot.available_slot))
            .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)
            .filter(AvailableGame.vendor_id == vendor_id, Slot.is_available.is_(True))
            .scalar()
            or 0
        )

        return jsonify({
            "totalGamers": total_gamers,
            "averageRevenue": round(float(average_revenue), 2),
            "premiumMembers": premium_members,
            "avgSessionTime": f"{avg_session_time:.1f} hrs" if avg_session_time > 0 else "N/A",
            "revenueGrowth": revenue_growth,
            "totalGamersGrowth": total_gamers_growth,
            "premiumMembersGrowth": premium_members_growth,
            "membersGrowth": premium_members_growth,
            "sessionGrowth": session_growth,
            "promoDiscountApplied": promo_discount,
            "availableSlots": int(available_slots),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/vendor/master', methods=['GET'])
def get_master_stats():
    email = request.args.get("email_id", type=str)

    if not email:
        return jsonify({"error": "Missing email_id parameter"}), 400

    # Get VendorAccount by email
    vendor_account = VendorAccount.query.filter_by(email=email).first()

    if not vendor_account:
        return jsonify({"error": "No vendor account found for this email"}), 404

    # Get all vendor IDs under this VendorAccount
    vendor_ids = [vendor.id for vendor in vendor_account.vendors]

    if not vendor_ids:
        return jsonify({"error": "No vendors linked to this account"}), 404

    def get_date_range(period):
        today = datetime.utcnow().date()
        if period == "Weekly":
            return today - timedelta(days=7), today
        elif period == "Monthly":
            return today.replace(day=1), today
        elif period == "Yearly":
            return today.replace(month=1, day=1), today

    analytics = {}

    for period in ["Yearly", "Monthly", "Weekly"]:
        start_date, end_date = get_date_range(period)

        # Revenue & Bookings
        revenue_query = (
            db.session.query(
                Vendor.cafe_name.label("cafe"),
                func.sum(Transaction.amount).label("revenue"),
                func.count(Transaction.id).label("bookings")
            )
            .join(Vendor, Vendor.id == Transaction.vendor_id)
            .filter(Transaction.vendor_id.in_(vendor_ids))
            .filter(Transaction.booking_date.between(start_date, end_date))
            .group_by(Vendor.cafe_name)
            .all()
        )

        revenue_by_cafe = []
        bookings_by_cafe = []
        master_revenue = 0
        master_bookings = 0

        for row in revenue_query:
            revenue_by_cafe.append({"cafe": row.cafe, "revenue": float(row.revenue)})
            bookings_by_cafe.append({"cafe": row.cafe, "bookings": row.bookings})
            master_revenue += float(row.revenue)
            master_bookings += row.bookings

        revenue_by_cafe.append({"cafe": "Master Analytics", "revenue": master_revenue})
        bookings_by_cafe.append({"cafe": "Master Analytics", "bookings": master_bookings})

        # Top Games
        top_games_query = (
            db.session.query(
                Vendor.cafe_name.label("cafe"),
                AvailableGame.game_name.label("game"),
                func.count(Booking.id).label("plays")
            )
            .join(AvailableGame, AvailableGame.vendor_id == Vendor.id)
            .join(Booking, Booking.game_id == AvailableGame.id)
            .join(Transaction, Transaction.booking_id == Booking.id)
            .filter(Vendor.id.in_(vendor_ids))
            .filter(Transaction.booking_date.between(start_date, end_date))
            .group_by(Vendor.cafe_name, AvailableGame.game_name)
            .all()
        )

        games_by_cafe = defaultdict(list)
        master_game_counts = defaultdict(int)

        for row in top_games_query:
            games_by_cafe[row.cafe].append({"game": row.game, "plays": row.plays})
            master_game_counts[row.game] += row.plays

        games_by_cafe["Master Analytics"] = [
            {"game": game, "plays": plays}
            for game, plays in sorted(master_game_counts.items(), key=lambda x: -x[1])
        ]

        # Payment Modes
        payment_query = (
            db.session.query(
                Vendor.cafe_name.label("cafe"),
                Transaction.mode_of_payment.label("mode"),
                func.count(Transaction.id).label("count")
            )
            .join(Vendor, Vendor.id == Transaction.vendor_id)
            .filter(Transaction.vendor_id.in_(vendor_ids))
            .filter(Transaction.booking_date.between(start_date, end_date))
            .group_by(Vendor.cafe_name, Transaction.mode_of_payment)
            .all()
        )

        payment_modes = defaultdict(list)
        master_payments = defaultdict(int)

        for row in payment_query:
            payment_modes[row.cafe].append({"mode": row.mode, "count": row.count})
            master_payments[row.mode] += row.count

        payment_modes["Master Analytics"] = [
            {"mode": mode, "count": count}
            for mode, count in master_payments.items()
        ]

        analytics[period] = {
            "revenueByCafe": revenue_by_cafe,
            "bookingsByCafe": bookings_by_cafe,
            "topGames": dict(games_by_cafe),
            "paymentModes": dict(payment_modes),
        }

    return jsonify(analytics)

# List categories with menus for vendor
@dashboard_service.route('/vendor/<int:vendor_id>/extras/categories', methods=['GET'])
def list_categories_with_menus(vendor_id):
    categories = ExtraServiceCategory.query.filter_by(vendor_id=vendor_id, is_active=True).all()
    result = []
    for cat in categories:
        menus = [
          {
            "id": menu.id,
            "name": menu.name,
            "price": menu.price,
            "description": menu.description,
            "is_active": menu.is_active,
          }
          for menu in cat.menus if menu.is_active
        ]
        result.append({
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "menus": menus
        })
    return jsonify(result), 200

# Add category
@dashboard_service.route('/vendor/<int:vendor_id>/extras/category', methods=['POST'])
def add_extra_service_category(vendor_id):
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')

    if not name:
        return jsonify({"error": "Category name required"}), 400

    # Check if the vendor already has 'food' amenity
    food_amenity = Amenity.query.filter_by(vendor_id=vendor_id, name='food').first()
    
    if not food_amenity:
        # Create a new 'food' amenity if it doesn't exist
        food_amenity = Amenity(
            vendor_id=vendor_id,
            name='food',
            available=True
        )
        db.session.add(food_amenity)
    else:
        # If it exists but is not available, mark it as available
        if not food_amenity.available:
            food_amenity.available = True
        db.session.add(food_amenity)  # ensure update is tracked

    # Add the new category
    category = ExtraServiceCategory(
        vendor_id=vendor_id,
        name=name,
        description=description
    )
    db.session.add(category)

    # Commit all changes together (amenity + category)
    db.session.commit()

    return jsonify({
        "id": category.id,
        "name": category.name,
        "description": category.description
    }), 201

# Add menu item under category
@dashboard_service.route('/vendor/<int:vendor_id>/extras/category/<int:category_id>/menu', methods=['POST'])
def add_extra_service_menu(vendor_id, category_id):
    category = ExtraServiceCategory.query.filter_by(id=category_id, vendor_id=vendor_id, is_active=True).first_or_404()

    data = request.get_json()
    name = data.get('name')
    price = data.get('price')
    description = data.get('description', '')

    if not name or price is None:
        return jsonify({"error": "Menu name and price required"}), 400

    menu = ExtraServiceMenu(category_id=category.id, name=name, price=price, description=description)
    db.session.add(menu)
    db.session.commit()
    return jsonify({"id": menu.id, "name": menu.name, "price": menu.price, "description": menu.description}), 201

# Update and delete endpoints similarly for categories and menus...
# Update category
@dashboard_service.route('/vendor/<int:vendor_id>/extras/category/<int:category_id>', methods=['PUT'])
def update_extra_service_category(vendor_id, category_id):
    try:
        data = request.get_json()
        category = ExtraServiceCategory.query.filter_by(id=category_id, vendor_id=vendor_id, is_active=True).first_or_404()

        name = data.get('name')
        description = data.get('description')

        if not name:
            return jsonify({"error": "Category name required"}), 400

        category.name = name
        if description is not None:
            category.description = description

        db.session.commit()
        return jsonify({"id": category.id, "name": category.name, "description": category.description}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"SQLAlchemy error updating category: {e}")
        return jsonify({"error": "Failed to update category"}), 500
    except Exception as e:
        current_app.logger.error(f"Error updating category: {e}")
        return jsonify({"error": "Failed to update category"}), 500

# Soft delete category (deactivate)
@dashboard_service.route('/vendor/<int:vendor_id>/extras/category/<int:category_id>', methods=['DELETE'])
def delete_extra_service_category(vendor_id, category_id):
    try:
        category = ExtraServiceCategory.query.filter_by(
            id=category_id, vendor_id=vendor_id, is_active=True
        ).first_or_404()

        # Soft delete the category
        category.is_active = False

        # Optionally, also soft delete all menus under this category
        for menu in category.menus:
            menu.is_active = False

        # Check if this vendor has any active categories left
        active_categories = ExtraServiceCategory.query.filter_by(
            vendor_id=vendor_id, is_active=True
        ).count()

        if active_categories == 0:
            # If no active categories left → disable "food" amenity
            food_amenity = Amenity.query.filter_by(
                vendor_id=vendor_id, name='food'
            ).first()
            if food_amenity and food_amenity.available:
                food_amenity.available = False
                db.session.add(food_amenity)

        db.session.commit()
        return jsonify({"message": "Category and related menus deactivated"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"SQLAlchemy error deleting category: {e}")
        return jsonify({"error": "Failed to delete category"}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting category: {e}")
        return jsonify({"error": "Failed to delete category"}), 500

# Update menu item
@dashboard_service.route('/vendor/<int:vendor_id>/extras/category/<int:category_id>/menu/<int:menu_id>', methods=['PUT'])
def update_extra_service_menu(vendor_id, category_id, menu_id):
    try:
        category = ExtraServiceCategory.query.filter_by(id=category_id, vendor_id=vendor_id, is_active=True).first_or_404()
        menu = ExtraServiceMenu.query.filter_by(id=menu_id, category_id=category.id, is_active=True).first_or_404()

        data = request.get_json()
        name = data.get('name')
        price = data.get('price')
        description = data.get('description')

        if not name or price is None:
            return jsonify({"error": "Menu name and price required"}), 400

        menu.name = name
        menu.price = price
        if description is not None:
            menu.description = description

        db.session.commit()
        return jsonify({"id": menu.id, "name": menu.name, "price": menu.price, "description": menu.description}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"SQLAlchemy error updating menu: {e}")
        return jsonify({"error": "Failed to update menu item"}), 500
    except Exception as e:
        current_app.logger.error(f"Error updating menu: {e}")
        return jsonify({"error": "Failed to update menu item"}), 500


# Soft delete menu item
@dashboard_service.route('/vendor/<int:vendor_id>/extras/category/<int:category_id>/menu/<int:menu_id>', methods=['DELETE'])
def delete_extra_service_menu(vendor_id, category_id, menu_id):
    try:
        category = ExtraServiceCategory.query.filter_by(id=category_id, vendor_id=vendor_id, is_active=True).first_or_404()
        menu = ExtraServiceMenu.query.filter_by(id=menu_id, category_id=category.id, is_active=True).first_or_404()

        menu.is_active = False
        db.session.commit()
        return jsonify({"message": "Menu item deactivated"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"SQLAlchemy error deleting menu: {e}")
        return jsonify({"error": "Failed to delete menu item"}), 500
    except Exception as e:
        current_app.logger.error(f"Error deleting menu: {e}")
        return jsonify({"error": "Failed to delete menu item"}), 500

# List all passes for this cafe
#@dashboard_service.route("/vendor/<int:vendor_id>/passes", methods=["GET"])
#def list_cafe_passes(vendor_id):
 #   passes = CafePass.query.filter_by(vendor_id=vendor_id, is_active=True).all()
  #  return jsonify([
   #     {
    #        "id": p.id,
     #       "name": p.name,
      #      "price": p.price,
       #     "days_valid": p.days_valid,
     #       "description": p.description,
     #       "pass_type": p.pass_type.name
     #   } for p in passes
   # ])"""

# Add a new cafe pass
#@dashboard_service.route("/vendor/<int:vendor_id>/passes", methods=["POST"])
#def create_cafe_pass(vendor_id):
 #   data = request.json
  #  name = data["name"]
   # price = data["price"]
    #days_valid = data["days_valid"]
    #pass_type_id = data["pass_type_id"]   # links to PassType (daily/monthly/...)
#    description = data.get("description", "")

 #   cafe_pass = CafePass(
#        vendor_id=vendor_id,
 #        name=name,
  #      price=price,
   #     days_valid=days_valid,
  #      pass_type_id=pass_type_id,
  #      description=description
   # )
   # db.session.add(cafe_pass)
   # db.session.commit()
  #  return jsonify({"message": "Pass created"}), 200

# Edit, delete, deactivate similar to your current pattern
@dashboard_service.route('/pass_types', methods=['GET'])
def list_pass_types():
    pass_types = PassType.query.filter_by(is_global=False).all()
    result = [{
        'id': pt.id,
        'name': pt.name,
        'description': pt.description
    } for pt in pass_types]
    return jsonify(result), 200

@dashboard_service.route('/pass_types', methods=['POST'])
def add_pass_type():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No input data provided'}), 400

    name = data.get('name')
    description = data.get('description')
    is_global = data.get('is_global', False)  # Default to False for vendor/cafe pass

    if not name:
        return jsonify({'error': 'Name is required'}), 400

    # ✅ Correct duplicate check
    existing_pass_type = PassType.query.filter_by(name=name, is_global=is_global).first()
    if existing_pass_type:
        return jsonify({'error': 'PassType with this name already exists'}), 409

    try:
        new_pass_type = PassType(
            name=name,
            description=description,
            is_global=is_global
        )
        db.session.add(new_pass_type)
        db.session.commit()

        return jsonify({
            'message': 'PassType created successfully',
            'pass_type': {
                'id': new_pass_type.id,
                'name': new_pass_type.name,
                'description': new_pass_type.description,
                'is_global': new_pass_type.is_global
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500

#dashboard_service.route("/vendor/<int:vendor_id>/passes/<int:pass_id>", methods=["DELETE"])
#def deactivate_cafe_pass(vendor_id, pass_id):
 #   try:
  #      cafe_pass = CafePass.query.filter_by(id=pass_id, vendor_id=vendor_id, is_active=True).first_or_404()
   #     cafe_pass.is_active = False
    #    db.session.commit()
     #   return jsonify({"message": "Pass deactivated successfully"}), 200
    #except Exception as e:
     #   current_app.logger.error(f"Error deactivating pass {pass_id} for vendor {vendor_id}: {e}")
      #  return jsonify({"error": "Failed to deactivate pass"}), 500

# Add these routes to your dashboard_service blueprint

@dashboard_service.route('/vendor/<int:vendor_id>/extra-services', methods=['GET'])
def get_extra_services(vendor_id):
    """Get all categories and menu items"""
    try:
        result, status_code = ExtraServiceService.get_categories_with_menus(vendor_id)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/vendor/<int:vendor_id>/extra-services/category', methods=['POST'])
def create_category(vendor_id):
    """Create new service category"""
    try:
        data = request.get_json()
        result, status_code = ExtraServiceService.create_category(vendor_id, data)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/vendor/<int:vendor_id>/extra-services/category/<int:category_id>/menu', methods=['POST'])
def create_menu_item(vendor_id, category_id):
    """Create menu item with optional image"""
    try:
        # Handle multipart form data for image upload
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = {
                'name': request.form.get('name'),
                'price': request.form.get('price'),
                'description': request.form.get('description', '')
            }
            image_file = request.files.get('image')
        else:
            data = request.get_json()
            image_file = None

        result, status_code = ExtraServiceService.create_menu_item(vendor_id, category_id, data, image_file)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/vendor/<int:vendor_id>/extra-services/category/<int:category_id>', methods=['DELETE'])
def delete_category(vendor_id, category_id):
    """Delete category"""
    try:
        result, status_code = ExtraServiceService.delete_category(vendor_id, category_id)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/vendor/<int:vendor_id>/extra-services/category/<int:category_id>/menu/<int:menu_id>', methods=['DELETE'])
def delete_menu_item(vendor_id, category_id, menu_id):
    """Delete menu item"""
    try:
        result, status_code = ExtraServiceService.delete_menu_item(vendor_id, category_id, menu_id)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_service.route('/admin/hash_pass', methods=['POST'])
def create_hash_pass():
    # Security: Add your admin authentication/authorization here
    # if not current_user.is_admin:
    #     return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    name = data.get('name')
    price = data.get('price')
    days_valid = data.get('days_valid')
    description = data.get('description', '')
    pass_type_id = data.get('pass_type_id')  # Optional - can auto-fetch

    # Find global PassType, or require pass_type_id
    pass_type = None
    if pass_type_id:
        pass_type = PassType.query.filter_by(id=pass_type_id, is_global=True).first()
    else:
        # You may choose to create a default "Hash Pass" type if not found
        pass_type = PassType.query.filter_by(is_global=True).first()

    if not pass_type:
        return jsonify({"error": "Global PassType (is_global=True) required. Please create it first."}), 400

    if not name or price is None or days_valid is None:
        return jsonify({"error": "name, price, and days_valid are required fields."}), 400

    # Create Hash Pass (vendor_id=None!)
    try:
        hash_pass = CafePass(
            vendor_id=None,
            name=name,
            price=price,
            days_valid=days_valid,
            description=description,
            pass_type_id=pass_type.id,
            is_active=True
        )
        db.session.add(hash_pass)
        db.session.commit()
        return jsonify({
            "message": "Hash Pass created successfully",
            "pass": {
                "id": hash_pass.id,
                "name": hash_pass.name,
                "price": hash_pass.price,
                "days_valid": hash_pass.days_valid,
                "description": hash_pass.description,
                "pass_type_id": hash_pass.pass_type_id,
                "vendor_id": hash_pass.vendor_id
            }
        }), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hash Pass creation failed: {e}")
        return jsonify({"error": "Failed to create Hash Pass"}), 500
    
# Profile image upload route
@dashboard_service.route('/vendor/<int:vendor_id>/update-profile-image', methods=['POST'])
def update_profile_image(vendor_id):
    """
    Upload profile image to Cloudinary and update VendorProfileImage table.
    Creates record if it doesn't exist.
    """
    try:
        # Validate request
        if 'profileImage' not in request.files:
            return jsonify({
                "success": False, 
                "message": "No profileImage file provided"
            }), 400

        profile_image = request.files['profileImage']
        
        if profile_image.filename == '':
            return jsonify({
                "success": False, 
                "message": "No file selected"
            }), 400

        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if not ('.' in profile_image.filename and 
                profile_image.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({
                "success": False, 
                "message": "Invalid file type. Please upload an image file."
            }), 400

        # Check if vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({
                "success": False, 
                "message": "Vendor not found"
            }), 404

        # Upload to Cloudinary using the service
        upload_result = CloudinaryProfileImageService.upload_profile_image(
            profile_image, 
            vendor_id
        )

        if not upload_result['success']:
            return jsonify({
                "success": False,
                "message": f"Failed to upload image: {upload_result['error']}"
            }), 500

        # Get or create VendorProfileImage record
        vendor_profile_image = VendorProfileImage.query.filter_by(vendor_id=vendor_id).first()
        if vendor_profile_image:
            # Update existing record
            vendor_profile_image.image_url = upload_result['url']
            vendor_profile_image.public_id = upload_result['public_id']
            vendor_profile_image.uploaded_at = datetime.utcnow()
        else:
            # Create new record
            vendor_profile_image = VendorProfileImage(
                vendor_id=vendor_id,
                image_url=upload_result['url'],
                public_id=upload_result['public_id']
            )
            db.session.add(vendor_profile_image)

        db.session.commit()

        current_app.logger.info(f"Profile image updated for vendor {vendor_id}: {upload_result['url']}")

        return jsonify({
            "success": True,
            "message": "Profile image updated successfully",
            "profileImage": {
                "url": upload_result['url'],
                "public_id": upload_result['public_id']
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error updating profile image for vendor {vendor_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            "success": False, 
            "message": "An error occurred while updating profile image"
        }), 500

# Get vendor profile image
@dashboard_service.route('/vendor/<int:vendor_id>/profile-image', methods=['GET'])
def get_vendor_profile_image(vendor_id):
    """Get vendor profile image information"""
    try:
        vendor_profile_image = VendorProfileImage.query.filter_by(vendor_id=vendor_id).first()
        
        if not vendor_profile_image:
            return jsonify({
                "success": False,
                "message": "Profile image not found"
            }), 404

        return jsonify({
            "success": True,
            "profileImage": {
                "id": vendor_profile_image.id,
                "vendor_id": vendor_profile_image.vendor_id,
                "url": vendor_profile_image.image_url,
                "public_id": vendor_profile_image.public_id,
                "uploaded_at": vendor_profile_image.uploaded_at.isoformat()
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching profile image for vendor {vendor_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to fetch profile image"
        }), 500

# Delete profile image
@dashboard_service.route('/vendor/<int:vendor_id>/delete-profile-image', methods=['DELETE'])
def delete_vendor_profile_image(vendor_id):
    """Delete vendor's profile image"""
    try:
        vendor_profile_image = VendorProfileImage.query.filter_by(vendor_id=vendor_id).first()
        
        if not vendor_profile_image:
            return jsonify({
                "success": False, 
                "message": "Profile image not found"
            }), 404

        # Delete from Cloudinary if exists
        if vendor_profile_image.public_id:
            delete_result = CloudinaryProfileImageService.delete_profile_image(
                vendor_profile_image.public_id
            )
            
            if not delete_result['success']:
                current_app.logger.warning(f"Failed to delete image from Cloudinary: {delete_result['error']}")

        # Delete from database
        db.session.delete(vendor_profile_image)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Profile image deleted successfully"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting profile image for vendor {vendor_id}: {str(e)}")
        db.session.rollback()
        return jsonify({
            "success": False, 
            "message": "An error occurred while deleting profile image"
        }), 500
        
   # update business details

@dashboard_service.route('/vendor/<int:vendor_id>/business-details', methods=['PATCH'])
def update_business_details(vendor_id):
    """Update vendor business details including website, phone, email, and address"""
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid or missing JSON payload'}), 400

        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'message': 'Vendor not found'}), 404

        # --- Cafe/Business Name ---
        business_name = data.get("businessName")
        if business_name:
            vendor.cafe_name = business_name.strip()

        # --- Contact Info (Phone & Email) ---
        phone = data.get("phone")
        email = data.get("email")
        if phone or email:
            contact_info = vendor.contact_info
            if not contact_info:
                contact_info = ContactInfo(
                    parent_id=vendor.id,
                    parent_type='vendor'
                )
                db.session.add(contact_info)
                vendor.contact_info = contact_info

            if phone:
                contact_info.phone = phone.strip()
            if email:
                contact_info.email = email.strip()

        # --- Website ---
        website_url = data.get("website")
        if website_url:
            website = vendor.website
            if not website:
                website = Website(vendor_id=vendor.id)
                db.session.add(website)
                vendor.website = website

            website.url = website_url.strip()

        # --- Physical Address ---
        address_line1 = data.get("address")
        if address_line1:
            physical_address = vendor.physical_address
            if not physical_address:
                physical_address = PhysicalAddress(
                    parent_id=vendor.id,        # ✅ correct field
                    parent_type="vendor",       # ✅ required for polymorphic link
                    address_type="business",    # you can adjust type if needed
                    addressLine1=address_line1.strip(),
                    pincode=data.get("pincode", ""),
                    state=data.get("state", ""),
                    country=data.get("country", "India")
                )
                db.session.add(physical_address)
                vendor.physical_address = physical_address
            else:
                physical_address.addressLine1 = address_line1.strip()
                if "pincode" in data:
                    physical_address.pincode = data["pincode"]
                if "state" in data:
                    physical_address.state = data["state"]
                if "country" in data:
                    physical_address.country = data["country"]

        db.session.commit()

        # ✅ Return updated vendor data
        return jsonify({
            'success': True,
            'message': 'Business details updated successfully',
            'data': {
                'vendorId': vendor.id,
                'businessName': vendor.cafe_name,
                'phone': vendor.contact_info.phone if vendor.contact_info else None,
                'email': vendor.contact_info.email if vendor.contact_info else None,
                'website': vendor.website.url if vendor.website else None,
                'address': {
                    'line1': vendor.physical_address.addressLine1 if vendor.physical_address else None,
                    'pincode': vendor.physical_address.pincode if vendor.physical_address else None,
                    'state': vendor.physical_address.state if vendor.physical_address else None,
                    'country': vendor.physical_address.country if vendor.physical_address else None
                } if vendor.physical_address else None
            }
        }), 200

    except SQLAlchemyError as db_err:
        db.session.rollback()
        current_app.logger.error(f"Database error updating business details: {db_err}")
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Unexpected error updating business details: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

# Get bank details for vendor
@dashboard_service.route('/vendor/<int:vendor_id>/bank-details', methods=['GET'])
def get_bank_details(vendor_id):
    """Get vendor's bank transfer details"""
    try:
        bank_details = BankTransferDetails.query.filter_by(vendor_id=vendor_id).first()
        
        if not bank_details:
            return jsonify({
                "success": False,
                "message": "No bank details found"
            }), 404
        
        # Helper functions for masking
        def mask_upi_id(upi_id):
            if not upi_id or len(upi_id) <= 4:
                return '****'
            return '****' + upi_id[4:]
        
        def mask_account_number(account_number):
            if not account_number or len(account_number) <= 4:
                return account_number
            return 'X' * (len(account_number) - 4) + account_number[-4:]
        
        return jsonify({
            "success": True,
            "bankDetails": {
                "id": bank_details.id,
                "accountHolderName": bank_details.account_holder_name,
                "bankName": bank_details.bank_name,
                "accountNumber": mask_account_number(bank_details.account_number) if bank_details.account_number else None,
                "fullAccountNumber": bank_details.account_number,
                "ifscCode": bank_details.ifsc_code,
                "upiId": mask_upi_id(bank_details.upi_id) if bank_details.upi_id else None,
                "fullUpiId": bank_details.upi_id,
                "isVerified": bank_details.is_verified,
                "verificationStatus": bank_details.verification_status,
                "createdAt": bank_details.created_at.isoformat() if bank_details.created_at else None,
                "updatedAt": bank_details.updated_at.isoformat() if bank_details.updated_at else None
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching bank details for vendor {vendor_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to fetch bank details"
        }), 500

# Add or update bank details
@dashboard_service.route('/vendor/<int:vendor_id>/bank-details', methods=['POST', 'PUT'])
def add_or_update_bank_details(vendor_id):
    """Add or update vendor's bank transfer details"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided"}), 400
        
        # Check if vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404
        
        # Determine if this is bank account or UPI based on provided data
        is_bank_account = bool(data.get('accountHolderName') or data.get('bankName') or 
                              data.get('accountNumber') or data.get('ifscCode'))
        is_upi_only = bool(data.get('upiId')) and not is_bank_account
        
        # Conditional validation based on payment method
        if is_bank_account:
            # Validate required bank fields
            required_bank_fields = ['accountHolderName', 'bankName', 'accountNumber', 'ifscCode']
            for field in required_bank_fields:
                if field not in data or not str(data[field]).strip():
                    return jsonify({"error": f"{field} is required for bank account"}), 400
            
            # Validate IFSC code format
            ifsc_code = str(data['ifscCode']).upper().strip()
            if len(ifsc_code) != 11:
                return jsonify({"error": "IFSC code must be 11 characters"}), 400
        elif is_upi_only:
            # Validate UPI ID
            if not data.get('upiId') or not str(data['upiId']).strip():
                return jsonify({"error": "UPI ID is required for UPI payment method"}), 400
        else:
            return jsonify({"error": "Please provide either bank account details or UPI ID"}), 400
        
        # Get or create bank details
        bank_details = BankTransferDetails.query.filter_by(vendor_id=vendor_id).first()
        
        if bank_details:
            # Update existing record
            if is_bank_account:
                bank_details.account_holder_name = str(data['accountHolderName']).strip()
                bank_details.bank_name = str(data['bankName']).strip()
                bank_details.account_number = str(data['accountNumber']).strip()
                bank_details.ifsc_code = str(data['ifscCode']).upper().strip()
                bank_details.upi_id = str(data.get('upiId', '')).strip() if data.get('upiId') else None
            else:  # UPI only
                # Clear bank fields for UPI-only setup
                bank_details.account_holder_name = None
                bank_details.bank_name = None
                bank_details.account_number = None
                bank_details.ifsc_code = None
                bank_details.upi_id = str(data['upiId']).strip()
            
            # Reset verification when details change
            bank_details.is_verified = False
            bank_details.verification_status = 'PENDING'
            action = "updated"
        else:
            # Create new record
            if is_bank_account:
                bank_details = BankTransferDetails(
                    vendor_id=vendor_id,
                    account_holder_name=str(data['accountHolderName']).strip(),
                    bank_name=str(data['bankName']).strip(),
                    account_number=str(data['accountNumber']).strip(),
                    ifsc_code=str(data['ifscCode']).upper().strip(),
                    upi_id=str(data.get('upiId', '')).strip() if data.get('upiId') else None
                )
            else:  # UPI only
                bank_details = BankTransferDetails(
                    vendor_id=vendor_id,
                    account_holder_name=None,
                    bank_name=None,
                    account_number=None,
                    ifsc_code=None,
                    upi_id=str(data['upiId']).strip()
                )
            
            db.session.add(bank_details)
            action = "added"
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Payment details {action} successfully",
            "bankDetails": {
                "id": bank_details.id,
                "accountHolderName": bank_details.account_holder_name,
                "bankName": bank_details.bank_name,
                "accountNumber": bank_details.get_masked_account_number() if bank_details.account_number else None,
                "fullAccountNumber": bank_details.account_number,
                "ifscCode": bank_details.ifsc_code,
                "upiId": bank_details.get_masked_upi_id() if bank_details.upi_id else None,
                "fullUpiId": bank_details.upi_id,
                "isVerified": bank_details.is_verified,
                "verificationStatus": bank_details.verification_status
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating bank details for vendor {vendor_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to update payment details"
        }), 500

# Get payout history
@dashboard_service.route('/vendor/<int:vendor_id>/payouts', methods=['GET'])
def get_payout_history(vendor_id):
    """Get vendor's payout transaction history"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Query payouts with pagination
        payouts_query = PayoutTransaction.query.filter_by(vendor_id=vendor_id)\
            .order_by(PayoutTransaction.payout_date.desc())
        
        total_payouts = payouts_query.count()
        payouts = payouts_query.offset((page - 1) * per_page).limit(per_page).all()
        
        return jsonify({
            "success": True,
            "payouts": [{
                "id": payout.id,
                "amount": float(payout.amount),
                "transferMode": payout.transfer_mode,
                "utrNumber": payout.utr_number,
                "payoutDate": payout.payout_date.isoformat() if payout.payout_date else None,
                "status": payout.status,
                "remarks": payout.remarks,
                "createdAt": payout.created_at.isoformat() if payout.created_at else None
            } for payout in payouts],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_payouts,
                "total_pages": (total_payouts + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching payouts for vendor {vendor_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to fetch payout history"
        }), 500

# Create a new payout (for testing or admin use)
@dashboard_service.route('/vendor/<int:vendor_id>/payouts', methods=['POST'])
def create_payout(vendor_id):
    """Create a new payout transaction"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided"}), 400
        
        # Validate required fields
        if 'amount' not in data or 'transferMode' not in data:
            return jsonify({"error": "Amount and transferMode are required"}), 400
        
        amount = float(data['amount'])
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400
        
        transfer_mode = data['transferMode'].upper()
        if transfer_mode not in ['BANK', 'UPI']:
            return jsonify({"error": "Transfer mode must be BANK or UPI"}), 400
        
        # Check if vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404
        
        # Create new payout
        payout = PayoutTransaction(
            vendor_id=vendor_id,
            amount=amount,
            transfer_mode=transfer_mode,
            utr_number=data.get('utrNumber'),
            status=data.get('status', 'PENDING'),
            remarks=data.get('remarks')
        )
        
        db.session.add(payout)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Payout created successfully",
            "payout": {
                "id": payout.id,
                "amount": float(payout.amount),
                "transferMode": payout.transfer_mode,
                "status": payout.status
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating payout for vendor {vendor_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to create payout"
        }), 500
        
        
        
        # Get vendor's current payment method preferences
# Updated API routes in dashboard_service.py

@dashboard_service.route('/vendor/<int:vendor_id>/paymentMethods', methods=['GET'])
def get_all_payment_methods_for_vendor(vendor_id):
    """Get ALL available payment methods from payment_method table and show vendor's selections"""
    try:
        # Check if vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Get ALL payment methods from payment_method table (available for all vendors)
        all_methods = PaymentMethod.query.all()
        
        if not all_methods:
            return jsonify({
                'success': False,
                'message': 'No payment methods available in system',
                'payment_methods': []
            }), 200
        
        # Get vendor's currently enabled payment methods
        vendor_selected_methods = db.session.query(PaymentVendorMap.pay_method_id).filter_by(vendor_id=vendor_id).all()
        enabled_method_ids = {method[0] for method in vendor_selected_methods}
        
        # Prepare response with all available methods
        methods_data = []
        for method in all_methods:
            display_name = 'Pay at Cafe' if method.method_name == 'Pay at Cafe' else 'Hash'
            description = (
                'Customers pay directly at your cafe using cash or card' 
                if method.method_name == 'pay_at_cafe' 
                else 'Customers can use Hash Pass for seamless digital payments'
            )
            
            methods_data.append({
                'pay_method_id': method.pay_method_id,
                'method_name': method.method_name,
                'display_name': display_name,
                'description': description,
                'is_enabled': method.pay_method_id in enabled_method_ids  # true if vendor has enabled this method
            })
        
        return jsonify({
            'success': True,
            'vendor_id': vendor_id,
            'payment_methods': methods_data,
            'total_available_methods': len(methods_data),
            'vendor_enabled_methods': len(enabled_method_ids)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching payment methods for vendor {vendor_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_service.route('/vendor/<int:vendor_id>/paymentMethods/toggle', methods=['POST'])
def toggle_payment_method_for_vendor(vendor_id):
    """Toggle payment method for vendor - registers/unregisters vendor in payment_vendor_map"""
    try:
        data = request.get_json()
        
        if not data or 'pay_method_id' not in data:
            return jsonify({'success': False, 'error': 'pay_method_id is required'}), 400
        
        pay_method_id = data['pay_method_id']
        
        # Validate vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'success': False, 'error': 'Vendor not found'}), 404
        
        # Validate payment method exists
        payment_method = PaymentMethod.query.get(pay_method_id)
        if not payment_method:
            return jsonify({'success': False, 'error': 'Payment method not found'}), 404
        
        # Check if vendor is already registered for this payment method
        existing_registration = PaymentVendorMap.query.filter_by(
            vendor_id=vendor_id, 
            pay_method_id=pay_method_id
        ).first()
        
        if existing_registration:
            # Vendor is registered - unregister (disable)
            db.session.delete(existing_registration)
            action = 'disabled'
            is_enabled = False
        else:
            # Vendor is not registered - register (enable)
            new_registration = PaymentVendorMap(
                vendor_id=vendor_id,
                pay_method_id=pay_method_id
            )
            db.session.add(new_registration)
            action = 'enabled'
            is_enabled = True
        
        db.session.commit()
        
        display_name = 'Pay at Cafe' if payment_method.method_name == 'pay_at_cafe' else 'Hash'
        
        return jsonify({
            'success': True,
            'message': f'{display_name} {action} successfully',
            'data': {
                'vendor_id': vendor_id,
                'pay_method_id': pay_method_id,
                'method_name': payment_method.method_name,
                'display_name': display_name,
                'is_enabled': is_enabled,
                'action': action
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling payment method for vendor {vendor_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Get payment methods statistics for vendor
@dashboard_service.route('/vendor/<int:vendor_id>/payment-methods/stats', methods=['GET'])
def get_payment_method_stats(vendor_id):
    """Get payment method usage statistics for vendor"""
    try:
        # Get vendor's enabled payment methods
        enabled_methods = db.session.query(
            PaymentMethod.method_name,
            PaymentMethod.pay_method_id
        ).join(
            PaymentVendorMap, PaymentMethod.pay_method_id == PaymentVendorMap.pay_method_id
        ).filter(PaymentVendorMap.vendor_id == vendor_id).all()
        
        # Get transaction counts by payment method for this vendor
        transaction_stats = db.session.query(
            Transaction.mode_of_payment,
            func.count(Transaction.id).label('count'),
            func.sum(Transaction.amount).label('total_amount')
        ).filter(
            Transaction.vendor_id == vendor_id
        ).group_by(Transaction.mode_of_payment).all()
        
        # Format response
        method_stats = []
        for method_name, method_id in enabled_methods:
            display_name = 'Pay at Cafe' if method_name == 'pay_at_cafe' else 'Hash'
            
            # Find matching transaction stats
            usage_count = 0
            total_revenue = 0
            for stat in transaction_stats:
                if (method_name == 'pay_at_cafe' and stat.mode_of_payment in ['cash', 'card']) or \
                   (method_name == 'hash' and stat.mode_of_payment == 'hash'):
                    usage_count += stat.count
                    total_revenue += float(stat.total_amount or 0)
            
            method_stats.append({
                'pay_method_id': method_id,
                'method_name': method_name,
                'display_name': display_name,
                'usage_count': usage_count,
                'total_revenue': total_revenue,
                'is_enabled': True
            })
        
        return jsonify({
            'success': True,
            'vendor_id': vendor_id,
            'payment_method_stats': method_stats,
            'total_enabled_methods': len(method_stats)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching payment method stats for vendor {vendor_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_service.route('/booking/<int:booking_id>/details', methods=['GET'])
def get_booking_details(booking_id):
    """Get detailed booking information including extra services/meals"""
    try:
        from app.models.bookingSquadMember import BookingSquadMember

        # Get the booking
        booking = Booking.query.filter_by(id=booking_id).first()
        
        if not booking:
            return jsonify({"success": False, "error": "Booking not found"}), 404
        
        # Get user details
        user = User.query.filter_by(id=booking.user_id).first()
        
        # Get extra services for this booking
        extra_services = []
        booking_extra_services = BookingExtraService.query.filter_by(booking_id=booking_id).all()
        squad_members = (
            BookingSquadMember.query
            .filter_by(booking_id=booking_id)
            .order_by(BookingSquadMember.member_position.asc())
            .all()
        )
        
        for extra in booking_extra_services:
            # Get menu item details
            menu_item = ExtraServiceMenu.query.filter_by(id=extra.menu_item_id).first()
            if menu_item:
                # Get category details
                category = ExtraServiceCategory.query.filter_by(id=menu_item.category_id).first()
                
                extra_detail = {
                    "id": extra.id,
                    "menu_item_id": extra.menu_item_id,
                    "menu_item_name": menu_item.name,
                    "category_name": category.name if category else "Unknown",
                    "quantity": extra.quantity,
                    "unit_price": float(extra.unit_price),
                    "total_price": float(extra.total_price)
                }
                extra_services.append(extra_detail)
        
        # Prepare response
        result = {
            "booking": {
                "id": booking.id,
                "user_id": booking.user_id,
                "username": user.name if user else "Unknown",
                "game_id": booking.game_id,
                "slot_id": booking.slot_id,
                "status": booking.status,
                "squad_details": booking.squad_details or {},
                "squad_members": [
                    {
                        "id": member.id,
                        "member_user_id": member.member_user_id,
                        "member_position": member.member_position,
                        "is_captain": member.is_captain,
                        "name": member.name_snapshot,
                        "phone": member.phone_snapshot,
                    }
                    for member in squad_members
                ],
               
                "extra_services": extra_services
            }
        }
        
        return jsonify({
            "success": True,
            **result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching booking details for booking_id {booking_id}: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# app/routes.py - Pass Management Routes

@dashboard_service.route('/vendor/<int:vendor_id>/passes', methods=['GET'])
def get_vendor_passes(vendor_id):
    """Get all passes for a vendor (both date-based and hour-based)"""
    try:
        from app.models.passModels import CafePass
        
        passes = CafePass.query.filter_by(vendor_id=vendor_id, is_active=True).all()
        
        return jsonify({
            'passes': [p.to_dict() for p in passes]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching passes for vendor {vendor_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_service.route('/vendor/<int:vendor_id>/passes', methods=['POST'])  # ✅ FIXED: Removed /create
def create_vendor_pass(vendor_id):
    """Create new pass (date-based or hour-based)"""
    try:
        from app.models.passModels import CafePass, PassType
        
        data = request.get_json()
        
        # Validate required fields for BOTH types
        required = ['name', 'price', 'pass_mode', 'days_valid']  # ✅ days_valid required for both
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields: name, price, pass_mode, days_valid'}), 400
        
        pass_mode = data['pass_mode']
        if pass_mode not in ['date_based', 'hour_based']:
            return jsonify({'error': 'Invalid pass_mode. Must be date_based or hour_based'}), 400
        
        # Validate hour-based specific fields
        if pass_mode == 'hour_based':
            required_hour = ['total_hours', 'hour_calculation_mode']
            if not all(k in data for k in required_hour):
                return jsonify({'error': 'total_hours and hour_calculation_mode required for hour_based pass'}), 400
            
            # Validate calculation mode
            if data['hour_calculation_mode'] not in ['actual_duration', 'vendor_config']:
                return jsonify({'error': 'hour_calculation_mode must be actual_duration or vendor_config'}), 400
            
            if data['hour_calculation_mode'] == 'vendor_config' and 'hours_per_slot' not in data:
                return jsonify({'error': 'hours_per_slot required when hour_calculation_mode is vendor_config'}), 400
        
        # Create pass
        new_pass = CafePass(
            vendor_id=vendor_id,
            pass_type_id=data.get('pass_type_id'),
            name=data['name'],
            price=float(data['price']),
            description=data.get('description'),
            pass_mode=pass_mode,
            days_valid=int(data['days_valid']),  # ✅ Always required
            total_hours=float(data['total_hours']) if data.get('total_hours') else None,
            hour_calculation_mode=data.get('hour_calculation_mode'),
            hours_per_slot=float(data['hours_per_slot']) if data.get('hours_per_slot') else None,
            is_active=True
        )
        
        db.session.add(new_pass)
        db.session.commit()
        
        current_app.logger.info(f"Pass created: {new_pass.name} (ID: {new_pass.id}) for vendor {vendor_id}")
        
        return jsonify({
            'success': True,
            'message': 'Pass created successfully',
            'pass': new_pass.to_dict()
        }), 201
        
    except ValueError as ve:
        return jsonify({'error': f'Invalid data format: {str(ve)}'}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating pass for vendor {vendor_id}: {str(e)}")
        return jsonify({'error': f'Failed to create pass: {str(e)}'}), 500


@dashboard_service.route('/vendor/<int:vendor_id>/passes/<int:pass_id>', methods=['PUT'])
def update_vendor_pass(vendor_id, pass_id):
    """Update existing pass"""
    try:
        from app.models.passModels import CafePass
        
        cafe_pass = CafePass.query.filter_by(id=pass_id, vendor_id=vendor_id).first()
        if not cafe_pass:
            return jsonify({'error': 'Pass not found'}), 404
        
        data = request.get_json()
        
        # Update common fields
        if 'name' in data:
            cafe_pass.name = data['name']
        if 'price' in data:
            cafe_pass.price = float(data['price'])
        if 'description' in data:
            cafe_pass.description = data['description']
        if 'is_active' in data:
            cafe_pass.is_active = bool(data['is_active'])
        if 'days_valid' in data:  # ✅ Can update for both types
            cafe_pass.days_valid = int(data['days_valid'])
        if 'pass_type_id' in data:
            cafe_pass.pass_type_id = data['pass_type_id']
        
        # Mode-specific updates
        if cafe_pass.pass_mode == 'hour_based':
            if 'total_hours' in data:
                cafe_pass.total_hours = float(data['total_hours'])
            if 'hour_calculation_mode' in data:
                if data['hour_calculation_mode'] not in ['actual_duration', 'vendor_config']:
                    return jsonify({'error': 'Invalid hour_calculation_mode'}), 400
                cafe_pass.hour_calculation_mode = data['hour_calculation_mode']
            if 'hours_per_slot' in data:
                cafe_pass.hours_per_slot = float(data['hours_per_slot']) if data['hours_per_slot'] else None
        
        db.session.commit()
        
        current_app.logger.info(f"Pass updated: {cafe_pass.name} (ID: {pass_id})")
        
        return jsonify({
            'success': True,
            'message': 'Pass updated successfully',
            'pass': cafe_pass.to_dict()
        }), 200
        
    except ValueError as ve:
        return jsonify({'error': f'Invalid data format: {str(ve)}'}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating pass {pass_id}: {str(e)}")
        return jsonify({'error': f'Failed to update pass: {str(e)}'}), 500


@dashboard_service.route('/vendor/<int:vendor_id>/passes/<int:pass_id>', methods=['DELETE'])
def delete_vendor_pass(vendor_id, pass_id):
    """Deactivate a pass (soft delete)"""
    try:
        from app.models.passModels import CafePass
        
        cafe_pass = CafePass.query.filter_by(id=pass_id, vendor_id=vendor_id).first()
        if not cafe_pass:
            return jsonify({'error': 'Pass not found'}), 404
        
        cafe_pass.is_active = False
        db.session.commit()
        
        current_app.logger.info(f"Pass deactivated: {cafe_pass.name} (ID: {pass_id})")
        
        return jsonify({
            'success': True,
            'message': 'Pass deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deactivating pass {pass_id}: {str(e)}")
        return jsonify({'error': f'Failed to deactivate pass: {str(e)}'}), 500
