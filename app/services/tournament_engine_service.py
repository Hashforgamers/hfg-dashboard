from datetime import datetime, timezone
from math import ceil, log2

from app.extension.extensions import db
from app.models.event import Event
from app.models.registration import Registration
from app.models.team import Team
from app.models.tournamentSeed import TournamentSeed
from app.models.tournamentMatch import TournamentMatch, MatchStatus
from app.models.matchParticipant import MatchParticipant
from app.models.matchResultSubmission import MatchResultSubmission
from app.models.matchDispute import MatchDispute
from app.models.mapVetoAction import MapVetoAction


DEFAULT_VALORANT_MAP_POOL = ["Bind", "Haven", "Split", "Ascent", "Icebox", "Lotus", "Sunset"]


def _now():
    return datetime.now(timezone.utc)


def _next_power_of_two(value):
    if value <= 1:
        return 1
    return 2 ** ceil(log2(value))


def _team_name_map(team_ids):
    if not team_ids:
        return {}
    teams = Team.query.filter(Team.id.in_(team_ids)).all()
    return {str(team.id): team.team_name for team in teams}


def _match_payload(match):
    team_ids = [tid for tid in [match.team_a_id, match.team_b_id, match.winner_team_id] if tid]
    names = _team_name_map(team_ids)
    return {
        "id": str(match.id),
        "event_id": str(match.event_id),
        "round_number": match.round_number,
        "match_number": match.match_number,
        "status": match.status,
        "team_a_id": str(match.team_a_id) if match.team_a_id else None,
        "team_b_id": str(match.team_b_id) if match.team_b_id else None,
        "team_a_name": names.get(str(match.team_a_id)) if match.team_a_id else None,
        "team_b_name": names.get(str(match.team_b_id)) if match.team_b_id else None,
        "winner_team_id": str(match.winner_team_id) if match.winner_team_id else None,
        "winner_team_name": names.get(str(match.winner_team_id)) if match.winner_team_id else None,
        "scheduled_at": match.scheduled_at.isoformat() if match.scheduled_at else None,
        "lobby_instructions": match.lobby_instructions,
        "map_name": match.map_name,
        "server_region": match.server_region,
        "admin_notes": match.admin_notes,
        "map_pool": match.map_pool or [],
        "veto_mode": match.veto_mode,
        "team_a_captain_confirmed_at": match.team_a_captain_confirmed_at.isoformat() if match.team_a_captain_confirmed_at else None,
        "team_b_captain_confirmed_at": match.team_b_captain_confirmed_at.isoformat() if match.team_b_captain_confirmed_at else None,
        "observer_user_id": match.observer_user_id,
        "stream_url": match.stream_url,
        "match_timer_started_at": match.match_timer_started_at.isoformat() if match.match_timer_started_at else None,
        "created_at": match.created_at.isoformat() if match.created_at else None,
        "updated_at": match.updated_at.isoformat() if match.updated_at else None,
    }


def list_matches(event_id):
    matches = (
        TournamentMatch.query
        .filter_by(event_id=event_id)
        .order_by(TournamentMatch.round_number.asc(), TournamentMatch.match_number.asc())
        .all()
    )
    return [_match_payload(match) for match in matches]


def get_bracket(event_id):
    matches = list_matches(event_id)
    rounds = {}
    for match in matches:
        rounds.setdefault(match["round_number"], []).append(match)
    return {
        "event_id": str(event_id),
        "rounds": [
            {"round_number": round_number, "matches": rounds[round_number]}
            for round_number in sorted(rounds)
        ],
    }


def build_lobby_instructions(event, match):
    region = match.server_region or event.server or event.region or "Organizer selected"
    map_text = match.map_name or "Map veto/admin selection pending"
    return (
        f"Valorant custom lobby: Team A creates the lobby and invites Team B. "
        f"Server: {region}. Map: {map_text}. Captains must upload the final scoreboard screenshot."
    )


def _set_participants(match):
    MatchParticipant.query.filter_by(match_id=match.id).delete()
    if match.team_a_id:
        db.session.add(MatchParticipant(match_id=match.id, team_id=match.team_a_id, side="A"))
    if match.team_b_id:
        db.session.add(MatchParticipant(match_id=match.id, team_id=match.team_b_id, side="B"))


def _ready_status(team_a_id, team_b_id):
    if team_a_id and team_b_id:
        return MatchStatus.READY
    if team_a_id or team_b_id:
        return MatchStatus.COMPLETED
    return MatchStatus.PENDING


