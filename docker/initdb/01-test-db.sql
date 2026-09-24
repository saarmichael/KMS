-- Runs once when the compose Postgres volume is first created.
-- A second database for the test suite, so tests never truncate dev data.
CREATE DATABASE kms_test;
