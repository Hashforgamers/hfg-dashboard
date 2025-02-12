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

# class ConsoleService:
#     @staticmethod
#     def add_console(data):
#         try:
#             vendor_id = data.get("vendorId")
#             available_game_type = data.get("availablegametype")

#             console_data = data.get("consoleDetails", {})
#             hardware_data = data.get("hardwareSpecifications", {})
#             maintenance_data = data.get("maintenanceStatus", {})
#             price_data = data.get("priceAndCost", {})
#             additional_data = data.get("additionalDetails", {})

#             # ✅ Create Console Entry
#             console = Console(
#                 console_number=console_data["consoleNumber"],
#                 model_number=console_data["modelNumber"],
#                 serial_number=console_data["serialNumber"],
#                 brand=console_data["brand"],
#                 console_type=console_data["consoleType"],
#                 release_date=datetime.strptime(console_data["releaseDate"], "%Y-%m-%d").date(),
#                 description=console_data["description"],
#             )
#             db.session.add(console)
#             db.session.flush()  # ✅ Get the console ID before commit

#             # ✅ Create Hardware Specifications
#             hardware_spec = HardwareSpecification(
#                 console_id=console.id,
#                 processor_type=hardware_data["processorType"],
#                 graphics_card=hardware_data["graphicsCard"],
#                 ram_size=hardware_data["ramSize"],
#                 storage_capacity=hardware_data["storageCapacity"],
#                 connectivity=hardware_data["connectivity"],
#             )
#             db.session.add(hardware_spec)

#             # ✅ Create Maintenance Status
#             maintenance_status = MaintenanceStatus(
#                 console_id=console.id,
#                 available_status=maintenance_data["availableStatus"],
#                 condition=maintenance_data["condition"],
#                 last_maintenance=datetime.strptime(maintenance_data["lastMaintenance"], "%Y-%m-%d").date(),
#                 next_maintenance=datetime.strptime(maintenance_data["nextMaintenance"], "%Y-%m-%d").date(),
#                 maintenance_notes=maintenance_data["maintenanceNotes"],
#             )
#             db.session.add(maintenance_status)

#             # ✅ Create Price and Cost
#             price_and_cost = PriceAndCost(
#                 console_id=console.id,
#                 price=price_data["price"],
#                 rental_price=price_data["rentalPrice"],
#                 warranty_period=price_data["warrantyPeriod"],
#                 insurance_status=price_data["insuranceStatus"],
#             )
#             db.session.add(price_and_cost)

#             # ✅ Create Additional Details
#             additional_details = AdditionalDetails(
#                 console_id=console.id,
#                 supported_games=additional_data["supportedGames"],
#                 accessories=additional_data["accessories"],
#             )
#             db.session.add(additional_details)

#             # ✅ Find or Create AvailableGame
#             available_game = AvailableGame.query.filter_by(
#                 vendor_id=vendor_id, game_name=available_game_type
#             ).first()

#             if available_game:
#                 available_game.total_slot += 1  # ✅ Increment total slots
#             else:
#                 available_game = AvailableGame(
#                     vendor_id=vendor_id,
#                     game_name=available_game_type,
#                     total_slot=1,
#                     single_slot_price=price_data["rentalPrice"],
#                 )
#                 db.session.add(available_game)
#                 db.session.flush()  # ✅ Get available_game.id before association

#             # ✅ Associate Console with AvailableGame (Many-to-Many)
#             if console not in available_game.consoles:
#                 available_game.consoles.append(console)

#             # ✅ Update existing Slot entries (set available_slot = 1 and is_available = True)
#             slots_to_update = Slot.query.filter_by(gaming_type_id=available_game.id).all()

#             for slot in slots_to_update:
#                 slot.available_slot+=1  # Set the available slot to 1
#                 slot.is_available = True  # Set the slot as available
#                 db.session.add(slot)
            
#             # ✅ flush slot updates first
#             db.session.flush()

#             # ✅ Update VENDOR_{vendor_id}_SLOT view
#             # Check if the materialized view exists
#             check_view_query = text("""
#                 SELECT to_regclass(:view_name);
#             """)
#             view_exists = db.session.execute(check_view_query, {"view_name": f"VENDOR_{vendor_id}_SLOT"}).fetchone()

#             # If the view exists, refresh it
#             if view_exists[0] is not None:
#                 # Dynamically insert the view name into the SQL string and wrap in `text()`
#                 refresh_query = text(f"""
#                     REFRESH MATERIALIZED VIEW VENDOR_{vendor_id}_SLOT;
#                 """)
#                 db.session.execute(refresh_query)
#                 db.session.commit()
#             else:
#                 current_app.logger.info(f"Materialized view VENDOR_{vendor_id}_SLOT does not exist.")


#             # ✅ Commit all changes
#             db.session.commit()

#             return {"message": "Console added successfully!"}, 201

#         except Exception as e:
#             db.session.rollback()
#             return {"error": str(e)}, 500

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
            db.session.flush()  # ✅ Get the console ID before commit

            # ✅ Create Hardware Specifications
            hardware_spec = HardwareSpecification(
                console_id=console.id,
                processor_type=hardware_data["processorType"],
                graphics_card=hardware_data["graphicsCard"],
                ram_size=hardware_data["ramSize"],
                storage_capacity=hardware_data["storageCapacity"],
                connectivity=hardware_data["connectivity"],
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

            # ✅ Insert/update VENDOR_{vendor_id}_SLOT table to reflect new slots for each date
            table_name = f"VENDOR_{vendor_id}_SLOT"
            sql_insert = text(f"""
                INSERT INTO {table_name} (vendor_id, date, slot_id, is_available, available_slot)
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
                    SELECT 1 FROM {table_name} v WHERE v.date = gs.date AND v.slot_id = s.id
                );
            """)
            db.session.execute(sql_insert, {"vendor_id": vendor_id, "available_game_id": available_game.id})
            db.session.commit()

            # ✅ Commit all changes
            db.session.commit()

            return {"message": "Console added successfully!"}, 201

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500
