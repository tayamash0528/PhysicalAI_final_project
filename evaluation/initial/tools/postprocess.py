"""Posthoc only: replay saved states for visibility, analyze logs, validate recordings."""
import datetime, json, subprocess, sys, traceback
from pathlib import Path

BASE = Path('evaluation/initial')
MAIN = BASE / 'main_comparison'
assert json.loads((MAIN/'execution_status.json').read_text())['return_code'] == 0
assert len(list((MAIN/'trials').glob('episode_*/result.json'))) == 20
record = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'policy_or_manipulation_executed': False, 'commands': []}

def save():
    (BASE/'postprocessing_status.json').write_text(json.dumps(record,indent=2)+'\n')

def run(script, *args):
    cmd = [sys.executable, str(script), *map(str,args)]
    item = {'command':cmd,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    record['commands'].append(item);save()
    print('POSTHOC_START',json.dumps(cmd),flush=True)
    proc = subprocess.run(cmd)
    item.update(return_code=proc.returncode,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
    if proc.returncode: raise RuntimeError(f'Posthoc command failed: {cmd}')

try:
    with (BASE/'reproducibility/requirements.actual.freeze.txt').open('w') as f:
        subprocess.run([sys.executable,'-m','pip','freeze'],stdout=f,check=True)
    run(BASE/'tools/evaluate_visibility.py','--root',BASE/'clear_skip_sanity','--max-episodes','1')
    clear = json.loads((BASE/'clear_skip_sanity/episode_00/visibility_evaluation.json').read_text())
    # Preserve strict render quality failures, while still analyzing every saved trial.
    smoke = {}
    for label in ('initial','matched_time'):
        assert clear[label]['status'] == 'measured', clear[label]
        smoke[label]=clear[label]['actual_replay_image_error']
    record['clear_render_smoke']=smoke;save()
    if not all(smoke[label][view]['exact_match'] for label in smoke for view in ('image','image2')):
        print('STRICT_RENDER_QUALITY_WARNING: keep ratio_valid=false; do not infer exact visible-surface fractions.',flush=True)
    run(BASE/'tools/evaluate_visibility.py','--root',MAIN)
    run(BASE/'tools/analyze_three_stages.py','--root',MAIN,'--expect','20')
    run(BASE/'tools/plot_three_stages.py','--root',MAIN/'three_stage_analysis','--expect-n','5')
    run('scripts/export_improvement_materials.py','--root',BASE)
    review = BASE/'tools/review_drop_candidates.py'
    if review.exists():run(review,'--root',MAIN)
    record['return_code']=0
except Exception:
    record.update(return_code=1,traceback=traceback.format_exc())
    raise
finally:
    record['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
