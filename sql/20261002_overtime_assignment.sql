BEGIN;
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
       AND (($3=''current'' AND d.book_status=''current'' AND NOT EXISTS (
            SELECT 1 FROM bookings old_b JOIN bookings new_b ON new_b.id=$2
            WHERE old_b.id=d.book_id AND old_b.user_id=new_b.user_id
              AND old_b.game_id=new_b.game_id AND old_b.access_code_id IS NOT NULL
              AND old_b.access_code_id=new_b.access_code_id)) OR
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

COMMIT;