def _advance_winner(event, match, winner_team_id):
    match.winner_team_id = winner_team_id
    match.status = MatchStatus.COMPLETED
    next_match = TournamentMatch.query.filter_by(
        event_id=event.id,
        round_number=match.round_number + 1,
        match_number=ceil(match.match_number / 2),
    ).first()
    if not next_match:
        return
    if match.match_number % 2 == 1:
        next_match.team_a_id = winner_team_id
    else:
        next_match.team_b_id = winner_team_id
    next_match.status = _ready_status(next_match.team_a_id, next_match.team_b_id)
    next_match.lobby_instructions = build_lobby_instructions(event, next_match)
    _set_participants(next_match)
    if next_match.status == MatchStatus.COMPLETED and next_match.team_a_id and not next_match.team_b_id:
        _advance_winner(event, next_match, next_match.team_a_id)
    if next_match.status == MatchStatus.COMPLETED and next_match.team_b_id and not next_match.team_a_id:
        _advance_winner(event, next_match, next_match.team_b_id)


def open_check_in(event):
    event.check_in_starts_at = event.check_in_starts_at or _now()
    db.session.commit()
    return event


def close_check_in(event):
    event.check_in_ends_at = _now()
    db.session.commit()
    return event


def check_in_registration(event_id, team_id):
    reg = Registration.query.filter_by(event_id=event_id, team_id=team_id).first_or_404()
    reg.checked_in_at = _now()
    db.session.commit()
    return reg


def generate_single_elimination_bracket(event, require_check_in=False, force=False):
    if event.format != "single_elimination":
        raise ValueError("Phase 1 bracket generation supports single_elimination only")

    existing = TournamentMatch.query.filter_by(event_id=event.id).first()
    if existing and not force:
        raise ValueError("Bracket already exists. Pass force=true to regenerate.")

    if force:
        MatchDispute.query.filter_by(event_id=event.id).delete()
        MatchResultSubmission.query.filter_by(event_id=event.id).delete()
        MapVetoAction.query.filter_by(event_id=event.id).delete()
        TournamentMatch.query.filter_by(event_id=event.id).delete()
        TournamentSeed.query.filter_by(event_id=event.id).delete()
        db.session.flush()

    query = (
        Registration.query
        .filter(Registration.event_id == event.id)
        .filter(Registration.status == "confirmed")
        .order_by(Registration.created_at.asc())
    )
    if require_check_in:
        query = query.filter(Registration.checked_in_at.isnot(None))
    regs = query.all()
    if len(regs) < 2:
        raise ValueError("At least two confirmed teams are required")

    for idx, reg in enumerate(regs, start=1):
        reg.seed_number = idx
        db.session.add(TournamentSeed(event_id=event.id, team_id=reg.team_id, seed_number=idx))

    bracket_size = _next_power_of_two(len(regs))
    total_rounds = int(log2(bracket_size))
    slots = [reg.team_id for reg in regs] + [None] * (bracket_size - len(regs))
    map_pool = event.map_pool or (DEFAULT_VALORANT_MAP_POOL if event.game == "valorant" else [])
    bye_matches = []

    for round_number in range(1, total_rounds + 1):
        match_count = bracket_size // (2 ** round_number)
        for match_number in range(1, match_count + 1):
            team_a_id = slots[(match_number - 1) * 2] if round_number == 1 else None
            team_b_id = slots[(match_number - 1) * 2 + 1] if round_number == 1 else None
            match = TournamentMatch(
                event_id=event.id,
                round_number=round_number,
                match_number=match_number,
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                status=_ready_status(team_a_id, team_b_id),
                map_pool=map_pool,
                veto_mode=event.veto_mode or "none",
                server_region=event.server or event.region,
            )
            match.lobby_instructions = build_lobby_instructions(event, match)
            db.session.add(match)
            db.session.flush()
            _set_participants(match)
            if match.status == MatchStatus.COMPLETED:
                bye_matches.append(match)

    for match in bye_matches:
        winner = match.team_a_id or match.team_b_id
        if winner:
            _advance_winner(event, match, winner)

    db.session.commit()
    return get_bracket(event.id)


def update_match(match, patch):
    allowed = {
        "status", "scheduled_at", "lobby_instructions", "map_name", "server_region",
        "admin_notes", "observer_user_id", "stream_url", "veto_mode", "map_pool",
    }
    for key, value in patch.items():
        if key in allowed:
            setattr(match, key, value)
    db.session.commit()
    return _match_payload(match)


def start_match(event, match):
    if not match.team_a_id or not match.team_b_id:
        raise ValueError("Both teams are required to start a match")
    match.status = MatchStatus.IN_PROGRESS
    match.match_timer_started_at = match.match_timer_started_at or _now()
    match.lobby_instructions = match.lobby_instructions or build_lobby_instructions(event, match)
    db.session.commit()
    return _match_payload(match)


def admin_result(event, match, vendor_id, payload):
    winner_team_id = payload.get("winner_team_id")
    if not winner_team_id or str(winner_team_id) not in {str(match.team_a_id), str(match.team_b_id)}:
        raise ValueError("winner_team_id must be one of the match teams")
    db.session.add(MatchResultSubmission(
        event_id=event.id,
        match_id=match.id,
        team_id=winner_team_id,
        winner_team_id=winner_team_id,
        submitted_by_vendor=vendor_id,
        team_a_score=payload.get("team_a_score"),
        team_b_score=payload.get("team_b_score"),
        screenshot_url=payload.get("screenshot_url"),
        notes=payload.get("notes"),
        status="accepted",
    ))
    _advance_winner(event, match, winner_team_id)
    db.session.commit()
    return _match_payload(match)


