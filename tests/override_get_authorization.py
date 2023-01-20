"""
Module representing authorization middleware override for testing.
"""


def override_get_authorization():
    """
    Extracts authorization details out of the token.
    """
    return {
        'email': 'test_user@test.edu',
        'campus_id': '000101234',
        'roles': ['Admin'],
        'authorizations': {
            'root': True,
            '_read': ['Admin', 'Liaison'],
            '_write': ['Admin', 'Liaison']
        }
    }


def override_get_authorization_liaison():
    """
    Extracts authorization details out of the token.
    """
    return {
        'email': 'test_user@test.edu',
        'campus_id': '000101234',
        'roles': ['Admin'],
        'authorizations': {
            'fmi_read': True,
            'asset-mgmt_read': True,
            'clearance_read': True,
            'clearance_write': True,
            'audit_read': True,
            'clearance_assignment_read': True,
            'clearance_assignment_write': True,
            'personnel_read': True,
            'personnel_write': True,
            '_read': ['Admin', 'Liaison'],
            '_write': ['Admin', 'Liaison']
        }
    }
