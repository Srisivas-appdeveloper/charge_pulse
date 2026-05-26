#!/bin/sh
# Daily pg_dump → /backups + optional S3 upload.
# Run as a sidecar container, or via cron on the host.
# Keeps 30 daily + 12 monthly snapshots.

set -eu
TS=$(date +%Y%m%d-%H%M%S)
OUT=/backups/chargepulse-$TS.sql.gz
mkdir -p /backups

while true; do
    echo "[$(date)] dumping → $OUT"
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" --no-owner --no-acl \
        | gzip > "$OUT"

    # Optional S3 upload — requires AWS CLI in image.
    if [ -n "${BACKUP_S3_BUCKET:-}" ] && command -v aws >/dev/null 2>&1; then
        aws s3 cp "$OUT" "s3://$BACKUP_S3_BUCKET/$(basename "$OUT")"
    fi

    # Rotation: keep last 30 daily, last 12 of monthly snapshots.
    find /backups -name "chargepulse-*.sql.gz" -mtime +30 -delete
    DAY=$(date +%d)
    if [ "$DAY" != "01" ]; then
        # Always keep the 1st of each month
        find /backups -name "chargepulse-*01-*.sql.gz" -mtime +365 -delete
    fi

    # Next run in 24h
    OUT=/backups/chargepulse-$(date -d '+1 day' +%Y%m%d-%H%M%S 2>/dev/null || date +%Y%m%d-%H%M%S).sql.gz
    sleep 86400
done