def resolve_dispute(event, match, vendor_id, payload):
    winner_team_id = payload.get("winner_team_id")
    resolution = payload.get("resolution")
    disputes = MatchDispute.query.filter_by(match_id=match.id, status="open").all()
    for dispute in disputes:
        dispute.status = "resolved"
        dispute.resolution = resolution
        dispute.resolved_by_vendor = vendor_id
        dispute.resolved_at = _now()
    if winner_team_id:
        _advance_winner(event, match, winner_team_id)
    else:
        match.status = MatchStatus.ADMIN_CLOSED
    db.session.commit()
    return _match_payload(match)


def submit_result(event, match, user_id, payload):
    team_id = payload.get("team_id")
    winner_team_id = payload.get("winner_team_id")
    if not team_id or str(team_id) not in {str(match.team_a_id), str(match.team_b_id)}:
        raise ValueError("team_id must be one of the match teams")
    if winner_team_id and str(winner_team_id) not in {str(match.team_a_id), str(match.team_b_id)}:
        raise ValueError("winner_team_id must be one of the match teams")
    submission = MatchResultSubmission(
        event_id=event.id,
        match_id=match.id,
        team_id=team_id,
        winner_team_id=winner_team_id,
        submitted_by_user=user_id,
        team_a_score=payload.get("team_a_score"),
        team_b_score=payload.get("team_b_score"),
        screenshot_url=payload.get("screenshot_url"),
        notes=payload.get("notes"),
    )
    db.session.add(submission)
    prior = (
        MatchResultSubmission.query
        .filter(MatchResultSubmission.match_id == match.id)
        .filter(MatchResultSubmission.team_id != team_id)
        .order_by(MatchResultSubmission.created_at.desc())
        .first()
    )
    if prior and prior.winner_team_id and winner_team_id and str(prior.winner_team_id) == str(winner_team_id):
        _advance_winner(event, match, winner_team_id)
        submission.status = "accepted"
        prior.status = "accepted"
    elif prior and prior.winner_team_id and winner_team_id and str(prior.winner_team_id) != str(winner_team_id):
        match.status = MatchStatus.DISPUTED
        db.session.add(MatchDispute(
            event_id=event.id,
            match_id=match.id,
            team_id=team_id,
            opened_by_user=user_id,
            reason="Captain result mismatch",
        ))
    else:
        match.status = MatchStatus.AWAITING_RESULTS
    db.session.commit()
    return _match_payload(match)


def confirm_match(event, match, user_id, team_id):
    if str(team_id) == str(match.team_a_id):
        match.team_a_captain_confirmed_at = _now()
    elif str(team_id) == str(match.team_b_id):
        match.team_b_captain_confirmed_at = _now()
    else:
        raise ValueError("team_id must be one of the match teams")
    if match.team_a_captain_confirmed_at and match.team_b_captain_confirmed_at and match.status == MatchStatus.READY:
        match.status = MatchStatus.LOBBY_CREATED
    db.session.commit()
    return _match_payload(match)


def open_dispute(event, match, user_id, team_id, reason):
    if str(team_id) not in {str(match.team_a_id), str(match.team_b_id)}:
        raise ValueError("team_id must be one of the match teams")
    match.status = MatchStatus.DISPUTED
    db.session.add(MatchDispute(
        event_id=event.id,
        match_id=match.id,
        opened_by_user=user_id,
        team_id=team_id,
        reason=reason,
    ))
    db.session.commit()
    return _match_payload(match)


def add_veto_action(event, match, user_id, payload):
    team_id = payload.get("team_id")
    map_name = payload.get("map_name")
    action = payload.get("action", "ban")
    if action not in {"ban", "pick"}:
        raise ValueError("action must be ban or pick")
    if not team_id or str(team_id) not in {str(match.team_a_id), str(match.team_b_id)}:
        raise ValueError("team_id must be one of the match teams")
    pool = match.map_pool or event.map_pool or DEFAULT_VALORANT_MAP_POOL
    if map_name not in pool:
        raise ValueError("map_name is not in the match map pool")
    existing = MapVetoAction.query.filter_by(match_id=match.id).order_by(MapVetoAction.action_order.asc()).all()
    if any(v.map_name == map_name for v in existing):
        raise ValueError("map already vetoed or picked")
    db.session.add(MapVetoAction(
        event_id=event.id,
        match_id=match.id,
        team_id=team_id,
        actor_user_id=user_id,
        action=action,
        map_name=map_name,
        action_order=len(existing) + 1,
    ))
    remaining = [m for m in pool if m not in {v.map_name for v in existing} and m != map_name]
    if len(remaining) == 1:
        match.map_name = remaining[0]
        match.lobby_instructions = build_lobby_instructions(event, match)
    db.session.commit()
    return _match_payload(match)
