import csv, zipfile
from pathlib import Path
p=Path(__file__).parent
with (p/'iladata.csv').open(newline='') as f:
 r=csv.reader(f); header=next(r); next(r)
 a=[[int(v,10 if i<3 else 16) for i,v in enumerate(row)] for row in r]
with zipfile.ZipFile(p/'iladata.ila') as z:
 print('native_csv_identical',z.read('waveform.csv')==(p/'iladata.csv').read_bytes())
print('samples',len(a),'trigger',[i for i,r in enumerate(a) if r[2]])
print('fault_low12',sorted(set(r[58]+(r[59]<<9)+(r[60]<<10) for r in a)))
print('format_error_samples',[i for i,r in enumerate(a) if r[17]])
print('commit_samples',[i for i,r in enumerate(a) if r[16]])
for j in range(1,len(a)):
 if a[j-1][4]==1 and a[j][4]==0:
  end=next((k for k in range(j+1,len(a)) if a[k][4]==1),len(a))
  rises=[k for k in range(j+1,end) if a[k-1][5]==0 and a[k][5]==1]
  bits=[''.join(str(a[k][col]) for k in rises) for col in [6,7]]
  print('transaction',j,end,'complete',end<len(a),'rises',len(rises),'MOSI_bits',bits[0],'MISO_bits',bits[1])
for k in [2698,2699,6378,6379]:
 r=a[k]; print('load',k,'address',hex(r[13]+(r[14]<<3)),'txD',hex(sum(r[22+b]<<b for b in range(32))),'txQ',hex(r[55]+(r[56]<<31)),'pending',r[54])
