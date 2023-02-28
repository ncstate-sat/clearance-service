"""Pydantic types"""

from typing import Optional
from pydantic import BaseModel


class AssignRevokeConfig(BaseModel):
    """For Ccure assign_clearances and revoke_clearances methods"""
    assignee_id: str
    assigner_id: str
    clearance_guid: str
    message: Optional[str]
    activate: Optional[str]
