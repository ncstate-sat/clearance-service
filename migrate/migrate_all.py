import acslib
from acslib.base.connection import ACSRequestException
from acslib.base.search import BooleanOperators
from acslib.ccure import PersonnelFilter, filters
from sat.logs import SATLogger

from migrate_audit import AuditMigrate
from migrate_liaison import LiaisonMigrate
from migrate_scheduled_action import ScheduledActionMigrate


logger = SATLogger(__name__)


class Migrator:

    ccure_api = acslib.CcureAPI()

    @staticmethod
    def get_all_cids() -> list[str]:
        """Get all the campus IDs that we'll need to change to emails in the collections"""
        campus_ids = set()
        campus_ids |= AuditMigrate.get_audit_cids()
        campus_ids |= ScheduledActionMigrate.get_scheduled_action_cids()
        # we don't need cids from liaison

        valid_cids = list(filter(None, campus_ids))  # filter out the falsy ones
        logger.info(f"Found {len(valid_cids)} campus IDs to map to emails.")
        return valid_cids

    @classmethod
    def map_cids_to_emails(cls, cids: list[str]) -> dict[str, str]:
        """Eg. {"001132808": "lmena@email.com", ...}"""
        personnel_filter = PersonnelFilter(
            lookups={"Text1": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=["Text1", "EmailAddress"],
        )
        results = {}
        cids_with_no_email = set()
        cids_not_in_ccure = set()
        CID_SLICE_SIZE = 500
        for start in range(0, len(cids), CID_SLICE_SIZE):
            cid_slice = cids[start:start+CID_SLICE_SIZE]
            logger.info(f"Searching IDs {start} - {start + CID_SLICE_SIZE}")
            try:
                acslib_response = cls.ccure_api.personnel.search(
                    terms=cid_slice,
                    search_filter=personnel_filter,
                    page_size=CID_SLICE_SIZE,
                )
                mapping_results = cls.make_mapping(cid_slice, acslib_response)
                results |= mapping_results["cid to email map"]
                cids_with_no_email |= mapping_results["cids with no associated email"]
                cids_not_in_ccure |= set(mapping_results["people who don't even exist in ccure at all"])
            except ACSRequestException:
                pass

        logger.info(f"Found email addresses for {len(results)} campus IDs.")
        if cids_with_no_email:
            logger.info(
                "No email address was found or could be added for these campus IDs: "
                + ", ".join(cids_with_no_email)
            )
        if cids_not_in_ccure:
            logger.info(
                f"These campus IDs were not found in ccure: {', '.join(cids_not_in_ccure)}"
            )
        return results

    @classmethod
    def make_mapping(cls, cid_slice: list[str], acs_search_results: list[dict]) -> dict:
        """Map each cid to an email address. If an email address isn't found, add one in acs"""
        cid_email_map = {person["Text1"]: person["EmailAddress"] for person in acs_search_results}
        cids_of_people_who_arent_in_ccure = list({cid for cid in cid_slice if cid not in cid_email_map})
        cids_of_people_missing_email_addresses = [k for k, v in cid_email_map.items() if not v]
        cid_email_map = {k: v for k, v in cid_email_map.items() if v}

        personnel_filter = PersonnelFilter(
            lookups={"Text1": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=["Text1", "ObjectID"],
        )
        try:
            personnel_who_are_in_ccure_but_dont_have_emails = cls.ccure_api.personnel.search(
                terms=cids_of_people_missing_email_addresses,
                search_filter=personnel_filter,
                page_size=len(cids_of_people_missing_email_addresses),
            )
        except ACSRequestException:
            return {
                "cid to email map": cid_email_map,
                "cids with no associated email": set(),
                "people who don't even exist in ccure at all": cid_slice,
            }
        cids_we_couldnt_add_an_email_address_for = set()
        for person in personnel_who_are_in_ccure_but_dont_have_emails:
            campus_id: str = person["Text1"]
            if campus_id.startswith("1"):
                email = f"{campus_id}@cmt308migration.email"
                try:
                    cls.ccure_api.personnel.update(
                        object_id=person["ObjectID"],
                        update_data={"EmailAddress": email},
                    )
                    cid_email_map[campus_id] = email
                except ACSRequestException:
                    cids_we_couldnt_add_an_email_address_for.add(campus_id)
        return {
            "cid to email map": cid_email_map,
            "cids with no associated email": cids_we_couldnt_add_an_email_address_for,
            "people who don't even exist in ccure at all": cids_of_people_who_arent_in_ccure,
        }

    @staticmethod
    def migrate_collections(cid_email_map):
        """Run the migration queries for the three collections"""
        AuditMigrate.migrate(cid_email_map)
        LiaisonMigrate.migrate()
        ScheduledActionMigrate.migrate(cid_email_map)


if __name__ == "__main__":
    logger.info("Starting migration...")
    all_cids = Migrator.get_all_cids()
    cids_to_emails = Migrator.map_cids_to_emails(all_cids)
    Migrator.migrate_collections(cids_to_emails)
    logger.info("Finished migration.")
