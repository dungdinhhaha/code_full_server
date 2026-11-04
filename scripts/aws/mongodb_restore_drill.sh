#!/usr/bin/env bash
# Restore-drill the latest SMIOT S3 backup into temporary collections in the
# same database. This does not overwrite production collections.
set -Eeuo pipefail
umask 077

source /etc/smiot/app.env
source /etc/smiot/backup.env

db="${MONGODB_DATABASE:-smiot}"
key="${1:?Usage: mongodb_restore_drill.sh backups/<timestamp>.tar.gz}"
suffix="$(date -u +%s)"
restore_ts="restore_drill_telemetry_${suffix}"
restore_incidents="restore_drill_operational_incidents_${suffix}"
work="$(mktemp -d /var/tmp/smiot-restore-drill.XXXXXX)"
cleanup() {
  mongosh "$MONGODB_URI" --quiet --eval \
    "const d=db.getSiblingDB('$db'); d.getCollection('$restore_ts').drop(); d.getCollection('$restore_incidents').drop();" \
    >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

aws s3 cp "s3://${S3_BACKUP_BUCKET}/${key}" "$work/backup.tar.gz" --only-show-errors
tar -xzf "$work/backup.tar.gz" -C "$work"
expected="$(sed -n 's/^telemetry_documents=//p' "$work/manifest.txt")"
source_incidents="$(mongosh "$MONGODB_URI" --quiet --eval "db.getSiblingDB('$db').operational_incidents.countDocuments({})" | tail -n 1 | tr -d '\r')"

mongorestore --uri="$MONGODB_URI" --archive="$work/collections.archive.gz" --gzip \
  --nsFrom="${db}.operational_incidents" --nsTo="${db}.${restore_incidents}" --drop --quiet
mongosh "$MONGODB_URI" --quiet --eval \
  "db.getSiblingDB('$db').createCollection('$restore_ts',{timeseries:{timeField:'timestamp',metaField:'meta',granularity:'seconds',bucketMaxSpanSeconds:3600}})" >/dev/null
mongoimport --uri="$MONGODB_URI" --db="$db" --collection="$restore_ts" \
  --file="$work/telemetry.ndjson" --numInsertionWorkers=4 --quiet

restored_ts="$(mongosh "$MONGODB_URI" --quiet --eval "db.getSiblingDB('$db').getCollection('$restore_ts').countDocuments({})" | tail -n 1 | tr -d '\r')"
restored_incidents="$(mongosh "$MONGODB_URI" --quiet --eval "db.getSiblingDB('$db').getCollection('$restore_incidents').countDocuments({})" | tail -n 1 | tr -d '\r')"
[[ "$expected" =~ ^[0-9]+$ && "$restored_ts" == "$expected" ]]
[[ "$source_incidents" =~ ^[0-9]+$ && "$restored_incidents" == "$source_incidents" ]]
echo "SMIOT_RESTORE_DRILL_OK telemetry=${restored_ts}/${expected} operational_incidents=${restored_incidents}/${source_incidents} source_database_unchanged=true"
