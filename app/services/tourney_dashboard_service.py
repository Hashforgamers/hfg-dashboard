import datetime
from models.events import Events
from models.provisional_results import ProvisionalResults
from models.verification_checks import VerificationChecks
from models.registrations import Registrations
from models.winners import Winners
from extension.extensions import db


class EventService:
    @staticmethod
    def create_event(vendor_id, data):
        """Create a new event for a vendor"""
        event = Events(
            vendor_id=vendor_id,
            title=data.get("title"),
            description=data.get("description"),
            start_at=data.get("start_at"),
            end_at=data.get("end_at"),
            registration_fee=data.get("registration_fee"),
            currency=data.get("currency"),
            registration_deadline=data.get("registration_deadline"),
            capacity_team=data.get("capacity_team"),
            capacity_player=data.get("capacity_player"),
            min_team_size=data.get("min_team_size"),
            max_team_size=data.get("max_team_size"),
            allow_solo=data.get("allow_solo", False),
            qr_code_url=data.get("qr_code_url"),
            status=data.get("status", "draft"),
            visibility=data.get("visibility", False),
            show_individual=data.get("show_individual", False),
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        )
        db.session.add(event)
        db.session.commit()
        return event

    @staticmethod
    def get_vendor_events(vendor_id):
        """Get all events for a vendor"""
        events = Events.query.filter_by(vendor_id=vendor_id).all()
        return events

    @staticmethod
    def publish_event(event_id):
        """Publish an event (open registrations)"""
        event = Events.query.get(event_id)
        if not event:
            return None

        event.status = "published"
        event.visibility = True
        event.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        return event

    @staticmethod
    def open_registration(event_id):
        """Open registration for an event"""
        event = Events.query.get(event_id)
        if not event:
            return None

        event.status = "registration_open"
        event.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        return event

    @staticmethod
    def lock_registration(event_id):
        """Lock registration for an event"""
        event = Events.query.get(event_id)
        if not event:
            return None

        event.status = "registration_locked"
        event.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        return event

    @staticmethod
    def submit_provisional_results(event_id, team_id, vendor_id, proposed_rank):
        """Submit provisional results for an event"""
        provisional_result = ProvisionalResults(
            event_id=event_id,
            team_id=team_id,
            proposed_rank=proposed_rank,
            submitted_at=datetime.datetime.utcnow(),
            submitted_by_vendor=vendor_id,
        )
        db.session.add(provisional_result)
        db.session.commit()
        return provisional_result

    @staticmethod
    def verify_event(event_id, team_id, flag, details):
        """Create a verification check for an event"""
        verification = VerificationChecks(
            event_id=event_id,
            team_id=team_id,
            flag=flag,
            details=details,
            created_at=datetime.datetime.utcnow(),
        )
        db.session.add(verification)
        db.session.commit()
        return verification

    @staticmethod
    def publish_results(event_id, results_data):
        """Publish final results for an event"""
        # Delete existing winners for this event
        Winners.query.filter_by(event_id=event_id).delete()

        # Create new winners
        winners = []
        for result in results_data:
            winner = Winners(
                event_id=event_id,
                team_id=result.get("team_id"),
                rank=result.get("rank"),
                verified_snapshot=result.get("verified_snapshot"),
                published_at=datetime.datetime.utcnow(),
            )
            db.session.add(winner)
            winners.append(winner)

        # Update event status
        event = Events.query.get(event_id)
        if event:
            event.status = "completed"
            event.updated_at = datetime.datetime.utcnow()

        db.session.commit()
        return winners
