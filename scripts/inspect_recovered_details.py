import json
from service.mongodb_store import collection
def main():
 out=[]
 for d in collection('operational_incidents').find({'status':'recovered'},{'_id':1,'kind':1,'scenario':1,'workflow_id':1,'monitor_id':1,'evidence':1,'opened_at':1,'recovered_at':1}).sort('recovered_at',-1).limit(100):
  out.append(d)
 print(json.dumps(out,default=str,ensure_ascii=False))
if __name__=='__main__': main()
