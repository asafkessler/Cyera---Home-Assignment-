#!/bin/sh
# Makes `docker compose up` work with zero configuration.
#
# The app refuses to start without APP_SECRET_KEY and APP_ENCRYPTION_KEY. When
# they are not provided (via .env or the environment), this script generates
# them once and keeps them in the data volume, next to the database, so they
# survive restarts. That is a convenience for local evaluation: in production
# the keys are supplied explicitly and never stored next to the data.
set -e

DATA_DIR="${APP_DATA_DIR:-/data}"
SECRETS_FILE="$DATA_DIR/generated-secrets.env"

if [ -z "$APP_SECRET_KEY" ] || [ -z "$APP_ENCRYPTION_KEY" ]; then
  if [ ! -f "$SECRETS_FILE" ]; then
    echo "[entrypoint] APP_SECRET_KEY / APP_ENCRYPTION_KEY not provided."
    echo "[entrypoint] Generating them once into $SECRETS_FILE (local evaluation only; set them explicitly in production)."
    python -m app.keys > "$SECRETS_FILE"
    chmod 600 "$SECRETS_FILE"
  fi
  # Export only the values that are still missing, so explicit settings always win.
  while IFS='=' read -r name value; do
    [ -n "$name" ] || continue
    if [ -z "$(eval "printf '%s' \"\$$name\"")" ]; then
      export "$name=$value"
    fi
  done < "$SECRETS_FILE"
fi

exec "$@"
