FROM python:3.10-slim-bookworm

WORKDIR /app
ADD requirements /app/requirements

ADD https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-x86_64-100.12.0.deb /app

RUN set -ex \
    && BUILD_DEPS=" \
    build-essential \
    " \
    && apt-get update && apt-get install -y --no-install-recommends $BUILD_DEPS \
    /app/mongodb-database-tools-debian12-x86_64-100.12.0.deb \
    && pip install -r requirements/base/base.txt \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false $BUILD_DEPS \
    && rm -rf /var/lib/apt/lists/* /app/mongodb-database-tools-debian12-x86_64-100.12.0.deb

COPY . .

ARG PORT=8000
ARG HOST="0.0.0.0"

ENV UVICORN_PORT=$PORT
ENV UVICORN_HOST=$HOST

EXPOSE $UVICORN_PORT

CMD ["uvicorn", "main:app"]
