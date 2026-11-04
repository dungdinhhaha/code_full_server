"""Idempotently copy SMIOT operational SQLite tables into MongoDB collections."""
from __future__ import annotations
import argparse, os, sqlite3
from pathlib import Path
from pymongo import MongoClient, ReplaceOne
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env',override=False)
TABLES=('users','permissions','inverter_mode','schedules','schedule_logs','notifications')

def rows(conn, table):
    return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--sqlite',default=str(ROOT/'farm_data.db')); p.add_argument('--dry-run',action='store_true'); a=p.parse_args()
    uri=os.getenv('MONGODB_URI')
    if not uri: raise SystemExit('MONGODB_URI is missing; no values are printed.')
    sql=sqlite3.connect(Path(a.sqlite).resolve().as_uri()+'?mode=ro',uri=True); sql.row_factory=sqlite3.Row
    data={t:rows(sql,t) for t in TABLES}
    perms={r['key'] for r in data['permissions']}
    up={}
    for r in sql.execute('SELECT user_id, permission_key FROM user_permissions'): up.setdefault(r['user_id'],[]).append(r['permission_key'])
    uf={}
    for r in sql.execute('SELECT user_id, farm_key FROM user_farms'): uf.setdefault(r['user_id'],[]).append(r['farm_key'])
    for u in data['users']:
        u['permissions']=up.get(u['id'],[]); u['farms']=uf.get(u['id'],[])
    sql.close()
    print('SQLite rows:',', '.join(f'{t}={len(data[t])}' for t in TABLES),f'user_permission_links={sum(map(len,up.values()))}',f'user_farm_links={sum(map(len,uf.values()))}')
    if a.dry_run: print('Dry run only; MongoDB unchanged.'); return
    c=MongoClient(uri,serverSelectionTimeoutMS=10000,appname='smiot-sqlite-to-mongodb-operational')
    c.admin.command('ping'); db=c[os.getenv('MONGODB_DATABASE','smiot')]
    mappings={
      'users':('users',lambda r:{**r,'_id':r['id']}),
      'permissions':('permissions',lambda r:{**r,'_id':r['key']}),
      'inverter_mode':('inverter_mode',lambda r:{**r,'_id':r['farm_key']}),
      'schedules':('schedules',lambda r:{**r,'_id':r['id']}),
      'schedule_logs':('schedule_logs',lambda r:{**r,'_id':r['id']}),
      'notifications':('notifications',lambda r:{**r,'_id':r['id']}),
    }
    for table,(name,convert) in mappings.items():
        docs=[convert(r) for r in data[table]]
        if docs: db[name].bulk_write([ReplaceOne({'_id':d['_id']},d,upsert=True) for d in docs],ordered=False)
        print(f'{table} -> {name}: upserted {len(docs)}')
    db.users.create_index('username',unique=True)
    db.schedules.create_index([('farm_key',1),('schedule_date',1),('start_time',1)])
    db.schedule_logs.create_index([('farm_key',1),('start_at',-1)])
    db.schedule_logs.create_index([('schedule_id',1),('status',1)])
    db.notifications.create_index([('created_at',-1)])
    for table in ('users','schedules','schedule_logs','notifications'):
        db['_counters'].update_one({'_id':table},{'$max':{'value':max([r['id'] for r in data[table]],default=0)}},upsert=True)
    expected={'users':len(data['users']),'permissions':len(data['permissions']),'inverter_mode':len(data['inverter_mode']),'schedules':len(data['schedules']),'schedule_logs':len(data['schedule_logs']),'notifications':len(data['notifications'])}
    actual={name:db[name].count_documents({}) for name in expected}
    print('Mongo counts:',', '.join(f'{k}={v}' for k,v in actual.items()))
    mismatches={k:(expected[k],actual[k]) for k in expected if expected[k]!=actual[k]}
    if mismatches: raise SystemExit('Count mismatch detected; do not enable Mongo primary: '+repr(mismatches))
    print('Operational collections count-verified. Existing telemetry collection was not rewritten.')
    c.close()

if __name__=='__main__': main()
