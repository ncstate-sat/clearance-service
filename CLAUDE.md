# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Backend service (FastAPI) for the Clearance Tool, which manages physical door-access "clearances" for NCSU. It's a
middle layer between:
- **CCure (ACS)**: the real access-control system, accessed via the `acslib` package (`acslib.CcureAPI()`), for
  clearances, doors, clearance items, and other CCure objects. Most domain data (clearances, doors) actually lives
  in CCure, not in this service's own database.
- **MongoDB** (`clearance_service` database): stores everything CCure doesn't — liaison permissions, audit log,
  scheduled actions, spaces, space schedules.

Users are either **Admins** (full access) or **Liaisons** (scoped to a set of clearances they're permitted to
assign/revoke, tracked in the `liaison` collection).

## Commands

```shell
make setup              # install-dev: pip-tools + pip-sync requirements/{base,dev}.txt
make run-db              # start local Mongo via docker compose (no app)
make run-dev             # stop compose, restart db, run `uvicorn main:app --reload --port 8005`
make run-tests           # start test-db, run `pytest`, stop test-db
make update-requirements # pip-compile pyproject.toml -> requirements/base/base.txt and requirements/dev/dev.txt
make refresh-db          # wipe local mongo volume and restore from ./remotedb-dump
make get-backup          # mongodump from TEST into ./remotedb-dump
make restore-local       # mongorestore ./remotedb-dump into local db
```

Dependencies are declared in `pyproject.toml` ( `[project]` = runtime, `[project.optional-dependencies].dev` = dev)
and compiled to `requirements/base/base.txt` / `requirements/dev/dev.txt` via `make update-requirements`. Edit
`pyproject.toml`, never the requirements txt files directly.

### Tests

Tests need a running Mongo test instance (`docker compose up -d test-db`, URL from `TEST_DB_URL`); `make run-tests`
handles this. To run directly:

```shell
docker compose up -d test-db
pytest                                                    # full suite (see pytest.ini: testpaths, coverage gate)
pytest clearance_service/tests/test_spaces_controller.py  # single file
pytest clearance_service/tests/test_spaces_controller.py::test_name -vvv  # single test
docker compose down test-db
```

Coverage is enforced at 60% (`--cov-fail-under=60` in `pytest.ini`) and reports to `.coveragerc` config (source =
`clearance_service`). `clearance_service/tests/conftest.py` provides DB fixtures (`db`, `dbp` — seeds Mongo
collections with fixture data) and `fake_auth` (monkeypatches `AuthChecker.__call__` to bypass real JWT permission
checks in tests). `clearance_service/tests/override_get_authorization.py` provides `override_get_authorization_admin`
/ `_liaison`, used via `app.dependency_overrides[get_authorization]` to inject a fake `TokenPayload` for a given
test.

### Linting / formatting

Enforced via pre-commit (`pre-commit install` once, then runs on `git commit`): `black` (line-length 100),
`ruff --fix`, `pyupgrade`, `bandit` (`-c bandit.yml`), plus standard hygiene hooks. Run manually with
`pre-commit run --all-files`. `mypy --strict` is configured in `pyproject.toml` but not wired into pre-commit.

## Architecture

Three-layer structure under `clearance_service/`:

- **`crud/`** — FastAPI routers (one per resource: `assignments`, `audit`, `clearances`, `doors`, `liaison`,
  `personnel`, `reports`, `spaces`, `space_schedules`). Each exposes a `router` that `main.py` mounts under a
  prefix (e.g. `clearances_router` → `/clearances`). Route handlers do auth/permission branching and call into
  `models/`; they should stay thin.
- **`models/`** — domain classes (`Clearance`, `Personnel`, `ScheduledAction`, `Space`, etc.) with the actual query
  logic, as static/class methods rather than ORM-style instances tied to a single collection. Some talk to CCure
  via the shared `acs` object, others to Mongo via `get_clearance_collection(...)`, many do both.
- **`util/`** — cross-cutting helpers: auth (`authorization.py`, `authorization_roles.py`), Mongo connection
  (`db_connect.py`), outbound HTTP handling (`handle_requests.py`), config (`settings.py`), the background
  scheduler (`scheduler_framework.py`, `scheduler_service.py`).

