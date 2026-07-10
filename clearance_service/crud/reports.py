"""Controller functions for usage reports"""
import csv
import io
from datetime import datetime, timezone

from acslib.base.search import BooleanOperators
from acslib.ccure.base import CcureACS
from acslib.ccure.types import ObjectType
from auth_checker.models.models import Account
from auth_checker.models.models import TokenAuthorizer as AuthChecker
from clearance_service.models import acs, filters
from clearance_service.models.audit import Audit
from clearance_service.models.clearance import Clearance
from clearance_service.util.authorization import get_authorization
from clearance_service.util.authorization_roles import READ_ROLES
from clearance_service.util.parse_list_param import parse_list_param
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get(
    "/usage/monthly-by-user",
    tags=["Reports"],
    dependencies=[Depends(AuthChecker(READ_ROLES))],
    response_class=StreamingResponse,
)
async def get_liaisons_csv():
    """
    Get total clearances assigned or revoked by each user of the clearance tool, as a csv.
    Each user has twelve rows, one for each of the last twelve full calendar months.
    """
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)
    monthly_data = Audit.get_monthly_report()
    UsageReport.header(csv_writer)
    for record in monthly_data:
        usage_report = UsageReport(record)
        usage_report.body(csv_writer)
    response = StreamingResponse(iter([csv_buffer.getvalue()]), media_type="text/csv")
    csv_buffer.close()
    response.headers["Content-Disposition"] = "attachment; filename=monthly-report.csv"
    return response


class UsageReport:
    """Helper for monthly-by-user endpoint"""

    month_map = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }
    date_range = None

    def __init__(self, assignment: dict) -> None:
        self.assigner = assignment["_id"]["assigner"]
        self.email = assignment["_id"]["assigner_email"]
        self.assignments = assignment["monthly_assignments"]
        self.date_range = self.date_range or self.build_date_range()

    @classmethod
    def build_date_range(cls):
        """Set cls.date_range to a list of (month, year) tuples. eg. (11, 2004)"""
        date_range = []
        now = datetime.now(timezone.utc)
        year = now.year - 1
        month = now.month
        for _ in range(12):
            date_range.append((month, year))
            month += 1
            if month > 12:
                month = 1
                year += 1
        cls.date_range = date_range
        return date_range

    @property
    def normal_assigner(self) -> str:
        """Normalized assigner name"""
        return self.assigner or "Unknown Liaison"

    @staticmethod
    def header(csv_writer: csv.writer) -> None:
        """Write the first row of the csv"""
        csv_writer.writerow(["Liaison", "Liaison Email", "Month", "Year", "Assignments"])

    def get_liaison_data_for_month(self, month: int, year: int) -> dict:
        """Get a liaison's data for the given month"""
        for assignment in self.assignments:
            if assignment["year"] == year and assignment["month"] == month:
                return assignment
        return {"month": month, "year": year, "assignments": 0}

    def body(self, csv_writer: csv.writer) -> None:
        """Write 12 rows for a given liaison"""
        for month, year in self.date_range:
            assignment = self.get_liaison_data_for_month(month, year)
            csv_writer.writerow(
                [
                    self.normal_assigner,
                    self.email,
                    self.month_map[assignment["month"]],
                    assignment["year"],
                    assignment["assignments"],
                ]
            )


