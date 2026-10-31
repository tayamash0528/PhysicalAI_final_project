"""Independently recompute sampled predicates from the20 saved traces. No simulation."""
import csv,datetime,hashlib,json
from pathlib import Path
BASE=Path('evaluation/relocated_apple');P=BASE/'holdout_comparison';OLD=Path('evaluation/initial')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def lines(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
lock=read(P/'LOCK.json');assert read(P/'execution_status.json')['return_code']==0 and sha(P/'LOCK.json')==read(P/'execution_status.json')['protocol_sha256']
parent=read(OLD/'main_comparison/LOCK.json');assert sha(lock['delta'])==parent['delta_sha256']==lock['delta_sha256']
for key in ('source_sha256','asset_sha256'):
    assert lock[key]==parent[key]
    for path,digest in lock[key].items():assert sha(path)==digest
old_manifest=read(OLD/'adoption_check/confirmation_manifest.json');old_checks={}
for file in ['main_comparison/results.csv','main_comparison/results_summary.json','main_comparison/LOCK.json']:
    old_checks[file]=sha(OLD/file)==old_manifest['files'][file]
assert all(old_checks.values())
with (P/'results.csv').open(encoding='utf-8-sig') as f:csvrows=list(csv.DictReader(f))
audits=[]
for ep in sorted((P/'trials').glob('episode_*')):
    r=read(ep/'result.json');a=lines(ep/'actions.jsonl');t=lines(ep/'arm_telemetry.jsonl');e=lines(ep/'evaluation_only.jsonl');m=read(ep/'telemetry_metadata.json')
    assert len(a)==len(t)==len(e)==r['steps'];assert m['measured_center_local_m']==[0.,0.,0.]
    h=streak=longest=0;placements=False;dt=[]
    for i,(ac,te,ev) in enumerate(zip(a,t,e)):
        assert ac['step']==te['step']==ev['step']==i
        height=te['object_world_z_m']-m['initial_object_root_world_m'][2];assert abs(height-te['object_lift_from_initial_m'])<1e-10
        held=te['phase']=='vla' and height>=.05 and te['stages']['bilateral_contact'];h=h+1 if held else 0;longest=max(longest,h)
        released=ac['applied_action'][-1]<-.5 and sum(abs(x) for x in te['gripper_qpos_m'])>=.075
        assert released==ev['released']
        inside=ev['footprint_inside_tray'] and -.002<=ev['mesh_bottom_tray_m']<=.016;assert inside==ev['contained_and_supported']
        streak=streak+1 if inside and released else 0;assert streak==ev['hold_streak']==ac['tray_hold_steps']
        placements|=streak>=40
        if i:dt.append(te['simulation_time_s']-t[i-1]['simulation_time_s'])
    row=next(x for x in csvrows if x['episode']==ep.name);assert (row['placement_success']=='True')==placements==r['project_success'];assert (row['grasp_success_50mm_2sec']=='True')==(longest>=40)
    assert all(abs(x-.05)<1e-10 for x in dt)
    audits.append({'episode':ep.name,'case_id':r['case_id'],'method':r['method'],'steps':len(t),'max_bilateral_50mm_hold_samples':longest,'containment_success':placements,'all_time_height_contact_release_hold_checks_passed':True})
assert len(audits)==20
out={'audited_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_actions_or_tuning':False,'all20_match_official_CSV':True,'old5_data_and_protocol_unchanged':old_checks,'audits':audits,'limits':'Footprint boolean was logged by unchanged executed geometry code; no per-step object rotation for independent vertex re-render.20Hz sampled intervals, not continuous substep verification.'}
(BASE/'FINAL_PREDICATE_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:all20new traces,original5dataunchanged,frozenmodel/source/physics,every sampledtime-height-open-holdpredicate.')
