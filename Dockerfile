FROM ubuntu:22.04

WORKDIR /app

RUN apt-get update && apt-get install -y python3 python3-pip
RUN python3 -m pip install -r requirements.txt

COPY . .

ARG PORT=8000
ARG HOST="0.0.0.0"

ENV UVICORN_PORT=$PORT
ENV UVICORN_HOST=$HOST

EXPOSE $UVICORN_PORT

CMD ["uvicorn", "main:app"]
