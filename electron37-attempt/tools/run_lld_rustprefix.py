import json,os,subprocess,sys
k=int(sys.argv[1]); j=json.load(open('/work/electron37-attempt/tools/printed-lldcmd.json')); a=j['argv']
# preserve all options and @rsp, drop rlib indexes >=94, keep first k
keep_end=94+k
a=[x for i,x in enumerate(a) if i<keep_end or i>=190]
a=[x for x in a if x != '-Wl,-z,defs']
a[a.index('-o')+1]=f'./electron-rust{k}'
print('running',k,len(a),flush=True)
try:
 r=subprocess.run(a,env=os.environ,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
 print('status',r.returncode,flush=True); print(r.stdout.decode('utf8','replace')[-5000:],flush=True)
except subprocess.TimeoutExpired: print('TIMEOUT',flush=True)
