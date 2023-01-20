# Clearance Assignment Service

Backend service for Clearance Assignment functionality.

## Required Environment Variables

| Name (Required \*)            | Description                                                             | Example                                          |
| ----------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------ |
| JWT_SECRET\*                  | The secret used to decode JWTs for auth.                                | khMSpZkNsjwr                                     |
| CLEARANCE_DB_URL\*            | The full MongoDB URL.                                                   | mongodb://username:password@university.edu       |
| CCURE_BASE_URL\*              | The host name of the CCURE api.                                         | http://c9k.university.edu                        |
| CCURE_USERNAME\*              | The username for the CCURE api.                                         | username                                         |
| CCURE_PASSWORD\*              | The password for the CCURE api.                                         | secure_password123                               |
| CCURE_CLIENT_NAME\*           | The title for the CCURE client.                                         | University CCURE Client                          |
| CCURE_CLIENT_VERSION\*        | The CCURE api version.                                                  | 2.0                                              |
| RUN_SCHEDULER                 | Configure whether the scheduler transfers data from MongoDB to CCURE    | True                                             |


## Minimum Database Config

<details>
<summary><b>Required:</b> Database + Collection</summary>
You'll need a database called <code>clearance_service</code> and the following collections:

<ul>
    <li>
        <code>audit</code> - Stores past events that have occurred in the system.
    </li>
    <li>
        <code>clearance</code> - Stores all clearances.
    </li>
    <li>
        <code>clearance_assignment</code> - Clearances that assigned to users.
    </li>
    <li>
        <code>liaison</code> - Stores all Liaisons.
    </li>
    <li>
        <code>liaison-clearance-permissions</code> - Decides who has access to what clearances.
    </li>
    <li>
        <code>liaison_master</code> - unknown
    </li>
</ul>
</details>

<details>
<summary><b>Required:</b> AuthChecker permissions</summary>

<ul>
    <li>
        <code>clearance_assignment_read</code> - Allows clearance assignments to be read.
    </li>
    <li>
        <code>clearance_assignment_write</code> - Allows clearance assignments to be written.
    </li>
    <li>
        <code>audit_read</code> - Allows someone to read the audit log.
    </li>
    <li>
        <code>personnel_read</code> - Allows someone to read personnel data.
    </li>
</ul>

</details>

## Other Requirements

For this application to run, the machine on which it's running must be able to reach the CCURE server. A VPN connection might be required.

Access to the following is required for all endpoints to work properly:

-   CCURE server

These are all configured with the environment variables.

### Install Requirements

The requirements.txt contains all of the dependencies required to run the Clearance Assignment Service. Developer Dependencies
are separated into the `requirements.dev.txt` file. The packages in `requirements.dev.txt` are not required to run the service
but is required for code-coverage, pytests, etc.

### Running in a Docker Container

First, build the image. Optionally, add build arguments for PORT and HOST. By default, these will be 8000 and 0.0.0.0, respectively.

```
docker build -t clearance-service .
or
docker build -t clearance-service --build-arg PORT=8080 --build-arg HOST=0.0.0.0 .
```

Next, run the container, ensuring all environment variables are present.

```
docker run --env-file .env -p 8000:8000 clearance-service
```

### Testing

Tests are written using Pytest, and they require a running instance of MongoDB. Ensure a blank MongoDB database is running, then run the pytest command.

#### Running tests with act

Install [act](https://github.com/nektos/act) and then run:

```
act -P hosted=catthehacker/ubuntu:act-20.04 -W ./.github/workflows/unit-test.yml
```

#### Running tests manually

```
docker run -p 27017:27017 --rm -d mongo
pytest
```

Optionally, you can add `-s` to show print output, and you can run only certain test files by including the relative path to the file.

```
pytest -s tests/test_personnel_controller.py
```

You can also run the tests within a Docker container if you don't have Python or pip on your machine. Run docker exec to enter the container and run the test command.

```
docker exec -it clearance-service bash
pytest
```

### Endpoints

Documentation for legacy endpoints in this API in in Postman's format. Import the files in the `docs` folder in Postman to view the legacy endpoints and how to use them.

Documentation for all other endpoints will be available by navigating to `/docs` in the browser with this application running.

## CI/CD

Continuous integration and continuous deployment are setup as GitHub Actions in the `.github` directory.
