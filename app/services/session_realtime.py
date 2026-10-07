"""Authenticated app session stream; user room is derived from signed claims."""
import time
import jwt
from flask import current_app,request
from flask_socketio import join_room

_gamer_sids={}
_socketio=None

def register_gamer_realtime(app,socketio):
    global _socketio
    _socketio=socketio
    @socketio.on('watch',namespace='/cafe-availability')
    def watch(data):
        # Public invalidation contains no player or financial information.
        from app.extension.extensions import db
        from sqlalchemy import text
        if not isinstance(data,dict):return {'ok':False}
        value=data.get('vendor_id')
        if type(value) is not int or value<=0: return {'ok':False}
        exists=db.session.execute(text('SELECT id FROM vendors WHERE id=:id'),{'id':value}).scalar()
        if not exists:return {'ok':False}
        join_room(f'public-cafe:{value}');return {'ok':True}
    @socketio.on('connect',namespace='/cafe-availability')
    def availability_connect(auth=None): return True
    @socketio.on('connect',namespace='/cafe-gamer')
    def connect(auth=None):
        try:
            token=(auth or {}).get('token')
            claims=jwt.decode(token,current_app.config['JWT_SECRET_KEY'],algorithms=['HS256'],audience='cafe-checkout',
                options={'require':['exp','iat','sub']})
            user=int(claims['sub'])
            if claims.get('scope')!='cafe_gamer' or user<=0:return False
            _gamer_sids[request.sid]=float(claims['exp']);join_room(f'cafe-user:{user}')
        except (jwt.InvalidTokenError,ValueError,TypeError): return False
    @socketio.on('disconnect',namespace='/cafe-gamer')
    def disconnect(reason=None): _gamer_sids.pop(request.sid,None)

def expire_gamer_connections():
    if not _socketio:return
    for sid,expiry in list(_gamer_sids.items()):
        if expiry<=time.time():
            _gamer_sids.pop(sid,None);_socketio.server.disconnect(sid,namespace='/cafe-gamer')
