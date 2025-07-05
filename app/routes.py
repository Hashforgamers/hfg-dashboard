from flask import Blueprint, request, jsonify, current_app
from datetime import datetime,timedelta
from .models.transaction import Transaction
from app.extension.extensions import db
from sqlalchemy import cast, Date, text, func
from app.services.console_service import ConsoleService

from .models.console import Console
from .models.availableGame import AvailableGame, available_game_console
from .models.booking import Booking

from .models.hardwareSpecification import HardwareSpecification
from .models.maintenanceStatus import MaintenanceStatus
from .models.priceAndCost import PriceAndCost
from .models.slot import Slot
from .models.user import User
from .models.additionalDetails import AdditionalDetails
from sqlalchemy.orm import joinedload

from app.models.vendor import Vendor  # adjust import as per your structure
from app.models.uploadedImage import Image
from app.models.documentSubmitted import DocumentSubmitted
from app.models.timing import Timing
from app.models.openingDay import OpeningDay
from app.models.contactInfo import ContactInfo
from app.models.businessRegistration import BusinessRegistration

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
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"
        booking_table_name = f"VENDOR_{vendor_id}_DASHBOARD"

        # ✅ Check if the console is available
        sql_check_availability = text(f"""
            SELECT is_available FROM {console_table_name}
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        result = db.session.execute(sql_check_availability, {
            "console_id": console_id,
            "game_id": gameid
        }).fetchone()

        if not result:
            return jsonify({"error": "Console not found in the availability table"}), 404

        is_available = result.is_available

        if not is_available:
            return jsonify({"error": "Console is already in use"}), 400

        # ✅ Update the console status to FALSE (occupied)
        sql_update_status = text(f"""
            UPDATE {console_table_name}
            SET is_available = FALSE
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        db.session.execute(sql_update_status, {
            "console_id": console_id,
            "game_id": gameid
        })

        # ✅ Update book_status from "upcoming" to "current"
        sql_update_booking_status = text(f"""
            UPDATE {booking_table_name}
            SET book_status = 'current', console_id = :console_id
            WHERE book_id = :booking_id AND game_id = :game_id AND book_status = 'upcoming'
        """)

        db.session.execute(sql_update_booking_status, {
            "console_id": console_id,
            "game_id": gameid,
            "booking_id":booking_id
        })

        # ✅ Commit the changes
        db.session.commit()

        return jsonify({"message": "Console status and booking status updated successfully!"}), 200

    except Exception as e:
        db.session.rollback()
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

        # ✅ Commit the changes
        db.session.commit()

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
        
        for row in result:
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

@dashboard_service.route('/vendor/<int:vendor_id>/dashboard', methods=['GET'])
def get_vendor_dashboard(vendor_id):
    vendor = db.session.query(Vendor).options(
        joinedload(Vendor.physical_address),
        joinedload(Vendor.contact_info),
        joinedload(Vendor.business_registration),
        joinedload(Vendor.timing),
        joinedload(Vendor.opening_days),
        joinedload(Vendor.images),
        joinedload(Vendor.documents)
    ).filter_by(id=vendor_id).first()

    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    payload = {
        "navigation": [
            {"icon": "User", "label": "Profile"},
            {"icon": "Building2", "label": "Business Details"},
            {"icon": "Wallet", "label": "Billing"},
            {"icon": "FileCheck", "label": "Verified Documents"},
        ],
        "cafeProfile": {
            "name": vendor.cafe_name,
            "avatar": vendor.images[0].path if vendor.images else "",
            "membershipStatus": "Premium Member",  # hardcoded; change if needed
            "website": "www.demo.com",
            "email": vendor.contact_info.email if vendor.contact_info else "",
        },
        "cafeGallery": {
            "images": [img.path for img in vendor.images]
        },
        "businessDetails": {
            "businessName": "Game Cafe",
            "businessType": "Cafe",
            "phone": vendor.contact_info.phone if vendor.contact_info else "",
            "website": "www.mail.com",
            "address": vendor.physical_address.addressLine1 if vendor.physical_address else ""
        },
        "operatingHours": [
            {
                "day": opening_day.day,
                "open": "09:00",
                "close": "18:00"
            } for opening_day in vendor.opening_days
        ],
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
                "expiry": None  # Your new model doesn’t include expiry
            } for doc in vendor.documents
        ]
    }

    return jsonify(payload), 200

# @dashboard_service.route('/vendor/<int:vendor_id>/knowYourGamer', methods=['GET'])
# def get_your_gamers(vendor_id):
#     try:
#         transactions = Transaction.query.filter_by(vendor_id=vendor_id).all()
#         if not transactions:
#             return jsonify([])

#         promo_table = f"VENDOR_{vendor_id}_PROMO_DETAIL"
#         user_summary = {}

#         for trans in transactions:
#             user_id = trans.user_id
#             booking_id = trans.booking_id
#             amount = trans.amount
#             booked_date = trans.booked_date

#             user_obj = User.query.filter_by(id=user_id).first()
#             booking = Booking.query.filter_by(id=booking_id).first()

#             if not user_obj or not booking:
#                 continue

#             contact_info = user_obj.contact_info
#             phone = contact_info.phone if contact_info else "N/A"

