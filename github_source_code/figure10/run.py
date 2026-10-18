#!/usr/bin/env python3
"""Build a portable C++17 replay and reproduce or smoke-test this experiment."""
from pathlib import Path
import argparse,csv,gzip,math,os,shlex,subprocess
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
g=p.add_mutually_exclusive_group(required=True)
g.add_argument('--smoke',action='store_true',help='Replay a small original-data subset and compare every estimate.')
g.add_argument('--full',action='store_true',help='Replay the full original workload; this can take hours.')
p.add_argument('--output',type=Path,default=ROOT/'outputs')
p.add_argument('--cxx',default=os.environ.get('CXX','c++'))
args=p.parse_args()
build=ROOT/'build';build.mkdir(exist_ok=True)
exe=build/'replay'
subprocess.run(shlex.split(args.cxx)+['-O3','-std=c++17',str(ROOT/'src/replay.cpp'),'-o',str(exe)],check=True)
out=args.output/('smoke' if args.smoke else 'replay');out.mkdir(parents=True,exist_ok=True)
def load(path):
 with (gzip.open(path,'rt') if str(path).endswith('.gz') else path.open()) as f:
  return list(csv.DictReader(f))
def same(a,b,fields):
 for key in fields:
  if not math.isclose(float(a[key]),float(b[key]),rel_tol=1e-11,abs_tol=1e-10):
   raise AssertionError(f'Mismatch in {key}: replay={a[key]}, reference={b[key]}')
def execute(command,target):
 if target.exists():raise FileExistsError(f'Refusing to overwrite {target}; choose another --output directory.')
 subprocess.run(command,check=True)

layouts=load(ROOT/'data/layouts.csv')
verified=0
for row in layouts:
 b=int(row['budget_bits']);target=out/f'raw_{b}.csv'
 trials=1 if args.smoke else (100 if b==1000 else 20)
 command=[str(exe),str(b),row['hll_m'],row['k'],row['elastic_k'],str(trials),'50','0' if args.smoke else '-1',str(target)]
 execute(command,target)
 if args.smoke:
  ref={(r['algorithm'],r['trial'],r['query']):r for r in load(ROOT/f'data/raw_{b}.csv.gz') if r['cardinality']=='1000' and r['trial']=='50'}
  rows=load(target);assert len(rows)==len(ref)==45
  for r in rows:
   z=ref[(r['algorithm'],r['trial'],r['query'])]
   same(r,z,['estimate','m','k','allocated_bits','time','wrapped_time','saturated'])
   verified+=1
print(f'PASS: {verified} replayed queries match the saved data.' if args.smoke else f'Full replay complete: {out}')
