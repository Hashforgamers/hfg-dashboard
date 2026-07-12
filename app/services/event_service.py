from datetime import datetime, timezone

from app.extension.extensions import db
from app.models.event import Event, EventStatus


TERMINAL_STATUSES = {EventStatus.DRAFT, EventStatus.COMPLETED, EventStatus.CANCELED}


def _as_aware_datetime(value):
    if value is None or isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return value

    if parsed and parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_datetime_fields(payload):
    normalized = dict(payload or {})
    for key in (
        "start_at",
        "end_at",
        "registration_deadline",
        "check_in_starts_at",
        "check_in_ends_at",
    ):
        if key in normalized and normalized[key]:
            normalized[key] = _as_aware_datetime(normalized[key])
    return normalized


def derive_event_status(event, now=None):
    status = event.status or EventStatus.DRAFT
    if status in TERMINAL_STATUSES:
        return status

    start_at = _as_aware_datetime(event.start_at)
    end_at = _as_aware_datetime(event.end_at)
    current_time = now or datetime.now(timezone.utc)

    if not start_at or not end_at:
        return status
    if current_time > end_at:
        return EventStatus.COMPLETED
    if current_time >= start_at:
        return EventStatus.ONGOING
    return EventStatus.PUBLISHED


def sync_event_status(event, now=None):
    next_status = derive_event_status(event, now)
    changed = event.status != next_status
    if changed:
        event.status = next_status
    return changed


def sync_event_statuses(events):
    changed = False
    now = datetime.now(timezone.utc)
    for event in events:
        changed = sync_event_status(event, now) or changed
    if changed:
        db.session.commit()
    return events

def create_event(vendor_id, payload):
    payload = _normalize_datetime_fields(payload)
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
    sync_event_status(ev)
    db.session.add(ev)
    db.session.commit()
    return ev

def list_events(vendor_id, status=None):
    q = Event.query.filter_by(vendor_id=vendor_id)
    events = q.order_by(Event.created_at.desc()).all()
    sync_event_statuses(events)
    if status:
        events = [event for event in events if event.status == status]
    return events

def update_event(vendor_id, event_id, patch):
    patch = _normalize_datetime_fields(patch)
    ev = Event.query.filter_by(id=event_id, vendor_id=vendor_id).first_or_404()
    for k, v in patch.items():
        if hasattr(ev, k):
            setattr(ev, k, v)
    sync_event_status(ev)
    db.session.commit()
    return ev
