import re
from flask import current_app, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt

from app.services.rbac_service import claim_vendor_id, claims_permissions


# method, regex path, permission
RBAC_ROUTE_RULES = [
    ("GET", r"^/api/getConsoles/vendor/(?P<vendor_id>\d+)$", "gaming.manage"),
    ("POST", r"^/api/addConsole$", "gaming.manage"),
    ("DELETE", r"^/api/console/(?P<vendor_id>\d+)/\d+$", "gaming.manage"),
    ("PUT", r"^/api/console/update/vendor/(?P<vendor_id>\d+)$", "gaming.manage"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/dashboard$", "dashboard.view"),
    ("GET", r"^/api/getLandingPage/vendor/(?P<vendor_id>\d+)$", "dashboard.view"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/console-pricing$", "pricing.manage"),
    ("POST", r"^/api/vendor/(?P<vendor_id>\d+)/console-pricing$", "pricing.manage"),

    ("GET", r"^/api/transactionReport/(?P<vendor_id>\d+)/\d{8}/.+$", "transactions.view"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/knowYourGamer$", "gamers.view"),
    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/knowYourGamer/stats$", "gamers.view"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/extras/categories$", "extras.manage"),
    ("POST", r"^/api/vendor/(?P<vendor_id>\d+)/extras/category$", "extras.manage"),
    ("POST", r"^/api/vendor/(?P<vendor_id>\d+)/extras/category/\d+/menu$", "extras.manage"),
    ("PUT", r"^/api/vendor/(?P<vendor_id>\d+)/extras/category/\d+$", "extras.manage"),
    ("DELETE", r"^/api/vendor/(?P<vendor_id>\d+)/extras/category/\d+$", "extras.manage"),
    ("PUT", r"^/api/vendor/(?P<vendor_id>\d+)/extras/category/\d+/menu/\d+$", "extras.manage"),
    ("DELETE", r"^/api/vendor/(?P<vendor_id>\d+)/extras/category/\d+/menu/\d+$", "extras.manage"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/passes$", "passes.manage"),
    ("POST", r"^/api/vendor/(?P<vendor_id>\d+)/passes$", "passes.manage"),
    ("PUT", r"^/api/vendor/(?P<vendor_id>\d+)/passes/\d+$", "passes.manage"),
    ("DELETE", r"^/api/vendor/(?P<vendor_id>\d+)/passes/\d+$", "passes.manage"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/available-games$", "games.manage"),
    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/vendor-games$", "games.manage"),
    ("POST", r"^/api/vendor/(?P<vendor_id>\d+)/vendor-games$", "games.manage"),
    ("PUT", r"^/api/vendor/(?P<vendor_id>\d+)/vendor-games/\d+$", "games.manage"),
    ("DELETE", r"^/api/vendor/(?P<vendor_id>\d+)/vendor-games/\d+$", "games.manage"),
    ("DELETE", r"^/api/vendor/(?P<vendor_id>\d+)/games/\d+/bulk-delete$", "games.manage"),

    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/bank-details$", "account.manage"),
    ("POST", r"^/api/vendor/(?P<vendor_id>\d+)/bank-details$", "account.manage"),
    ("PUT", r"^/api/vendor/(?P<vendor_id>\d+)/bank-details$", "account.manage"),
    ("PATCH", r"^/api/vendor/(?P<vendor_id>\d+)/business-details$", "account.manage"),
    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/notification-preferences$", "account.manage"),
    ("PUT", r"^/api/vendor/(?P<vendor_id>\d+)/notification-preferences$", "account.manage"),
    ("GET", r"^/api/vendor/(?P<vendor_id>\d+)/settlements/summary$", "transactions.view"),
]


COMPILED_RULES = [(method, re.compile(pattern), permission) for method, pattern, permission in RBAC_ROUTE_RULES]


def _extract_vendor_id_from_request(path: str, path_match: re.Match):
    if path_match and path_match.groupdict().get("vendor_id"):
        return int(path_match.group("vendor_id"))

    if path == "/api/addConsole":
        payload = request.get_json(silent=True) or {}
        vendor_id = payload.get("vendorId") or payload.get("vendor_id")
        if vendor_id is not None:
            try:
                return int(vendor_id)
            except (TypeError, ValueError):
                return None

    return None


def enforce_rbac_permissions():
    if request.method == "OPTIONS":
        return None

    path = request.path

    # skip auth endpoints and non-api routes
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/vendor/") and "/access" in path:
        return None

    matched_rule = None
    match_obj = None
    for method, pattern, permission in COMPILED_RULES:
        if method != request.method:
            continue
        found = pattern.match(path)
        if found:
            matched_rule = (method, pattern, permission)
            match_obj = found
            break

    if not matched_rule:
        return None

    _, _, required_permission = matched_rule
    vendor_id = _extract_vendor_id_from_request(path, match_obj)
    if vendor_id is None:
        return jsonify({"error": "Unable to infer vendor_id for RBAC check"}), 400

    auth_header = request.headers.get("Authorization")
    enforcement_enabled = bool(current_app.config.get("RBAC_ENFORCEMENT", False))

    # Backward compatible mode: if no header and enforcement disabled, bypass.
    if not enforcement_enabled and not auth_header:
        return None

    try:
        verify_jwt_in_request()
        claims = get_jwt() or {}
    except Exception:
        return jsonify({"error": "Authorization required"}), 401

    claim_vid = claim_vendor_id(claims)
    if claim_vid is not None and claim_vid != vendor_id:
        return jsonify({"error": "Vendor mismatch"}), 403

    permissions = claims_permissions(claims, vendor_id)
    if required_permission not in permissions:
        return jsonify({
            "error": "Forbidden",
            "required_permission": required_permission,
        }), 403

    return None
