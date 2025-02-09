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
            cast(Transaction.booking_date, Date).between(from_date, to_date)
        ).all()

        
        current_app.logger.info(f"transactions {transactions} {to_date} {from_date}")

        # Format response data
        result = [{
            "id": txn.id,
            "slotDate": txn.booking_date.strftime("%Y-%m-%d"),
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


@dashboard_service.route('/getConsoles/<int:vendor_id>', methods=['GET'])
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
                }
                consoles.append(console_data)

        return jsonify(consoles), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @dashboard_service.route('/console/<int:console_id>', methods=['DELETE'])
# def delete_console(console_id):
#     try:
#         console = Console.query.get(console_id)
#         if not console:
#             return jsonify({"error": "Console not found"}), 404

#         # ✅ Fetch the associated available_game_id
#         available_game_entry = db.session.execute(
#             available_game_console.select().where(available_game_console.c.console_id == console_id)
#         ).fetchone()

#         available_game_id = available_game_entry[0] if available_game_entry else None

#         # ✅ Delete related entries from dependent tables (if cascade is not applied)
#         if console.hardware_specifications:
#             db.session.delete(console.hardware_specifications)
#         if console.maintenance_status:
#             db.session.delete(console.maintenance_status)
#         if console.price_and_cost:
#             db.session.delete(console.price_and_cost)
#         if console.additional_details:
#             db.session.delete(console.additional_details)

#         # ✅ Remove Console Associations from available_game_console
#         db.session.execute(
#             available_game_console.delete().where(available_game_console.c.console_id == console_id)
#         )

#         # ✅ Delete Console
#         db.session.delete(console)

#         # ✅ Perform decrement in total_slot of AvailableGame
#         if available_game_id:
#             available_game = AvailableGame.query.get(available_game_id)
#             if available_game and available_game.total_slot > 0:
#                 available_game.total_slot -= 1

#         db.session.commit()
#         return jsonify({"message": "Console deleted successfully, and total_slot updated"}), 200

#     except Exception as e:
#         db.session.rollback()
#         return jsonify({"error": str(e)}), 500

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

            # Refresh materialized view for this vendor
            view_exists_query = text("""
                SELECT to_regclass(:view_name);
            """)
            view_exists = db.session.execute(view_exists_query, {"view_name": f"VENDOR_{vendor_id}_SLOT"}).fetchone()

            if view_exists[0] is not None:
                # If the view exists, refresh it
                current_app.logger.info(f"Refreshing materialized view VENDOR_{vendor_id}_SLOT")
                refresh_query = text(f"REFRESH MATERIALIZED VIEW VENDOR_{vendor_id}_SLOT")
                db.session.execute(refresh_query)
                db.session.commit()
            else:
                current_app.logger.info(f"Materialized view VENDOR_{vendor_id}_SLOT does not exist.")
            

        # Delete Console
        db.session.delete(console)

        # Commit all changes
        db.session.commit()

        return jsonify({"message": "Console deleted successfully, and total_slot updated"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@dashboard_service.route('/console/update', methods=['PUT'])
def update_console():
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

        # ✅ Fetch or Update Maintenance Status
        if console.maintenance_status:
            console.maintenance_status.available_status = console_details.get("status", console.maintenance_status.available_status)

        # ✅ Commit Changes
        db.session.commit()

        return jsonify({"message": "Console updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500