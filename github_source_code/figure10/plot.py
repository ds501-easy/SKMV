#!/usr/bin/env python3
from pathlib import Path
import csv,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator,LogFormatterMathtext,NullLocator,FuncFormatter
import argparse,gzip
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Analyze saved or replayed estimates and draw Figure 10.')
parser.add_argument('--data',type=Path,default=ROOT/'data')
parser.add_argument('--output',type=Path,default=ROOT/'outputs')
args=parser.parse_args();DATA=args.data;OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
FIG=OUT/'figure10'
layout_rows={int(r['budget_bits']):r for r in csv.DictReader((ROOT/'data/layouts.csv').open())}
def open_raw(b):
 p=DATA/f'raw_{b}.csv'
 return p.open() if p.exists() else gzip.open(str(p)+'.gz','rt')
BUDGETS=[1000,5000,10000,50000,1000000,5000000]
ALGS=['Sliding HLL','Sliding KMV','Elastic S-KMV','VATE-LC','T-FM']
COLORS=['#2356a0','#b42b35','#21815b','#333333','#9a5aab']
MARKERS=['o','D','^','s','v'];STYLES=['--','-','-.',':',(0,(4,1,1,1))]
ns=np.array([int(np.floor(10**(3+j/20)+.5)) for j in range(81)])
Q=9; summary=[];audit={}; groups={};layouts=[]
rng=np.random.default_rng(2026101301)
for b in BUDGETS:
 TRIALS=100 if b==1000 else 20
 # Resample whole trials: the nine queries in each share sketch history.
 bs=rng.integers(0,TRIALS,(2000,TRIALS))
 layout=layout_rows[b]
 expected_m={a:int(layout[k]) for a,k in zip(ALGS,['hll_m','skmv_m','elastic_m','vate_m','tfm_m'])}
 assert int(layout['kmv_hash_bits'])==32 and int(layout['hll_rank_bits'])==5
 with open_raw(b) as f:rows=list(csv.DictReader(f))
 assert len(rows)==81*TRIALS*Q*5,(b,len(rows))
 values={a:np.full((81,TRIALS,Q),np.nan) for a in ALGS};saturation={a:np.zeros((81,TRIALS,Q),bool) for a in ALGS}
 ni={int(n):i for i,n in enumerate(ns)};peak=0
 for r in rows:
  n=int(r['cardinality']);t=int(r['trial'])-50;q=int(r['query']);a=r['algorithm'];v=float(r['estimate'])
  assert int(r['budget_bits'])==b and int(r['allocated_bits'])==b//64*64
  assert int(r['m'])==expected_m[a] and int(r['k'])==(int(layout['k']) if a=='Sliding KMV' else int(layout['elastic_k']) if a=='Elastic S-KMV' else 0)
  assert int(r['time'])==99+25*q and int(r['wrapped_time'])==int(r['time'])%256
  assert np.isnan(values[a][ni[n],t,q]) and np.isfinite(v) and v>=0
  assert int(r['hll_peak'])<=int(r['hll_capacity']);peak=max(peak,int(r['hll_peak']))
  if int(r['saturated']):assert a=='VATE-LC' and np.isclose(v,int(r['m'])*np.log(int(r['m'])),rtol=1e-13)
  values[a][ni[n],t,q]=v/n-1;saturation[a][ni[n],t,q]=int(r['saturated'])!=0
 for a in ALGS:
  assert np.isfinite(values[a]).all()
  # Pool squared relative errors first, then take the root (RRMSE).
  err=values[a];pertrial=(err**2).mean(axis=2);rmse=np.sqrt(pertrial.mean(axis=1))
  interval=np.quantile(np.sqrt(pertrial[:,bs].mean(axis=2)),[.025,.975],axis=1)
  groups[b,a]=(rmse,interval[0],interval[1])
  for i,n in enumerate(ns):summary.append({'budget_bits':b,'algorithm':a,'cardinality':int(n),'trials':TRIALS,'queries_per_trial':Q,'relative_rmse':rmse[i],'ci_low':interval[0,i],'ci_high':interval[1,i],'relative_bias':err[i].mean(),'relative_mae':np.abs(err[i]).mean(),'saturation_fraction':saturation[a][i].mean()})
 audit[str(b)]={'raw_rows':len(rows),'hll_peak':peak,'hll_capacity':int(rows[0]['hll_capacity'])}
 layouts.append(layout)
