import acslib
from acslib.base.connection import ACSRequestException
from acslib.base.search import BooleanOperators
from acslib.ccure import PersonnelFilter, filters
from sat.logs import SATLogger


logger = SATLogger(__name__)
ccure_api = acslib.CcureAPI()


def populate_emails():
    personnel_filter = PersonnelFilter(
        lookups={"Text1": filters.RFUZZ},
        outer_bool=BooleanOperators.OR,
        display_properties=["Text1", "ObjectID", "Text14"],
    )
    try:
        missing_email_personnel = ccure_api.personnel.search(
            search_filter=personnel_filter,
            page_size=99999,
            where_clause="(Text1 LIKE ? OR Text1 LIKE ?) AND EmailAddress IS NULL",
            where_arg_list=["100%", "65%"],
        )
    except ACSRequestException as e:
        logger.info(f"Couldn't search personnel: {e}")
        return
    cids_wo_added_email = set()
    for person in missing_email_personnel:
        campus_id = person["Text1"]
        new_email = person.get("Text14") or f"{campus_id}@add_email.email"
        try:
            ccure_api.personnel.update(
                object_id=person["ObjectID"],
                update_data={"EmailAddress": new_email},
            )
        except ACSRequestException:
            cids_wo_added_email.add(campus_id)

    email_add_failures = len(cids_wo_added_email)
    logger.info(
        f"Could not add an email address for these {email_add_failures} people: " +
        ", ".join(cids_wo_added_email)
    )
    logger.info(
        f"Added email addresses to {len(missing_email_personnel) - email_add_failures} personnel"
    )


if __name__ == "__main__":
    logger.info("Starting populate_emails task...")
    populate_emails()
    logger.info("Finished populating emails.")