#             if user_id not in user_summary:
#                 user_summary[user_id] = {
#                     "id": user_id,
#                     "name": user_obj.name,
#                     "contact": phone,
#                     "totalSlots": 0,
#                     "totalAmount": 0.0,
#                     "promoCodesUsed": 0,
#                     "discountAvailed": 0.0,
#                     "lastVisit": booked_date,
#                     "membershipTier": "Silver",
#                     "notes": "N/A"
#                 }

#             user_summary[user_id]["totalSlots"] += 1
#             user_summary[user_id]["totalAmount"] += amount
#             user_summary[user_id]["lastVisit"] = max(user_summary[user_id]["lastVisit"], booked_date)

#             # Promo Code Data
#             sql = text(f"SELECT discount_applied FROM {promo_table} WHERE transaction_id = :trans_id")
#             promo_result = db.session.execute(sql, {"trans_id": trans.id}).fetchone()

#             if promo_result:
#                 user_summary[user_id]["promoCodesUsed"] += 1
#                 user_summary[user_id]["discountAvailed"] += promo_result[0]

#         # Format result
#         result = []
#         for user in user_summary.values():
#             total_amount = user["totalAmount"]
#             total_slots = user["totalSlots"]
#             discount = user["discountAvailed"]
#             net = total_amount - discount

#             user["averagePerSlot"] = round(total_amount / total_slots) if total_slots else 0
#             user["netRevenue"] = net

#             if total_slots > 50:
#                 user["membershipTier"] = "Platinum"
#             elif total_slots > 30:
#                 user["membershipTier"] = "Gold"

#             result.append(user)

#         return jsonify(result), 200

#     except Exception as e:
#         current_app.logger.error(f"Error generating Know Your Gamer: {e}")
#         return jsonify({"message": "Internal server error", "error": str(e)}), 500

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

@dashboard_service.route('/vendor/<int:vendor_id>/master', methods=['GET'])
def get_master_stats(vendor_id):
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

        # Revenue and Bookings
        revenue_query = (
            db.session.query(
                Vendor.cafe_name.label("cafe"),
                func.sum(Transaction.amount).label("revenue"),
                func.count(Transaction.id).label("bookings")
            )
            .join(Vendor, Vendor.id == Transaction.vendor_id)
            .filter(Transaction.booking_date.between(start_date, end_date))
        )

        if vendor_id != 0:
            revenue_query = revenue_query.filter(Transaction.vendor_id == vendor_id)

        revenue_query = revenue_query.group_by(Vendor.name).all()

        revenue_by_cafe = []
        bookings_by_cafe = []
        master_revenue = 0
        master_bookings = 0

        for row in revenue_query:
            revenue_by_cafe.append({"cafe": row.cafe, "revenue": row.revenue})
            bookings_by_cafe.append({"cafe": row.cafe, "bookings": row.bookings})
            master_revenue += row.revenue
            master_bookings += row.bookings

        revenue_by_cafe.append({"cafe": "Master Analytics", "revenue": master_revenue})
        bookings_by_cafe.append({"cafe": "Master Analytics", "bookings": master_bookings})

        # Top Games
        top_games_query = (
            db.session.query(
                Vendor.name.label("cafe"),
                AvailableGame.game_name.label("game"),
                func.count(Booking.id).label("plays")
            )
            .join(AvailableGame, AvailableGame.vendor_id == Vendor.id)
            .join(Booking, Booking.game_id == AvailableGame.id)
            .join(Transaction, Transaction.id == Booking.transaction_id)
            .filter(Transaction.booking_date.between(start_date, end_date))
        )

        if vendor_id != 0:
            top_games_query = top_games_query.filter(Vendor.id == vendor_id)

        top_games_query = top_games_query.group_by(Vendor.name, AvailableGame.game_name).all()

        games_by_cafe = defaultdict(list)
        master_game_counts = defaultdict(int)

        for row in top_games_query:
            games_by_cafe[row.cafe].append({"game": row.game, "plays": row.plays})
            master_game_counts[row.game] += row.plays

        games_by_cafe["Master Analytics"] = [
            {"game": k, "plays": v} for k, v in sorted(master_game_counts.items(), key=lambda x: -x[1])
        ]

        # Payment Modes
        payment_query = (
            db.session.query(
                Vendor.name.label("cafe"),
                Transaction.mode_of_payment.label("mode"),
                func.count(Transaction.id).label("count")
            )
            .join(Vendor, Vendor.id == Transaction.vendor_id)
            .filter(Transaction.booking_date.between(start_date, end_date))
        )

        if vendor_id != 0:
            payment_query = payment_query.filter(Transaction.vendor_id == vendor_id)

        payment_query = payment_query.group_by(Vendor.name, Transaction.mode_of_payment).all()

        payment_modes = defaultdict(list)
        master_payments = defaultdict(int)

        for row in payment_query:
            payment_modes[row.cafe].append({"mode": row.mode, "count": row.count})
            master_payments[row.mode] += row.count

        payment_modes["Master Analytics"] = [
            {"mode": k, "count": v} for k, v in master_payments.items()
        ]

        analytics[period] = {
            "revenueByCafe": revenue_by_cafe,
            "bookingsByCafe": bookings_by_cafe,
            "topGames": dict(games_by_cafe),
            "paymentModes": dict(payment_modes)
        }

    return jsonify(analytics)