# app/controllers/booking_bridge_controller.py
from flask import Blueprint, request, jsonify
from app.services.booking_bridge import join_vendor, leave_vendor, bridge_status

bridge_bp = Blueprint("bridge_control", __name__, url_prefix="/bridge")

@bridge_bp.get("/status")
def status():
    return jsonify(bridge_status()), 200

@bridge_bp.post("/join")
def join_vendor_room():
    payload = request.get_json(force=True) or {}
    vendor_id = payload.get("vendor_id")
    if vendor_id is None:
        return jsonify({"message": "vendor_id required"}), 400
    try:
        join_vendor(int(vendor_id))
        return jsonify({"message": f"joined vendor_{vendor_id}"}), 200
    except Exception as e:
        return jsonify({"message": "failed", "error": str(e)}), 500

@bridge_bp.post("/leave")
def leave_vendor_room():
    payload = request.get_json(force=True) or {}
    vendor_id = payload.get("vendor_id")
    if vendor_id is None:
        return jsonify({"message": "vendor_id required"}), 400
    try:
        leave_vendor(int(vendor_id))
        return jsonify({"message": f"left vendor_{vendor_id} (if supported)"}), 200
    except Exception as e:
        return jsonify({"message": "failed", "error": str(e)}), 500
