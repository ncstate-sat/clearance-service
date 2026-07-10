from typing import Optional

from fastapi import Query


async def parse_list_param(
    additional_acs_properties: Optional[str] = Query(default=None),
) -> list[str]:
    """Parse a comma-separated string in a query param and return a list of strings"""
    if additional_acs_properties is None:
        return []
    return [prop.strip() for prop in additional_acs_properties.split(",") if prop.strip()]
