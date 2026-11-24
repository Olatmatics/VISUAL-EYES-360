#!/bin/sh
set -e
# Migrations are run once by the `migrate` service before api/ingest start.
exec "$@"
