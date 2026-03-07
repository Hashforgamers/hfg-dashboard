from datetime import datetime, timedelta, date, time as dtime
from app.extension.extensions import db
from app.models.console import Console
from app.models.hardwareSpecification import HardwareSpecification
from app.models.maintenanceStatus import MaintenanceStatus
from app.models.priceAndCost import PriceAndCost
from app.models.additionalDetails import AdditionalDetails
from app.models.availableGame import AvailableGame  # ✅ Import association table
from app.models.slot import Slot
from sqlalchemy.sql import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import tuple_

class ConsoleService:
    WEEKDAY_MAP = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}  # Postgres DOW

    @staticmethod
    def _normalize_day_key(day_value):
        raw = str(day_value or "").strip().lower()
        if raw in ConsoleService.WEEKDAY_MAP:
            return raw
        if len(raw) >= 3 and raw[:3] in ConsoleService.WEEKDAY_MAP:
            return raw[:3]
        return None

    @staticmethod
    def _parse_time_flexible(value):
        raw = str(value or "").strip()
        if not raw:
            return None
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                return datetime.strptime(raw, fmt).time()
            except ValueError:
                continue
        return None

    @staticmethod
    def _generate_blocks(anchor_day, start_time, end_time, slot_duration):
        start_dt = datetime.combine(anchor_day, start_time)
        end_dt = datetime.combine(anchor_day, end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        blocks = []
        cur_dt = start_dt
        while cur_dt < end_dt:
            nxt_dt = cur_dt + timedelta(minutes=int(slot_duration))
            if nxt_dt > end_dt:
                break
            block_start_t = cur_dt.time()
            block_end_t = (
                nxt_dt.time() if nxt_dt.date() == cur_dt.date()
                else (nxt_dt - timedelta(days=1)).time()
            )
            blocks.append((block_start_t, block_end_t))
            cur_dt = nxt_dt
        return blocks

    @staticmethod
    def _bootstrap_new_game_slots(vendor_id, available_game_id, total_slots):
        config_rows = db.session.execute(
            text("""
                SELECT day, opening_time, closing_time, slot_duration
                FROM vendor_day_slot_config
                WHERE vendor_id = :vendor_id
            """),
            {"vendor_id": vendor_id},
        ).fetchall()

        if not config_rows:
            return

        slot_table_name = f"VENDOR_{vendor_id}_SLOT"
        anchor = date.today()

        for cfg in config_rows:
            day_key = ConsoleService._normalize_day_key(cfg.day)
            if not day_key:
                continue

            try:
                duration = int(cfg.slot_duration or 0)
            except (TypeError, ValueError):
                continue
            if duration < 15 or duration > 240:
                continue

            open_t = ConsoleService._parse_time_flexible(cfg.opening_time)
            close_t = ConsoleService._parse_time_flexible(cfg.closing_time)
            if not open_t or not close_t:
                continue

            blocks = ConsoleService._generate_blocks(anchor, open_t, close_t, duration)
            if not blocks:
                continue

            existing = (
                Slot.query
                .filter(
                    Slot.gaming_type_id == available_game_id,
                    tuple_(Slot.start_time, Slot.end_time).in_(blocks),
                )
                .all()
            )
            slot_id_map = {(s.start_time, s.end_time): int(s.id) for s in existing}

            to_create = []
            for st, et in blocks:
                if (st, et) in slot_id_map:
                    continue
                to_create.append(
                    Slot(
                        gaming_type_id=available_game_id,
                        start_time=st,
                        end_time=et,
                        available_slot=int(total_slots or 1),
                        is_available=False,
                    )
                )

            if to_create:
                db.session.add_all(to_create)
                db.session.flush()
                for s in to_create:
                    slot_id_map[(s.start_time, s.end_time)] = int(s.id)

            slot_ids = [slot_id_map[(st, et)] for st, et in blocks if (st, et) in slot_id_map]
            if not slot_ids:
                continue

            insert_vendor_rows_sql = text(f"""
                INSERT INTO {slot_table_name} (vendor_id, slot_id, date, available_slot, is_available)
                SELECT
                    :vendor_id,
                    s_id.slot_id,
                    gs.date::date,
                    :available_slot,
                    TRUE
                FROM (SELECT unnest(:slot_ids) AS slot_id) s_id
                CROSS JOIN generate_series(CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days', '1 day'::INTERVAL) gs
                WHERE EXTRACT(DOW FROM gs.date) = :target_dow
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {slot_table_name} v
                      WHERE v.vendor_id = :vendor_id
                        AND v.slot_id = s_id.slot_id
                        AND v.date = gs.date::date
                  );
            """)
            db.session.execute(
                insert_vendor_rows_sql,
                {
                    "vendor_id": vendor_id,
                    "slot_ids": slot_ids,
                    "available_slot": int(total_slots or 1),
                    "target_dow": ConsoleService.WEEKDAY_MAP[day_key],
                },
            )

    @staticmethod
    def _is_blank(value):
        return value is None or str(value).strip() == ""

    @staticmethod
    def validate_console_payload(console_data, hardware_data):
        console_type = str(console_data.get("consoleType", "")).strip().lower()
        if console_type not in {"pc", "ps5", "xbox", "vr"}:
            return "Unsupported consoleType. Expected one of: pc, ps5, xbox, vr."

        console_name = console_data.get("modelNumber")
        if ConsoleService._is_blank(console_name):
            console_name = console_data.get("name")

        required_common = {
            "consoleNumber": console_data.get("consoleNumber"),
            "name": console_name,
            "serialNumber": console_data.get("serialNumber"),
            "brand": console_data.get("brand"),
            "releaseDate": console_data.get("releaseDate"),
        }
        for field, value in required_common.items():
            if ConsoleService._is_blank(value):
                if field == "name":
                    return "Missing required field: consoleDetails.name (or consoleDetails.modelNumber)"
                return f"Missing required field: consoleDetails.{field}"

        if console_type == "pc":
            pc_required = {
                "processorType": hardware_data.get("processorType"),
                "graphicsCard": hardware_data.get("graphicsCard"),
                "ramSize": hardware_data.get("ramSize"),
                "storageCapacity": hardware_data.get("storageCapacity"),
                "connectivity": hardware_data.get("connectivity"),
            }
            for field, value in pc_required.items():
                if ConsoleService._is_blank(value):
                    return f"Missing required field for PC: hardwareSpecifications.{field}"
        else:
            non_pc_required = {
                "consoleModelType": hardware_data.get("consoleModelType"),
                "storageCapacity": hardware_data.get("storageCapacity"),
            }
            for field, value in non_pc_required.items():
                if ConsoleService._is_blank(value):
                    return f"Missing required field for {console_type.upper()}: hardwareSpecifications.{field}"

        return None

    @staticmethod
    def normalize_hardware_spec(console_type, hardware_data):
        normalized_type = str(console_type or "").strip().lower()
        source = hardware_data or {}
        if normalized_type == "pc":
            return {
                "processorType": source.get("processorType"),
                "graphicsCard": source.get("graphicsCard"),
                "ramSize": source.get("ramSize"),
                "storageCapacity": source.get("storageCapacity"),
                "connectivity": source.get("connectivity"),
                "consoleModelType": source.get("consoleModelType") or "Custom Build",
            }

        # Non-PC consoles should not store PC-only hardware fields.
        return {
            "processorType": None,
            "graphicsCard": None,
            "ramSize": None,
            "storageCapacity": source.get("storageCapacity"),
            "connectivity": None,
            "consoleModelType": source.get("consoleModelType"),
        }

    @staticmethod
    def add_console(data):
        try:
            vendor_id = (
                data.get("vendorId")
                or data.get("vendor_id")
                or data.get("vendorID")
            )
            if vendor_id is None:
                return {"error": "Missing required field: vendorId"}, 400
            try:
                vendor_id = int(vendor_id)
            except (TypeError, ValueError):
                return {"error": "Invalid vendorId. Expected an integer."}, 400
            if vendor_id <= 0:
                return {"error": "Invalid vendorId. Must be greater than 0."}, 400

            available_game_type = (
                data.get("availablegametype")
                or data.get("availableGameType")
                or data.get("available_game_type")
            )
            if not available_game_type:
                return {"error": "Missing required field: availablegametype"}, 400

            console_data = data.get("consoleDetails", {})
            hardware_data = data.get("hardwareSpecifications", {})
            maintenance_data = data.get("maintenanceStatus", {})
            price_data = data.get("priceAndCost", {})
            additional_data = data.get("additionalDetails", {})

            validation_error = ConsoleService.validate_console_payload(console_data, hardware_data)
            if validation_error:
                return {"error": validation_error}, 400

            # ✅ Create Console Entry
            console_name = console_data.get("modelNumber")
            if ConsoleService._is_blank(console_name):
                console_name = console_data.get("name")

            console = Console(
                vendor_id=vendor_id,
                console_number=console_data["consoleNumber"],
                model_number=console_name,
                serial_number=console_data["serialNumber"],
                brand=console_data["brand"],
                console_type=console_data["consoleType"],
                release_date=datetime.strptime(console_data["releaseDate"], "%Y-%m-%d").date(),
                description=console_data["description"],
            )
            db.session.add(console)
            db.session.flush()  # ✅ Get console.id before commit

            normalized_hardware = ConsoleService.normalize_hardware_spec(
                console_data.get("consoleType"),
                hardware_data,
            )

            # ✅ Create Hardware Specifications
            hardware_spec = HardwareSpecification(
                console_id=console.id,
                processor_type=normalized_hardware.get("processorType"),
                graphics_card=normalized_hardware.get("graphicsCard"),
                ram_size=normalized_hardware.get("ramSize"),
                storage_capacity=normalized_hardware.get("storageCapacity"),
                connectivity=normalized_hardware.get("connectivity"),
                console_model_type=normalized_hardware.get("consoleModelType"),
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

            is_new_game = False
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
                is_new_game = True

            # ✅ Associate Console with AvailableGame (Many-to-Many)
            if console not in available_game.consoles:
                available_game.consoles.append(console)

            if is_new_game:
                # First console of a game type: bootstrap slot templates + vendor rows from day-wise config.
                ConsoleService._bootstrap_new_game_slots(
                    vendor_id=vendor_id,
                    available_game_id=available_game.id,
                    total_slots=available_game.total_slot,
                )
                slots_to_update = Slot.query.filter_by(gaming_type_id=available_game.id).all()
                for slot in slots_to_update:
                    db.session.add(slot)
                db.session.flush()
            else:
                # ✅ Existing game type: increment existing slot capacities by 1 for new console.
                slots_to_update = Slot.query.filter_by(gaming_type_id=available_game.id).all()
                for slot in slots_to_update:
                    slot.available_slot += 1
                    slot.is_available = True
                    db.session.add(slot)
                db.session.flush()

                slot_table_name = f"VENDOR_{vendor_id}_SLOT"
                update_existing_slots_sql = text(f"""
                    UPDATE {slot_table_name} v
                    SET available_slot = COALESCE(v.available_slot, 0) + 1,
                        is_available = TRUE
                    WHERE v.vendor_id = :vendor_id
                      AND v.date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '365 days'
                      AND v.slot_id IN (SELECT id FROM slots WHERE gaming_type_id = :available_game_id);
                """)
                db.session.execute(
                    update_existing_slots_sql,
                    {"vendor_id": vendor_id, "available_game_id": available_game.id},
                )

                insert_missing_slots_sql = text(f"""
                    INSERT INTO {slot_table_name} (vendor_id, date, slot_id, is_available, available_slot)
                    SELECT
                        :vendor_id AS vendor_id,
                        gs.date::date AS date,
                        s.id AS slot_id,
                        TRUE AS is_available,
                        1 AS available_slot
                    FROM generate_series(CURRENT_DATE, CURRENT_DATE + INTERVAL '365 days', '1 day'::INTERVAL) gs
                    CROSS JOIN slots s
                    WHERE s.gaming_type_id = :available_game_id
                      AND NOT EXISTS (
                        SELECT 1
                        FROM {slot_table_name} v
                        WHERE v.vendor_id = :vendor_id
                          AND v.date = gs.date::date
                          AND v.slot_id = s.id
                      );
                """)
                db.session.execute(
                    insert_missing_slots_sql,
                    {"vendor_id": vendor_id, "available_game_id": available_game.id},
                )


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
            hardware = getattr(console, "hardware_specifications", None)
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

            normalized_hardware = ConsoleService.normalize_hardware_spec(
                console.console_type,
                {
                    "processorType": hardware.processor_type if hardware else None,
                    "graphicsCard": hardware.graphics_card if hardware else None,
                    "ramSize": hardware.ram_size if hardware else None,
                    "storageCapacity": hardware.storage_capacity if hardware else None,
                    "connectivity": hardware.connectivity if hardware else None,
                    "consoleModelType": hardware.console_model_type if hardware else None,
                },
            )

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
                    "processorType": normalized_hardware.get("processorType"),
                    "graphicsCard": normalized_hardware.get("graphicsCard"),
                    "ramSize": normalized_hardware.get("ramSize"),
                    "storageCapacity": normalized_hardware.get("storageCapacity"),
                    "connectivity": normalized_hardware.get("connectivity"),
                    "consoleModelType": normalized_hardware.get("consoleModelType"),
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