@router.get(
    "/clearances/persons",
    tags=["Reports"],
    dependencies=[Depends(AuthChecker(READ_ROLES))],
)
def get_clearance_assignee_report(
    response: Response,
    account: Account = Depends(get_authorization),
    clearances_skip: int = 0,
    clearances_limit: int = 10,
    assignees_page: int = 1,
    assignees_page_size: int = 3,
    clearance_id: int = 0,
    assignee_name: str = "",
    additional_acs_properties: list[str] = Depends(parse_list_param),
):
    """
    Get a report of all personnel assigned to a liaison's assignable clearances.

    By default, the report will show only up to ten clearances and three assignees per clearance.
    Querying with a `clearance_id` value will limit the report to the one specified clearance.

    Parameters:
        clearances_skip: number of clearances to skip in the report
        clearances_limit: maximum number of clearances to include in the response
        assignees_page: for a given clearance, the page of assignees to include. starts at page 1.
        assignees_page_size: number of assignees to include for each clearance
        clearance_id: if an ID is given, only return results for this clearance
        assignee_name: if given, only include assignees whose names include this substring
        additional_acs_properties: a list of optional additional properties to display
            for each assignee. First and last name are shown by default
    """
    if assignees_page > 1 and not clearance_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Clearance ID must be specified"}
    assigner_email = account.get_email

    # Get this user's allowed clearances
    all_allowed_clearances = Clearance.get_allowed(email=assigner_email)
    if not all_allowed_clearances:
        return {
            "total_clearances": 0,
            "clearances": {},
        }

    # Clearances for this page (out of all allowed clearances)
    allowed_clearances = all_allowed_clearances[
        clearances_skip : clearances_skip + clearances_limit
    ]
    clearances_count = len(all_allowed_clearances)

    # Get Clearance/Personnel relationships
    if clearance_id:
        allowed_clearances = [
            clearance for clearance in allowed_clearances if clearance.id == clearance_id
        ]
        if not allowed_clearances:
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"detail": "You can't generate a report for this clearance."}

        clearance_pairs = acs.action.clearance.get_assignees(
            clearance_id, page_size=assignees_page_size, page_number=assignees_page
        )

    else:
        allowed_clearance_ids = sorted([clearance.id for clearance in allowed_clearances])
        clearance_pairs = CcureACS(acs.connection).search(
            object_type=ObjectType.CLEARANCE_ASSIGNMENT.complete,
            search_filter=filters.CcureFilter(),
            where_clause=" OR ".join(f"ClearanceID = {_id}" for _id in allowed_clearance_ids),
            page_size=99999,
        )

    # Get clearance names for this page
    clearance_names = {clearance.id: clearance.name for clearance in allowed_clearances}

    # Set up a dictionary for assignees of a clearance
    clearance_assignees = {
        clearance_names[_id]: {
            "clearance_id": _id,
            "assignee_count": 0,
            "assignee_acs_ids": [],
        }
        for _id in clearance_names
    }

    clearance_pairs_this_page = [
        d for d in clearance_pairs if d.get("ClearanceID") in clearance_names
    ]
    for pair in clearance_pairs_this_page:
        clearance = clearance_assignees[clearance_names[pair["ClearanceID"]]]
        clearance["assignee_count"] += 1
        clearance["assignee_acs_ids"].append(pair["PersonnelID"])

    all_assignee_emails = set()
    for clearance in clearance_assignees.values():
        if not clearance_id:
            clearance["assignee_acs_ids"] = clearance["assignee_acs_ids"][
                (assignees_page - 1) * assignees_page_size : assignees_page * assignees_page_size
            ]
        for assignee_acs_id in clearance["assignee_acs_ids"]:
            all_assignee_emails.add(assignee_acs_id)

    personnel_filter = filters.PersonnelFilter(
        display_properties=["FirstName", "LastName"] + additional_acs_properties
    )
    where_clause = " OR ".join(f"ObjectID = {email}" for email in all_assignee_emails)
    if assignee_name:
        assignee_names = assignee_name.split()
        name_filter = " AND ".join(
            f"(FirstName LIKE '%{name}%' OR LastName LIKE '%{name}%')" for name in assignee_names
        )
        where_clause = f"({where_clause}) AND {name_filter}"
    assignees = acs.personnel.search(
        search_filter=personnel_filter, timeout=30, where_clause=where_clause, page_size=99999
    )
    assignees_by_acs_id = {
        assignee["ObjectID"]: {
            "first": assignee["FirstName"],
            "last": assignee["LastName"],
        } | {prop: assignee[prop] for prop in additional_acs_properties}
        for assignee in assignees
    }
    if clearance_id:
        return {
            "total_clearances": clearances_count,
            "clearances": {
                clearance_name: {
                    "clearance_id": clearance_data["clearance_id"],
                    "assignees": [
                        assignees_by_acs_id[assignee_acs_id]
                        for assignee_acs_id in clearance_data["assignee_acs_ids"]
                        if assignee_acs_id in assignees_by_acs_id
                    ],
                }
                for clearance_name, clearance_data in clearance_assignees.items()
            },
        }
    return {
        "total_clearances": clearances_count,
        "clearances": {
            clearance_name: {
                "clearance_id": clearance_data["clearance_id"],
                "assignee_count": clearance_data["assignee_count"],
                "assignees": [
                    assignees_by_acs_id[assignee_acs_id]
                    for assignee_acs_id in clearance_data["assignee_acs_ids"]
                    if assignee_acs_id in assignees_by_acs_id
                ],
            }
            for clearance_name, clearance_data in clearance_assignees.items()
        },
    }


