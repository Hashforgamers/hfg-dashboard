from flask import Blueprint, request, jsonify
from services.tourney_dashboard_service import EventService
from models.events import Events
from extension.extensions import db
from models.vendor import Vendor

event_bp = Blueprint("event", __name__, url_prefix="/events")
vendor_bp = Blueprint("vendor", __name__, url_prefix="/vendors")


# Event Controller Routes
@event_bp.route("/<int:event_id>/publish", methods=["POST"])
def publish_event(event_id):
    """
    POST /events/{id}/publish
    Publish an event (make it visible)
    """
    try:
        event = EventService.publish_event(event_id)

        if not event:
            return jsonify({"error": "Event not found"}), 404

        return jsonify(
            {
                "message": "Event published successfully",
                "event": {
                    "id": event.id,
                    "title": event.title,
                    "status": event.status,
                    "visibility": event.visibility,
                },
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@event_bp.route("/<int:event_id>/open-registrations", methods=["POST"])
def open_registrations(event_id):
    """
    POST /events/{id}/open-registrations
    Open registration for an event
    """
    try:
        event = EventService.open_registration(event_id)

        if not event:
            return jsonify({"error": "Event not found"}), 404

        return jsonify(
            {
                "message": "Registration opened successfully",
                "event": {"id": event.id, "title": event.title, "status": event.status},
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@event_bp.route("/<int:event_id>/lock-registrations", methods=["POST"])
def lock_registrations(event_id):
    """
    POST /events/{id}/lock-registrations
    Lock registration for an event
    """
    try:
        event = EventService.lock_registration(event_id)

        if not event:
            return jsonify({"error": "Event not found"}), 404

        return jsonify(
            {
                "message": "Registration locked successfully",
                "event": {"id": event.id, "title": event.title, "status": event.status},
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@event_bp.route("/<int:event_id>/provisional-results", methods=["POST"])
def submit_provisional_results(event_id):
    """
    POST /events/{id}/provisional-results
    Submit provisional results for an event
    """
    try:
        data = request.get_json()

        # Validate required fields
        if (
            "team_id" not in data
            or "proposed_rank" not in data
            or "vendor_id" not in data
        ):
            return jsonify(
                {"error": "Missing required fields: team_id, proposed_rank, vendor_id"}
            ), 400

        provisional_result = EventService.submit_provisional_results(
            event_id=event_id,
            team_id=data["team_id"],
            vendor_id=data["vendor_id"],
            proposed_rank=data["proposed_rank"],
        )

        return jsonify(
            {
                "message": "Provisional results submitted successfully",
                "result": {
                    "id": provisional_result.id,
                    "event_id": provisional_result.event_id,
                    "team_id": provisional_result.team_id,
                    "proposed_rank": provisional_result.proposed_rank,
                    "submitted_at": provisional_result.submitted_at.isoformat()
                    if provisional_result.submitted_at
                    else None,
                },
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@event_bp.route("/<int:event_id>/verify", methods=["POST"])
def verify_event(event_id):
    """
    POST /events/{id}/verify
    Create a verification check for an event
    """
    try:
        data = request.get_json()

        # Validate required fields
        if "team_id" not in data or "flag" not in data:
            return jsonify({"error": "Missing required fields: team_id, flag"}), 400

        verification = EventService.verify_event(
            event_id=event_id,
            team_id=data["team_id"],
            flag=data["flag"],
            details=data.get("details", {}),
        )

        return jsonify(
            {
                "message": "Verification check created successfully",
                "verification": {
                    "id": verification.id,
                    "event_id": verification.event_id,
                    "team_id": verification.team_id,
                    "flag": verification.flag,
                    "created_at": verification.created_at.isoformat()
                    if verification.created_at
                    else None,
                },
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@event_bp.route("/<int:event_id>/publish-results", methods=["POST"])
def publish_results(event_id):
    """
    POST /events/{id}/publish-results
    Publish final results for an event
    """
    try:
        data = request.get_json()

        # Validate required fields
        if "results" not in data or not isinstance(data["results"], list):
            return jsonify({"error": "Missing or invalid results array"}), 400

        winners = EventService.publish_results(event_id, data["results"])

        winners_list = []
        for winner in winners:
            winners_list.append(
                {
                    "id": winner.id,
                    "event_id": winner.event_id,
                    "team_id": winner.team_id,
                    "rank": winner.rank,
                    "published_at": winner.published_at.isoformat()
                    if winner.published_at
                    else None,
                }
            )

        return jsonify(
            {"message": "Results published successfully", "winners": winners_list}
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# Vendor Controller Routes
@vendor_bp.route("/<int:vendor_id>/events", methods=["POST"])
def create_event(vendor_id):
    """
    POST /vendors/{id}/events
    Create a new event for a vendor
    """
    try:
        # Verify vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404

        data = request.get_json()

        # Validate required fields
        required_fields = ["title", "start_at", "end_at"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        event = EventService.create_event(vendor_id, data)

        return jsonify(
            {
                "message": "Event created successfully",
                "event": {
                    "id": event.id,
                    "title": event.title,
                    "status": event.status,
                    "start_at": event.start_at.isoformat() if event.start_at else None,
                    "end_at": event.end_at.isoformat() if event.end_at else None,
                },
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@vendor_bp.route("/<int:vendor_id>/events", methods=["GET"])
def get_vendor_events(vendor_id):
    """
    GET /vendors/{id}/events
    Get all events for a vendor (manage views)
    """
    try:
        # Verify vendor exists
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404

        events = EventService.get_vendor_events(vendor_id)

        events_list = []
        for event in events:
            events_list.append(
                {
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "start_at": event.start_at.isoformat() if event.start_at else None,
                    "end_at": event.end_at.isoformat() if event.end_at else None,
                    "status": event.status,
                    "visibility": event.visibility,
                    "registration_fee": float(event.registration_fee)
                    if event.registration_fee
                    else None,
                    "currency": event.currency,
                    "capacity_team": event.capacity_team,
                    "capacity_player": event.capacity_player,
                    "created_at": event.created_at.isoformat()
                    if event.created_at
                    else None,
                }
            )

        return jsonify({"events": events_list, "total": len(events_list)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
