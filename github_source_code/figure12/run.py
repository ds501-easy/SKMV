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

verified=0
for b in [1000,50000]:
 schedules=[('rise',8)] if args.smoke else [('drop',512),('rise',128),('cycle',512)]
 for pattern,windows in schedules:
  target=out/f'{pattern}_{b}.csv'
  command=[str(exe),pattern,str(windows),'4000','1' if args.smoke else '60',str(target),str(b)]
  execute(command,target)
  if args.smoke:
   ref={(r['seed'],r['window']):r for r in load(ROOT/f'data/{pattern}_{b}.csv.gz') if r['seed']=='4000' and int(r['window'])<=windows}
   rows=load(target);assert len(rows)==len(ref)==windows
   for r in rows:
    same(r,ref[(r['seed'],r['window'])],['truth','skmv_estimate','elastic_estimate','hll_estimate','tfm_estimate','hll_used','hll_peak','hll_capacity','hll_registers','tfm_registers','allocated_bits'])
    verified+=1
if args.smoke:
 validator=build/'validate_baselines'
 subprocess.run(shlex.split(args.cxx)+['-O3','-std=c++17',str(ROOT/'src/validate_baselines.cpp'),'-o',str(validator)],check=True)
 subprocess.run([str(validator)],check=True)
print(f'PASS: {verified} paired query rows match saved data.' if args.smoke else f'Full replay complete: {out}')
