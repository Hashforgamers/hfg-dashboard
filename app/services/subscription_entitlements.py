"""Dashboard feature access is independent of staff permissions."""
import re
from flask import request, jsonify
from app.services.subscription_service import get_active_subscription
from app.services.subscription_commerce import terms

# Only paid optional modules are mapped. Billing, authentication, safety/unlink,
# and wallet balance/history remain reachable independently.
RULES = [
 (r'/api/vendor/(\d+)/(?:console-pricing|pricing-offers|active-pricing|controller-pricing|squad-pricing-rules)', 'pricing'),
 (r'/api/vendor/(\d+)/access/(?:staff|role-permissions)', 'staff'),
 (r'/api/cafe/(\d+)/wallets/\d+/(?:topups|adjustments)', 'cafe_wallet'),
 (r'/api/vendor/(\d+)/(?:extras|extra-services)', 'food'),
 (r'/api/vendor/(\d+)/passes', 'passes'),
 (r'/api/vendor/(\d+)/(?:knowYourGamer/stats|payment-methods/stats)', 'analytics'),
 (r'/api/transactionReport/(\d+)', 'analytics'),
]

def require_feature(vendor_id,feature):
    sub=get_active_subscription(vendor_id)
    if not sub or feature not in terms(sub)['entitlements']:
        return jsonify(error='This feature is not included in the active subscription',feature=feature,upgrade_url='/subscription'),403


def enforce_entitlements():
    if request.method=='OPTIONS': return
    if request.path == '/api/kiosk/start-session' and request.method == 'POST':
        from app.services.kiosk_security import runtime_identity
        return require_feature(runtime_identity()['vendor_id'],'kiosk')
    if request.path == '/api/cafe/checkout' and request.method == 'POST':
        body=request.get_json(silent=True) or {}
        if isinstance(body,dict) and body.get('booking_id') is None:
            from app.controllers.cafe_wallet_controller import resolve_qr
            link=resolve_qr(body.get('qr'))
            return require_feature(link.vendor_id,'cafe_wallet') or require_feature(link.vendor_id,'kiosk')
    for pattern,feature in RULES:
        match=re.match(pattern+'(?:/|$)',request.path)
        if not match: continue
        return require_feature(int(match[1]),feature)
