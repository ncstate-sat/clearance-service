db.createUser({
  user: "dev-user",
  pwd: "dev-password",
  roles: [
    {
      role: "readWrite",
      db: "clearance_service",
    },
  ],
});

db = new Mongo().getDB("clearance_service");
db.createCollection("clearance");
