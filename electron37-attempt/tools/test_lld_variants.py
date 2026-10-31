import json,os,subprocess,sys
j=json.load(open('/work/electron37-attempt/tools/printed-lldcmd.json')); base=j['argv']
# run exact and variants. Remove output old.
variants={}
variants['exact']=base
# change output target
for name,drop in [('norust',set(range(94,190))),('rustonly',set(range(18,94))),('nocrt',set(range(18,94))),('nolibs',set(range(45,190)))]:
 a=[x for i,x in enumerate(base) if i not in drop]
 # Remove end group marker if no rust
 variants[name]=a
for name,a in variants.items():
 a=list(a); 
 if '-o' in a: a[a.index('-o')+1]=f'./electron-{name}'
 print('====',name,len(a),flush=True)
 try:
  r=subprocess.run(a,env=os.environ,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=40)
  print('status',r.returncode,'out',r.stdout[-3000:].decode('utf8','replace'),flush=True)
 except subprocess.TimeoutExpired as e:
  print('TIMEOUT',flush=True)
