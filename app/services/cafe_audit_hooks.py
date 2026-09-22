"""Audit existing pricing/staff mutations in their database commit for configured cafes."""
import re
from flask import request, g, has_request_context
from flask_jwt_extended import verify_jwt_in_request
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.extension.extensions import db
from app.models.cafe_wallet import CafePaymentPolicy
from app.services.cafe_wallet_service import audit

_INSTALLED = False


def install_cafe_audit_hooks(app):
    global _INSTALLED
    @app.before_request
    def track_mutation():
        if request.method not in ('POST','PUT','PATCH','DELETE'):
            return
        match = re.match(r'^/api/vendor/(\d+)/(console-pricing|access/(staff|role-permissions))(?:/|$)', request.path)
        if not match:
            return
        vendor_id = int(match[1])
        if db.session.get(CafePaymentPolicy, vendor_id) is None:
            return
        verify_jwt_in_request()
        from app.controllers.cafe_wallet_controller import staff_actor
        permission = 'pricing.manage' if match[2] == 'console-pricing' else 'staff.manage'
        actor = staff_actor(vendor_id, permission)
        body = request.get_json(silent=True) or {}
        # Persist useful changes, never PINs, passwords or tokens.
        secret_names = {'pin','pin_code','pin_hash','password','token','authorization'}
        def clean(value):
            if isinstance(value,dict):
                return {k:clean(v) for k,v in value.items() if k.lower() not in secret_names}
            if isinstance(value,list):return [clean(v) for v in value]
            return value
        g.cafe_mutation = (vendor_id, actor, 'pricing.changed' if permission=='pricing.manage' else 'staff.changed',
                           {'path':request.path, 'method':request.method, 'changes':clean(body)})
    if not _INSTALLED:
        @event.listens_for(Session, 'before_commit')
        def capture(session):
            if has_request_context() and getattr(g, 'cafe_mutation', None):
                mutation = g.cafe_mutation
                g.cafe_mutation = None
                audit(*mutation)
        _INSTALLED = True
