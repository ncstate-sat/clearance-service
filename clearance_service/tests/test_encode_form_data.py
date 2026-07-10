"""Test for the encode util function"""

from clearance_service.util.encode_form_data import encode


def test_encode_valid_datatypes():
    """
    It should return encoded value for valid datatype.
    """
    valid_data = {
        "type": ("Software"),
        "ID": 123,
        "Children": [
            {
                "PropertyNames": ["PersonnelID", "ClearanceID"],
                "PropertyValues": [123, "1a"],
                "AnotherThing": 5,
            },
            "ClearanceA",
            "ClearanceB",
        ],
    }
    assert encode(valid_data) == (
        "type=Software&ID=123&Children[0][PropertyNames][]=PersonnelID"
        "&Children[0][PropertyNames][]=ClearanceID&Children[0][PropertyValues][]=123"
        "&Children[0][PropertyValues][]=1a&Children[0][AnotherThing]=5"
        "&Children[]=ClearanceA&Children[]=ClearanceB"
    )


def test_encode_invalid_datatypes():
    """
    It should return empty value for invalid datatype.
    The function currently supports list, int, and str as values, but not tuple, float, and bytes
    """
    invalid_data = {"type": ("a", 12, True, 45.90), "ID": 3646.90, "Children": b"Hello"}

    assert encode(invalid_data) == ""
