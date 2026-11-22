-- Starting back-to-back bookings of one gamer on one PC (e.g. 2:00 and 2:30
-- slots from the ticket QR) marks them all 'current' in one UPDATE. The guard
-- only accepted that when the bookings shared an access code, so a pay-at-cafe
-- chain whose later slot had no code failed with "Console already has a booking
-- during this interval". Same gamer + same game + same PC + same day is one
-- session; real time overlaps are still rejected by the interval check.
BEGIN;

CREATE OR REPLACE FUNCTION cafe_guard_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE bid integer := (to_jsonb(NEW)->>'book_id')::integer;
        starts timestamp;
        finishes timestamp;
        conflict boolean;
BEGIN
 IF NEW.book_status IN ('current','upcoming') AND NEW.console_id > 0 THEN
   PERFORM id FROM consoles WHERE id=NEW.console_id OR id IN (
       SELECT jsonb_array_elements_text(COALESCE(b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb))::integer
       FROM bookings b WHERE b.id=bid) ORDER BY id FOR UPDATE;
   starts := NEW.date + NEW.start_time;
   finishes := NEW.date + NEW.end_time;
   IF finishes <= starts THEN finishes := finishes + interval '1 day'; END IF;
   EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I d LEFT JOIN bookings guard_b ON guard_b.id=d.book_id WHERE (d.console_id=$1 OR
       (COALESCE(guard_b.squad_details::jsonb->''assigned_console_ids'',''[]''::jsonb) @> to_jsonb($1)
        AND NOT COALESCE(guard_b.squad_details::jsonb->''released_console_ids'',''[]''::jsonb) @> to_jsonb($1)))
       AND d.book_status IN (''current'',''upcoming'') AND d.book_id IS DISTINCT FROM $2
       AND (($3=''current'' AND d.book_status=''current'' AND NOT EXISTS (
            SELECT 1 FROM bookings old_b JOIN bookings new_b ON new_b.id=$2
            WHERE old_b.id=d.book_id AND old_b.user_id=new_b.user_id
              AND old_b.game_id=new_b.game_id
              AND ((old_b.access_code_id IS NOT NULL AND old_b.access_code_id=new_b.access_code_id)
                   OR (d.date=CAST($4 AS date) AND d.console_id=$1)))) OR
          (d.date+d.start_time < $5 AND $4 < d.date+d.end_time+
              CASE WHEN d.end_time<=d.start_time THEN interval ''1 day'' ELSE interval ''0 day'' END)))',TG_TABLE_NAME)
       INTO conflict USING NEW.console_id,bid,NEW.book_status,starts,finishes;
   IF conflict THEN
     RAISE EXCEPTION 'Console already has a booking during this interval' USING ERRCODE='23514';
   END IF;
   IF EXISTS (SELECT 1 FROM kiosk_runtime_sessions r WHERE (r.console_id=NEW.console_id OR EXISTS (SELECT 1 FROM bookings owner_b WHERE owner_b.id=bid
           AND COALESCE(owner_b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb) @> to_jsonb(r.console_id)
           AND NOT COALESCE(owner_b.squad_details::jsonb->'released_console_ids','[]'::jsonb) @> to_jsonb(r.console_id)))
       AND r.ended_at IS NULL AND NOT (r.source_kind='booking' AND r.booking_ids::jsonb @> to_jsonb(bid))
       AND starts < ((r.reserved_until AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata')
       AND ((r.started_at AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata') < finishes) THEN
     RAISE EXCEPTION 'Console interval held by session extension' USING ERRCODE='23514';
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
