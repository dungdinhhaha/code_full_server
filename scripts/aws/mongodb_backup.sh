#!/usr/bin/env bash
# Back up SMIOT MongoDB Community without reading MongoDB's internal
# system.buckets.* collections. Time Series documents are exported through
# the logical collection API and bundled with the ordinary mongodump archive.
set -Eeuo pipefail
umask 077

source /etc/smiot/app.env
source /etc/smiot/backup.env

db="${MONGODB_DATABASE:-smiot}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p /var/backups/smiot
work="$(mktemp -d "/var/backups/smiot/${stamp}.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# Dump application collections, excluding the logical time-series collection
# and MongoDB's private bucket collection (which the app user cannot count).
mongodump --uri="$MONGODB_URI" --db="$db" \
  --excludeCollection=telemetry \
  --excludeCollection=system.buckets.telemetry \
  --archive="$work/collections.archive.gz" --gzip

# Export logical time-series documents, not MongoDB's internal bucket format.
# Retry if the live stream appends a sample during export; publish only a
# snapshot whose exported count matches a stable before/after source count.
stable=false
for attempt in 1 2 3; do
  before="$(mongosh "$MONGODB_URI" --quiet --eval "db.getSiblingDB('$db').getCollection('telemetry').countDocuments({})" | tail -n 1 | tr -d '\r')"
  [[ "$before" =~ ^[0-9]+$ ]]
  mongoexport --uri="$MONGODB_URI" --db="$db" --collection=telemetry \
    --jsonFormat=canonical --out="$work/telemetry.ndjson"
  after="$(mongosh "$MONGODB_URI" --quiet --eval "db.getSiblingDB('$db').getCollection('telemetry').countDocuments({})" | tail -n 1 | tr -d '\r')"
  exported="$(wc -l < "$work/telemetry.ndjson" | tr -d ' ' )"
  if [[ "$exported" =~ ^[0-9]+$ && "$before" == "$after" && "$exported" == "$after" ]]; then
    stable=true
    break
  fi
  echo "Telemetry changed during export (attempt ${attempt}/3); retrying" >&2
done
[[ "$stable" == true ]]

cat > "$work/manifest.txt" <<MANIFEST
format=smiot-mongodb-backup-v2
created_utc=$stamp
database=$db
telemetry_collection=telemetry
telemetry_time_field=timestamp
telemetry_meta_field=meta
telemetry_granularity=seconds
telemetry_documents=$exported
telemetry_count_verified=true
telemetry_source_quiescence=verified by matching count before and after export
ordinary_collections=collections.archive.gz (mongodump gzip archive)
time_series_documents=telemetry.ndjson (mongoexport canonical Extended JSON)
restore_order=restore ordinary archive, create telemetry time-series collection, then mongoimport NDJSON
MANIFEST

bundle="/var/backups/smiot/smiot-${stamp}.tar.gz"
tar -C "$work" -czf "$bundle" .
aws s3 cp "$bundle" "s3://${S3_BACKUP_BUCKET}/backups/${stamp}.tar.gz" \
  --sse AES256 --only-show-errors

bytes="$(stat -c %s "$bundle")"
find /var/backups/smiot -maxdepth 1 -type f -name 'smiot-*.tar.gz' -mtime +2 -delete
echo "SMIOT_MONGODB_BACKUP_OK timestamp=${stamp} telemetry_documents=${exported} bytes=${bytes} s3_key=backups/${stamp}.tar.gz"
