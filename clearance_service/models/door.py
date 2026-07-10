class Door:
    def __init__(self, acs_id: int, name: str):
        self.id = acs_id
        self.name = name
        self.type = "door"

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)
