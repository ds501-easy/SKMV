"""Draw Figure 12 from the paired dynamic-rate summaries."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator, FuncFormatter

D=Path(__file__).resolve().parent
import argparse
parser=argparse.ArgumentParser(description='Draw Figure 12 from curve summaries.')
parser.add_argument('--data',type=Path,default=D/'data')
parser.add_argument('--output',type=Path,default=D/'outputs')
args=parser.parse_args();F=args.output;F.mkdir(parents=True,exist_ok=True)
budgets=[1000,50000]
curves={b:json.loads((args.data/f'curves_{b}.json').read_text()) for b in budgets}
base_settings={'relative_rmse_ylim':{'1000':[0,2],'50000':[0,.2]}}
limits={}
for b in budgets:
    max_ci=max(p['ci_high'] for p in curves[b])
    scale=10**np.floor(np.log10(max_ci))
    upper=float(np.ceil(max_ci*1.08/scale*2)/2*scale)
    limits[b]=[0,max(upper,base_settings['relative_rmse_ylim'][str(b)][1])]
# Match the requested display range without changing the measured estimates.
limits[1000]=[0,2]
clipped_points=[]
plt.rcParams.update({'font.family':'STIXGeneral','mathtext.fontset':'stix',
    'font.size':8,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,
    'pdf.fonttype':42,'ps.fonttype':42,'axes.linewidth':.55,
    'xtick.direction':'in','ytick.direction':'in'})
fig,axes=plt.subplots(3,3,figsize=(7.05,2.90),sharex='col',
                     gridspec_kw={'height_ratios':[.30,1,1]})
fig.subplots_adjust(left=.095,right=.99,bottom=.145,top=.92,hspace=.14,wspace=.25)
# Double only the workload plane; retain all other physical heights and gaps.
base_height=2.90
positions=[[ax.get_position().frozen() for ax in row] for row in axes]
added_height=positions[0][0].height*base_height
figure_height=base_height+added_height
fig.set_size_inches(7.05,figure_height)
for row in range(3):
    for col in range(3):
        p=positions[row][col]
        axes[row,col].set_position([p.x0,p.y0*base_height/figure_height,
            p.width,p.height*base_height/figure_height*(2 if row==0 else 1)])
for col,(pattern,windows,title) in enumerate([
        ('drop',512,'Permanent decrease'),('rise',128,'Permanent increase'),
        ('cycle',512,'Repeated rate changes')]):
    w=np.arange(1,windows+1)
    high=w<=20 if pattern=='drop' else w>4 if pattern=='rise' else ((w-1)//64)%2==0
    top=axes[0,col]
    top.step(w,np.where(high,1e6,62500),where='mid',color='#333333',lw=.8)
    top.set_yscale('log');top.set_ylim(40000,1600000)
    top.yaxis.set_major_locator(FixedLocator([62500,1000000]))
    top.set_yticklabels([r'$6.25\!\times\!10^4$',r'$10^6$'] if col==0 else [])
    top.yaxis.set_minor_locator(NullLocator())
    if col==0:top.set_ylabel('True $n$',labelpad=2)
    for row,budget in enumerate(budgets,1):
        ax=axes[row,col]
        for alg,color,ls in [('S-KMV','#c9272c','-'),('Elastic S-KMV','#2456b3','--'),('Sliding HLL','#168568','-.'),('T-FM','#9b53b3',':')]:
            r=[p for p in curves[budget] if p['pattern']==pattern and p['algorithm']==alg]
            x=np.array([p['window'] for p in r])
            y=np.array([p['rmse'] for p in r])
            lo=np.array([p['ci_low'] for p in r]);hi=np.array([p['ci_high'] for p in r])
            ax.plot(x,y,color=color,ls=ls,lw=1.0,label=alg,zorder=3)
            ax.fill_between(x,lo,hi,color=color,alpha=.10,lw=0,zorder=2)
            above=y>limits[budget][1]
            if np.any(above):
                ax.plot(x[above],np.full(np.sum(above),limits[budget][1]),
                        ls='none',marker='^',ms=4,color=color,clip_on=False,zorder=5)
                clipped_points.extend({'memory_bits':budget,'pattern':pattern,
                    'algorithm':alg,'window':float(xx),'rmse':float(yy)}
                    for xx,yy in zip(x[above],y[above]))
        ax.set_ylim(*limits[budget])
        ax.set_yticks(np.linspace(*limits[budget],3))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v:g}'))
        ax.grid(axis='y',color='#ddd',lw=.3)
        if col==0:ax.set_ylabel(f'Relative RMSE\n({budget//1000} kbit)',labelpad=3)
    axes[-1,col].set_xlabel('Completed windows',labelpad=2)
    axes[-1,col].set_xlim(1,windows)
    axes[-1,col].set_xticks([20,128,256,384,512] if pattern=='drop' else [1,128,256,384,512] if windows==512 else [1,32,64,96,128])
    for ax in axes[:,col]:
        ax.tick_params(length=2,pad=2)
        for change in ([20.5] if pattern=='drop' else [4.5] if pattern=='rise' else np.arange(64.5,512,64)):
            ax.axvline(change,color='#888',ls=':',lw=.5,zorder=1)
    pos=axes[-1,col].get_position()
    fig.text((pos.x0+pos.x1)/2,.02*base_height/figure_height,f'({chr(97+col)}) {title}',
             ha='center',va='center',fontsize=8,color='black')
h,l=axes[1,0].get_legend_handles_labels()
fig.legend(h,l,loc='upper center',bbox_to_anchor=(.55,1.0),ncol=4,
           frameon=False,columnspacing=1.0,handlelength=2.5,handletextpad=.5,
           borderaxespad=0)
for ext in ['pdf','svg','png']:
    fig.savefig(F/f'figure12.{ext}',dpi=400)
settings={'size_inches':[7.05,figure_height],'one_shared_legend':True,
          'one_shared_cardinality_row':True,'memory_rows_bits':budgets,
          'relative_rmse_ylim':limits,'above_range_points':clipped_points,
          'plot_row_heights_inches':[float(axes[i,0].get_position().height*figure_height) for i in range(3)],
          'workload_row_height_multiplier':2, 'error_row_heights_unchanged':True,
          'drop_high_epochs':20, 'drop_first_low_epoch':21,
          'algorithms':['S-KMV','Elastic S-KMV','Sliding HLL','T-FM'],
          'kmv_curves_exactly_reused':True, 'paired_seeds':60}
(F/'figure_settings.json').write_text(json.dumps(settings,indent=2)+'\n')
plt.close(fig)
