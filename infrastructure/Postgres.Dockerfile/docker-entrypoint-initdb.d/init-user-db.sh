#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL

  revoke all on database postgres from public;

  create user $POSTGRES_DB_USER with
    login
    superuser
    inherit
    createrole
    createdb
    replication
	  password '$POSTGRES_DB_PASS';

  create database $POSTGRESQL_DATABASE with
    owner = $POSTGRES_DB_USER
    encoding = 'utf8'
    lc_collate = 'en_US.utf8'
    lc_ctype = 'en_US.utf8'
    connection limit = -1;

  create extension pg_stat_statements;

  create user $AIRFLOW_DB_USER with
    login
    superuser
    inherit
    createrole
    createdb
    replication
	  password '$AIRFLOW_DB_PASS';

  create database $AIRFLOW_DATABASE with
    owner = $AIRFLOW_DB_USER
    encoding = 'utf8'
    lc_collate = 'en_US.utf8'
    lc_ctype = 'en_US.utf8'
    connection limit = -1;

EOSQL

{
    echo "host all         pts       0.0.0.0/0      trust"
} >> "$PGDATA/pg_hba.conf"