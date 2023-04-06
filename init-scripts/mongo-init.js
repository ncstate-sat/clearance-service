db.createUser(
    {
        user: "dev-user",
        pwd: "dev-password",
        roles: [
            {
                role: "readWrite",
                db: "clearancedb"
            }
        ]
    }
);
