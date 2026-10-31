import json, os, subprocess, sys
name=sys.argv[1]; j=json.load(open('/work/electron37-attempt/tools/printed-lldcmd.json')); a=j['argv']
if name=='norust':
  drop=set(range(94,190))
elif name=='rustonly':
  drop={i for i,x in enumerate(a) if 18<=i<94 and (not x.startswith('-') or x.startswith('@'))}
elif name=='noffmpeg': drop={45,46}
elif name=='no-pie': drop=set()
else: drop=set()
a=[x for i,x in enumerate(a) if i not in drop]
a[a.index('-o')+1]=f'./electron-{name}'
if name=='no-pie': a=[('-shared' if x=='-pie' else x) for x in a]
print('running',name,len(a),flush=True)
r=subprocess.run(a,env=os.environ,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
print('status',r.returncode,flush=True); print(r.stdout.decode('utf8','replace')[-10000:],flush=True)
