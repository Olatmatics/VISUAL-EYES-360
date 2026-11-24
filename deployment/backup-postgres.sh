#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
env_file="${ENV_FILE:-$script_dir/.env.production}"
backup_dir="${BACKUP_DIR:-$script_dir/backups}"

if [[ ! -f "$env_file" ]]; then
  echo "Missing environment file: $env_file" >&2
  exit 1
fi

set -a
source "$env_file"
set +a

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
backup_file="$backup_dir/ve360-$(date -u +%Y%m%dT%H%M%SZ).dump"

docker compose --env-file "$env_file" -f "$script_dir/compose.yaml" \
  exec -T db pg_dump -U "$POSTGRES_USER" --format=custom "$POSTGRES_DB" > "$backup_file"
chmod 600 "$backup_file"
echo "Created database backup: $backup_file"
