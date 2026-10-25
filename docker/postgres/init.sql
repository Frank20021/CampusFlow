-- Development databases created on first Postgres container start.
-- The app database is created by POSTGRES_DB. This extra database is
-- used by pytest so tests never touch local development data.
SELECT 'CREATE DATABASE campusflow_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'campusflow_test')\gexec
GRANT ALL PRIVILEGES ON DATABASE campusflow_test TO campusflow;
