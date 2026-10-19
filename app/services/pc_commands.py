"""Durable command identity and delivery evidence; a timeout never frees an occupied PC."""
import uuid
from sqlalchemy import text
from app.extension.extensions import db
from app.services.kiosk_security import KioskError


def ready():
    return db.engine.dialect.name=='postgresql' and bool(db.session.execute(text("SELECT to_regclass('pc_session_commands')")).scalar())

def newer_player(vendor_id,console_id,booking_id):
    other=db.session.execute(text(f'''SELECT 1 FROM VENDOR_{int(vendor_id)}_DASHBOARD d JOIN bookings b ON b.id=d.book_id
      WHERE d.book_status='current' AND b.status NOT IN ('cancelled','canceled','completed') AND d.book_id<>:bid
      AND (d.console_id=:cid OR COALESCE(b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb) @> to_jsonb(CAST(:cid AS integer)))
      AND NOT COALESCE(b.squad_details::jsonb->'released_console_ids','[]'::jsonb) @> to_jsonb(CAST(:cid AS integer)) LIMIT 1'''),
      {'cid':console_id,'bid':booking_id}).scalar()
    if other:return True
    if db.session.execute(text("SELECT to_regclass('cafe_play_sessions')")).scalar():
        return bool(db.session.execute(text("SELECT 1 FROM cafe_play_sessions WHERE vendor_id=:vid AND console_id=:cid AND state IN ('reserved','active') LIMIT 1"),{'vid':vendor_id,'cid':console_id}).scalar())
    return False


def issue(vendor_id,console_id,booking_id,action='unlock',retry_failed=False):
    if not ready():return None
    db.session.execute(text('''INSERT INTO pc_session_commands(id,vendor_id,console_id,booking_id,action)
       VALUES(:id,:vid,:cid,:bid,:action) ON CONFLICT(vendor_id,console_id,booking_id,action) DO NOTHING'''),
       {'id':str(uuid.uuid4()),'vid':vendor_id,'cid':console_id,'bid':booking_id,'action':action})
    if retry_failed:
        db.session.execute(text('''UPDATE pc_session_commands SET id=:id,state='pending',created_at=CURRENT_TIMESTAMP,acknowledged_at=NULL
          WHERE vendor_id=:vid AND console_id=:cid AND booking_id=:bid AND action=:action AND state='failed' '''),
          {'id':str(uuid.uuid4()),'vid':vendor_id,'cid':console_id,'bid':booking_id,'action':action})
    return delivery(vendor_id,console_id,booking_id,action)


def delivery(vendor_id,console_id,booking_id,action='unlock'):
    if not ready():return {'state':'unconfirmed','acknowledged':False}
    r=db.session.execute(text('''SELECT id,state,created_at,acknowledged_at FROM pc_session_commands
       WHERE vendor_id=:vid AND console_id=:cid AND booking_id=:bid AND action=:action'''),
       {'vid':vendor_id,'cid':console_id,'bid':booking_id,'action':action}).mappings().first()
    if not r:return {'state':'unconfirmed','acknowledged':False}
    return {'command_id':str(r['id']),'action':action,'state':r['state'],'acknowledged':r['state']=='acked',
      'created_at':r['created_at'].isoformat(),'acknowledged_at':r['acknowledged_at'].isoformat() if r['acknowledged_at'] else None}


def acknowledge(identity,body):
    if not ready():raise KioskError('command_migration_required',503)
    if not isinstance(body,dict) or type(body.get('success')) is not bool:raise KioskError('invalid_ack',400)
    try:command_id=str(uuid.UUID(str(body.get('command_id'))))
    except ValueError:raise KioskError('invalid_ack',400)
    r=db.session.execute(text('SELECT * FROM pc_session_commands WHERE id=:id FOR UPDATE'),{'id':command_id}).mappings().first()
    if not r or r['vendor_id']!=identity['vendor_id'] or r['console_id']!=identity['console_id']:raise KioskError('command_scope_mismatch',403)
    if r['action']=='lock' and newer_player(r['vendor_id'],r['console_id'],r['booking_id']):raise KioskError('stale_command',409)
    # A delayed acknowledgement cannot confirm a previous booking on this PC.
    if r['action']=='unlock':
        from app.services.kiosk_runtime import booking_window
        if booking_window(r['vendor_id'],r['booking_id'],r['console_id'])['status']!='active':raise KioskError('session_ended',409)
    state='acked' if body['success'] else 'failed'
    if r['state']!='pending' and r['state']!=state:raise KioskError('ack_conflict',409)
    db.session.execute(text("UPDATE pc_session_commands SET state=:state,acknowledged_at=COALESCE(acknowledged_at,CURRENT_TIMESTAMP) WHERE id=:id"),{'id':command_id,'state':state})
    return delivery(r['vendor_id'],r['console_id'],r['booking_id'],r['action'])
