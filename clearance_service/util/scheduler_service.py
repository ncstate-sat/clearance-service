"""Module containing SchedulerService, handling scheduled tasks"""

from datetime import datetime, timedelta, timezone

from fastapi import status
from pydantic import ValidationError
from sat.logs import SATLogger

from clearance_service.models import acs
from clearance_service.models.clearance import Clearance
from clearance_service.models.scheduled_action import ScheduledAction
from clearance_service.util.db_connect import get_clearance_collection
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.settings import (
    PURGE_OLD_SCHEDULED_ACTIONS,
    SCHEDULED_ACTION_PURGE_CUTOFF,
    SCHEDULER_LIMIT,
)

logger = SATLogger(__name__)


class SchedulerService:
    """Class to handle tasks scheduled in the ServiceScheduler"""

    scheduled_action_coll = get_clearance_collection("scheduled_action")
    liaison_coll = get_clearance_collection("liaison")

    @classmethod
    def get_scheduled_actions(cls) -> list[dict]:
        """
        Get all assignment and revocation actions due to be processed
        """
        now = datetime.now(timezone.utc)
        all_assignments = cls.scheduled_action_coll.aggregate(
            [
                {
                    "$match": {"action_time": {"$lte": now}, "status": "pending"},
                },
                {
                    "$sort": {"action_time": 1},
                },
                {
                    "$limit": SCHEDULER_LIMIT,
                },
                {
                    "$project": {
                        "assigner_email": 1,
                        "assigner_name": 1,
                        "assignee_email": 1,
                        "clearance_id": 1,
                        "action": 1,
                        "action_time": 1,
                        "status": 1,
                    }
                },
            ]
        )
        return list(all_assignments)

    @classmethod
    def purge_scheduled_actions(cls):
        """
        Daily job to remove processed items from the scheduled_action collection
        after a set length of time
        """
        age_limit_days = SCHEDULED_ACTION_PURGE_CUTOFF
        if not PURGE_OLD_SCHEDULED_ACTIONS:
            logger.info("Purging old scheduled actions is disabled.")
            return
        scheduled_action_coll = cls.scheduled_action_coll
        now = datetime.now()
        purge_cutoff = now - timedelta(days=age_limit_days)

        logger.info(
            f"Purging scheduled_action documents processed more than {age_limit_days} days ago"
        )
        delete_response = scheduled_action_coll.delete_many(
            {
                "status": {
                    "$in": ["succeeded", "failed", "already_completed"],
                },
                "action_time": {"$lt": purge_cutoff},
            }
        )
        logger.info(f"Purged {delete_response.deleted_count} documents from scheduled_action")

    @classmethod
    def push_to_ccure(cls):
        """
        An automated job that pushes new clearance assignments to CCure
        """
        due_actions = cls.get_scheduled_actions()

        scheduled_actions = []
        action_configs = []
        malformed_ids = []
        for action in due_actions:
            try:
                action_configs.append(ScheduledAction.ActionConfig(**action))
                scheduled_actions.append(action)
            except ValidationError as e:
                logger.error(
                    f"Scheduled action document {action.get('_id')} is missing required "
                    f"fields and will be marked failed: {e}"
                )
                malformed_ids.append(action["_id"])

        if malformed_ids:
            cls.scheduled_action_coll.update_many(
                {"_id": {"$in": malformed_ids}},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": "Scheduled action is missing required fields.",
                    }
                },
            )

        results = ScheduledAction.process(action_configs)

        # Loop through successful actions, update documents
        succeeded_ids = []
        failed_actions = []
        already_done_actions = []
        pending_ids = []
        for action in scheduled_actions:
            assignee_email = action["assignee_email"]
            clearance_id = action["clearance_id"]
            if (
                results.get("succeeded", {}).get(assignee_email, {}).get(clearance_id, False)
                is True
            ):
                succeeded_ids.append(action["_id"])
            elif (
                results.get("failed", {}).get(assignee_email, {}).get(clearance_id, None)
                is not None
            ):
                error_message = (
                    results.get("failed", {}).get(assignee_email, {}).get(clearance_id, None)
                )
                failed_actions.append({"id": action["_id"], "error_message": error_message})
            elif (
                results.get("already_completed", {}).get(assignee_email, {}).get(clearance_id)
                is not None
            ):
                already_done_actions.append({"id": action["_id"]})
            else:
                pending_ids.append(action["_id"])

        cls.scheduled_action_coll.update_many(
            {"_id": {"$in": succeeded_ids}}, {"$set": {"status": "succeeded"}}
        )
        for action in failed_actions:
            cls.scheduled_action_coll.update_one(
                {"_id": action["id"]},
                {"$set": {"status": "failed", "error_message": action["error_message"]}},
            )

        if len(pending_ids) > 0:
            logger.info(
                "When trying to process these scheduled actions, actions with these IDs neither "
                + f"succeeded nor failed: {', '.join([str(_id) for _id in pending_ids])}."
            )
        if len(failed_actions):
            logger.info(
                "When trying to process these scheduled actions, actions with these IDs "
                + f"failed: {', '.join([str(action['id']) for action in failed_actions])}."
            )
        if already_done_actions:
            logger.info(
                "Actions with these ids have already been processed: "
                + ", ".join(str(action["id"]) for action in already_done_actions)
            )

    @staticmethod
    def ccure_keepalive():
        """Keep the CCure api session active"""
        try:
            acs.connection.keepalive()
        except RequestException as e:
            if e.status_code == status.HTTP_408_REQUEST_TIMEOUT:
                logger.error("CCure timeout: Session keepalive call was not successful.")
            else:
                logger.error(f"{e.status_code}: {e.message}")
            acs.connection.logout()

    @classmethod
    def update_liaison_clearance_names(cls):
        """
        A daily automated job that retrieves current clearance names from CCure
        and updates possibly stale clearance names from the `liaison` Mongo collection.
        """
        liaison_collection = cls.liaison_coll
        all_liasons = liaison_collection.find()
        current_clearances = Clearance.get_all()
        changes = 0
        failures = []
        for liaison in all_liasons:
            stored_clearance_ids = [clearance["id"] for clearance in liaison["clearances"]]
            new_clearances = [current_clearances.get(_id) for _id in stored_clearance_ids]
            if new_clearances != liaison["clearances"]:
                response = liaison_collection.update_one(
                    {"_id": liaison["_id"]},
                    {"$set": {"clearances": list(filter(None, new_clearances))}},
                )
                if response.modified_count:
                    changes += 1
                else:
                    failures.append(liaison.get("email"))
        logger.info(f"Updated clearance names for {changes} liaisons.")
        if failures:
            logger.info(f"Could not update clearance names for liaison(s) {', '.join(failures)}.")
