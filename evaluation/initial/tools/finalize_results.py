"""CPU-only qualified results. Preserve the raw analysis and all failed cases."""
import csv,datetime,hashlib,json
from pathlib import Path
BASE=Path('evaluation/initial');MAIN=BASE/'main_comparison';AN=MAIN/'three_stage_analysis'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def true(v):return v is True or str(v)=='True'
lock=read(MAIN/'LOCK.json');execution=read(MAIN/'execution_status.json');post=read(BASE/'postprocessing_status.json')
assert execution['return_code']==post['return_code']==0
assert sha(MAIN/'LOCK.json')==execution['protocol_sha256']
for k in ('source_sha256','asset_sha256'):
    for p,h in lock[k].items():assert sha(p)==h,p
assert sha(lock['delta'])==lock['delta_sha256']
assert sha(lock['evaluation_spec_file'])==lock['evaluation_spec_sha256']
raw=read(AN/'summary.json');assert raw['trials']==20 and len(raw['pairs'])==10
with (AN/'trials.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
with (MAIN/'drop_candidate_review/manual_review.csv').open(encoding='utf-8-sig') as f:reviews=list(csv.DictReader(f))
assert all(x['manual_review_status']!='unreviewed' and x['confirmed_drop'] for x in reviews)
confirmed={x['episode'] for x in reviews if true(x['confirmed_drop'])}
for r in rows:
    valid=true(r['visibility_quality_initial']) and true(r['visibility_quality_after_observation']) and int(r['observation_steps'])>0
    r['strict_proxy_gain_evaluable']=valid
    r['strict_proxy_gain_ge_0p20']=true(r['observation_proxy_gain_ge_0p20']) if valid else None
    r['confirmed_drop_trial']=r['episode'] in confirmed
    r['confirmed_drop_review']='drop_candidate_review/manual_review.csv' if r['episode'] in confirmed else ''
with (MAIN/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
groups=[]
for g in raw['groups']:
    g=dict(g);ss=[r for r in rows if r['occlusion']==g['occlusion'] and r['method']==g['method']]
    g['raw_proxy_gain_ge_0p20']=g.pop('observation_proxy_gain_ge_0p20')
    g['raw_proxy_gain_available_trials']=g.pop('observation_proxy_gain_measured_trials')
    valid=[r for r in ss if r['strict_proxy_gain_evaluable']]
    g['strict_proxy_gain_evaluable_trials']=len(valid)
    g['strict_proxy_gain_ge_0p20']=sum(true(r['strict_proxy_gain_ge_0p20']) for r in valid) if valid else None
    g['actual_wrist_red_ge200_initial']=sum(true(r['red_evidence_initial']) for r in ss)
    g['actual_wrist_red_ge200_matched45']=sum(true(r['red_evidence_matched45']) for r in ss)
    g['actual_wrist_red_ge200_after_observation']=sum(int(r['wrist_red_after_observation'])>=200 for r in ss if r['wrist_red_after_observation'])
    g['confirmed_drop_trials']=sum(r['confirmed_drop_trial'] for r in ss)
    for k in ('observation_wall_seconds','manipulation_wall_seconds','wall_seconds_including_reset'):
        values=[float(r[k]) for r in ss if r[k]];g[k+'_mean']=sum(values)/len(values) if values else None
    groups.append(g)
video=read(BASE/'materials/video_validation.json');assert video['all_full_decodes_passed']
assert sum(x['role']=='VLA_main' for x in video['videos'])==20
result={'status':'completed_fixed20_no_post_main_tuning','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'groups':groups,'pairs':raw['pairs'],'protocol_sha256':sha(MAIN/'LOCK.json'),'model_delta_sha256':lock['delta_sha256'],
    'common_total_sim_seconds_limit':45,'common_total_steps_limit':900,'all20_results_retained':True,
    'observation_conclusion':'Actual wrist images become less occluded in5/5 active leaf cases, red46/53/76/0/0 ->1035/1041/1042/1057/1047. Baseline live images at matched45 also reveal apple5/5. No claim that active has more information at equal elapsed time.',
    'strict_normalized_visibility_gain':'Not measured: no post-motion replay meets exact-match quality. Raw proxies retained separately, not treated as validated visible-area fractions.',
    'grasp_pair_changes':{'leaf_02':'improved to stable grasp and placement','leaf_03':'regressed from stable grasp to approach failure','leaf_04':'stable grasp in both, placement improves'},
    'limits':['n5 per group, narrow reserved positions, pretrained overlap unknown','Visual-only small elevated occluder; fixed camera already sees apple','Observation changes posture and action timing as well as images; causal mediation not isolated','clear00 places successfully after a loss of grasp; only1.0s strict bilateral lift hold','Candidate-based drop review does not guarantee detection of all transient substep losses'],
    'video_validation':{'videos':len(video['videos']),'frames':sum(x['frames'] for x in video['videos']),'all_full_decodes_passed':True},
    'checks':{'execution_exit0':True,'postprocessing_exit0':True,'LOCK_unchanged':True,'sources_assets_checkpoint_match_LOCK':True,'evaluation_spec_unchanged':True},
    'raw_analysis':'three_stage_analysis/summary.json','official_csv':'results.csv'}
(MAIN/'results_summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'final_csv':str(MAIN/'results.csv'),'groups':[{k:g[k] for k in ['occlusion','method','grasp_success_50mm_2sec','placement_success','confirmed_drop_trials','strict_proxy_gain_evaluable_trials']} for g in groups]}))
