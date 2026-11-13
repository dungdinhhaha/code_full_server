import json
from service.mongodb_store import collection

def main():
    c=collection('operational_incidents')
    rows=[]
    for d in c.find({}, {'kind':1,'status':1,'recovered_at':1,'workflow_only':1,'synthetic':1,'_id':1}).sort('updated_at',-1).limit(500):
        rows.append(d)
    counts={}
    for d in rows:
        k=str(d.get('kind')); s=str(d.get('status'))
        counts.setdefault(k,{}).setdefault(s,0); counts[k][s]+=1
    print(json.dumps({'total_sample':len(rows),'counts':counts,'latest':rows[:30]},default=str))
if __name__=='__main__': main()
