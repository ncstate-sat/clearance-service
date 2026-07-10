"""Model for Clearance Assignments"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, StringConstraints
from sat.logs import SATLogger

from clearance_service.models import acs, filters
from clearance_service.models.audit import Audit
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from clearance_service.util.db_connect import get_clearance_collection
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.settings import C9K_CLEARANCE_LIMIT

logger = SATLogger(__name__)


class ScheduledAction:
    """A future action to be executed by the scheduler"""

    def __init__(
        self,
        assigner_email: str,
        assignee_email: str,
        clearance_id: int,
        action: str,
        action_time: datetime,
        submitted_time: datetime,
        assignment_id: Optional[ObjectId] = None,
        assigner_name: Optional[str] = None,
        clearance_name: Optional[str] = None,
        status: Literal[
            "pending",
            "succeeded",
            "failed",
            "cancelled",
            "already_completed",
        ] = "pending",
        error_message: Optional[str] = None,
    ) -> None:
        """Initialize a ScheduledAction object"""
        self.assigner_email = assigner_email
        self.assignee_email = assignee_email
        self.clearance_id = clearance_id
        self.action = action
        self.action_time = action_time
        self.submitted_time = submitted_time
        self.assignment_id = assignment_id
        self.assigner_name = assigner_name
        self.clearance_name = clearance_name
        self.status = status
        self.error_message = error_message

    @staticmethod
    def get_clearances_by_assignee(assignee_email: str) -> list["Clearance"]:
        """
        Fetch an individual's clearances
        Parameters:
            assignee_email: the individual's email address
        Returns: A list of clearances
        """
        # first get object ids for clearances assigned to assignee_email
        personnel_search_filter = filters.PersonnelFilter(
            lookups={"EmailAddress": filters.NFUZZ},
            display_properties=["ObjectID"],
        )
        personnel_results = acs.personnel.search([assignee_email], personnel_search_filter)
        if not personnel_results:
            logger.info(f"No personnel found with the email address {assignee_email}.")
            return []
        assignee_object_id = personnel_results[0].get("ObjectID")

        assigned_clearances = acs.action.personnel.get_assigned_clearances(
            personnel_id=assignee_object_id
        )
        clearance_ids = [pair.get("ClearanceID") for pair in assigned_clearances]
        if not clearance_ids:
            return []

        # then get the names for those clearances
        assigned_clearances = Clearance.get_by_ids(clearance_ids)
        return [
            Clearance(clearance.get("id"), clearance.get("name"))
            for clearance in assigned_clearances
        ]

    @staticmethod
    def get(
        assigner_email: Optional[str] = None,
        assignee_email: Optional[str] = None,
        assignment_ids: Optional[list[ObjectId]] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        clearance_id: Optional[int] = None,
        action_type: Optional[str] = None,
        status: Optional[list[str]] = [
            "pending",
            "succeeded",
            "failed",
            "cancelled",
            "already_completed",
        ],
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        if action_type is not None and action_type not in ("assign", "revoke"):
            raise RequestException(400, "Action type must be 'assign' or 'revoke'.")
        scheduled_action_coll = get_clearance_collection("scheduled_action")
        match = {}
        if assigner_email:
            assigner = Personnel.find_one(assigner_email, [])
            if assigner:
                match["assigner_email"] = assigner.email
        if assignee_email:
            assignee = Personnel.find_one(assignee_email, [])
            if assignee:
                match["assignee_email"] = assignee.email
        if assignment_ids:
            match["_id"] = {"$in": assignment_ids}
        if clearance_id:
            match["clearance_id"] = clearance_id
        if action_type:
            match["action"] = action_type
        if status:
            match["status"] = {"$in": status}
        if from_time or to_time:
            match["action_time"] = {}
            if from_time is not None:
                match["action_time"]["$gte"] = from_time
            if to_time is not None:
                match["action_time"]["$lt"] = to_time
        raw_results = scheduled_action_coll.aggregate(
            [
                {"$match": match},
                {
                    "$facet": {
                        "count": [
                            {"$count": "total_results"},
                        ],
                        "actions": [
                            {"$sort": {"action_time": -1, "_id": -1}},
                            {
                                "$project": {
                                    "_id": {"$toString": "$_id"},
                                    "assigner_email": 1,
                                    "assigner_name": 1,
                                    "assignee_email": 1,
                                    "clearance_id": 1,
                                    "action": 1,
                                    "action_time": 1,
                                    "submitted_time": 1,
                                    "status": 1,
                                }
                            },
                            {"$skip": skip},
                            {"$limit": limit},
                        ],
                    }
                },
                {
                    "$project": {
                        "count": {
                            "$cond": {
                                "if": {"$gt": [{"$size": "$count.total_results"}, 0]},
                                "then": {"$first": "$count.total_results"},
                                "else": 0,
                            },
                        },
                        "actions": 1,
                    }
                },
            ]
        )
        results = list(raw_results)[0]
        clearance_names = Clearance.get_by_ids(
            ids=[result["clearance_id"] for result in results["actions"]]
        )
        clearance_names = {
            item.get("id"): item.get("name")
            for item in clearance_names
            if "id" in item and "name" in item
        }
        parsed_results = {
            "actions": [
                {
                    **action,
                    "action_time": action["action_time"].replace(tzinfo=timezone.utc),
                    "clearance_name": clearance_names.get(action.get("clearance_id"), None),
                }
                for action in results["actions"]
            ],
            "count": results["count"],
        }
        return parsed_results

    @staticmethod
    def cancel_scheduled_actions(assignment_id_strings: list[str]) -> int:
        """
        Set scheduled action statuses to 'cancelled'
        return the number of updated objects
        """
        assignment_ids = [ObjectId(assignment_id) for assignment_id in assignment_id_strings]
        scheduled_action_coll = get_clearance_collection("scheduled_action")
        update_result = scheduled_action_coll.update_many(
            {"_id": {"$in": assignment_ids}},
            {"$set": {"status": "cancelled"}},
        )
        return update_result.modified_count

    class ActionConfig(BaseModel):
        """Data required for new clearance assignments"""

        assigner_email: str
        assigner_name: str
        assignee_email: str
        clearance_id: int
        # action gets checked against lowercase strings
        action: Annotated[str, StringConstraints(to_lower=True)]
        action_time: Optional[datetime] = None

    @classmethod
    def process(
        cls,
        configs: list[ActionConfig],
    ) -> dict:
        """
        Assign a list of clearances to a list of individuals

        Parameters:
            configs: data for each new assignment
                - assigner_email: email address of the person assigning the clearance
                - assigner_name: name of the person assigning the clearance
                - assignee_email: email address of the person receiving the clearance
                - clearance_id: the clearance's ID in ACS
                - action: a string, either "assign" or "revoke"
                - action_time: the time the action should be executed
                    - `None` to process the action immediately

        Returns: the number of changes made
        """
        now = datetime.now(timezone.utc)
        scheduled_action_coll = get_clearance_collection("scheduled_action")

        # Get assigner and assignee objects and organize that data
        assigner_emails = {config.assigner_email for config in configs}
        display_properties=[
            "FirstName",
            "MiddleName",
            "LastName",
            "EmailAddress",
            "ObjectID",
            "Disabled",
        ]
        assigner_filter = filters.PersonnelFilter(
            lookups={"EmailAddress": filters.NFUZZ},
            display_properties=display_properties,
        )
        assigner_results = acs.personnel.search(list(assigner_emails), assigner_filter)
        assigner_personnel_configs = [
            {prop: result.get(prop) for prop in display_properties}
            for result in assigner_results
        ]
        assigners_in_acs = [Personnel(config) for config in assigner_personnel_configs]
        assignee_emails = {config.assignee_email for config in configs}
        assignees_in_acs = Personnel.search_by_email(list(assignee_emails), ["ObjectID"])
        personnel_in_acs = list(set(assigners_in_acs + assignees_in_acs))
        email_to_acs_map = {person.email: person.acs_id for person in personnel_in_acs}
        assignee_emails_in_acs = {
            assignee.email
            for assignee in assignees_in_acs
            if assignee.email in assignee_emails
        }

        # Get clearance objects from acs
        all_clearance_ids = {config.clearance_id for config in configs}
        clearances_in_acs = Clearance.get_by_ids(list(all_clearance_ids))
        clearance_ids_in_acs = {clearance.get("id") for clearance in clearances_in_acs}
        clearance_id_name_map = {
            clearance.get("id"): clearance.get("name") for clearance in clearances_in_acs
        }

        # Set up variables for processing actions
        new_actions = []
        immediate_new_actions_by_assignee = defaultdict(list)
        assigner_names_by_email = {}
        succeeded_actions = {}
        failed_actions = {}
        already_done_actions = {}

        def save_action_status(
            assignee_email: str,
            clearance_id: int,
            error_message: Optional[str] = None,
            already_completed: bool = False,
        ):
            if already_completed:
                if already_done_actions.get(assignee_email) is None:
                    already_done_actions[assignee_email] = {}
                already_done_actions[assignee_email][
                    clearance_id
                ] = "This action has already been done."
            elif error_message is not None:
                if failed_actions.get(assignee_email) is None:
                    failed_actions[assignee_email] = {}
                failed_actions[assignee_email][clearance_id] = error_message
            else:
                if succeeded_actions.get(assignee_email) is None:
                    succeeded_actions[assignee_email] = {}
                succeeded_actions[assignee_email][clearance_id] = True

        # Process each action, one by one.
        for config in configs:
            assignee_email = config.assignee_email
            clearance_id = config.clearance_id

            # If the clearance or person is not in acs, the action fails.
            if assignee_email not in assignee_emails_in_acs:
                save_action_status(
                    assignee_email=assignee_email,
                    clearance_id=clearance_id,
                    error_message="This assignee does not exist in ACS.",
                )
                continue
            if clearance_id not in clearance_ids_in_acs:
                save_action_status(
                    assignee_email=assignee_email,
                    clearance_id=clearance_id,
                    error_message="This clearance does not exist in ACS.",
                )
                continue

            assigner_email = config.assigner_email
            assigner_names_by_email[assigner_email] = config.assigner_name
            assignee_acs_id = email_to_acs_map.get(config.assignee_email)
            action_time_naive = config.action_time
            if action_time_naive is None:
                action_time = now
            else:
                action_time = datetime(
                    action_time_naive.year,
                    action_time_naive.month,
                    action_time_naive.day,
                    action_time_naive.hour,
                    action_time_naive.minute,
                    action_time_naive.second,
                    tzinfo=timezone.utc,
                )

            if action_time <= now:  # If the start time is now or earlier, assign this now.
                immediate_new_actions_by_assignee[assignee_acs_id].append(
                    {
                        "assigner_email": assigner_email,
                        "assigner_name": config.assigner_name,
                        "assignee_email": config.assignee_email,
                        "clearance_id": config.clearance_id,
                        "action": config.action,
                        "message_base": " activated",
                        "action_time": action_time,
                    }
                )

            else:  # Otherwise, add it to database to be processed later.
                new_actions.append(
                    {
                        "assigner_email": config.assigner_email,
                        "assigner_name": config.assigner_name,
                        "assignee_email": config.assignee_email,
                        "clearance_id": config.clearance_id,
                        "action": config.action,
                        "action_time": action_time,
                        "submitted_time": now,
                        "status": "pending",
                    }
                )

        # Add all future actions to the database.
        if new_actions:
            scheduled_action_coll.insert_many(new_actions)

        # Handle each action.
        for assignee_acs_id, actions in immediate_new_actions_by_assignee.items():
            # Establish sets of clearance changes.
            assignee_added_clearance_ids = set()
            assignee_removed_clearance_ids = set()

            # Get the assignee's current clearances (and clearance IDs)
            current_clearances = acs.action.personnel.get_assigned_clearances(
                personnel_id=assignee_acs_id
            )
            current_clearance_ids = [
                clearance.get("ClearanceID") for clearance in current_clearances
            ]

            # Sort the clearance IDs by assigned or revoked.
            for action in actions:
                if (
                    action["clearance_id"] not in current_clearance_ids
                    and action["action"] == "assign"
                ):
                    assignee_added_clearance_ids.add(action["clearance_id"])
                elif (
                    action["clearance_id"] in current_clearance_ids and action["action"] == "revoke"
                ):
                    assignee_removed_clearance_ids.add(action["clearance_id"])
                else:
                    save_action_status(
                        assignee_email=action.get("assignee_email"),
                        clearance_id=action.get("clearance_id"),
                        already_completed=True,
                    )
                    scheduled_action_coll.update_many(
                        {
                            "assignee_email": action["assignee_email"],
                            "clearance_id": action["clearance_id"],
                            "action": action["action"],
                            "action_time": {"$lte": action["action_time"]},
                        },
                        {"$set": {"status": "already_completed"}},
                    )
                    continue

            # Make sure the new assignment won't push the person over their clearances limit.
            if C9K_CLEARANCE_LIMIT:
                available_clearance_spots = C9K_CLEARANCE_LIMIT - len(current_clearance_ids)
                net_new_clearances_length = len(assignee_added_clearance_ids) - len(
                    assignee_removed_clearance_ids
                )
                if net_new_clearances_length > available_clearance_spots:
                    logger.error(
                        f"This request would give {assignee_acs_id} more than the "
                        f"maximum of {C9K_CLEARANCE_LIMIT} assigned clearances"
                    )
                    for action in actions:
                        save_action_status(
                            assignee_email=action.get("assignee_email"),
                            clearance_id=action.get("clearance_id"),
                            error_message="This action would exceed this "
                            + "person's allowed number of clearances.",
                        )
                    continue

            # Revoke and audit clearances.
            if assignee_removed_clearance_ids:
                try:
                    acs.action.personnel.revoke_clearances(
                        assignee_acs_id, clearance_ids=list(assignee_removed_clearance_ids)
                    )

                    audit_configs = []
                    for _id in assignee_removed_clearance_ids:
                        action = next(
                            (
                                action
                                for action in actions
                                if action["action"] == "revoke" and action["clearance_id"] == _id
                            ),
                            None,
                        )
                        audit_config = Audit.NewAuditData(
                            assigner_email=action.get("assigner_email"),
                            assigner_name=assigner_names_by_email.get(
                                action.get("assigner_email"), action.get("assigner_name")
                            ),
                            assignee_email=action.get("assignee_email"),
                            clearance_id=action.get("clearance_id"),
                            clearance_name=clearance_id_name_map.get(action["clearance_id"]),
                            message_base=" revoked",
                        )
                        audit_configs.append(audit_config)
                        save_action_status(
                            assignee_email=action.get("assignee_email"),
                            clearance_id=_id,
                        )
                    Audit.add_many(audit_configs)

                except RequestException as e:
                    logger.error(f"Could not revoke clearances to personnel {assignee_acs_id}: {e}")

                    for _id in assignee_removed_clearance_ids:
                        action = next(
                            (
                                action
                                for action in actions
                                if action["action"] == "revoke" and action["clearance_id"] == _id
                            ),
                            None,
                        )
                        save_action_status(
                            assignee_email=action.get("assigner_email"),
                            clearance_id=_id,
                            error_message="This clearance failed to be revoked.",
                        )

            # Assign and audit clearances.
            if assignee_added_clearance_ids:
                try:
                    acs.action.personnel.assign_clearances(
                        personnel_id=assignee_acs_id,
                        clearance_ids=list(assignee_added_clearance_ids),
                    )

                    audit_configs = []
                    for _id in assignee_added_clearance_ids:
                        action = next(
                            (
                                action
                                for action in actions
                                if action["action"] == "assign" and action["clearance_id"] == _id
                            ),
                            None,
                        )
                        audit_config = Audit.NewAuditData(
                            assigner_email=action.get("assigner_email"),
                            assigner_name=assigner_names_by_email.get(
                                action.get("assigner_email")
                            )
                            or action.get("assigner_name")
                            or action.get("assigner_email"),
                            assignee_email=action.get("assignee_email"),
                            clearance_id=action.get("clearance_id"),
                            clearance_name=clearance_id_name_map.get(action["clearance_id"]),
                            message_base=" assigned",
                        )
                        audit_configs.append(audit_config)
                        save_action_status(
                            assignee_email=action.get("assignee_email"),
                            clearance_id=_id,
                        )
                    Audit.add_many(audit_configs)

                except RequestException as e:
                    logger.error(f"Could not assign clearances to personnel {assignee_acs_id}: {e}")

                    for _id in assignee_added_clearance_ids:
                        action = next(
                            (
                                action
                                for action in actions
                                if action["action"] == "assign" and action["clearance_id"] == _id
                            ),
                            None,
                        )
                        save_action_status(
                            assignee_email=action.get("assignee_email"),
                            clearance_id=_id,
                            error_message="This clearance failed to be assigned.",
                        )

        missing_clearances = all_clearance_ids - clearance_ids_in_acs
        missing_assignees = assignee_emails - assignee_emails_in_acs
        if missing_clearances:
            logger.info(
                "These clearances could not be found and could not be assigned/revoked: "
                f"{', '.join(map(str, missing_clearances))}"
            )
        if missing_assignees:
            logger.info(
                "These people could not be found, and their clearances have not "
                f"been assigned/revoked: {', '.join(missing_assignees)}"
            )

        return {
            "succeeded": succeeded_actions,
            "failed": failed_actions,
            "already_completed": already_done_actions,
            "pending": [
                {
                    "assigner_email": action.get("assigner_email"),
                    "assignee_email": action.get("assignee_email"),
                    "clearance_id": action.get("clearance_id"),
                    "action": action.get("action"),
                    "action_time": action.get("action_time"),
                }
                for action in new_actions
            ],
        }

    @staticmethod
    def bulk_schedule_actions(action_configs: list[ActionConfig]):
        """Add actions from the bulk scheduler to the scheduled_action collection"""
        now = datetime.now(timezone.utc)
        scheduled_action_coll = get_clearance_collection("scheduled_action")
        new_actions = [
            {
                "assigner_email": config.assigner_email,
                "assigner_name": config.assigner_name,
                "assignee_email": config.assignee_email,
                "clearance_id": config.clearance_id,
                "action": config.action,
                "action_time": config.action_time,
                "submitted_time": now,
                "status": "pending",
            }
            for config in action_configs
        ]
        response = scheduled_action_coll.insert_many(new_actions)
        return response.acknowledged