for name,records in [('summary.csv',summary),('layouts.csv',layouts)]:
 with (OUT/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
plt.rcParams.update({'font.family':'STIXGeneral','mathtext.fontset':'stix','font.size':8,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'pdf.fonttype':42,'ps.fonttype':42,'axes.linewidth':.55,'xtick.direction':'in','ytick.direction':'in'})
fig,axs=plt.subplots(2,3,figsize=(7.05,3.45),sharex=True,sharey=False)
fig.subplots_adjust(left=.078,right=.988,bottom=.16,top=.92,hspace=.42,wspace=.24)
for j,(b,ax) in enumerate(zip(BUDGETS,axs.flat)):
 ymin=0.0
 ymax=[1.0,.30,.20,.08,.025,.01][j]
 for ai,a in enumerate(ALGS):
  y,lo,hi=groups[b,a]
  ax.fill_between(ns,lo,hi,color=COLORS[ai],alpha=.09,lw=0)
  ax.plot(ns,y,color=COLORS[ai],ls=STYLES[ai],lw=.95,marker=MARKERS[ai],markevery=10,ms=2.5,mfc='white',mew=.65,label=a,clip_on=True)
  # Mark every crossing of the visible upper limit without capping data.
  for i in np.flatnonzero((y[:-1]>ymax)!=(y[1:]>ymax)):
   fraction=(ymax-y[i])/(y[i+1]-y[i])
   x=np.exp(np.log(ns[i])+fraction*(np.log(ns[i+1])-np.log(ns[i])))
   ax.plot(x,ymax,marker='^',ms=3.5,color=COLORS[ai],mew=.5,clip_on=False,zorder=5)
 ax.set_xscale('log');ax.set_yscale('linear')
 ax.set_xlim(900,1.12e7);ax.set_ylim(ymin,ymax)
 ax.xaxis.set_major_locator(FixedLocator([1e3,1e4,1e5,1e6,1e7]));ax.xaxis.set_major_formatter(LogFormatterMathtext());ax.xaxis.set_minor_locator(NullLocator())
 ticks=np.linspace(0,ymax,[5,4,5,5,6,6][j]);ax.yaxis.set_major_locator(FixedLocator(ticks));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v:g}'));ax.yaxis.set_minor_locator(NullLocator())
 ax.tick_params(length=2,pad=2,labelbottom=True)
 ax.grid(axis='y',color='#dddddd',lw=.35,zorder=0)
 label=f'{b//1000} kbit' if b<1000000 else f'{b//1000000} Mbit'
 ax.text(.5,-.21,f'({chr(97+j)}) {label}, $k_S/k_E={layouts[j]["k"]}/{layouts[j]["elastic_k"]}$',transform=ax.transAxes,ha='center',va='top',fontsize=8,color='black')
 if j%3==0:ax.set_ylabel('Relative RMSE',labelpad=3)
fig.text(.53,.018,'Window cardinality',ha='center',fontsize=8)
handles=[Line2D([0],[0],color=c,ls=s,marker=m,ms=3,mfc='white',mew=.7,lw=.95,label=a) for a,c,m,s in zip(ALGS,COLORS,MARKERS,STYLES)]
fig.legend(handles=handles,ncol=5,loc='upper center',bbox_to_anchor=(.54,.999),frameon=False,handlelength=2.0,handletextpad=.4,columnspacing=1.0,fontsize=8)
for ext in ('pdf','svg','png'):fig.savefig(str(FIG)+'.'+ext,dpi=400)
plt.close(fig)
report={'selection_tolerance':0.10,'processing_tolerance':0.10,'policy':'choose minimum-error k when its median time <= 1.10 times practical k time, otherwise choose practical k','selection_trials':[0,49],'measurement_trial_offset':50,'selected_k':{r['budget_bits']:int(r['k']) for r in layouts},'elastic_k':{r['budget_bits']:int(r['elastic_k']) for r in layouts},'elastic_rule':'maximize occupied layout bits within k_S +/- 2; ties prefer nearest k_S then smaller k; no accuracy tuning','kmv_hash_bits':32,'hll_rank_bits':5,'hll_rank_cap':31,'window_slots':100,'budgets_bits':BUDGETS,'cardinalities':ns.tolist(),'trials_per_budget':{str(b):100 if b==1000 else 20 for b in BUDGETS},'queries_per_trial':Q,'raw_rows':sum((100 if b==1000 else 20)*5*len(ns)*Q for b in BUDGETS),'bootstrap_repetitions':2000,'checks':audit,'error_axis':'linear, dimensionless relative RMSE; zero lower bound','line_smoothing':'none','vertical_limits':dict(zip(map(str,BUDGETS),[1.0,.30,.20,.08,.025,.01])),'overflow_markers':'upward triangles at mean-curve upper-bound crossings; data are not capped'}
(OUT/'validation_summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