`clearance_service/models/__init__.py` creates the single shared CCure connection (`acs = acslib.CcureAPI()`) and
`filters = acslib.ccure.filters` that model modules import from `clearance_service.models`. It requires
`ACS_SYSTEM=ccure` in the environment — if unset or anything else, import raises `OSError`, so nothing in this
module tree can be imported (including in tests) without that env var set.

### Auth

`get_authorization` (`util/authorization.py`) decodes a JWT from the `Authorization` header into an `auth_checker`
`TokenPayload` (`email`, `roles`, `inherited_roles`, `permissions`) — **signature verification is disabled**, since
actual verification happens upstream. Route-level access control is layered:
- `Depends(AuthChecker(*required_permissions))` on the route enforces that the token's `permissions` list contains
  every permission string passed in. Permission strings live in `PERMISSIONS` (`util/authorization_roles.py`), a
  dict keyed by names like `CLEARANCE_ASSIGNMENTS_READ` / `CLEARANCE_ASSIGNMENTS_WRITE` mapping to the actual
  `"clearance-<domain>:<read|write>"` strings issued by the Auth Service — always reference permissions through
  this dict (e.g. `AuthChecker(PERMISSIONS["CLEARANCE_ASSIGNMENTS_WRITE"])`), never as bare strings. There is no
  role-based tier here (the old `READ_ROLES` / `READ_WRITE_ROLES` / `ADMIN_ROLES` cumulative-role scheme is gone).
- Inside the handler, `user_is_admin(account.roles)` checks the token's `roles` against `SAT_INTERNAL_ROLES`
  (`util/authorization_roles.py`) and typically branches between an "admin" code path (unrestricted CCure access)
  and a "liaison" code path (scoped to what's recorded for that email in the `liaison` Mongo collection). This is
  a separate concern from the permission-based route gating above — a request can pass the `AuthChecker` dependency
  without being admin, and `user_is_admin` is never used to gate route access on its own.

### Scheduler

`ServiceScheduler` (`util/scheduler_framework.py`) is started from `main.py`'s startup event, unless `DEVELOPMENT`
is truthy (default true in `envrc_example` — must be unset/false to exercise scheduler behavior locally). It uses
APScheduler cron jobs (`daily_jobs`, `hourly_jobs`, `one_minute_jobs`, `keep_alive`) that call into
`SchedulerService` (`util/scheduler_service.py`) to push due `scheduled_action` documents to CCure, purge old
scheduled actions, refresh cached liaison clearance names, and keep the CCure session alive.

### Requests to CCure / other remote calls

`util/handle_requests.py`'s `handle_request(requests_method, RequestData(...))` wraps `requests` calls, normalizing
every failure mode (timeouts, connection errors, HTTP errors, non-2xx status) into a single `RequestException`
with `status_code` and `message`. Route handlers generally catch `RequestException` and set `response.status_code`
rather than letting FastAPI raise a 500.

### Mongo access pattern

There's no ODM — `util/db_connect.get_clearance_collection(name)` opens a fresh `MongoClient` per call (using
`CLEARANCE_DB_URL`) and returns a raw pymongo collection. Query logic (including aggregation pipelines) lives
directly in the relevant model's methods, e.g. `Clearance.get_allowed`, `SchedulerService.get_scheduled_actions`.

### Env vars

Configuration is read via `os.getenv` in `util/settings.py`, `util/db_connect.py`, `util/authorization.py`, and
`clearance_service/models/__init__.py`. See `envrc_example` for the full list (Mongo URLs, JWT secret, CCure
credentials, scheduler toggles). `DEVELOPMENT=True` (the default) disables the background scheduler.

## Notes

- User-facing docs live in `docs/` (mkdocs) and are published to a *different* public repo's `gh-pages` branch —
  see the "User Guide" section of `README.md` for the manual `mkdocs gh-deploy` + cross-repo push process.
- `migrate/` contains one-off data migration scripts (not part of the app's runtime).
