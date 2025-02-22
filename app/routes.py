from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from .models.transaction import Transaction
from app.extension.extensions import db
from sqlalchemy import cast, Date, text
from app.services.console_service import ConsoleService

from .models.console import Console
from .models.availableGame import AvailableGame, available_game_console

from .models.hardwareSpecification import HardwareSpecification
from .models.maintenanceStatus import MaintenanceStatus
from .models.priceAndCost import PriceAndCost
from .models.slot import Slot
from .models.additionalDetails import AdditionalDetails

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
        # Fetch available games associated with the given vendor ID
        available_games = AvailableGame.query.filter_by(vendor_id=vendor_id).all()

        # Extract consoles from the available games
        consoles = []
        for game in available_games:
            for console in game.consoles:
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
                    "status": console.maintenance_status.available_status if console.maintenance_status else "Unknown",
                    "consoleModelType":console.hardware_specifications.console_model_type if console.hardware_specifications else "N/A",
                }
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

@dashboard_service.route('/updateDeviceStatus/consoleTypeId/<gameid>/console/<console_id>/vendor/<vendor_id>', methods=['POST'])
def update_console_status(gameid, console_id, vendor_id):
    try:
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"

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

        # ✅ Update the status to false (occupied)
        sql_update_status = text(f"""
            UPDATE {console_table_name}
            SET is_available = FALSE
            WHERE console_id = :console_id AND game_id = :game_id
        """)

        db.session.execute(sql_update_status, {
            "console_id": console_id,
            "game_id": gameid
        })

        # ✅ Commit the changes
        db.session.commit()

        return jsonify({"message": "Console status updated successfully!"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/releaseDevice/consoleTypeId/<gameid>/console/<console_id>/vendor/<vendor_id>', methods=['POST'])
def release_console(gameid, console_id, vendor_id):
    try:
        # ✅ Define the dynamic console availability table name
        console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"

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
