get-backup:
	mongodump -u ${REMOTE_MONGO_USER} -p ${REMOTE_MONGO_PASSWORD} --uri="mongodb://vm-vrb-mdb-01.ehps.ncsu.edu/clearance_service?authSource=clearance_service" -o ./remotedb.dump

restore-local:
	mongorestore -u ${LOCAL_MONGO_USER} -p ${LOCAL_MONGO_PASSWORD} --port=${LOCAL_MONGO_PORT} --uri="mongodb://127.0.0.1/clearance_service?authSource=clearance_service" --dir=./remotedb.dump/clearance_service/