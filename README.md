# Clearance Service

Backend service for Clearance-app functionality.

## System Requirements

- Python 3.10
- MongoDB 4.4
- make
- mongo-tools
- mongosh
- Docker :(optional)
- pyenv (optional)
- direnv 2.3.2 (optional)
- nix-shell (optional)

## Dev Setup

Development environments are highly personal and can be configured in many different ways.
This project is designed around [direnv](https://direnv.net/), [pyenv](https://github.com/pyenv/pyenv),
and [nix-shell](https://nixos.org/manual/nix/stable/#description-1) to provide a consistent development environment for all developers.
If you don't want to use these tools, you can still use this project, but you'll need to manage the things they do for you manually.

### Install pyenv

[Install instructions](https://github.com/pyenv/pyenv#getting-pyenv) for pyenv. There are a lot of options here,
for most people the [pyenv-installer](https://github.com/pyenv/pyenv-installer) is the easiest way to get started.

```shell
    $> curl https://pyenv.run | bash
```

#### Install Python 3.10.4

```shell
    $> pyenv install 3.10.4
```

### Install direnv

For most things you won't need to install system packages, but direnv operates best as a system package.

**Important**
Follow all the instructions [here](https://direnv.net/docs/installation.html) to install direnv on your system.

### Install Nix

To install nix, run the following command:

```shell
  $> sh <(curl -L https://nixos.org/nix/install) --no-daemon
```

NOTE: Darwin/MacOS does not support the `--no-daemon` flag, so if you are on a Mac, omit the flag.

The primary role for nix-shell is to provide access to `mongo-tools` and `mongosh`. If you don't want to use nix-shell, you can install `mongo-tools` and `mongosh` manually.

### Required Environment Variables

If you are using `direnv` then copy the `envrc_example` file to `.envrc` and fill in the missing values. Ask in `dev-support` if
you do not have access to some of the values.

```shell
    $> cp envrc_example .envrc
    # Fill in the missing values, then
    $> direnv allow
```

This will create and activate a python 3.10.4 virtual environment located in your project directory at `./.direnv`,
and set the environment variables required to run the application.

If you are not using `direnv` then you will need to activate your venv and set the environment variables manually. Refer to the `envrc_example` file for the required variables.

NOTE: The default environment variables have `DEVELOPMENT=True`, which stops the application from spinning
up the service scheduler. If you need to develop against the scheduler, comment out the DEBUG in the `.envrc`.

### Install Requirements

If this is the first time you have set up this project in a virtual environment, run the following command to install the requirements:

```shell
  $> make setup
```

#### Updating Requirements

This project uses `pip-tools` to manage requirements. To update the requirements add your requirement
to the `pyproject.toml` file.

For dependencies required to run the app in production, add them to the `pyproject.toml` file under the `[project]` section.
These dependencies should be pinned to a specific version.

```toml
[project]
name = "clearance-service"
version = "0.1.0"
dependencies = [
    "fastapi==0.95.1",
    "apscheduler==3.10.1",
    "...",
    "<YOUR NEW REQUIREMENT HERE>",
    "...",
]
```

For developer dependencies required or nice to have for development, add them to the `pyproject.toml` file under the `[project.optional-dependencies]` section.
These dependencies can have a range of versions, since they are not critical to the running of the application.

```toml
[project.optional-dependencies]
dev = [
    "pytest>=6.2.5, <7.0.0",
    "pytest-mock>=3.10.0, <4.0.0",
    "pytest-cov>=4.0.0, <5.0.0",
    "...",
    "<YOUR NEW DEV REQUIREMENT HERE>",
    "...",
]
```

Then run the following command to update the `requirements/base/base.txt` and `requirements/dev/dev.txt` files.

```shell
    $> make update-requirements
```

### Install Pre-Commit

Automated code quality is enforced with [pre-commit](https://pre-commit.com/). To install pre-commit, run the following command:

```shell
  $> pre-commit install
```

Now when you make a commit, pre-commit will run the checks defined in `.pre-commit-config.yaml`, and
refuse to complete the commit if any of them fail. Most of the checks automatically fix things and
all you need to do is add the changed files and commit again. Depending on how far astray your code is 😅 you may need to manually fix some things.

### Setup Database

This application requires a MongoDB database to run. The database connection string is configured with the `CLEARANCE_DB_URL` variable.

If you are using `direnv`, then the `CLEARANCE_DB_URL` variable will be set for you when you run `direnv allow`.

```shell
    $> docker compose up -d db
```

Will start the database and configure the `clearance_service` database with the correct user permissions.

You can verify it is up and running by running the following command:

```shell
    $> docker compose ps
```

#### Getting and Restoring a Database Dump

If you need to get a copy of the database, you can use the `get-backup` make target to download a copy of the database from TEST.

```shell
    $> make get-backup
```

`make get-backup` will download the latest database dump from TEST and place it in the `./remotedb-dump` directory.

To restore the database, run the following command:

```shell
    $> make restore-local
```

If you've been messing about and want to return the database to a known state, you can run the following command:

```shell
    $> make refresh-db
```

### Running Locally

With the database up and running, you can start the application with the following command:

```shell
  $> make run-dev
```

### Testing

Tests are written using Pytest, and they require a running instance of test MongoDB.

```shell
    $> make run-tests
```

### Metrics
Prometheus metrics are provided for the app at the `/metrics` endpoint.
These include metrics about request handling (numbers of response types, response times, etc),
and information about the python process itself (memory usage, threads, etc.).

### User Guide

The user documentation (found at https://ncstate-sat.github.io/clearance-service/) is generated by the files in the /docs folder of this repo, and hosted via GitHub Pages from this same repo's `gh-pages` branch.

Once the /docs folder has been updated with some new information for users, those changes need to be pushed to the `publishing` branch. That push automatically triggers the `Deploy Docs` GitHub Actions workflow (`.github/workflows/deploy-docs.yml`), which runs `mkdocs gh-deploy --force` to build the static site and commit it to the `gh-pages` branch, with a commit msg of `Deployed _someHash_ with MkDocs version: _someVersion_`, where _someHash_ is the abbreviated commit hash of the changes and _someVersion_ is the MkDocs version used.

That push to `gh-pages` in turn kicks off GitHub's own `pages build and deployment` workflow, which builds and deploys the updated site.
