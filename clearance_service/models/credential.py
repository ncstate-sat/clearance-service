"""Model for a Credential"""


class Credential:
    """A card associated with a person."""

    id: int
    personnel_id: int
    disabled: bool

    def __init__(self, id: int, personnel_id: int, disabled: bool):
        self.id = id
        self.personnel_id = personnel_id
        self.disabled = disabled