@router.get("/clearances/doors", tags=["Reports"], dependencies=[Depends(AuthChecker(READ_ROLES))])
def get_clearance_door_report(
    response: Response,
    account: Account = Depends(get_authorization),
    clearances_skip: int = 0,
    clearances_limit: int = 10,
    clearance_id: int = 0,
    door_ids: str = "",
    elevator_ids: str = "",
    limit_doors_per_clearance: bool = True,
):
    """
    Get a report of all doors tied to a liaison's assignable clearances.
    By default, the report will show up to ten clearances.
    Shows three doors per clearance.
    Querying with a `clearance_id` value will limit the report to the one specified clearance.

    Parameters:
        clearances_skip: number of clearances to skip in the report
        clearances_limit: maximum number of clearances to include in the response
        clearance_id: if an ID is given, only return results for this clearance
        door_ids: one or more DoorID values for filtering clearances
        elevator_ids: one or more ElevatorID values for filtering clearances
    """
    door_ids = [int(door_id) for door_id in filter(None, door_ids.split(","))]
    elevator_ids = [int(elevator_id) for elevator_id in filter(None, elevator_ids.split(","))]

    # Get clearances allowed to be assigned by this person
    assigner_email = account.get_email
    allowed_clearances = Clearance.get_allowed(email=assigner_email)
    if not allowed_clearances:
        return {"total_clearances": 0, "clearances": {}}

    # If we're only getting doors for one clearance, get doors for just the one clearance
    if clearance_id:
        allowed_clearances = [
            clearance for clearance in allowed_clearances if clearance.id == clearance_id
        ]
        if not allowed_clearances:
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"detail": "You can't generate a report for this clearance."}
        clearance_item_filter = filters.ClearanceItemFilter(
            lookups={"ClearanceID": filters.NFUZZ},
            display_properties=[
                "ClearanceID",
                "DoorID",
                "ElevatorID",
                "ScheduleID",
                "DoorGroupID",
                "ElevatorGroupID",
            ],
        )
        clearance_items = acs.clearance_item.search(
            terms=[clearance_id], search_filter=clearance_item_filter, timeout=35, page_size=99999
        )

    # Get doors for all clearances which this person can assign
    else:
        allowed_clearance_ids = sorted([clearance.id for clearance in allowed_clearances])[
            clearances_skip : clearances_skip + clearances_limit
        ]
        clearance_item_filter = filters.ClearanceItemFilter(
            lookups={"ClearanceID": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=[
                "ClearanceID",
                "DoorID",
                "ElevatorID",
                "ScheduleID",
                "DoorGroupID",
                "ElevatorGroupID",
            ],
        )
        clearance_items = acs.clearance_item.search(
            terms=allowed_clearance_ids,
            search_filter=clearance_item_filter,
            timeout=35,
            page_size=99999,
        )

    # Extract item specific ACS ids from clearance items
    door_clearance_item_ids = [
        clearance_item["DoorID"] for clearance_item in clearance_items if clearance_item["DoorID"]
    ]
    elevator_clearance_item_ids = [
        clearance_item["ElevatorID"]
        for clearance_item in clearance_items
        if clearance_item["ElevatorID"]
    ]

    door_group_clearance_items = [
        clearance_item for clearance_item in clearance_items if clearance_item.get("DoorGroupID")
    ]
    elevator_group_clearance_items = [
        clearance_item
        for clearance_item in clearance_items
        if clearance_item.get("ElevatorGroupID")
    ]

    # Get all schedules
    schedules = acs.ccure_object.search(
        object_type=ObjectType.TIME_SPEC.complete,
        search_filter=filters.CcureFilter(display_properties=["ObjectID", "Name"]),
        terms=[],
        timeout=35,
        page_size=99999,
    )
    schedules_by_id = {schedule["ObjectID"]: schedule["Name"] for schedule in schedules}

    door_group_ids = [item["DoorGroupID"] for item in door_group_clearance_items]
    door_group_ids_map = {
        item["DoorGroupID"]: item["ClearanceID"] for item in door_group_clearance_items
    }

    group_members_filter = filters.GroupMemberFilter(
        lookups={"GroupID": filters.NFUZZ},
        outer_bool=BooleanOperators.OR,
        display_properties=["TargetObjectID", "GroupID"],
    )

    # Get door group members
    # Only run the query if group id list isn't empty;
    # the query returns every door if the list is empty
    if door_group_ids:
        door_group_members = acs.group_member.search(
            terms=door_group_ids,
            search_filter=group_members_filter,
            page_size=99999,
            page_number=1,
            timeout=35,
        )
        # Add door group member ids to clearance item door ids
        door_group_ids = [member["TargetObjectID"] for member in door_group_members]
        total_door_ids = list(set(door_clearance_item_ids + door_group_ids))
        member_door_clearance_items = [
            {
                "ClearanceID": door_group_ids_map[group_member["GroupID"]],
                "ObjectID": None,
                "DoorID": group_member["TargetObjectID"],
                "DoorGoupID": None,
                "ElevatorID": None,
                "ElevatorGroupID": None,
            }
            for group_member in door_group_members
        ]
    else:
        member_door_clearance_items = []
        total_door_ids = list(set(door_clearance_item_ids))

    clearance_items += member_door_clearance_items

    # Get elevator groups
    elevator_group_ids = [item["ElevatorGroupID"] for item in elevator_group_clearance_items]
    elevator_group_ids_map = {
        item["ElevatorGroupID"]: item["ClearanceID"] for item in elevator_group_clearance_items
    }

    # Get elevator group members
    # Have to use an if statement here because a query with an empty list returns every elevator
    if elevator_group_ids:
        elevator_group_members = acs.group_member.search(
            terms=elevator_group_ids,
            search_filter=group_members_filter,
            page_size=99999,
            page_number=1,
        )
        # Add elevator group member ids to clearance item elevator ids
        elevator_group_member_ids = [member["TargetObjectID"] for member in elevator_group_members]
        total_elevator_ids = list(set(elevator_clearance_item_ids + elevator_group_member_ids))

        # Create clearance item entries for the group members
        member_elevator_clearance_items = [
            {
                "ClearanceID": elevator_group_ids_map[group_member["GroupID"]],
                "ObjectID": None,
                "DoorID": None,
                "DoorGoupID": None,
                "ElevatorID": group_member["TargetObjectID"],
                "ElevatorGroupID": None,
            }
            for group_member in elevator_group_members
        ]
    else:
        member_elevator_clearance_items = []
        total_elevator_ids = list(set(elevator_clearance_item_ids))

    clearance_items += member_elevator_clearance_items

    # Get clearance-item mappings for all clearances
    door_filter = filters.ClearanceItemFilter(
        lookups={"ObjectID": filters.NFUZZ},
        outer_bool=BooleanOperators.OR,
        display_properties=["ObjectID", "Name"],
    )
    door_items = (
        acs.ccure_object.search(
            object_type=ObjectType.DOOR.complete,
            terms=total_door_ids,
            search_filter=door_filter,
            page_size=99999,
        )
        if total_door_ids
        else []
    )

    elevator_filter = filters.ClearanceItemFilter(
        lookups={"ObjectID": filters.NFUZZ},
        outer_bool=BooleanOperators.OR,
        display_properties=["ObjectID", "Name"],
    )
    elevator_items = (
        acs.ccure_object.search(
            object_type=ObjectType.ELEVATOR.complete,
            terms=total_elevator_ids,
            search_filter=elevator_filter,
            page_size=99999,
        )
        if total_elevator_ids
        else []
    )

    doors_by_id = {item["ObjectID"]: item["Name"] for item in door_items}
    elevators_by_id = {item["ObjectID"]: item["Name"] for item in elevator_items}

    # Combine data into a response
    items_by_clearance = {}
    filtered_clearances_by_door = {}
    clearance_names = {clearance.id: clearance.name for clearance in allowed_clearances}

    # Filter out DoorGroup and ElevatorGroup clearance items
    clearance_items = [
        clearance_item
        for clearance_item in clearance_items
        if (not clearance_item.get("ElevatorGroupID") and not clearance_item.get("DoorGroupID"))
    ]

    for item in clearance_items:
        clearance_name = clearance_names.get(item["ClearanceID"])

        # get the name of the door by door id
        new_item = {
            "id": item.get("ObjectID", None),
            "door_id": item.get("DoorID", None),
            "elevator_id": item.get("ElevatorID", None),
            "name": doors_by_id.get(
                item.get("DoorID", None), elevators_by_id.get(item.get("ElevatorID", None), None)
            ),
            "schedule_name": schedules_by_id.get(item.get("ScheduleID", None), None),
            "is_elevator": bool(item.get("ElevatorID")),
        }

        # identify which clearances have this door
        if new_item["door_id"] is not None:
            filtered_clearances_by_door[clearance_name] = True
        if new_item["elevator_id"] is not None:
            filtered_clearances_by_door[clearance_name] = True

        if items_by_clearance.get(clearance_name) is not None:
            if (
                limit_doors_per_clearance
                and not clearance_id
                and items_by_clearance.get(clearance_name, {}).get("door_count", 3) >= 3
            ):
                continue
            if new_item["door_id"] is not None or new_item["elevator_id"] is not None:
                if items_by_clearance[clearance_name].get("door_count"):
                    items_by_clearance[clearance_name]["door_count"] += 1
                else:
                    items_by_clearance[clearance_name]["door_count"] = 1
                items_by_clearance[clearance_name]["doors"].append(new_item)
        else:
            if new_item["door_id"] is not None or new_item["elevator_id"] is not None:
                items_by_clearance[clearance_name] = {
                    "clearance_id": item.get("ClearanceID", None),
                    "door_count": 1,
                    "doors": [new_item],
                }
            else:
                items_by_clearance[clearance_name] = {
                    "clearance_id": item.get("ClearanceID", None),
                    "door_count": 0,
                    "doors": [],
                }

    items_by_clearance = {
        key: value
        for key, value in items_by_clearance.items()
        if key in filtered_clearances_by_door
    }

    return {"total_clearances": len(items_by_clearance), "clearances": items_by_clearance}


@router.get("/search-items", tags=["Reports"], dependencies=[Depends(AuthChecker(READ_ROLES))])
def search_items(response: Response, search: str = "", doors_only: bool = True) -> list[dict]:
    """
    Search for clearance items by name. Returns doors by default, optionally include elevators

    Parameters:
        search: a fuzzy search string. Only include results whose names include this value
        doors_only: only search doors. set to False, in order to include elevators
    """
    door_response = acs.ccure_object.search(
        object_type=ObjectType.DOOR.complete,
        terms=search.split(),
        search_filter=filters.ClearanceItemFilter(display_properties=["Name", "ObjectID"]),
        page_size=99999,
    )
    all_items = [
        {
            "item_type": "Door",
            "item_id": item["ObjectID"],
            "name": item["Name"],
        }
        for item in door_response
    ]

    if not doors_only:
        elevator_response = acs.ccure_object.search(
            object_type=ObjectType.ELEVATOR.complete,
            terms=search.split(),
            search_filter=filters.ClearanceItemFilter(display_properties=["Name", "ObjectID"]),
            page_size=99999,
        )
        all_items.extend(
            [
                {
                    "item_type": "Elevator",
                    "item_id": item["ObjectID"],
                    "name": item["Name"],
                }
                for item in elevator_response
            ]
        )
    return all_items
