from flask import Blueprint, request, jsonify, current_app
from datetime import datetime,timedelta
from .models.transaction import Transaction
from app.extension.extensions import db
from sqlalchemy import cast, Date, text, func
from app.services.console_service import ConsoleService

from .models.console import Console
from .models.availableGame import AvailableGame, available_game_console
from .models.booking import Booking
from .models.cafePass import CafePass
from .models.passType import PassType
from .models.userPass import UserPass
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

dashboard_service = Blueprint("dashboard_service", __name__)

@dashboard_service.route('/transactionReport/<int:vendor_id>/<string:to_date>/<string:from_date>', methods=['GET'])
def get_transaction_report(to_date, from_date, vendor_id):
    try:
        # Convert date parameters to datetime objects
        to_date = datetime.strptime(to_date, "%Y%m%d").date()

        if not from_date or from_date.lower() == "null":
            from_date = datetime.utcnow().date()
        else:
            from_date = datetime.strptime(from_date, "%Y%m%d").date()

        transactions = Transaction.query.filter(
            Transaction.vendor_id == vendor_id and
            cast(Transaction.booked_date, Date).between(from_date, to_date)
        ).all()


        current_app.logger.info(f"transactions {transactions} {to_date} {from_date}")

        # Format response data
        result = [{
            "id": txn.id,
            "slotDate": txn.booked_date.strftime("%Y-%m-%d"),
            "slotTime": txn.booking_time.strftime("%I:%M %p"),
            "userName": User.query.filter(User.id == txn.user_id).first().name if txn.user_id else None,
            "amount": txn.amount,
            "modeOfPayment": txn.mode_of_payment,
            "bookingType": txn.booking_type,
            "settlementStatus": txn.settlement_status,
            "userId":txn.user_id,
            "bookedOn":txn.booked_date
        } for txn in transactions]
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    try:
        availability_table = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        # Fetch available games associated with the given vendor ID
        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()

        # Extract consoles from the available games
        consoles = []
        for game in available_games:
            for console in game.consoles:
                # Get availability status for each console
                availability_query = text(f"""
                SELECT is_available 
                FROM {availability_table} 
                WHERE console_id = :console_id
                """)
                result = db.session.execute(availability_query, {"console_id": console.id})
                available_status = result.scalar()  # Get the first value of the result, which is `is_available`

                # Prepare the console data
                console_data = {
                    "id": console.id,
                    "type": console.console_type,
                    "name": console.model_number,
                    "number": console.console_number,
                    "icon": "Monitor" if "PC" in console.console_type else "Tv" if "PS" in console.console_type else "Gamepad",
                    "brand": console.brand,
                    "processor": console.hardware_specifications.processor_type if console.hardware_specifications else "N/A",
                    "gpu": console.hardware_specifications.graphics_card if console.hardware_specifications else "N/A",
                    "ram": console.hardware_specifications.ram_size if console.hardware_specifications else "N/A",
                    "storage": console.hardware_specifications.storage_capacity if console.hardware_specifications else "N/A",
                    "status": available_status,
                    "consoleModelType": console.hardware_specifications.console_model_type if console.hardware_specifications else "N/A",
                }

                # Append the console data to the list
                consoles.append(console_data)

        return jsonify(consoles), 200

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

            # Update the standard table VENDOR_{vendor_id}_SLOT
            table_name = f"VENDOR_{vendor_id}_SLOT"
            update_query = text(f"""
                UPDATE {table_name}
                SET available_slot = available_slot - 1,
                    is_available = CASE WHEN available_slot - 1 > 0 THEN TRUE ELSE FALSE END
                WHERE slot_id IN (
                    SELECT id FROM slots WHERE gaming_type_id = :available_game_id
                );
            """)
            db.session.execute(update_query, {"available_game_id": available_game_id})
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

        return jsonify({"message": "Console deleted successfully, availability updated"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/console/update/vendor/<vendor_id>', methods=['PUT'])
def update_console(vendor_id):
    try:
        data = request.get_json()
        console_id = data.get("consoleId")
        console_details = data.get("consoleDetails", {})

        if not console_id or not console_details:
            return jsonify({"error": "Missing required fields"}), 400

        # ✅ Fetch the console from the database
        console = Console.query.get(console_id)
        if not console:
            return jsonify({"error": "Console not found"}), 404

        # ✅ Update Console Details
        console.brand = console_details.get("brand", console.brand)

        # ✅ Fetch or Create Related Hardware Specification
        if not console.hardware_specifications:
            hardware_spec = HardwareSpecification(console_id=console.id)
            db.session.add(hardware_spec)
        else:
            hardware_spec = console.hardware_specifications

        hardware_spec.processor_type = console_details.get("processor", hardware_spec.processor_type)
        hardware_spec.graphics_card = console_details.get("gpu", hardware_spec.graphics_card)
        hardware_spec.ram_size = console_details.get("ram", hardware_spec.ram_size)
        hardware_spec.storage_capacity = console_details.get("storage", hardware_spec.storage_capacity)
        hardware_spec.console_model_type = console_details.get("consoleModelType", hardware_spec.console_model_type)

        # ✅ Fetch or Update Maintenance Status
        if console.maintenance_status:
             # ✅ Define the dynamic console availability table name
            console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
            console.maintenance_status.available_status = console_details.get("status", console.maintenance_status.available_status)
            if console.maintenance_status.available_status != "available":
                # ✅ Update the status to false (occupied)
                sql_update_status = text(f"""
                    UPDATE {console_table_name}
                    SET is_available = FALSE
                    WHERE console_id = :console_id
                """)
            else:
                # ✅ Update the status to false (occupied)
                sql_update_status = text(f"""
                    UPDATE {console_table_name}
                    SET is_available = TRUE
                    WHERE console_id = :console_id
                """)

            db.session.execute(sql_update_status, {
                "console_id": console_id
            })

        # ✅ Commit Changes
        db.session.commit()

        return jsonify({"message": "Console updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getAllDevice/consoleTypeId/<gameid>/vendor/<vendor_id>', methods=['GET'])
def get_device_for_console_type(gameid, vendor_id):
    try:
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"

        # ✅ SQL query to fetch console details
        sql_query = text(f"""
            SELECT ca.console_id, c.model_number, c.brand, ca.is_available, ca.game_id
            FROM {console_table_name} ca
            JOIN consoles c ON ca.console_id = c.id
            WHERE ca.game_id = :game_id
        """)

        # ✅ Execute the query
        result = db.session.execute(sql_query, {"game_id": gameid}).fetchall()

        # ✅ Format the response
        devices = []
        for row in result:
            # Fetch the related AvailableGame instance by game_id
            game = AvailableGame.query.filter_by(id=row.game_id).first()
            
            devices.append({
                "consoleId": row.console_id,
                "consoleModelNumber": row.model_number,
                "brand": row.brand,
                "is_available": row.is_available,
                "consoleTypeName": game.game_name if game else "Unknown",  # If game exists, use game_name
                "consolePrice": game.single_slot_price
            })

        return jsonify(devices), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/updateDeviceStatus/consoleTypeId/<gameid>/console/<console_id>/bookingId/<booking_id>/vendor/<vendor_id>', methods=['POST'])
def update_console_status(gameid, console_id, booking_id, vendor_id):
    try:
        current_app.logger.debug(
            "Starting update_console_status | gameid=%s console_id=%s booking_id=%s vendor_id=%s",
            gameid, console_id, booking_id, vendor_id
        )

        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"
        current_app.logger.debug("Resolved table names: %s, %s", console_table_name, booking_table_name)

        # Check if the console is available
        sql_check_availability = text(f"""
            SELECT is_available FROM {console_table_name}
            WHERE console_id = :console_id AND game_id = :game_id
        """)
        result = db.session.execute(sql_check_availability, {
            "console_id": console_id,
            "game_id": gameid
        }).fetchone()
        current_app.logger.debug("Console availability query result: %s", result)

        if not result:
            current_app.logger.warning("Console not found in availability table")
            return jsonify({"error": "Console not found in the availability table"}), 404

        if not result.is_available:
            current_app.logger.warning("Console already in use | console_id=%s", console_id)
            return jsonify({"error": "Console is already in use"}), 400

        # Update console status to FALSE (occupied)
        sql_update_status = text(f"""
            UPDATE {console_table_name}
            SET is_available = FALSE
            WHERE console_id = :console_id AND game_id = :game_id
        """)
        db.session.execute(sql_update_status, {
            "console_id": console_id,
            "game_id": gameid
        })
        current_app.logger.debug("Updated console status to occupied")

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

        db.session.commit()
        current_app.logger.debug("DB commit successful")

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
                    d.slot_id
                FROM {booking_table_name} b
                JOIN available_games ag ON b.game_id = ag.id
                JOIN bookings d ON b.book_id = d.id
                LEFT JOIN users u ON b.user_id = u.id
                WHERE b.book_id = :booking_id AND b.game_id = :game_id
            """)
            b_row = db.session.execute(sql_fetch_booking, {
                "booking_id": booking_id,
                "game_id": gameid
            }).mappings().fetchone()
            current_app.logger.debug("Fetched booking row: %s", dict(b_row) if b_row else None)

            if b_row and b_row.get("book_status") == "current":
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
        # ======= END =======

        current_app.logger.debug("Successfully completed update_console_status")
        return jsonify({"message": "Console status and booking status updated successfully!"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Failed update_console_status | error=%s", str(e))
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/assignConsoleToMultipleBookings', methods=['POST'])
def assign_console_to_multiple_bookings():
    try:
        data = request.get_json()
        console_id = data.get('console_id')
        game_id = data.get('game_id')
        booking_ids = data.get('booking_ids')  # List[int]
        vendor_id = data.get('vendor_id')

        if not all([console_id, game_id, booking_ids, vendor_id]):
            return jsonify({"error": "Missing required fields"}), 400

        if not isinstance(booking_ids, list) or not all(isinstance(bid, int) for bid in booking_ids):
            return jsonify({"error": "booking_ids must be a list of integers"}), 400

        # Dynamic table names
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"

        # ✅ Check if the console is currently available
        sql_check_availability = text(f"""
            SELECT is_available FROM {console_table_name}
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        result = db.session.execute(sql_check_availability, {
            "console_id": console_id,
            "game_id": game_id
        }).fetchone()

        if not result:
            return jsonify({"error": "Console not found"}), 404

        if not result.is_available:
            return jsonify({"error": "Console is already in use"}), 400

        # ✅ Mark the console as unavailable
        sql_update_console_status = text(f"""
            UPDATE {console_table_name}
            SET is_available = FALSE
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        db.session.execute(sql_update_console_status, {
            "console_id": console_id,
            "game_id": game_id
        })

        # ✅ Update multiple bookings to status 'current' and assign the console
        sql_update_bookings = text(f"""
            UPDATE {booking_table_name}
            SET book_status = 'current', console_id = :console_id
            WHERE book_id = ANY(:booking_ids) AND game_id = :game_id AND book_status = 'upcoming'
        """)

        db.session.execute(sql_update_bookings, {
            "console_id": console_id,
            "game_id": game_id,
            "booking_ids": booking_ids
        })

        db.session.commit()

        return jsonify({"message": "Console assigned to multiple bookings successfully."}), 200

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
            SELECT is_available FROM {console_table_name}
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        result = db.session.execute(sql_check_console, {
            "console_id": console_id,
            "game_id": gameid
        }).fetchone()

        if not result:
            return jsonify({"error": "Console not found in the availability table"}), 404

        is_available = result.is_available

        if is_available:
            return jsonify({"message": "Console is already available"}), 200

        # ✅ Update the status to TRUE (available)
        sql_update_status = text(f"""
            UPDATE {console_table_name}
            SET is_available = TRUE
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        db.session.execute(sql_update_status, {
            "console_id": console_id,
            "game_id": gameid
        })

         # ✅ Update book_status from "upcoming" to "current"
        sql_update_booking_status = text(f"""
            UPDATE {booking_table_name}
            SET book_status = 'completed'
            WHERE console_id = :console_id AND book_status = 'current'
        """)

        db.session.execute(sql_update_booking_status, {
            "console_id": console_id,
            "game_id": gameid
        })

        # Commit the changes
        db.session.commit()
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
        

        return jsonify({"message": "Console released successfully!"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getAllDevice/vendor/<vendor_id>', methods=['GET'])
def get_all_device_for_vendor(vendor_id):
    try:
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"

        # ✅ SQL query to fetch console details
        sql_query = text(f"""
            SELECT ca.console_id, c.model_number, c.brand, ca.is_available, ca.game_id
            FROM {console_table_name} ca
            JOIN consoles c ON ca.console_id = c.id
            WHERE ca.vendor_id = :vendor_id
        """)

        # ✅ Execute the query
        result = db.session.execute(sql_query, {"vendor_id": vendor_id}).fetchall()

        devices = []

        for row in result:
            # Fetch the related AvailableGame instance by game_id
            game = AvailableGame.query.filter_by(id=row.game_id).first()

            devices.append({
                "consoleId": row.console_id,
                "consoleModelNumber": row.model_number,
                "brand": row.brand,
                "is_available": row.is_available,
                "consoleTypeName": game.game_name if game else "Unknown",  # If game exists, use game_name
                "console_type_id": row.game_id,  # Include game_id as consoleTypeId
                "consolePrice": game.single_slot_price
            })

        return jsonify(devices), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/getLandingPage/vendor/<int:vendor_id>', methods=['GET'])
def get_landing_page_vendor(vendor_id):
    """Fetches vendor dashboard data including stats, booking stats, upcoming bookings, and current slots."""
    try:
        table_name = f"VENDOR_{vendor_id}_DASHBOARD"
        today = datetime.utcnow().date()
        
        # Fetch transaction stats
        today_earnings = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.vendor_id == vendor_id, Transaction.booked_date == today).scalar() or 0
        today_bookings = db.session.query(func.count(Transaction.id)).filter(
            Transaction.vendor_id == vendor_id, Transaction.booked_date == today).scalar() or 0
        pending_amount = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.vendor_id == vendor_id, Transaction.settlement_status == 'pending').scalar() or 0
        cleared_amount = today_earnings - pending_amount
        
        # Fetch bookings from vendor-specific dashboard table
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
                d.slot_id
            FROM {table_name} b
            JOIN available_games ag ON b.game_id = ag.id
            JOIN bookings d ON b.book_id = d.id
            LEFT JOIN users u ON b.user_id = u.id
        """)
        
        result = db.session.execute(sql_fetch_bookings).fetchall()
        
        upcoming_bookings = []
        current_slots = []
        
        # Fetch all booking_ids with extras in one go
        booking_ids = [row.book_id for row in result]
        if booking_ids:
          meals_lookup = set(
              r[0] for r in db.session.query(BookingExtraService.booking_id)
              .filter(BookingExtraService.booking_id.in_(booking_ids))
              .distinct()
              .all()
            )
        else:
            meals_lookup = set()

        
        for row in result:
            has_meals = row.book_id in meals_lookup

            booking_data = {
                "slotId": row.slot_id,
                "bookingId": row.book_id,
                "username": row.username,
                "userId":row.user_id,
                "game": row.game_name,
                "consoleType": f"Console-{row.console_id}",
                "time": f"{row.start_time.strftime('%I:%M %p')} - {row.end_time.strftime('%I:%M %p')}",
                "status": "Confirmed" if row.status != 'pending_verified' else "Pending",
                "game_id":row.game_id,
                "date":row.date,
                "slot_price": row.single_slot_price,
                "hasMeals": has_meals

            }
            
            slot_data = {
                "slotId": row.slot_id,
                "bookId" : row.book_id,
                "startTime": row.start_time.strftime('%I:%M %p'),
                "endTime": row.end_time.strftime('%I:%M %p'),
                "status": "Booked" if row.status != 'pending_verified' else "Available",
                "consoleType": f"HASH{row.console_id}",
                "consoleNumber": str(row.console_id),
                "username": row.username,
                "userId":row.user_id,
                "game_id":row.game_id,
                "date":row.date,
                "slot_price": row.single_slot_price,
                "hasMeals": has_meals
                
            }
            
            if row.book_status == "upcoming":
                upcoming_bookings.append(booking_data)
            elif row.book_status == "current":
                current_slots.append(slot_data)
        
        # Compute booking statistics
        total_bookings = db.session.query(func.count(Booking.id)).filter_by().scalar() or 0
        completed_bookings = db.session.query(func.count(Booking.id)).filter_by(status='completed').scalar() or 0
        cancelled_bookings = db.session.query(func.count(Booking.id)).filter_by(status='cancelled').scalar() or 0
        rescheduled_bookings = db.session.query(func.count(Booking.id)).filter_by(status='rescheduled').scalar() or 0
        
        # Calculate average booking duration (assume per-day average over past week)
        total_slots = db.session.query(func.count(Slot.id)).scalar() or 1  # Avoid division by zero
        average_booking_duration = f"{round((total_slots * 30) / 60)} min"  # Assuming 30 min per slot
        
        # Calculate peak booking hours from past transactions
        peak_hours = (
            db.session.query(
                func.to_char(Transaction.booking_time, 'HH24'),  # Use TO_CHAR to extract the hour
                func.count(Transaction.id)
            )
            .group_by(func.to_char(Transaction.booking_time, 'HH24'))
            .order_by(func.count(Transaction.id).desc())
            .limit(3)
            .all()
        )
        
        peak_booking_hours = [f"{int(hour)}:00 - {int(hour)+1}:00" for hour, _ in peak_hours]
        
        return jsonify({
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
            "currentSlots": current_slots
        })
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
            "slotDurationMinutes": duration_int  # always int or None
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
        # Dynamic Promo Table name based on vendor_id
        promo_table = f"VENDOR_{vendor_id}_PROMO_DETAIL"
        slot_table = f"VENDOR_{vendor_id}_SLOT"  # Dynamic Slot Table name based on vendor_id
        
        # Start a transaction
        with db.session.begin():
            # 1. Total Gamers (distinct users who have made bookings)
            total_gamers = db.session.query(func.count(func.distinct(Transaction.user_id)))\
                .filter(Transaction.vendor_id == vendor_id).scalar()

            # 2. Average Revenue (total revenue / total slots)
            total_revenue = db.session.query(func.sum(Transaction.amount))\
                .filter(Transaction.vendor_id == vendor_id).scalar() or 0
            total_slots = db.session.query(func.count(Booking.id))\
                .join(Slot, Booking.slot_id == Slot.id)\
                .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)\
                .filter(AvailableGame.vendor_id == vendor_id).scalar() or 1

            average_revenue = total_revenue / total_slots

            # 3. Premium Members (number of distinct users with premium membership)
            premium_members = db.session.query(func.count(func.distinct(Transaction.user_id)))\
                .filter(Transaction.vendor_id == vendor_id, Transaction.amount > 1000).scalar()  # Assuming premium users are those who spent > 1000

            # 4. Average Session Time (average time between bookings, in hours)
            session_times = db.session.query(Booking.slot_id, func.min(Transaction.booking_date).label('min_time'), func.max(Transaction.booking_date).label('max_time'))\
                .join(Slot, Booking.slot_id == Slot.id)\
                .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)\
                .filter(AvailableGame.vendor_id == vendor_id)\
                .group_by(Booking.slot_id).all()

            total_session_time = 0
            total_sessions = 0
            for session in session_times:
                start_time = session.min_time
                end_time = session.max_time
                session_duration = (end_time - start_time).total_seconds() / 3600  # in hours
                total_session_time += session_duration
                total_sessions += 1

            avg_session_time = total_session_time / total_sessions if total_sessions > 0 else 0

            # 5. Revenue Growth (comparing current month revenue vs previous month)
            current_month_start = datetime(datetime.now().year, datetime.now().month, 1)
            previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            previous_month_end = current_month_start - timedelta(days=1)

            current_month_revenue = db.session.query(func.sum(Transaction.amount))\
                .filter(Transaction.vendor_id == vendor_id, Transaction.booking_date >= current_month_start).scalar() or 0
            previous_month_revenue = db.session.query(func.sum(Transaction.amount))\
                .filter(Transaction.vendor_id == vendor_id, Transaction.booking_date >= previous_month_start, Transaction.booking_date <= previous_month_end).scalar() or 0

            revenue_growth = ((current_month_revenue - previous_month_revenue) / previous_month_revenue) * 100 if previous_month_revenue else 0
            revenue_growth = f"+{revenue_growth:.2f}%" if revenue_growth >= 0 else f"{revenue_growth:.2f}%"

            # 6. Members Growth (comparing current month premium members vs previous month)
            current_month_premium = db.session.query(func.count(func.distinct(Transaction.user_id)))\
                .filter(Transaction.vendor_id == vendor_id, Transaction.amount > 1000, Transaction.booking_date >= current_month_start).scalar() or 0
            previous_month_premium = db.session.query(func.count(func.distinct(Transaction.user_id)))\
                .filter(Transaction.vendor_id == vendor_id, Transaction.amount > 1000, Transaction.booking_date >= previous_month_start, Transaction.booking_date <= previous_month_end).scalar() or 0

            members_growth = ((current_month_premium - previous_month_premium) / previous_month_premium) * 100 if previous_month_premium else 0
            members_growth = f"+{members_growth:.2f}%" if members_growth >= 0 else f"{members_growth:.2f}%"

            # 7. Session Growth (comparing current month sessions vs previous month)
            current_month_sessions = db.session.query(func.count(Booking.id))\
                .join(Slot, Booking.slot_id == Slot.id)\
                .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)\
                .join(Transaction, Transaction.booking_id == Booking.id)\
                .filter(AvailableGame.vendor_id == vendor_id, Transaction.booking_date >= current_month_start)\
                .scalar() or 0
            previous_month_sessions = db.session.query(func.count(Booking.id))\
                .join(Slot, Booking.slot_id == Slot.id)\
                .join(AvailableGame, Slot.gaming_type_id == AvailableGame.id)\
                .filter(AvailableGame.vendor_id == vendor_id, Transaction.booking_date >= previous_month_start, Transaction.booking_date <= previous_month_end).scalar() or 0

            session_growth = ((current_month_sessions - previous_month_sessions) / previous_month_sessions) * 100 if previous_month_sessions else 0
            session_growth = f"+{session_growth:.2f}%" if session_growth >= 0 else f"{session_growth:.2f}%"

            # 8. Discount Applied from Promo (sum of all discounts applied in vendor-specific promo table)
            promo_discount = db.session.execute(
                text(f"SELECT SUM(discount_applied) FROM {promo_table}")
            ).scalar() or 0

            # 9. Slot Availability (Check availability from dynamic slot table)
            available_slots = db.session.execute(
                text(f"""
                SELECT SUM(available_slot) 
                FROM {slot_table} 
                WHERE vendor_id = :vendor_id AND is_available = TRUE
                """), {"vendor_id": vendor_id}
            ).scalar() or 0

        # Return stats as JSON response
        return jsonify({
            "totalGamers": total_gamers,
            "averageRevenue": average_revenue,
            "premiumMembers": premium_members,
            "avgSessionTime": f"{avg_session_time:.1f} hrs" if avg_session_time > 0 else "N/A",
            "revenueGrowth": revenue_growth,
            "membersGrowth": members_growth,
            "sessionGrowth": session_growth,
            "promoDiscountApplied": promo_discount,
            "availableSlots": available_slots  # Slot availability data
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
@dashboard_service.route("/vendor/<int:vendor_id>/passes", methods=["GET"])
def list_cafe_passes(vendor_id):
    passes = CafePass.query.filter_by(vendor_id=vendor_id, is_active=True).all()
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "days_valid": p.days_valid,
            "description": p.description,
            "pass_type": p.pass_type.name
        } for p in passes
    ])

# Add a new cafe pass
@dashboard_service.route("/vendor/<int:vendor_id>/passes", methods=["POST"])
def create_cafe_pass(vendor_id):
    data = request.json
    name = data["name"]
    price = data["price"]
    days_valid = data["days_valid"]
    pass_type_id = data["pass_type_id"]   # links to PassType (daily/monthly/...)
    description = data.get("description", "")

    cafe_pass = CafePass(
        vendor_id=vendor_id,
        name=name,
        price=price,
        days_valid=days_valid,
        pass_type_id=pass_type_id,
        description=description
    )
    db.session.add(cafe_pass)
    db.session.commit()
    return jsonify({"message": "Pass created"}), 200

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

@dashboard_service.route("/vendor/<int:vendor_id>/passes/<int:pass_id>", methods=["DELETE"])
def deactivate_cafe_pass(vendor_id, pass_id):
    try:
        cafe_pass = CafePass.query.filter_by(id=pass_id, vendor_id=vendor_id, is_active=True).first_or_404()
        cafe_pass.is_active = False
        db.session.commit()
        return jsonify({"message": "Pass deactivated successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"Error deactivating pass {pass_id} for vendor {vendor_id}: {e}")
        return jsonify({"error": "Failed to deactivate pass"}), 500

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
        # Get the booking
        booking = Booking.query.filter_by(id=booking_id).first()
        
        if not booking:
            return jsonify({"success": False, "error": "Booking not found"}), 404
        
        # Get user details
        user = User.query.filter_by(id=booking.user_id).first()
        
        # Get extra services for this booking
        extra_services = []
        booking_extra_services = BookingExtraService.query.filter_by(booking_id=booking_id).all()
        
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

@dashboard_service.route('/vendor/<int:vendor_id>/getAllPc', methods=['GET'])
def get_all_pc(vendor_id):
    vendor = Vendor.query.filter_by(id=vendor_id).first_or_404()
    # plan capacity
    plan_limit = vendor.plan_pc_limit  # e.g., 3 for basic, 5 for pro, N for custom
    # count active links
    active_links = db.session.query(ConsoleLinkSession).filter_by(
        vendor_id=vendor_id, status='active'
    ).count()
    remaining = max(0, plan_limit - active_links)

    pcs = Console.query.filter_by(vendor_id=vendor_id, console_type='pc').all()

    return jsonify({
        "plan_limit": plan_limit,
        "active_links": active_links,
        "remaining_capacity": remaining,
        "pcs": [
            {
                "id": c.id,
                "number": c.console_number,
                "brand": c.brand,
                "model": c.model_number,
                "linked": db.session.query(ConsoleLinkSession).filter_by(
                    console_id=c.id, status='active'
                ).count() > 0
            } for c in pcs
        ]
    }), 200

@dashboard_service.route('/vendor/<int:vendor_id>/link', methods=['POST'])
def link_pc(vendor_id):
    data = request.get_json()
    console_id = data['console_id']

    with db.session.begin_nested():  # allows SERIALIZABLE outside
        # lock vendor row
        vendor = db.session.query(Vendor).filter_by(id=vendor_id).with_for_update().first_or_404()
        plan_limit = vendor.plan_pc_limit

        # ensure console belongs to vendor and is a PC
        console = db.session.query(Console).filter_by(
            id=console_id, vendor_id=vendor_id, console_type='pc'
        ).with_for_update().first_or_404()

        # prevent duplicate active link for this console
        existing = db.session.query(ConsoleLinkSession).filter_by(
            console_id=console_id, status='active'
        ).with_for_update().first()
        if existing:
            return jsonify({"error": "Console already linked"}), 409

        # enforce plan limit
        active_links = db.session.query(ConsoleLinkSession).filter_by(
            vendor_id=vendor_id, status='active'
        ).with_for_update().count()
        if active_links >= plan_limit:
            return jsonify({"error": "Plan limit reached"}), 402  # Payment Required or 409

        # create session
        token = secrets.token_urlsafe(24)
        sess = ConsoleLinkSession(
            vendor_id=vendor_id, console_id=console_id,
            started_at=datetime.utcnow(), status='active',
            session_token=token
        )
        db.session.add(sess)

    db.session.commit()
    return jsonify({"session_token": token, "ws_url": f"wss://.../ws?token={token}"}), 201
