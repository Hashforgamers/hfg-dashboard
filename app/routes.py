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
from .models.additionalDetails import AdditionalDetails
from sqlalchemy.orm import joinedload


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
            "userName": txn.user_name,
            "amount": txn.amount,
            "modeOfPayment": txn.mode_of_payment,
            "bookingType": txn.booking_type,
            "settlementStatus": txn.settlement_status
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
            SELECT ca.console_id, c.model_number, c.brand, ca.is_available
            FROM {console_table_name} ca
            JOIN consoles c ON ca.console_id = c.id
            WHERE ca.game_id = :game_id
        """)

        # ✅ Execute the query
        result = db.session.execute(sql_query, {"game_id": gameid}).fetchall()

        # ✅ Format the response
        devices = [
            {
                "consoleId": row.console_id,
                "consoleModelNumber": row.model_number,
                "brand": row.brand,
                "is_available": row.is_available
            }
            for row in result
        ]

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
            SELECT ca.console_id, c.model_number, c.brand, ca.is_available
            FROM {console_table_name} ca
            JOIN consoles c ON ca.console_id = c.id
            WHERE ca.vendor_id = :vendor_id
        """)

        # ✅ Execute the query
        result = db.session.execute(sql_query, {"vendor_id": vendor_id}).fetchall()

        devices = []

        for row in result:
            # Fetch the single associated available_game_id for this console_id
            game_query = text("""
                SELECT available_game_id 
                FROM available_game_console 
                WHERE console_id = :console_id
                LIMIT 1  -- Since each console is mapped to only one game
            """)
            game_result = db.session.execute(game_query, {"console_id": row.console_id}).fetchone()

            # Extract single game ID (or set None if not found)
            game_id = game_result[0] if game_result else None

            devices.append({
                "consoleId": row.console_id,
                "consoleModelNumber": row.model_number,
                "brand": row.brand,
                "is_available": row.is_available,
                "console_type_id": game_id  # Single available_game_id
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
            SELECT username, user_id, start_time, end_time, date, book_id, game_id, game_name, console_id, status, book_status
            FROM {table_name}
        """)
        result = db.session.execute(sql_fetch_bookings).fetchall()
        
        upcoming_bookings = []
        current_slots = []
        
        for row in result:
            booking_data = {
                "bookingId": row.book_id,
                "username": row.username,
                "game": row.game_name,
                "consoleType": f"Console-{row.console_id}",
                "time": f"{row.start_time.strftime('%I:%M %p')} - {row.end_time.strftime('%I:%M %p')}",
                "status": "Confirmed" if row.status != 'pending_verified' else "Pending",
                "game_id":row.game_id,
                "date":row.date,
            }
            
            slot_data = {
                "slotId": row.book_id,
                "startTime": row.start_time.strftime('%I:%M %p'),
                "endTime": row.end_time.strftime('%I:%M %p'),
                "status": "Booked" if row.status != 'pending_verified' else "Available",
                "consoleType": f"Console-{row.console_id}",
                "consoleNumber": str(row.console_id),
                "username": row.username,
                "game_id":row.game_id,
                "date":row.date,
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
