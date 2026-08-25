#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE identity_db;
    CREATE DATABASE finance_db;
    CREATE DATABASE notification_db;
    CREATE DATABASE ai_db;
EOSQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname ai_db -c "CREATE EXTENSION IF NOT EXISTS vector;"