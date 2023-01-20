"""A module for mocking responses."""


class MockResponse:
    """Mock a response object."""

    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Returns the response data."""
        return self.json_data
