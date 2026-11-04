#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
exec > >(tee -a /var/log/smiot-bootstrap.log) 2>&1
REGION="${1:?region required}"
BUCKET="${2:?bucket required}"
SSM_SECRET="${3:?secret parameter name required}"
APP_OBJECT="${4:-smiot/app.zip}"
DATA_OBJECT="${5:-smiot/mongodb-export.tar.gz}"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg unzip jq python3-venv python3-pip python3-dev build-essential nginx certbot python3-certbot-nginx mosquitto
if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
  rm -rf /tmp/aws /tmp/awscliv2.zip
fi
snap install amazon-ssm-agent --classic || true
systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent.service || true
if ! swapon --show=NAME --noheadings | grep -qx '/swapfile'; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
mkdir -p /opt/smiot /etc/smiot /var/backups/smiot
chmod 700 /etc/smiot /var/backups/smiot
aws s3 cp "s3://${BUCKET}/${APP_OBJECT}" /tmp/smiot-app.zip --region "$REGION"
aws s3 cp "s3://${BUCKET}/${DATA_OBJECT}" /tmp/smiot-mongodb-export.tar.gz --region "$REGION"
unzip -oq /tmp/smiot-app.zip -d /opt/smiot
mkdir -p /opt/smiot/logs /opt/smiot/mongo-import
mkdir -p /opt/smiot/.nicegui
id smiot >/dev/null 2>&1 || useradd --system --home-dir /opt/smiot --shell /usr/sbin/nologin smiot
TOKEN=$(curl -fsS -X PUT 'http://169.254.169.254/latest/api/token' -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600')
PUBLIC_IP=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" 'http://169.254.169.254/latest/meta-data/public-ipv4')
DOMAIN=$(printf '%s' "$PUBLIC_IP" | tr '.' '-').sslip.io
python3 - "$SSM_SECRET" "$REGION" "$DOMAIN" <<'PY'
import json, subprocess, sys, urllib.parse
name, region, domain=sys.argv[1:]
raw=subprocess.check_output(['aws','ssm','get-parameter','--name',name,'--with-decryption','--query','Parameter.Value','--output','text','--region',region],text=True)
s=json.loads(raw)
uri='mongodb://smiot_app:'+urllib.parse.quote_plus(s['MONGO_APP_PASSWORD'])+'@127.0.0.1:27017/smiot?authSource=admin&retryWrites=false'
v={'APP_ENV':'production','MONGODB_URI':uri,'MONGODB_DATABASE':'smiot','MONGODB_TELEMETRY_COLLECTION':'telemetry','MONGODB_LIVE_INGEST_ENABLED':'true','DATADOG_METRICS_ENABLED':'true','DATADOG_APM_ENABLED':'true','DATADOG_LLMOBS_ENABLED':'true','DD_API_KEY':s['DD_API_KEY'],'DD_APP_KEY':s['DD_APP_KEY'],'DD_SITE':s['DD_SITE'],'DD_SERVICE':'smiot-smart-farm','DD_ENV':'production','DD_VERSION':'1.1.0','DD_AGENT_HOST':'127.0.0.1','DD_DOGSTATSD_PORT':'8125','DD_TRACE_AGENT_URL':'http://127.0.0.1:8126','GEMINI_API_KEY':s.get('GEMINI_API_KEY',''),'AI_ENABLED':s.get('AI_ENABLED','true'),'NICEGUI_STORAGE_SECRET':s['NICEGUI_STORAGE_SECRET'],'SMIOT_DEMO_MODE':'true','SMIOT_DEMO_INTERVAL_SECONDS':'30','WOKWI_CLI_TOKEN':s['WOKWI_CLI_TOKEN'],'WOKWI_CHANNEL':'greenhouse-a-7f38c2d1','WOKWI_MQTT_HOST':'broker.hivemq.com','WOKWI_MQTT_PORT':'1883','MQTT_HOST':'127.0.0.1','MQTT_PORT':'1883'}
def q(x): return '"'+str(x).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
with open('/etc/smiot/app.env','w',encoding='utf-8') as f:
 for k,x in v.items(): f.write(k+'='+q(x)+'\n')
with open('/etc/smiot/secrets.json','w',encoding='utf-8') as f: json.dump(s,f)
open('/etc/smiot/domain','w').write(domain+'\n')
PY
chown root:smiot /etc/smiot/app.env
chmod 640 /etc/smiot/app.env
chmod 600 /etc/smiot/secrets.json
rm -f /usr/share/keyrings/mongodb-server-8.0.gpg
curl -fsSL https://pgp.mongodb.com/server-8.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg
chmod 644 /usr/share/keyrings/mongodb-server-8.0.gpg
echo 'deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse' > /etc/apt/sources.list.d/mongodb-org-8.0.list
apt-get update
apt-get install -y mongodb-org mongodb-database-tools
cat > /etc/mongod.conf <<'YAML'
storage:
  dbPath: /var/lib/mongodb
  wiredTiger:
    engineConfig:
      cacheSizeGB: 0.5
systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log
net:
  port: 27017
  bindIp: 127.0.0.1
processManagement:
  timeZoneInfo: /usr/share/zoneinfo
setParameter:
  internalQueryStatsSampleRate: 1.0
YAML
systemctl enable --now mongod
export MONGO_APP_PASSWORD=$(jq -r .MONGO_APP_PASSWORD /etc/smiot/secrets.json)
export MONGO_DD_PASSWORD=$(jq -r .MONGO_DD_PASSWORD /etc/smiot/secrets.json)
mongosh --quiet --eval 'const a=db.getSiblingDB("admin"); a.createUser({user:"smiot_app",pwd:process.env.MONGO_APP_PASSWORD,roles:[{role:"readWrite",db:"smiot"}]}); a.createUser({user:"datadog",pwd:process.env.MONGO_DD_PASSWORD,roles:[{role:"read",db:"admin"},{role:"read",db:"local"},{role:"clusterMonitor",db:"admin"},{role:"read",db:"smiot"}]});'
cat >> /etc/mongod.conf <<'YAML'
security:
  authorization: enabled
YAML
systemctl restart mongod
python3 -m venv /opt/smiot/.venv
/opt/smiot/.venv/bin/pip install --no-cache-dir -r /opt/smiot/requirements.txt
chown -R smiot:smiot /opt/smiot
# Restore with BSON types and the MongoDB time-series collection options preserved.
set -a
source /etc/smiot/app.env
set +a
tar -xzf /tmp/smiot-mongodb-export.tar.gz -C /opt/smiot/mongo-import
/opt/smiot/.venv/bin/python -X utf8 /opt/smiot/scripts/aws/import_mongodb.py --archive /opt/smiot/mongo-import --database smiot
cd /opt/smiot
/opt/smiot/.venv/bin/python - <<'PY'
import json, os
from pymongo import MongoClient
from service.auth import _hash_password
s=json.load(open('/etc/smiot/secrets.json',encoding='utf-8'))
c=MongoClient(os.environ['MONGODB_URI'],serverSelectionTimeoutMS=15000)
u=c.smiot.users
n=0
for d in u.find({}, {'username':1}):
 name=d.get('username'); password=s['SMIOT_ADMIN_PASSWORD'] if name=='admin' else s['ROTATED_USER_PASSWORDS'][name]
 u.update_one({'_id':d['_id']},{'$set':{'password':_hash_password(password)}}); n+=1
print('CLOUD_PASSWORD_ROTATION_OK accounts='+str(n))
c.close()
PY
rm -rf /opt/smiot/mongo-import /tmp/smiot-app.zip /tmp/smiot-mongodb-export.tar.gz
cat > /etc/mosquitto/conf.d/smiot.conf <<'CONF'
listener 1883 127.0.0.1
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
CONF
systemctl enable --now mosquitto
cat > /etc/nginx/sites-available/smiot <<NGINX
server {
 listen 80;
 server_name ${DOMAIN};
 location /.well-known/acme-challenge/ { root /var/www/html; }
 location / {
  proxy_pass http://127.0.0.1:8080;
  proxy_http_version 1.1;
  proxy_set_header Host \$host;
  proxy_set_header X-Real-IP \$remote_addr;
  proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto \$scheme;
  proxy_set_header Upgrade \$http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_read_timeout 3600s;
  proxy_buffering off;
 }
}
NGINX
ln -sfn /etc/nginx/sites-available/smiot /etc/nginx/sites-enabled/smiot
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d "$DOMAIN" || echo 'TLS_CERT_PENDING: rerun certbot after DNS propagates'
cat > /etc/systemd/system/smiot.service <<'UNIT'
[Unit]
Description=SMIOT Smart Farm application
After=network-online.target mongod.service mosquitto.service datadog-agent.service
Wants=network-online.target
[Service]
Type=simple
User=smiot
Group=smiot
WorkingDirectory=/opt/smiot
EnvironmentFile=/etc/smiot/app.env
ExecStart=/opt/smiot/.venv/bin/python -X utf8 /opt/smiot/main.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/opt/smiot/logs /opt/smiot/.nicegui
[Install]
WantedBy=multi-user.target
UNIT
# Standard MongoDB integration with a dedicated read-only user; DBM is billed separately.
source /etc/smiot/app.env
curl -fsSL https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh -o /tmp/dd-install.sh
DD_API_KEY="$DD_API_KEY" DD_SITE="$DD_SITE" bash /tmp/dd-install.sh
DD_DB_PASS=$(jq -r .MONGO_DD_PASSWORD /etc/smiot/secrets.json)
cat > /etc/datadog-agent/conf.d/mongo.d/conf.yaml <<MONGO
init_config:
instances:
 - hosts: ["127.0.0.1:27017"]
   username: datadog
   password: "${DD_DB_PASS}"
   options: {authSource: admin}
    dbm: false
   cluster_name: smiot-community
   additional_metrics: ["metrics.commands", "tcmalloc", "top", "collection"]
   collections_indexes_stats: true
   database_autodiscovery: {enabled: true}
MONGO
chmod 640 /etc/datadog-agent/conf.d/mongo.d/conf.yaml
chown root:dd-agent /etc/datadog-agent/conf.d/mongo.d/conf.yaml
sed -i 's/^# logs_enabled: false/logs_enabled: true/' /etc/datadog-agent/datadog.yaml
cat >> /etc/datadog-agent/datadog.yaml <<'DDCFG'
apm_config:
  enabled: true
  receiver_port: 8126
dogstatsd_port: 8125
tags:
 - env:production
 - project:smiot
 - database:mongodb-community
DDCFG
mkdir -p /etc/datadog-agent/conf.d/smiot.d
install -d -o dd-agent -g smiot -m 2750 /opt/smiot/logs/recovery
cat > /etc/datadog-agent/conf.d/smiot.d/conf.yaml <<'DDLOG'
logs:
  - type: file
    path: /opt/smiot/logs/*.log
    service: smiot-smart-farm
    source: python
  - type: file
    path: /opt/smiot/logs/recovery/*.jsonl
    service: smiot-smart-farm
    source: smiot-recovery
    tags:
      - env:production
      - project:smiot
DDLOG
chmod 640 /etc/datadog-agent/conf.d/smiot.d/conf.yaml
chown root:dd-agent /etc/datadog-agent/conf.d/smiot.d/conf.yaml
usermod -a -G smiot dd-agent || true
systemctl enable --now datadog-agent
systemctl daemon-reload
systemctl enable --now smiot
# Nightly compressed MongoDB backup to the encrypted S3 bucket; object lifecycle is 35 days.
cat > /etc/smiot/backup.env <<ENV
S3_BACKUP_BUCKET=${BUCKET}
AWS_DEFAULT_REGION=${REGION}
ENV
chmod 600 /etc/smiot/backup.env
cat > /usr/local/sbin/smiot-backup.sh <<'BACKUP'
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
BACKUP
chmod 700 /usr/local/sbin/smiot-backup.sh
cat > /etc/systemd/system/smiot-backup.service <<'UNIT'
[Unit]
Description=SMIOT MongoDB encrypted S3 backup
After=mongod.service
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/smiot-backup.sh
UNIT
cat > /etc/systemd/system/smiot-backup.timer <<'UNIT'
[Unit]
Description=Daily SMIOT MongoDB backup
[Timer]
OnCalendar=*-*-* 02:20:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now smiot-backup.timer
# Cloud Wokwi MQTT bridge; only forwards the virtual device's synthetic telemetry.
cat > /etc/systemd/system/wokwi-bridge.service <<'UNIT'
[Unit]
Description=SMIOT Wokwi MQTT bridge
After=network-online.target mosquitto.service smiot.service
Wants=network-online.target
[Service]
Type=simple
User=smiot
Group=smiot
WorkingDirectory=/opt/smiot
EnvironmentFile=/etc/smiot/app.env
ExecStart=/opt/smiot/.venv/bin/python -X utf8 /opt/smiot/scripts/wokwi_datadog_bridge.py
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now wokwi-bridge
# Expose real systemd unit state/restart counters to Datadog for server-level
# diagnosis. Keep this after creating the bridge unit so the check can resolve
# every configured service on first start.
mkdir -p /etc/datadog-agent/conf.d/systemd.d
cat > /etc/datadog-agent/conf.d/systemd.d/conf.yaml <<'DDSYSTEMD'
init_config:
instances:
  - unit_names:
      - smiot.service
      - mongod.service
      - mosquitto.service
      - nginx.service
      - wokwi-bridge.service
      - datadog-agent.service
DDSYSTEMD
chmod 640 /etc/datadog-agent/conf.d/systemd.d/conf.yaml
chown root:dd-agent /etc/datadog-agent/conf.d/systemd.d/conf.yaml
datadog-agent configcheck
systemctl restart datadog-agent
# Wokwi CI minutes are quota-limited; the Wokwi cloud run starts only on demand.
curl -fsSL https://wokwi.com/ci/install.sh | sh || true
WOKWI_BIN=$(command -v wokwi-cli || true)
if [[ -n "$WOKWI_BIN" ]]; then ln -sfn "$WOKWI_BIN" /usr/local/bin/wokwi-cli; fi
cat > /etc/systemd/system/wokwi-sim.service <<'UNIT'
[Unit]
Description=On-demand Wokwi cloud simulation, bounded to five minutes
After=network-online.target smiot.service
Wants=network-online.target
[Service]
Type=simple
User=smiot
Group=smiot
WorkingDirectory=/opt/smiot
EnvironmentFile=/etc/smiot/app.env
ExecStart=/usr/local/bin/wokwi-cli /opt/smiot/wokwi/smiot_demo --timeout 300000
Restart=no
UNIT
systemctl daemon-reload
rm -f /etc/smiot/secrets.json
chmod 640 /etc/smiot/app.env

echo "SMIOT_BOOTSTRAP_COMPLETE domain=${DOMAIN} public_ip=${PUBLIC_IP}"
