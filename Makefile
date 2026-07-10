get-backup:
	mongodump -u ${REMOTE_MONGO_USER} -p ${REMOTE_MONGO_PASSWORD} --uri=${REMOTE_BACKUP_URI} -o ./remotedb-dump

restore-local:
	mongorestore -u ${LOCAL_MONGO_USER} -p ${LOCAL_MONGO_PASSWORD} --port=${LOCAL_MONGO_PORT} --uri="mongodb://127.0.0.1/clearance_service?authSource=clearance_service" --dir=./remotedb-dump/clearance_service/

remote-mongo:
	mongosh -u ${REMOTE_MONGO_USER} -p ${REMOTE_MONGO_PASSWORD} --authenticationDatabase=clearance_service ${REMOTE_MONGO_URI}

local-mongo:
	mongosh ${CLEARANCE_DB_URL}

refresh-db:
	docker compose down
	docker volume rm clearance-service-mirror_mongo
	docker compose up -d --remove-orphans
	sleep 2
	make restore-local

run-dev:
	docker compose stop
	docker compose up -d --remove-orphans
	uvicorn main:app --reload --port 8005

run-db:
	docker compose up -d --remove-orphans

update-requirements:
	pip install -U -q pip-tools
	pip-compile --resolver=backtracking -o requirements/base/base.txt pyproject.toml
	pip-compile --resolver=backtracking --extra dev -o requirements/dev/dev.txt pyproject.toml

install-dev:
	@echo 'Installing pip-tools...'
	export PIP_REQUIRE_VIRTUALENV=true; \
	pip install -U -q pip-tools
	@echo 'Installing requirements...'
	pip-sync requirements/base/base.txt requirements/dev/dev.txt

run-tests:
	@echo 'Running tests...'
	docker compose up -d test-db
	pytest
	docker compose down test-db

lab:
	@echo 'Starting Jupyter Lab...'
	jupyter lab

setup:
	@echo 'Setting up the environment...'
	make install-dev
