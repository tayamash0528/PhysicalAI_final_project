"""Bounded 12-layout collection; evaluation locations are reserved before collection."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
reserved=[[-.1190442533,.2262070835],[-.1158592701,.2196100864],
          [-.14,.12],[-.11,.13],[-.135,.18],[-.105,.22],[-.14,.235],
          [-.13,.115],[-.1,.175],[-.145,.215],[-.115,.24],[-.097,.23]]
train=[{'id':f'train_{i:02d}','seed':1200+i,'apple_xy':[x,y],'tray_xy':[.04,.15]}
       for i,(x,y) in enumerate(( (x,y) for x in [-.15,-.12,-.09] for y in [.10,.15,.20,.25]))]
for c in train:
    assert min(np.linalg.norm(np.array(c['apple_xy'])-p) for p in reserved)>.004
plan={'status':'training_and_evaluation_locations_fixed_before_collection',
      'train':train,'reserved_evaluation_xy':reserved,'attempt_cap':12,
      'teacher_control':'GT-position compact servo, never counted as VLA success',
      'evaluation_policy_inputs':'RGB/state/instruction only; no target truth',
      'main_comparison':'occluder/camera settings to be frozen before main comparison; layouts reserved now'}
(out/'collection_plan.json').write_text(json.dumps(plan,indent=2))
accepted=[];attempts=[];start=time.perf_counter()
for c in train:
    folder=out/c['id'];cmd=[sys.executable,'scripts/diagnose_physical_grasp.py',
      '--initial-state','training/seed_state/initial_sim_state.npy',
      '--seed',str(c['seed']),'--apple-xy',*map(str,c['apple_xy']),'--tray-xy',*map(str,c['tray_xy']),
      '--place','--compact','--save-dataset','--out',str(folder)]
    with (out/(c['id']+'.log')).open('w') as log:
        proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    result={'id':c['id'],'return_code':proc.returncode,'success':False,'dataset_valid':False}
    if proc.returncode==0 and (folder/'result.json').exists():
        r=json.loads((folder/'result.json').read_text());result['success']=r['teacher_placement_success']
        if (folder/'teacher_episode.npz').exists():
            d=np.load(folder/'teacher_episode.npz');n=d['state'].shape[0]
            result['dataset_valid']=d['state'].shape==(n,8) and d['action'].shape==(n,7) and bool(np.isfinite(d['action']).all())
            result['frames']=n;d.close()
        if result['success'] and result['dataset_valid']:accepted.append(str(folder/'teacher_episode.npz'))
    attempts.append(result)
    (out/'collection_results.json').write_text(json.dumps({'attempts':attempts,'accepted':accepted,
        'count_success':len(accepted),'wall_seconds':time.perf_counter()-start},indent=2))
    print(json.dumps(result),flush=True)
    if len(attempts)>=3 and all(not r['success'] for r in attempts[-3:]):
        print('Three consecutive failures; stop collection for diagnosis.',flush=True);break
(out/'dataset_list.json').write_text(json.dumps({'episodes':accepted,'evaluation_locations':reserved,
       'success_count':len(accepted),'split':'train'},indent=2))
if not accepted:raise RuntimeError('No verified successful teacher episodes')
