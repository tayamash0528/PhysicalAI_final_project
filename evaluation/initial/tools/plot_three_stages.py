"""CPU-only PNG/SVG figures from the frozen three-stage analysis, no tuning."""
import argparse,csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

METHODS=[('no_reobserve','No additional observation','#2563eb'),('reobserve','Adaptive observation','#ea580c')]
def number(value):
    if value in [None,'','None','null']:return None
    return float(value)
def bounded(row,phase):
    value=number(row.get(f'wrist_visible_proxy_{phase}_bounded'))
    if value is None:
        raw=number(row.get(f'wrist_visible_proxy_{phase}'))
        value=None if raw is None else float(np.clip(raw,0,1))
    return value
def quality(row,phase):return row.get(f'visibility_quality_{phase}') not in ['False',False]
def save(fig,out,name):
    for ext in ['png','svg']:fig.savefig(out/f'{name}.{ext}',dpi=180)
    plt.close(fig)
def finish(fig,caption):
    fig.subplots_adjust(bottom=.25,top=.82,wspace=.24)
    fig.text(.02,.025,caption,ha='left',va='bottom',fontsize=8,wrap=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out');p.add_argument('--expect-n',type=int);a=p.parse_args()
    root=Path(a.root)
    if not (root/'summary.json').exists() and (root/'three_stage_analysis/summary.json').exists():root=root/'three_stage_analysis'
    summary=json.loads((root/'summary.json').read_text(encoding='utf-8-sig'))
    with (root/'trials.csv').open(encoding='utf-8-sig',newline='') as file:rows=list(csv.DictReader(file))
    out=Path(a.out) if a.out else root/'figures';out.mkdir(parents=True,exist_ok=True)
    groups={(g['occlusion'],g['method']):g for g in summary['groups']}
    if a.expect_n is not None:
        assert len(groups)==4 and all(g['trials']==a.expect_n for g in groups.values()),'Expected four equally sized clear/leaf method groups'
    fig,axes=plt.subplots(1,2,figsize=(11,4.8));x=np.arange(4);width=.34
    metrics=[('bilateral_contact_ever','Bilateral\ncontact'),('lift50mm','Lift\n>=50mm'),('grasp_success_50mm_2sec','Grasp:\nlift +2s hold'),('placement_success','Placement\nv2 +2s')]
    for ax,occ,title in zip(axes,['none','leaf_visual'],['Clear','Visual-only leaf']):
        present=False;counts=[]
        for j,(method,label,color) in enumerate(METHODS):
            group=groups.get((occ,method))
            if group is None:continue
            present=True;n=group['trials'];counts.append(f'{n} {label.lower()}')
            heights=[group[field]/n for field,_ in metrics];positions=x+(j-.5)*width
            ax.bar(positions,heights,width,color=color,label=label)
            for xx,h,(field,_) in zip(positions,heights,metrics):ax.text(xx,h+.025,f'{group[field]}/{n}',ha='center',fontsize=8)
        if not present:ax.text(.5,.5,'Not run / no trials',ha='center',transform=ax.transAxes)
        ax.set(xticks=x,xticklabels=[label for _,label in metrics],ylim=(0,1.19),ylabel='Fraction of all trials',title=title+' / '+('n='+str(groups.get((occ,'no_reobserve'),groups.get((occ,'reobserve'),{})).get('trials','N/A'))+' per method'))
        ax.spines[['top','right']].set_visible(False);ax.tick_params(axis='x',labelsize=8)
    handles,labels=next((ax.get_legend_handles_labels() for ax in axes if ax.get_legend_handles_labels()[0]),([],[]))
    fig.legend(handles,labels,loc='upper center',ncol=2,fontsize=9,frameon=False)
    finish(fig,'Contact is NOT grasp. Grasp = initial-center lift >=50mm plus bilateral contact continuously2s.\nPlacement is the executed v2 tray/open/2s predicate. Denominators include every success and failure.')
    save(fig,out,'stages_comparison')

    # Before/after within the adaptive method is not a between-method contrast.
    active=[r for r in rows if r['method']=='reobserve' and int(r['observation_steps'])>0]
    fig,ax=plt.subplots(figsize=(8.5,4.6));measured=0
    for i,row in enumerate(active):
        before=bounded(row,'initial');after=bounded(row,'after_observation')
        if before is None or after is None:
            ax.text(i,.04,'N/A',ha='center',fontsize=8);continue
        measured+=1;q=quality(row,'initial') and quality(row,'after_observation')
        ax.plot([i-.12,i+.12],[before,after],color='#94a3b8',linewidth=1,zorder=1)
        ax.scatter(i-.12,before,s=48,color='#64748b',alpha=1 if q else .35,label='Initial actual view' if measured==1 else None,zorder=2)
        ax.scatter(i+.12,after,s=48,color='#16a34a',alpha=1 if q else .35,label='After dedicated move' if measured==1 else None,zorder=2)
    ax.set(xticks=np.arange(len(active)),xticklabels=[r['case_id'] for r in active],ylim=(0,1.08),ylabel='Red-pixel visibility proxy [0,1]',title=f'Within adaptive observation: initial -> after move (measured {measured}/{len(active)})')
    if not active:ax.text(.5,.5,'No dedicated observation executed',ha='center',transform=ax.transAxes)
    elif not measured:ax.text(.5,.5,'No posthoc ratio sidecars measured yet',ha='center',transform=ax.transAxes)
    if measured:ax.legend(loc='best',fontsize=8)
    ax.spines[['top','right']].set_visible(False);ax.tick_params(axis='x',labelsize=8)
    finish(fig,'Red-pixel visibility proxy, NOT precise visible surface or placement success. Same-pose leaf-hidden reference is evaluation ONLY.\nRaw ratios remain in CSV; bounds apply to plotting/summary only. Faint points flag low reference/replay quality; no cases removed.\nThis within-method change is separate from the between-method comparison at shared frame45.')
    save(fig,out,'observation_within_active')

    fig,axes=plt.subplots(1,2,figsize=(11,4.8));width=.34
    for ax,occ,title in zip(axes,['none','leaf_visual'],['Clear','Visual-only leaf']):
        cases=sorted(set(r['case_id'] for r in rows if r['occlusion']==occ));x=np.arange(len(cases));hasdata=False
        for j,(method,label,color) in enumerate(METHODS):
            for i,case in enumerate(cases):
                row=next((r for r in rows if r['case_id']==case and r['method']==method),None)
                if row is None:continue
                value=bounded(row,'matched45');xx=i+(j-.5)*width
                if value is None:ax.text(xx,.04,'N/A',ha='center',fontsize=7,rotation=90);continue
                hasdata=True;q=quality(row,'matched45')
                ax.bar(xx,value,width,color=color,alpha=1 if q else .35,hatch=None if q else '//',label=label if i==0 else None)
        if not cases:ax.text(.5,.5,'Not run / no trials',ha='center',transform=ax.transAxes)
        elif not hasdata:ax.text(.5,.5,'Matched-time ratios not measured',ha='center',transform=ax.transAxes)
        ax.set(xticks=x,xticklabels=cases,ylim=(0,1.08),ylabel='Red-pixel visibility proxy [0,1]',title=f'{title}: matched frame45 / {len(cases)} paired cases')
        ax.tick_params(axis='x',labelrotation=20,labelsize=8);ax.spines[['top','right']].set_visible(False)
    fig.legend([plt.Rectangle((0,0),1,1,color=color) for _,_,color in METHODS],[label for _,label,_ in METHODS],loc='upper center',ncol=2,fontsize=9,frameon=False)
    finish(fig,'Same elapsed simulation time: frame45=2.25s. Normal VLA/camera motion and live image updates are enabled in BOTH methods.\nRed-pixel proxy uses posthoc same-camera leaf-hidden references, never policy input. N/A is unmeasured, not zero.\nFaint/hatched bars flag low reference/replay quality; raw values and every case remain in CSV. Intervention includes pose and images.')
    save(fig,out,'observation_matched45')
    (out/'FIGURE_NOTES.json').write_text(json.dumps({'analysis_version':summary['definitions']['analysis_version'],'source_analysis':str(root),'model_or_simulator_called':False,'denominators':[{k:g[k] for k in ['occlusion','method','trials']} for g in summary['groups']],
        'visibility_label':'Red-pixel visibility proxy','contact_not_grasp':True,'grasp_definition':'50mm lift +2s continuous bilateral hold','placement_definition':'Executed v2 tray/open/2s predicate','missing_visibility_never_zero_filled':True},indent=2))
    print(json.dumps({'figures':str(out),'source_trials':len(rows),'outputs':['stages_comparison','observation_within_active','observation_matched45']}))

if __name__=='__main__':main()
