from auth_checker.util.authorization_roles import DEV_ROLES

ADMIN_ROLES = ["clearance:admin", "service"] + DEV_ROLES
READ_WRITE_ROLES = ["clearance:access"] + ADMIN_ROLES
READ_ROLES = ["clearance:reader"] + READ_WRITE_ROLES
