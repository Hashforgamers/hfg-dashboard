"""Read-only movement ledger and per-console usage history; no synthetic payments."""
from datetime import datetime,timedelta,timezone
import pytz
from sqlalchemy import text
from app.extension.extensions import db
from app.services.cafe_wallet_service import CafeError

def bounds(args):
    zone=pytz.timezone('Asia/Kolkata');today=datetime.now(zone).date()
    try:
        start=datetime.strptime(args.get('from') or str(today-timedelta(days=30)),'%Y-%m-%d').date()
        end=datetime.strptime(args.get('to') or str(today),'%Y-%m-%d').date()
        page=int(args.get('page',1));size=int(args.get('limit',25))
    except (ValueError,TypeError):raise CafeError('Use valid dates and pagination')
    if start>end or page<1 or not 1<=size<=100:raise CafeError('Invalid date range or pagination')
    return dict(start=zone.localize(datetime.combine(start,datetime.min.time())).astimezone(timezone.utc).replace(tzinfo=None),
        end=zone.localize(datetime.combine(end+timedelta(days=1),datetime.min.time())).astimezone(timezone.utc).replace(tzinfo=None),limit=size,offset=(page-1)*size,page=page)

def page_query(sql,params,where):
    total=db.session.execute(text('SELECT count(*) FROM ('+sql+') events WHERE '+where),params).scalar()
    rows=db.session.execute(text('SELECT * FROM ('+sql+') events WHERE '+where+' ORDER BY occurred_at DESC,id DESC LIMIT :limit OFFSET :offset'),params).mappings().all()
    items=[]
    for row in rows:
        items.append({k:(v.isoformat()+'Z' if isinstance(v,datetime) else v) for k,v in row.items()})
    return dict(items=items,total=total,page=params['page'],limit=params['limit'])

def ledger_report(vendor_id,args):
    p=bounds(args);p['vendor']=vendor_id;p['kind']=args.get('kind','')
    sql="""SELECT 'ledger:'||CAST(l.id AS text) id,l.created_at occurred_at,l.kind,l.amount amount_paise,
        l.method,l.actor_name,COALESCE(u.name,'Guest') gamer_name,l.user_id,l.session_id reference,
        l.balance_after balance_after_paise,l.reserved_after reserved_after_paise,l.reason,'wallet_or_collection' category
        FROM cafe_wallet_ledger l LEFT JOIN users u ON u.id=l.user_id WHERE l.vendor_id=:vendor"""
    sql+=""" UNION ALL SELECT 'transaction:'||CAST(t.id AS text),
        ((t.booking_date+t.booking_time) AT TIME ZONE 'Asia/Kolkata') AT TIME ZONE 'UTC',
        'booking_'||t.booking_type,CAST(round(CAST(t.amount AS numeric)*100) AS bigint),t.mode_of_payment,
        COALESCE(t.initiated_by_staff_name,'App / system'),COALESCE(u.name,'Guest'),t.user_id,CAST(t.booking_id AS text),NULL,NULL,
        'Booking settlement: '||COALESCE(t.settlement_status,'unknown'),'booking_record'
        FROM transactions t LEFT JOIN users u ON u.id=t.user_id WHERE t.vendor_id=:vendor"""
    if db.session.execute(text("SELECT to_regclass('kiosk_session_credit_ledger')")).scalar():
        sql+=""" UNION ALL SELECT 'credit:'||c.id,c.created_at,'credit_'||c.kind,c.amount,NULL,
            'System / linked collection',COALESCE(u.name,'Guest'),r.user_id,r.id,NULL,NULL,
            'Session credit '||c.kind,'credit_debt' FROM kiosk_session_credit_ledger c
            JOIN kiosk_runtime_sessions r ON r.id=c.runtime_id LEFT JOIN users u ON u.id=r.user_id WHERE r.vendor_id=:vendor"""
    return page_query(sql,p,"occurred_at>=:start AND occurred_at<:end AND (:kind='' OR kind=:kind)")

def console_history(vendor_id,console_id,args):
    if not db.session.execute(text('SELECT 1 FROM consoles WHERE id=:cid AND vendor_id=:vid'),{'cid':console_id,'vid':vendor_id}).scalar():raise CafeError('Console not found',404)
    p=bounds(args);p.update(vendor=vendor_id,console=console_id)
    runtime=db.session.execute(text("SELECT to_regclass('kiosk_runtime_sessions')")).scalar()
    runtime_exclusion=" AND NOT EXISTS(SELECT 1 FROM kiosk_runtime_sessions r WHERE r.console_id=:console AND r.source_kind='booking' AND r.booking_ids::jsonb @> to_jsonb(b.id))" if runtime else ''
    qr_exclusion=" AND NOT EXISTS(SELECT 1 FROM kiosk_runtime_sessions r WHERE r.source_kind='self_qr' AND r.source_id=q.id)" if runtime else ''
    sql=f"""SELECT 'booking:'||CAST(b.id AS text) id,
        ((d.date+d.start_time) AT TIME ZONE 'Asia/Kolkata') AT TIME ZONE 'UTC' occurred_at,
        COALESCE(u.name,d.username,'Guest') gamer_name,'booking' source,b.status state,
        ((d.date+d.end_time+CASE WHEN d.end_time<d.start_time THEN interval '1 day' ELSE interval '0 days' END) AT TIME ZONE 'Asia/Kolkata') AT TIME ZONE 'UTC' ends_at,
        'scheduled' time_basis,CAST(b.id AS text) reference,NULL::bigint extension_due_paise
        FROM VENDOR_{int(vendor_id)}_DASHBOARD d JOIN bookings b ON b.id=d.book_id LEFT JOIN users u ON u.id=b.user_id
        WHERE (d.console_id=:console OR COALESCE(b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb) @> to_jsonb(CAST(:console AS integer))) {runtime_exclusion}
        UNION ALL SELECT 'qr:'||q.id,q.started_at,COALESCE(u.name,'Guest'),q.kind,q.state,COALESCE(q.ended_at,q.ends_at),
        CASE WHEN q.ended_at IS NULL THEN 'actual start / scheduled end' ELSE 'actual' END,q.id,q.due_amount
        FROM cafe_play_sessions q LEFT JOIN users u ON u.id=q.user_id WHERE q.vendor_id=:vendor AND q.console_id=:console
        AND q.kind<>'existing_booking' AND q.started_at IS NOT NULL {qr_exclusion}"""
    if runtime:
        sql+=""" UNION ALL SELECT 'runtime:'||r.id,r.started_at,COALESCE(u.name,'Guest'),r.source_kind,r.status,
            COALESCE(r.ended_at,r.reserved_until),CASE WHEN r.ended_at IS NULL THEN 'actual start / reserved end' ELSE 'actual' END,r.source_id,
            COALESCE((SELECT sum(s.credit_due-s.credit_paid) FROM kiosk_extension_segments s WHERE s.runtime_id=r.id),0)
            FROM kiosk_runtime_sessions r LEFT JOIN users u ON u.id=r.user_id WHERE r.vendor_id=:vendor AND r.console_id=:console"""
    return page_query(sql,p,'occurred_at>=:start AND occurred_at<:end')
