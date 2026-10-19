"""Read-only canonical session view; never infer device acknowledgement from payment."""
from sqlalchemy import text
from app.extension.extensions import db


def cafe_sessions(vendor_id,user_id=None):
    from app.services.kiosk_runtime import booking_window,assigned_consoles
    from app.services.pc_commands import delivery
    from app.models.cafe_wallet import CafePlaySession
    from app.services.cafe_continuation_service import snapshot as qr_snapshot
    from app.services.session_extensions import ready,RuntimeSession,snapshot
    from app.models.console import Console
    vendor_id=int(vendor_id)
    items=[]
    rows=db.session.execute(text(f'''SELECT d.*,b.squad_details FROM VENDOR_{vendor_id}_DASHBOARD d
       JOIN bookings b ON b.id=d.book_id WHERE d.book_status IN ('upcoming','current')
       AND b.status NOT IN ('cancelled','canceled','rejected')
       AND (CAST(:uid AS integer) IS NULL OR b.user_id=:uid)
       ORDER BY d.date,d.start_time,d.book_id'''),{'uid':user_id}).mappings().all()
    have_runtime=ready()
    runtimes=RuntimeSession.query.filter_by(vendor_id=vendor_id).all() if have_runtime else []
    by_booking={(bid,r.console_id):r for r in runtimes for bid in r.booking_ids}
    for row in rows:
        consoles=assigned_consoles(row) or {None}
        for cid in sorted(consoles,key=lambda x:x or 0):
            runtime=by_booking.get((row['book_id'],cid))
            if runtime and int(row['book_id'])!=int(runtime.source_id):continue
            delivered=delivery(vendor_id,cid,row['book_id']) if cid else {'state':'unassigned','acknowledged':False}
            window=booking_window(vendor_id,row['book_id'],cid) if cid else None
            base=db.session.execute(text('''SELECT COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) AS total,
              COALESCE(SUM(CASE WHEN settlement_status IN ('paid','processed') THEN amount ELSE 0 END),0) AS paid
              FROM transactions WHERE booking_id=:bid AND booking_type IN ('booking','regular','direct','pay_at_cafe','extra_controller')'''),{'bid':row['book_id']}).mappings().one()
            extension=snapshot(runtime) if runtime else None
            due=(extension or {}).get('billing',{}).get('amount_due_paise',0)
            base_total=round(float(base['total'])*100);base_paid=round(float(base['paid'])*100)
            payment=db.session.execute(text('''SELECT mode_of_payment,source_channel FROM transactions
              WHERE booking_id=:bid AND amount>=0 ORDER BY id LIMIT 1'''),{'bid':row['book_id']}).mappings().first()
            device_state='confirmed' if delivered['acknowledged'] else 'failed' if delivered['state']=='failed' else 'unconfirmed'
            state='ready' if row['book_status']=='upcoming' else 'active' if delivered['acknowledged'] else 'starting'
            console=db.session.get(Console,cid) if cid else None
            items.append({'session_id':f'booking:{row["book_id"]}:{cid or "unassigned"}',
              'session_ref':{'kind':'booking','id':str(row['book_id'])},'runtime_id':runtime.id if runtime else None,
              'booking_id':row['book_id'],'vendor_id':vendor_id,'console_id':cid,'console_number':getattr(console,'console_number',None),
              'console_name':getattr(console,'model_number',None),'customer_name':row.get('username'),
              'lifecycle_state':state,'allocation_state':'occupied' if row['book_status']=='current' else 'reserved' if cid else 'unassigned',
              'device_state':device_state,'delivery':delivered,'timing':dict(window or {},actual_start_time=delivered.get('acknowledged_at')),'runtime':extension,
              'booking_channel':payment['source_channel'] if payment else 'unknown',
              'billing':{'currency':'INR','initial_total_paise':base_total,'initial_collected_paise':base_paid,
                'initial_payment_method':payment['mode_of_payment'] if payment else None,
                'extension_due_paise':due,'amount_due_paise':max(0,base_total-base_paid)+due,
                'requires_reconciliation':(extension or {}).get('billing',{}).get('requires_reconciliation',False),
                'payment_status':'amount_due' if max(0,base_total-base_paid)+due>0 else 'extension_reserved' if (extension or {}).get('billing',{}).get('payment_status')=='extension_reserved' else 'paid'}})
    qr_rows=CafePlaySession.query.filter_by(vendor_id=vendor_id).filter(CafePlaySession.kind!='existing_booking',CafePlaySession.state.in_(['reserved','active']))
    if user_id is not None:qr_rows=qr_rows.filter_by(user_id=user_id)
    for qr in qr_rows.all():
        state=qr_snapshot(qr)
        items.append({'session_id':f'self_qr:{qr.id}','session_ref':{'kind':'self_qr','id':qr.id},'vendor_id':vendor_id,
            'console_id':qr.console_id,'user_id':qr.user_id,'lifecycle_state':'starting' if qr.state=='reserved' else 'active',
            'allocation_state':'reserved' if qr.state=='reserved' else 'occupied','device_state':'confirmed' if qr.state=='active' else 'unconfirmed',
            'timing':{'started_at':state.get('started_at'),'reserved_until':state.get('ends_at')},
            'billing':{'currency':'INR','amount_due_paise':state.get('payment_due',0)},'details':state})
    return items
