from datetime import datetime
from app.extension.extensions import db
from app.models.console import Console
from app.models.hardwareSpecification import HardwareSpecification
from app.models.maintenanceStatus import MaintenanceStatus
from app.models.priceAndCost import PriceAndCost
from app.models.additionalDetails import AdditionalDetails
from app.models.availableGame import AvailableGame, available_game_console  # ✅ Import association table
from app.models.slot import Slot
from sqlalchemy.sql import text
from sqlalchemy.exc import ProgrammingError

class ConsoleService:
    @staticmethod
    def add_console(data):
        try:
            vendor_id = data.get("vendorId")
            available_game_type = data.get("availablegametype")

            console_data = data.get("consoleDetails", {})
            hardware_data = data.get("hardwareSpecifications", {})
            maintenance_data = data.get("maintenanceStatus", {})
            price_data = data.get("priceAndCost", {})
            additional_data = data.get("additionalDetails", {})

            # ✅ Create Console Entry
            console = Console(
                console_number=console_data["consoleNumber"],
                model_number=console_data["modelNumber"],
                serial_number=console_data["serialNumber"],
                brand=console_data["brand"],
                console_type=console_data["consoleType"],
                release_date=datetime.strptime(console_data["releaseDate"], "%Y-%m-%d").date(),
                description=console_data["description"],
            )
            db.session.add(console)
            db.session.flush()  # ✅ Get console.id before commit

            # ✅ Create Hardware Specifications
            hardware_spec = HardwareSpecification(
                console_id=console.id,
                processor_type=hardware_data["processorType"],
                graphics_card=hardware_data["graphicsCard"],
                ram_size=hardware_data["ramSize"],
                storage_capacity=hardware_data["storageCapacity"],
                connectivity=hardware_data["connectivity"],
                console_model_type=hardware_data["consoleModelType"]
            )
            db.session.add(hardware_spec)

            # ✅ Create Maintenance Status
            maintenance_status = MaintenanceStatus(
                console_id=console.id,
                available_status=maintenance_data["availableStatus"],
                condition=maintenance_data["condition"],
                last_maintenance=datetime.strptime(maintenance_data["lastMaintenance"], "%Y-%m-%d").date(),
                next_maintenance=datetime.strptime(maintenance_data["nextMaintenance"], "%Y-%m-%d").date(),
                maintenance_notes=maintenance_data["maintenanceNotes"],
            )
            db.session.add(maintenance_status)

            # ✅ Create Price and Cost
            price_and_cost = PriceAndCost(
                console_id=console.id,
                price=price_data["price"],
                rental_price=price_data["rentalPrice"],
                warranty_period=price_data["warrantyPeriod"],
                insurance_status=price_data["insuranceStatus"],
            )
            db.session.add(price_and_cost)

            # ✅ Create Additional Details
            additional_details = AdditionalDetails(
                console_id=console.id,
                supported_games=additional_data["supportedGames"],
                accessories=additional_data["accessories"],
            )
            db.session.add(additional_details)

            # ✅ Find or Create AvailableGame
            available_game = AvailableGame.query.filter_by(
                vendor_id=vendor_id, game_name=available_game_type
            ).first()

            if available_game:
                available_game.total_slot += 1  # ✅ Increment total slots
            else:
                available_game = AvailableGame(
                    vendor_id=vendor_id,
                    game_name=available_game_type,
                    total_slot=1,
                    single_slot_price=price_data["rentalPrice"],
                )
                db.session.add(available_game)
                db.session.flush()  # ✅ Get available_game.id before association

            # ✅ Associate Console with AvailableGame (Many-to-Many)
            if console not in available_game.consoles:
                available_game.consoles.append(console)

            # ✅ Update existing Slot entries (set available_slot = 1 and is_available = True)
            slots_to_update = Slot.query.filter_by(gaming_type_id=available_game.id).all()

            for slot in slots_to_update:
                slot.available_slot += 1  # Set the available slot to 1
                slot.is_available = True  # Set the slot as available
                db.session.add(slot)
            
            # ✅ flush slot updates first
            db.session.flush()

            # ✅ Check if the slot exists in the VENDOR_{vendor_id}_SLOT table
            slot_table_name = f"VENDOR_{vendor_id}_SLOT"

            # First, check if the slot already exists (based on vendor_id, date, and slot_id)
            check_existing_slots_sql = text(f"""
                SELECT 1
                FROM {slot_table_name} v
                WHERE v.vendor_id = :vendor_id
                AND v.date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '365 days'
                AND v.slot_id IN (SELECT id FROM slots WHERE gaming_type_id = :available_game_id)
                LIMIT 1;
            """)

            # Execute the query to check for existing slots
            existing_slots = db.session.execute(check_existing_slots_sql, {"vendor_id": vendor_id, "available_game_id": available_game.id}).fetchone()

            if existing_slots:
                # ✅ If slots exist, update the existing ones
                update_slots_sql = text(f"""
                    UPDATE {slot_table_name} v
                    SET available_slot = v.available_slot + 1,
                        is_available = TRUE
                    WHERE v.vendor_id = :vendor_id
                    AND v.date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '365 days'
                    AND v.slot_id IN (SELECT id FROM slots WHERE gaming_type_id = :available_game_id);
                """)
                db.session.execute(update_slots_sql, {"vendor_id": vendor_id, "available_game_id": available_game.id})
            else:
                # ✅ If slots do not exist, insert new ones
                insert_slots_sql = text(f"""
                    INSERT INTO {slot_table_name} (vendor_id, date, slot_id, is_available, available_slot)
                    SELECT
                        :vendor_id AS vendor_id,
                        gs.date AS date,
                        s.id AS slot_id,
                        TRUE AS is_available,  -- Mark slots as available
                        1 AS available_slot   -- Set the available slot to 1 initially
                    FROM
                        generate_series(CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days', '1 day'::INTERVAL) gs
                    CROSS JOIN slots s
                    WHERE
                        s.gaming_type_id = :available_game_id
                    AND NOT EXISTS (
                        SELECT 1 FROM {slot_table_name} v WHERE v.date = gs.date AND v.slot_id = s.id
                    );
                """)
                db.session.execute(insert_slots_sql, {"vendor_id": vendor_id, "available_game_id": available_game.id})


            # ✅ Create Dynamic Console Availability Table
            console_table_name = f"VENDOR_{vendor_id}_CONSOLE_AVAILABILITY"

            # ✅ Insert Console Availability Data
            sql_insert_console_availability = text(f"""
                INSERT INTO {console_table_name} (vendor_id, console_id, game_id, is_available)
                VALUES (:vendor_id, :console_id, :game_id, TRUE)
            """)
            db.session.execute(sql_insert_console_availability, {
                "vendor_id": vendor_id,
                "console_id": console.id,
                "game_id": available_game.id
            })

            # ✅ Commit all changes
            db.session.commit()

            return {"message": "Console added successfully!"}, 201

        except ProgrammingError as e:
            db.session.rollback()
            return {"error": f"SQL Error: {str(e)}"}, 500
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    @staticmethod
    def get_console_details(console_id):
        try:
            # Fetch Console with related info
            console = db.session.query(Console).filter_by(id=console_id).first()
            if not console:
                return {"error": "Console not found"}, 404

            # Assuming your Console model has relationships set up for these:
            hardware = getattr(console, "hardware_specification", None)
            maintenance = getattr(console, "maintenance_status", None)
            price = getattr(console, "price_and_cost", None)
            additional = getattr(console, "additional_details", None)

            # Many-to-many relationship to AvailableGame
            available_games = [
                {
                    "id": game.id,
                    "game_name": game.game_name,
                    "total_slot": game.total_slot,
                    "single_slot_price": game.single_slot_price
                }
                for game in getattr(console, "available_games", [])
            ]

            result = {
                "console": {
                    "id": console.id,
                    "console_number": console.console_number,
                    "model_number": console.model_number,
                    "serial_number": console.serial_number,
                    "brand": console.brand,
                    "console_type": console.console_type,
                    "release_date": console.release_date.isoformat() if console.release_date else None,
                    "description": console.description,
                },
                "hardwareSpecification": {
                    "processorType": hardware.processor_type if hardware else None,
                    "graphicsCard": hardware.graphics_card if hardware else None,
                    "ramSize": hardware.ram_size if hardware else None,
                    "storageCapacity": hardware.storage_capacity if hardware else None,
                    "connectivity": hardware.connectivity if hardware else None,
                    "consoleModelType": hardware.console_model_type if hardware else None,
                },
                "maintenanceStatus": {
                    "availableStatus": maintenance.available_status if maintenance else None,
                    "condition": maintenance.condition if maintenance else None,
                    "lastMaintenance": maintenance.last_maintenance.isoformat() if maintenance and maintenance.last_maintenance else None,
                    "nextMaintenance": maintenance.next_maintenance.isoformat() if maintenance and maintenance.next_maintenance else None,
                    "maintenanceNotes": maintenance.maintenance_notes if maintenance else None,
                },
                "priceAndCost": {
                    "price": price.price if price else None,
                    "rentalPrice": price.rental_price if price else None,
                    "warrantyPeriod": price.warranty_period if price else None,
                    "insuranceStatus": price.insurance_status if price else None,
                },
                "additionalDetails": {
                    "supportedGames": additional.supported_games if additional else None,
                    "accessories": additional.accessories if additional else None,
                },
                "availableGames": available_games
            }

            return result, 200

        except Exception as e:
            current_app.logger.error(f"Error in get_console_details: {e}")
            return {"error": "An error occurred while fetching console details"}, 500