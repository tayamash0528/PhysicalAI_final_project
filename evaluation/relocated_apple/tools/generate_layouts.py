"""Outcome-blind deterministic positions inside the already evaluated workspace."""
import datetime,hashlib,json
from pathlib import Path
import numpy as np
BASE=Path('evaluation/relocated_apple')
plan=json.loads((BASE/'PLAN.json').read_text());audit_path=BASE/'position_audit/used_positions.json';audit=json.loads(audit_path.read_text())
used=np.asarray([r['xy_m'] for r in audit['positions']],dtype=float);assert used.ndim==2 and used.shape[1]==2 and len(used)>0
cfg=plan['position_generation'];bounds=plan['xy_bounds_m'];rng=np.random.default_rng(cfg['pool_seed'])
pool=np.column_stack([rng.uniform(*bounds['x'],cfg['candidate_pool_size']),rng.uniform(*bounds['y'],cfg['candidate_pool_size'])]);pool=np.unique(np.round(pool/cfg['rounding_m'])*cfg['rounding_m'],axis=0)
nearest=np.sqrt(((pool[:,None,:]-used[None,:,:])**2).sum(axis=2)).min(axis=1);base_dist=nearest.copy();selected=[]
for i in range(plan['case_count_fixed_before_results']):
    j=int(np.argmax(nearest));point=pool[j].copy();distance=float(nearest[j]);assert distance>=cfg['minimum_distance_from_used_and_new_m'],('Not enough geometrically separated unused points',i,distance)
    selected.append({'case_id':f'new_leaf_{i:02d}','xy_m':point.tolist(),'nearest_previously_recorded_position_m':float(base_dist[j]),'nearest_used_or_already_selected_m':distance,'seed':plan['trial_seed_base']+i})
    nearest=np.minimum(nearest,np.linalg.norm(pool-point,axis=1))
out=BASE/'NEW_POSITIONS.json';assert not out.exists()
out.write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'positions':selected,'algorithm':cfg,'bounds_m':bounds,'position_audit_file':str(audit_path),'position_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),'new_trial_outcomes_seen':False,'old_or_new_outcomes_used_for_selection':False,'pretraining_data_overlap_unknown':True},indent=2)+'\n')
print(json.dumps({'fixed_positions':selected,'position_count':len(selected)}))
