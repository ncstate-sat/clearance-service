get-backup:
	mongodump -u ${REMOTE_MONGO_USER} -p ${REMOTE_MONGO_PASSWORD} --uri="mongodb://vm-vrb-mdb-01.ehps.ncsu.edu/clearance_service?authSource=clearance_service" -o ./remotedb.dump

restore-local:
	mongorestore -u ${LOCAL_MONGO_USER} -p ${LOCAL_MONGO_PASSWORD} --port=${LOCAL_MONGO_PORT} --uri="mongodb://127.0.0.1/clearance_service?authSource=clearance_service" --dir=./remotedb.dump/clearance_service/

remote-mongo:
	mongosh -u ${REMOTE_MONGO_USER} -p ${REMOTE_MONGO_PASSWORD} --authenticationDatabase=clearance_service "mongodb://vm-vrb-mdb-01.ehps.ncsu.edu/clearance_service?authSource=clearance_service"

local-mongo:
	mongosh ${CLEARANCE_DB_URL}

refresh-db:
	docker-compose down
	docker volume rm clearance-service-mirror_mongo
	docker volume rm clearance-service-mirror_mongo-test

run-dev:
	docker-compose stop
	docker-compose up -d --remove-orphans
	uvicorn main:app --reload


update_requirements:
	pip install -U -q pip-tools
	pip-compile --generate-hashes -o requirements/base/base.txt pyproject.toml
	pip-compile --generate-hashes --extra dev -o requirements/dev/dev.txt pyproject.toml

install_dev:
	@echo 'Installing pip-tools...'
	export PIP_REQUIRE_VIRTUALENV=true; \
	pip install -U -q pip-tools
	@echo 'Installing requirements...'
	pip-sync requirements/base/base.txt requirements/dev/dev.txt

setup:
	@echo 'Setting up the environment...'
	pip config --site set site.extra-index-url https://pypi.ehps.ncsu.edu/
	make install_dev
