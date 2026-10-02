-- Apply after 20260923_unified_kiosk_qr.sql, before deploying shared QR capacity.
BEGIN;
CREATE TABLE IF NOT EXISTS cafe_slot_reservations (
 session_id varchar(36) NOT NULL,
 vendor_id integer NOT NULL,
 date date NOT NULL,
 slot_id integer NOT NULL,
 units integer NOT NULL CHECK (units > 0),
 released_at timestamp,
 PRIMARY KEY(session_id,vendor_id,date,slot_id)
);
CREATE INDEX IF NOT EXISTS ix_cafe_slot_reservation_capacity
 ON cafe_slot_reservations(vendor_id,date,slot_id,released_at);

-- Seed remaining capacity holds for QR sessions already running at rollout.
-- This lock prevents acknowledgement/completion while their holds are seeded.
LOCK TABLE cafe_play_sessions IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE play record; slot record; left_edge timestamp; right_edge timestamp;
        inserted integer; changed integer;
BEGIN
 FOR play IN SELECT * FROM cafe_play_sessions
   WHERE kind='wallet' AND state IN ('reserved','active') AND console_claim IS NOT NULL
     AND COALESCE(ends_at,deadline + minutes * interval '1 minute') > (now() AT TIME ZONE 'UTC')
   ORDER BY vendor_id,id
 LOOP
   left_edge := (GREATEST(now() AT TIME ZONE 'UTC',COALESCE(play.started_at,play.created_at)) AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata';
   right_edge := (COALESCE(play.ends_at,play.deadline + play.minutes * interval '1 minute') AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata';
   FOR slot IN EXECUTE format('SELECT v.date,v.slot_id FROM %I v JOIN slots s ON s.id=v.slot_id
       JOIN available_games ag ON ag.id=s.gaming_type_id
       WHERE v.vendor_id=$1 AND ag.vendor_id=$1
         AND EXISTS (SELECT 1 FROM available_game_console ac WHERE ac.available_game_id=ag.id AND ac.console_id=$2)
         AND v.date BETWEEN $3::date-1 AND $4::date
         AND v.date+s.start_time < $4
         AND $3 < v.date+s.end_time+CASE WHEN s.end_time<=s.start_time THEN interval ''1 day'' ELSE interval ''0 day'' END
       ORDER BY v.date,v.slot_id FOR UPDATE OF v','vendor_'||play.vendor_id||'_slot')
       USING play.vendor_id,play.console_id,left_edge,right_edge
   LOOP
     INSERT INTO cafe_slot_reservations(session_id,vendor_id,date,slot_id,units)
       VALUES(play.id,play.vendor_id,slot.date,slot.slot_id,1) ON CONFLICT DO NOTHING;
     GET DIAGNOSTICS inserted=ROW_COUNT;
     IF inserted=1 THEN
       EXECUTE format('UPDATE %I SET available_slot=available_slot-1,is_available=(available_slot-1>0)
           WHERE vendor_id=$1 AND date=$2 AND slot_id=$3 AND available_slot>=1','vendor_'||play.vendor_id||'_slot')
           USING play.vendor_id,slot.date,slot.slot_id;
       GET DIAGNOSTICS changed=ROW_COUNT;
       IF changed<>1 THEN
         RAISE EXCEPTION 'Existing QR session % has no remaining slot capacity; reconcile before rollout',play.id;
       END IF;
     END IF;
   END LOOP;
 END LOOP;
END $$;

-- All dated capacity writers (app, desk, kiosk and QR) fail atomically at zero.
CREATE OR REPLACE FUNCTION cafe_guard_slot_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.available_slot < 0 THEN
   RAISE EXCEPTION 'Slot capacity is no longer available' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

-- Console assignment and QR claims take the same console lock. A future
-- assignment cannot silently shorten a wallet session that already owns the PC.
CREATE OR REPLACE FUNCTION cafe_guard_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE bid integer := (to_jsonb(NEW)->>'book_id')::integer;
        starts timestamp;
        finishes timestamp;
        conflict boolean;
BEGIN
 IF NEW.book_status IN ('current','upcoming') AND NEW.console_id > 0 THEN
   PERFORM id FROM consoles WHERE id=NEW.console_id FOR UPDATE;
   starts := NEW.date + NEW.start_time;
   finishes := NEW.date + NEW.end_time;
   IF finishes <= starts THEN finishes := finishes + interval '1 day'; END IF;
   EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I d WHERE d.console_id=$1
       AND d.book_status IN (''current'',''upcoming'') AND d.book_id IS DISTINCT FROM $2
       AND (($3=''current'' AND d.book_status=''current'' AND
          ($4 IS NULL OR $5 IS NULL OR d.date IS NULL OR d.start_time IS NULL OR d.end_time IS NULL)) OR
          (d.date+d.start_time < $5 AND $4 < d.date+d.end_time+
              CASE WHEN d.end_time<=d.start_time THEN interval ''1 day'' ELSE interval ''0 day'' END)))',TG_TABLE_NAME)
       INTO conflict USING NEW.console_id,bid,NEW.book_status,starts,finishes;
   IF conflict THEN
     RAISE EXCEPTION 'Console already has a booking during this interval' USING ERRCODE='23514';
   END IF;
   IF EXISTS (
     SELECT 1 FROM cafe_play_sessions s WHERE s.console_claim=NEW.console_id
       AND NOT EXISTS (SELECT 1 FROM cafe_booking_claims c WHERE c.session_id=s.id AND c.booking_id=bid)
       AND (NEW.book_status='current' OR
         (starts < ((COALESCE(s.ends_at,s.booking_end,s.deadline + s.minutes * interval '1 minute') AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata')
           AND ((COALESCE(s.started_at,s.created_at) AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata') < finishes))
   ) OR (NEW.book_status='current' AND EXISTS (
     SELECT 1 FROM cafe_booking_claims c JOIN cafe_play_sessions s ON s.id=c.session_id
     WHERE c.booking_id=bid AND (s.state <> 'active' OR s.console_claim IS DISTINCT FROM NEW.console_id)
   )) THEN
     RAISE EXCEPTION 'Booking or console is already claimed by a QR session' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION cafe_guard_availability() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE occupied boolean;
BEGIN
 IF EXISTS (SELECT 1 FROM cafe_play_sessions WHERE console_claim=NEW.console_id) THEN
   NEW.is_available := false;
 ELSIF NEW.is_available THEN
   EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE console_id=$1 AND book_status=''current'')',
       'vendor_' || split_part(TG_TABLE_NAME,'_',2) || '_dashboard') INTO occupied USING NEW.console_id;
   IF occupied THEN NEW.is_available := false; END IF;
 END IF;
 RETURN NEW;
END $$;

-- Existing vendors receive guards; newly linked cafes use this installer too.
CREATE OR REPLACE FUNCTION cafe_install_console_guards(vid integer) RETURNS void LANGUAGE plpgsql AS $$
DECLARE availability text := 'vendor_' || vid || '_console_availability';
        dashboard text := 'vendor_' || vid || '_dashboard';
        slots_table text := 'vendor_' || vid || '_slot';
BEGIN
 IF to_regclass(availability) IS NULL OR to_regclass(dashboard) IS NULL THEN
   RAISE EXCEPTION 'Cafe console tables are missing';
 END IF;
 EXECUTE format('DROP TRIGGER IF EXISTS cafe_qr_guard ON %I',availability);
 EXECUTE format('CREATE TRIGGER cafe_qr_guard BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION cafe_guard_availability()',availability);
 EXECUTE format('DROP TRIGGER IF EXISTS cafe_qr_guard ON %I',dashboard);
 EXECUTE format('CREATE TRIGGER cafe_qr_guard BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION cafe_guard_assignment()',dashboard);
 IF to_regclass(slots_table) IS NOT NULL THEN
   EXECUTE format('DROP TRIGGER IF EXISTS cafe_slot_capacity_guard ON %I',slots_table);
   EXECUTE format('CREATE TRIGGER cafe_slot_capacity_guard BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION cafe_guard_slot_capacity()',slots_table);
 END IF;
END $$;
DO $$
DECLARE vid integer;
BEGIN
 FOR vid IN SELECT DISTINCT split_part(tablename,'_',2)::integer FROM pg_tables
   WHERE schemaname=current_schema() AND tablename ~ '^vendor_[0-9]+_dashboard$' LOOP
   IF to_regclass('vendor_'||vid||'_console_availability') IS NOT NULL
      AND to_regclass('vendor_'||vid||'_dashboard') IS NOT NULL THEN
     PERFORM cafe_install_console_guards(vid);
   END IF;
 END LOOP;
END $$;
COMMIT;
