ARG BASE_POSTGRES_IMAGE

FROM ${BASE_POSTGRES_IMAGE} as pg

USER root

COPY /docker-entrypoint-initdb.d /docker-entrypoint-initdb.d
RUN chmod +x /docker-entrypoint-initdb.d/init-user-db.sh

#USER 1001