"""Paired four-method analysis, reusing Figure 12's exact KMV observations."""
from pathlib import Path
import csv,json,hashlib,sys
import numpy as np
D=Path(__file__).resolve().parent
import argparse,gzip
parser=argparse.ArgumentParser(description='Recompute the 60-seed Figure 12 statistics.')
parser.add_argument('--data',type=Path,default=D/'data')
parser.add_argument('--output',type=Path,default=D/'outputs')
parser.add_argument('--memory',type=int,choices=[1000,50000],required=True)
args=parser.parse_args();b=args.memory;O=args.output;O.mkdir(parents=True,exist_ok=True)
algorithms=['S-KMV','Elastic S-KMV','Sliding HLL','T-FM']
keys=['skmv_estimate','elastic_estimate','hll_estimate','tfm_estimate']
# Bootstrap complete seed trajectories together across all four methods.
# Queries within a seed share sketch history and are not independent trials.
rng=np.random.default_rng(20261018);ix=rng.integers(0,60,(2000,60))
curves=[];scores=[];checks={};hashes={};peak=0
for pattern,windows in [('drop',512),('rise',128),('cycle',512)]:
 path=args.data/f'{pattern}_{b}.csv'
 if path.exists():
  with path.open() as f:rows=list(csv.DictReader(f))
 else:
  path=Path(str(path)+'.gz')
  with gzip.open(path,'rt') as f:rows=list(csv.DictReader(f))
 expected={(s,w) for s in range(4000,4060) for w in range(1,windows+1)}
 assert len(rows)==len(expected) and {(int(v['seed']),int(v['window'])) for v in rows}==expected
 for v in rows:
  assert v['pattern']==pattern
  assert int(v['hll_registers'])==(4 if b==1000 else 256)
  assert int(v['tfm_registers'])==(3 if b==1000 else 173)
  assert int(v['allocated_bits'])==b//64*64
  assert 0<=int(v['hll_used'])<=int(v['hll_peak'])<=int(v['hll_capacity'])
  peak=max(peak,int(v['hll_peak']))
 hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
 rows.sort(key=lambda v:(int(v['seed']),int(v['window'])))
 w=np.arange(1,windows+1)
 def arr(k):return np.array([float(v[k]) for v in rows]).reshape(60,windows)
 truth=arr('truth');high=w<=20 if pattern=='drop' else w>4 if pattern=='rise' else ((w-1)//64)%2==0
 assert np.all(truth==np.where(high,1000000,62500))
 est=np.stack([arr(k) for k in keys],axis=2);assert np.isfinite(est).all() and (est>=0).all()
 err=est/truth[:,:,None]-1
 # Pool squared relative errors within each displayed time group, then take
 # the square root. Grouping does not smooth or replace the stored estimates.
 if pattern=='drop':groups=[np.arange(a,a+4) for a in range(0,20,4)]+[np.arange(a,min(a+8,windows)) for a in range(20,windows,8)]
 else:groups=[np.arange(a,min(a+4,windows)) for a in range(0,windows,4)]
 for g in groups:
  mse=np.mean(err[:,g,:]**2,axis=1);rmse=np.sqrt(mse.mean(axis=0));dist=np.sqrt(mse[ix].mean(axis=1));lo,hi=np.quantile(dist,[.025,.975],axis=0)
  for j,alg in enumerate(algorithms):
   record={'pattern':pattern,'algorithm':alg,'first_window':int(g[0]+1),'last_window':int(g[-1]+1),'window':float(np.mean(g+1)),'rmse':float(rmse[j]),'ci_low':float(lo[j]),'ci_high':float(hi[j])}
   curves.append(record)
 if pattern=='drop':phases={'initial':w<=20,'late':w>=385}
 elif pattern=='rise':phases={'initial':w<=4,'late':w>=97}
 else:phases={'all':w>0,'late_high':(w>256)&high&(((w-1)%64)>=48),'late_low':(w>256)&~high&(((w-1)%64)>=48)}
 for phase,mask in phases.items():
  ee=err[:,mask,:];mse=np.mean(ee**2,axis=1);rmse=np.sqrt(mse.mean(axis=0));dist=np.sqrt(mse[ix].mean(axis=1));lo,hi=np.quantile(dist,[.025,.975],axis=0)
  for j,alg in enumerate(algorithms):
   scores.append({'pattern':pattern,'phase':phase,'algorithm':alg,'queries_per_seed':int(mask.sum()),'rmse':float(rmse[j]),'ci_low':float(lo[j]),'ci_high':float(hi[j]),'relative_bias':float(ee[:,:,j].mean()),'paired_rmse_difference_vs_elastic_ci':np.quantile(dist[:,j]-dist[:,1],[.025,.975]).tolist()})
 checks[pattern]={'paired_query_positions':len(rows),'seeds':60,'windows':windows,'true_cardinality_verified':True,'finite_estimates_and_valid_memory':True}
report={'status':'PASS','budget_bits':b,'patterns':checks,'hll_peak':peak,'hll_capacity':48 if b==1000 else 1964,'raw_source_sha256':hashes}
for name,value in [('curves',curves),('scores',scores),('validation',report)]:
 (O/f'{name}_{b}.json').write_text(json.dumps(value,indent=2)+'\n')
with (O/f'curves_{b}.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=curves[0]);writer.writeheader();writer.writerows(curves)
for v in scores:
 if v['phase'] in ['late','late_low']:print(b,v['pattern'],v['phase'],v['algorithm'],f"{v['rmse']:.6f}")
print('PASS maximum HLL history usage',peak,'/',report['hll_capacity'])
