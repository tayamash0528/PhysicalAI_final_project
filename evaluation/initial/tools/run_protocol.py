"""Validate frozen sources/weights/conditions and execute the20paired trials once."""
import argparse,hashlib,json,subprocess,sys,datetime
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root);lock=json.loads((root/'LOCK.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert lock['status']=='LOCKED_BEFORE_MAIN_TRIALS' and lock['no_tuning_after_main']
for key in ['source_sha256','asset_sha256']:
    for path,expected in lock[key].items():assert sha(path)==expected,path
assert sha(lock['delta'])==lock['delta_sha256'] and sha(root/'episode_setups.json')==lock['episode_setups_sha256']
setups=json.loads((root/'episode_setups.json').read_text());assert len(setups)==20
for case in {x['case_id'] for x in setups}:
    pair=[x for x in setups if x['case_id']==case];assert len(pair)==2 and {x['active_reobservation'] for x in pair}=={False,True};assert pair[0]['seed']==pair[1]['seed'] and pair[0]['initial_state']==pair[1]['initial_state']
cmd=[sys.executable,'scripts/run_rollout.py','--fruit-task','apple_single','--episode-setups',str(root/'episode_setups.json'),'--observer-profile',lock['observer_profile'],'--max-steps','900','--n-action-steps','10','--visibility-eval-step','45','--telemetry','--trainable-fp32','--inference-amp','--expert-delta',lock['delta'],'--out',str(root/'trials')]
status={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'protocol_sha256':sha(root/'LOCK.json'),'weights_changed_after_lock':False}
(root/'execution_status.json').write_text(json.dumps(status,indent=2));proc=subprocess.run(cmd);status.update(return_code=proc.returncode,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(root/'execution_status.json').write_text(json.dumps(status,indent=2))
if proc.returncode:raise SystemExit(proc.returncode)
assert len(list((root/'trials').glob('episode_*/result.json')))==20
print('ALL20COMPLETED',flush=True)
