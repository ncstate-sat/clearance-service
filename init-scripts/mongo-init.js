db.createUser({
  user: "dev-user",
  pwd: "dev-password",
  roles: [
    {
      role: "dbOwner",
      db: "clearance_service",
    },
  ],
});
