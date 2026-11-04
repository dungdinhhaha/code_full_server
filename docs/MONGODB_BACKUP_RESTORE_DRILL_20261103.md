# MongoDB backup and restore evidence — 2026-11-03

## What failed

The original nightly `mongodump --db smiot` exited before upload. The app database user can read/write logical collections but cannot count MongoDB's internal Time Series bucket collection (`system.buckets.telemetry`). Granting the app user access to internal system collections would be the wrong fix.

## Fix deployed

- Dump ordinary application collections with `mongodump`, excluding `telemetry` and its internal bucket namespace.
- Export logical Time Series documents through `mongoexport` in canonical Extended JSON.
- Compare the Time Series source count before and after export with the exported line count; retry up to three times if live ingestion changes the count during export.
- Bundle both data files with a restore manifest, upload to the existing S3 backup bucket using SSE-S3 AES-256, then remove local temporary files.
- Preserve the one-day systemd timer. The EC2 instance role now has `s3:GetObject` only for `arn:aws:s3:::smiot-demo-920235987407-ap-southeast-2/backups/*`; its existing `PutObject` permission remains scoped to the same prefix.

## Verified run

- Instance: `i-00bf2d3591d3ee0a2`, account `920235987407`, region `ap-southeast-2`.
- Backup object: `s3://smiot-demo-920235987407-ap-southeast-2/backups/20261103T113718Z.tar.gz`.
- Object size: 2,869,717 bytes; server-side encryption: `AES256`.
- Backup result: `SMIOT_MONGODB_BACKUP_OK`, 154,618 Time Series documents exported.
- Restore drill downloaded that exact S3 object, restored the Time Series data into a temporary Time Series collection, and restored `operational_incidents` into a temporary ordinary collection.
- Restore result: `LATEST_S3_BACKUP_RESTORE_OK telemetry=154618/154618 operational_incidents=1/1`.
- The drill's trap removed the temporary collections and files. The live source collection counts were not changed.
- Systemd `smiot-backup.timer` is enabled and active. The service completed successfully.

## Reproduce the restore drill

On the EC2 instance, run as a user able to read `/etc/smiot/app.env` and use the EC2 role:

```bash
sudo /usr/local/sbin/mongodb_restore_drill.sh backups/20261103T113718Z.tar.gz
```

The deployment-facing backup source is [scripts/aws/mongodb_backup.sh](../scripts/aws/mongodb_backup.sh). The bootstrap and resume scripts embed the same version so a rebuild retains this behavior.

## Scope and limits

This proves a restorable logical MongoDB backup for the tested Time Series data and the incident collection. It is not a restore of every collection into a separate server, a point-in-time recovery test, or an EBS snapshot restore. The EC2 application and MongoDB still share one instance, so the architecture retains a single-instance failure domain.
