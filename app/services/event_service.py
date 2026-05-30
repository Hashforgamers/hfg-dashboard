from app.extension.extensions import db
from app.models.event import Event, EventStatus

def create_event(vendor_id, payload):
    ev = Event(
        vendor_id=vendor_id,
        title=payload["title"],
        description=payload.get("description"),
        start_at=payload["start_at"],
        end_at=payload["end_at"],
        registration_fee=payload.get("registration_fee", 0),
        currency=payload.get("currency", "INR"),
        game=payload.get("game", "valorant"),
        format=payload.get("format", "single_elimination"),
        prize_pool=payload.get("prize_pool", 0),
        team_size=payload.get("team_size") or payload.get("max_team_size", 5),
        match_rules=payload.get("match_rules"),
        region=payload.get("region"),
        server=payload.get("server"),
        check_in_starts_at=payload.get("check_in_starts_at"),
        check_in_ends_at=payload.get("check_in_ends_at"),
        map_pool=payload.get("map_pool") or [],
        veto_mode=payload.get("veto_mode", "none"),
        registration_deadline=payload.get("registration_deadline"),
        capacity_team=payload.get("capacity_team"),
        capacity_player=payload.get("capacity_player"),
        min_team_size=payload.get("min_team_size", 1),
        max_team_size=payload.get("max_team_size", 5),
        allow_solo=payload.get("allow_solo", False),
        allow_individual=payload.get("allow_individual", False),
        visibility=payload.get("visibility", True),
        status=payload.get("status", EventStatus.DRAFT),
        qr_code_url=payload.get("qr_code_url"),
        banner_image_url=payload.get("banner_image_url"),
        banner_public_id=payload.get("banner_public_id"),
    )
    db.session.add(ev)
    db.session.commit()
    return ev

def list_events(vendor_id, status=None):
    q = Event.query.filter_by(vendor_id=vendor_id)
    if status:
        q = q.filter(Event.status == status)
    return q.order_by(Event.created_at.desc()).all()

def update_event(vendor_id, event_id, patch):
    ev = Event.query.filter_by(id=event_id, vendor_id=vendor_id).first_or_404()
    for k, v in patch.items():
        if hasattr(ev, k):
            setattr(ev, k, v)
    db.session.commit()
    return ev
