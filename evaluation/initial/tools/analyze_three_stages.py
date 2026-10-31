"""CPU-only observation/grasp/placement analysis of every completed paired trial.

This program never calls a policy, changes simulator state or selects conditions.
RGB area is a color-evidence proxy, not a true visible surface measurement.
"""
import argparse,csv,hashlib,json
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image,ImageDraw

VERSION='three_stage_metrics_v1'
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def lines(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pixel_sha(path):return hashlib.sha256(np.asarray(Image.open(path).convert('RGB')).tobytes()).hexdigest()
def first_step(items,predicate):return next((int(x['step']) for x in items if predicate(x)),None)
def mean(values):return float(np.mean(values)) if values else None
def color(path):
    a=np.asarray(Image.open(path).convert('RGB')).astype(float);r,g,b=a[...,0],a[...,1],a[...,2]
    red=(r>80)&(r>1.5*g)&(r>1.5*b);green=(g>60)&(g>1.4*r)&(g>1.3*b)
    nr=int(red.sum());ng=int(green.sum())
    return {'red_pixels':nr,'green_pixels':ng,'red_share':nr/max(1,nr+ng)}
def image_metrics(ep,label,key):
    if label=='initial':path=ep/'reobservation'/f'before_{key}.png'
    elif label=='matched':path=ep/'matched_time'/f'frame_0045_{key}.png'
    else:path=ep/'reobservation'/f'after_{key}.png'
    return (color(path),path) if path.exists() else (None,None)
def visibility(side,label,key):
    # Recommended sidecar schema; absent values remain unmeasured, never zero.
    block=side.get(label,{})
    return block.get('views',{}).get(key,{}).get('visible_red_ratio')
def bounded(value):return float(np.clip(value,0,1)) if value is not None else None
def visibility_quality(side,label,key):return side.get(label,{}).get('views',{}).get(key,{}).get('ratio_valid')

def analyze(root,out,expect,red_threshold):
    trialroot=root/'trials' if (root/'trials').is_dir() else root
    manifest=load(trialroot/'manifest.json');paths=sorted(trialroot.glob('episode_*/result.json'))
    if expect is not None:assert len(paths)==expect,(len(paths),expect)
    assert paths,'No completed trials; do not turn missing executions into failed operations'
    out.mkdir(parents=True,exist_ok=True);(out/'paired_images').mkdir(exist_ok=True)
    lock=load(root/'LOCK.json') if (root/'LOCK.json').exists() else None
    source_validation=[]
    for name,digest in manifest.get('source_sha256',{}).items():
        path=trialroot/'source_snapshot'/Path(name.replace('\\','/')).name
        assert sha(path)==digest,(name,'snapshot hash differs from executed manifest')
        source_validation.append({'source':name,'sha256':digest})
    if lock:
        assert manifest['expert_delta_sha256']==lock['delta_sha256']
        assert manifest['n_action_steps']==lock['n_action_steps'] and manifest['max_steps']==lock['max_steps']
        assert manifest['instruction']==lock['instruction']
        assert manifest['asset_sha256']==lock['asset_sha256']
        assert manifest['control_freq_hz']==lock.get('control_freq_hz',lock.get('control_hz'))
        assert manifest['placement_evaluator_version']==lock['placement_evaluator']
        assert manifest['model_revision']==lock['base_model']['revision']
        for name,digest in lock['source_sha256'].items():assert sha(trialroot/'source_snapshot'/Path(name.replace('\\','/')).name)==digest
        if lock.get('episode_setups_sha256'):assert sha(trialroot/'executed_episode_setups.json')==lock['episode_setups_sha256']
    expected_states={x.get('case_id',x.get('id')):x for x in lock.get('initial_states',[])} if lock else {}
    freq=manifest['control_freq_hz'];required_hold=int(round(2*freq));rows=[];details=[];input_audit=[]
    for path in paths:
        ep=path.parent;r=load(path);actions=lines(ep/'actions.jsonl');tele=lines(ep/'arm_telemetry.jsonl');ev=lines(ep/'evaluation_only.jsonl')
        assert len(actions)==len(tele)==len(ev)==r['steps']
        k=r['observation_steps'];enabled=r['method']=='reobserve';decision=r['reobservation_decision']
        if lock:
            expected=expected_states[r['case_id']];assert r['initial_state_sha256']==expected['state_array_sha256']
            initial_file=Path(r['setup_only']['initial_state'].replace('\\','/'))
            expected_file_sha=expected.get('state_file_sha256',expected.get('initial_state_file_sha256'))
            if expected_file_sha:assert sha(initial_file)==expected_file_sha,'Locked state file changed'
        assert 0<=k<=r['steps']<=manifest['max_steps']
        assert sum(x['source']=='observation_OSC' for x in actions)==k
        assert all(x['source']=='observation_OSC' for x in actions[:k]) and all(x['source']=='SmolVLA.select_action' for x in actions[k:])
        assert enabled or k==0,'No-reobserve method must not contain dedicated observation actions'
        assert all(x['applied_action'][-1]==-1 for x in actions[:k])
        vla=tele[k:];maxlift=max(x['object_lift_from_initial_m'] for x in vla);streak=longest=0;graspstep=None
        for t in vla:
            held=t['object_lift_from_initial_m']>=.05 and t['stages']['bilateral_contact']
            streak=streak+1 if held else 0;longest=max(longest,streak)
            if streak>=required_hold and graspstep is None:graspstep=t['step']
        approach=first_step(vla,lambda x:x['padmid_to_object_m']<.05)
        contact=first_step(vla,lambda x:x['stages']['bilateral_contact'])
        lift=first_step(vla,lambda x:x['object_lift_from_initial_m']>=.05)
        tray=first_step(ev,lambda x:lift is not None and x['step']>=lift and x['footprint_inside_tray'])
        support=first_step(ev,lambda x:lift is not None and x['step']>=lift and x['contained_and_supported'])
        release=first_step(ev,lambda x:x['contained_and_supported'] and x['released'])
        placement=bool(r['project_success']);assert placement==any(x['hold_streak']>=required_hold for x in ev)
        if not k and r.get('reobservation_count'):raise AssertionError('Observation visit count without moves')
        lifted=False;drop_steps=[];below=[]
        for j,t in enumerate(tele):
            lifted|=t['phase']=='vla' and t['object_lift_from_initial_m']>=.05
            vz=(t['object_world_z_m']-tele[max(0,j-1)]['object_world_z_m'])*freq
            lost=not t['stages']['left_contact'] and not t['stages']['right_contact']
            if lifted and lost and vz<-.15 and not ev[j]['footprint_inside_tray']:drop_steps.append(t['step'])
            if lifted and t['object_world_z_m']<.85:below.append(t['step'])
        if placement:failure='placement_success'
        elif approach is None:failure='approach'
        elif contact is None:failure='grasp_alignment'
        elif lift is None:failure='bilateral_contact_without_50mm_lift'
        elif graspstep is None:failure='lift_not_held_2seconds'
        elif tray is None:failure='transport'
        elif support is None:failure='tray_approach_or_lowering'
        elif release is None:failure='release'
        else:failure='tray_hold_less_than_2seconds'
        images={};evidence={}
        for label in ['initial','matched','after']:
            for key in ['image','image2']:
                metric,image=image_metrics(ep,label,key);images[label,key]=image;evidence[label,key]=metric
        sidepath=ep/'visibility_evaluation.json';side=load(sidepath) if sidepath.exists() else {}
        vi=visibility(side,'initial','image2');vm=visibility(side,'matched_time','image2');va=visibility(side,'after_observation','image2')
        rgb_i=evidence['initial','image2'];rgb_m=evidence['matched','image2'];rgb_a=evidence['after','image2']
        first=actions[k] if k<len(actions) else None
        audit={'episode':ep.name,'case_id':r['case_id'],'observation_steps':k,'after_input_checks':{},'normal_image_updates':{}}
        frameids=[x.get('pre_action_frame_id') for x in actions]
        if all(x is not None for x in frameids):assert frameids==list(range(len(actions)))
        audit['pre_action_frame_sequence_valid']=True if all(x is not None for x in frameids) else None
        for key in ['image','image2']:
            hashes=[x.get('image_sha256',{}).get(key) for x in actions]
            if all(h is not None for h in hashes):
                audit['normal_image_updates'][key]={'hash_samples':len(hashes),'distinct':len(set(hashes)),'scope':'Every pre-action frame; same mechanism in both methods'}
            else:
                saved=sorted((ep/'inputs').glob(f'*_{key}.png'))
                audit['normal_image_updates'][key]={'saved_samples':len(saved),'distinct':len(set(pixel_sha(x) for x in saved)),'scope':'Legacy10-step PNG sampling; exact per-frame acquisition log unavailable'}
            if k:
                assert first and first['predicted_new_chunk'] and first['action_queue_len_before']==0
                image=images['after',key];assert image
                if first.get('image_sha256',{}).get(key):matched=pixel_sha(image)==first['image_sha256'][key]
                else:
                    saved=ep/'inputs'/f'{k:04d}_{key}.png';assert saved.exists(),'Handoff not sampled and no per-frame image hash'
                    matched=pixel_sha(image)==pixel_sha(saved)
                assert matched,'Observation image was not actually used at policy handoff'
                audit['after_input_checks'][key]=True
        if k:
            assert decision['views_before']['image']==decision['views_after']['image'],'Fixed camera must retain physical identity'
            before=np.asarray(actions[k]['state_input'][0]);last=tele[k-1]
            assert np.max(np.abs(before[:3]-last['eef_world_m']))<1e-6
            assert np.max(np.abs(before[-2:]-last['gripper_qpos_m']))<1e-6
            audit['handoff_state_position_gripper_match']=True
        input_audit.append(audit)
        obs_wall=r.get('observation_wall_seconds',0. if not k else None)
        vla_wall=r.get('manipulation_wall_seconds',r.get('vla_wall_seconds'))
        row={'episode':ep.name,'case_id':r['case_id'],'occlusion':r['occlusion'],'method':r['method'],'split':r['setup_only'].get('split','locked_main' if lock else 'development'),
            'observation_triggered':decision['trigger'],'observation_executed':k>0,'observation_omitted':enabled and k==0,
            'observation_omitted_trigger_false':enabled and not decision['trigger'] and k==0,
            'wrist_red_initial':rgb_i['red_pixels'] if rgb_i else None,'wrist_red_matched45':rgb_m['red_pixels'] if rgb_m else None,
            'wrist_red_after_observation':rgb_a['red_pixels'] if rgb_a else None,
            'red_evidence_initial':rgb_i['red_pixels']>=red_threshold if rgb_i else None,'red_evidence_matched45':rgb_m['red_pixels']>=red_threshold if rgb_m else None,
            'wrist_rgb_increased_after_observation':rgb_a['red_pixels']>rgb_i['red_pixels'] if rgb_i and rgb_a else None,
            'wrist_visible_proxy_initial':vi,'wrist_visible_proxy_matched45':vm,'wrist_visible_proxy_after_observation':va,
            'wrist_visible_proxy_initial_bounded':bounded(vi),'wrist_visible_proxy_matched45_bounded':bounded(vm),'wrist_visible_proxy_after_observation_bounded':bounded(va),
            'visible_proxy_delta_after_observation_raw':va-vi if vi is not None and va is not None else None,
            'visible_proxy_delta_after_observation':bounded(va)-bounded(vi) if vi is not None and va is not None else None,
            'observation_proxy_gain_ge_0p20':bounded(va)-bounded(vi)>=.20 if k and vi is not None and va is not None else None,
            'visibility_quality_initial':visibility_quality(side,'initial','image2'),'visibility_quality_matched45':visibility_quality(side,'matched_time','image2'),
            'visibility_quality_after_observation':visibility_quality(side,'after_observation','image2'),
            'approach_within50mm':approach is not None,'bilateral_contact_ever':contact is not None,'lift50mm':lift is not None,
            'grasp_success_50mm_2sec':graspstep is not None,'max_lift_m':maxlift,'max_lift_bilateral_hold_seconds':longest/freq,
            'tray_xy_after_lift':tray is not None,'tray_supported_after_lift':support is not None,'release_inside_tray':release is not None,
            'placement_success':placement,'grasp_and_placement_success':placement and graspstep is not None,'unplaced':not placement,
            'drop_outside_candidate':bool(drop_steps or below),'fell_below_table_after_lift':bool(below),'fell_below_table_any':any(t['object_world_z_m']<.85 for t in tele),'max_placement_hold_seconds':max(x['hold_streak'] for x in ev)/freq,
            'first_approach_step':approach,'first_bilateral_contact_step':contact,'first_lift50mm_step':lift,'first_grasp_hold2sec_step':graspstep,
            'first_tray_xy_after_lift_step':tray,'first_release_inside_tray_step':release,'failure_stage':failure,
            'steps':r['steps'],'total_sim_seconds':r['steps']/freq,'observation_steps':k,'observation_sim_seconds':k/freq,
            'vla_steps':r['vla_steps'],'manipulation_sim_seconds':r['vla_steps']/freq,'reobservation_count':r['reobservation_count'],
            'observation_wall_seconds':obs_wall,'manipulation_wall_seconds':vla_wall,'decision_wall_seconds':r.get('decision_wall_seconds',decision.get('decision_wall_seconds')),
            'wall_seconds_including_reset':r['wall_seconds_including_reset'],'inference_wall_seconds':r['inference_seconds'],
            'seed':r['seed'],'initial_state_sha256':r['initial_state_sha256'],'delta_sha256':manifest['expert_delta_sha256'],
            'evaluator_version':r['placement_evaluator_version'],'video':str(ep/'rollout.mp4'),'result':str(path),
            'initial_image':str(images['initial','image']) if images['initial','image'] else None,'initial_wrist':str(images['initial','image2']) if images['initial','image2'] else None,
            'matched45_image':str(images['matched','image']) if images['matched','image'] else None,'matched45_wrist':str(images['matched','image2']) if images['matched','image2'] else None,
            'after_image':str(images['after','image']) if images['after','image'] else None,'after_wrist':str(images['after','image2']) if images['after','image2'] else None}
        assert abs(row['total_sim_seconds']-r['sim_seconds'])<1e-8
        rows.append(row);details.append({'episode':ep.name,'case':r['case_id'],'drop_candidate_steps':drop_steps,'below_table_steps':below,
            'visibility_sidecar':str(sidepath) if sidepath.exists() else None,'observation_decision':decision,'source':'Saved logs only, no simulator or policy called'})
    pairs=[];sheets=[]
    for case in sorted(set(r['case_id'] for r in rows)):
        subset=[r for r in rows if r['case_id']==case]
        if len(subset)!=2:continue
        by={r['method']:r for r in subset}
        if set(by)!={'no_reobserve','reobserve'}:continue
        no,yes=by['no_reobserve'],by['reobserve']
        assert no['initial_state_sha256']==yes['initial_state_sha256'] and no['seed']==yes['seed']
        assert no['occlusion']==yes['occlusion'] and no['evaluator_version']==yes['evaluator_version']
        initial_errors={}
        for name in ['initial_image','initial_wrist']:
            aa=np.asarray(Image.open(no[name]));bb=np.asarray(Image.open(yes[name]));error=int(np.abs(aa.astype(int)-bb.astype(int)).max());assert error==0
            initial_errors[name]=error
        pair={'case_id':case,'occlusion':no['occlusion'],'initial_state_and_seed_match':True,'initial_policy_images_max_error':initial_errors,
            'no_episode':no['episode'],'yes_episode':yes['episode'],
            'no_grasp_success':no['grasp_success_50mm_2sec'],'yes_grasp_success':yes['grasp_success_50mm_2sec'],
            'no_placement_success':no['placement_success'],'yes_placement_success':yes['placement_success'],
            'grasp_delta':int(yes['grasp_success_50mm_2sec'])-int(no['grasp_success_50mm_2sec']),
            'placement_delta':int(yes['placement_success'])-int(no['placement_success']),
            'matched45_red_pixel_delta':yes['wrist_red_matched45']-no['wrist_red_matched45'] if yes['wrist_red_matched45'] is not None and no['wrist_red_matched45'] is not None else None,
            'matched45_visible_proxy_delta':yes['wrist_visible_proxy_matched45']-no['wrist_visible_proxy_matched45'] if yes['wrist_visible_proxy_matched45'] is not None and no['wrist_visible_proxy_matched45'] is not None else None,
            'matched45_visible_proxy_delta_bounded':yes['wrist_visible_proxy_matched45_bounded']-no['wrist_visible_proxy_matched45_bounded'] if yes['wrist_visible_proxy_matched45_bounded'] is not None and no['wrist_visible_proxy_matched45_bounded'] is not None else None,
            'matched45_visibility_quality_no':no['visibility_quality_matched45'],'matched45_visibility_quality_yes':yes['visibility_quality_matched45'],
            'no_failure':no['failure_stage'],'yes_failure':yes['failure_stage'],'no_video':no['video'],'yes_video':yes['video']}
        pairs.append(pair)
        sheet=Image.new('RGB',(1024,600),'white');draw=ImageDraw.Draw(sheet)
        for y,r in enumerate([no,yes]):
            labels=[('initial_image','initial agent'),('initial_wrist','initial wrist'),('matched45_wrist','step45 wrist'),('after_wrist','after observation wrist')]
            for x,(field,label) in enumerate(labels):
                image=r[field];draw.text((x*256+3,y*300+3),r['method']+' / '+label,fill='black')
                if image:sheet.paste(Image.open(image).resize((256,256)),(x*256,y*300+22))
                else:draw.text((x*256+12,y*300+80),'Not acquired / no dedicated view',fill='black')
            draw.text((4,y*300+282),f"{case} grasp={r['grasp_success_50mm_2sec']} placement={r['placement_success']} / {r['failure_stage']}",fill='black')
        target=out/'paired_images'/f'{case}.png';sheet.save(target);pair['paired_image_sheet']=str(target)
    if expect==20:assert len(pairs)==10 and len(rows)==20
    flags=['observation_executed','observation_omitted_trigger_false','approach_within50mm','bilateral_contact_ever','lift50mm','grasp_success_50mm_2sec','tray_xy_after_lift','release_inside_tray','placement_success','grasp_and_placement_success','unplaced','drop_outside_candidate']
    groups=[]
    for occ,method in sorted(set((r['occlusion'],r['method']) for r in rows)):
        ss=[r for r in rows if (r['occlusion'],r['method'])==(occ,method)];g={'occlusion':occ,'method':method,'trials':len(ss),**{f:sum(bool(r[f]) for r in ss) for f in flags}}
        g.update(observation_omission_rate=sum(r['observation_omitted'] for r in ss)/len(ss) if method=='reobserve' else None,
            observation_sim_seconds_mean=mean([r['observation_sim_seconds'] for r in ss]),manipulation_sim_seconds_mean=mean([r['manipulation_sim_seconds'] for r in ss]),
            total_sim_seconds_mean=mean([r['total_sim_seconds'] for r in ss]),observation_count=sum(r['reobservation_count'] for r in ss),failure_breakdown=dict(Counter(r['failure_stage'] for r in ss)))
        measured=[r for r in ss if r['observation_proxy_gain_ge_0p20'] is not None]
        g.update(observation_proxy_gain_ge_0p20=sum(r['observation_proxy_gain_ge_0p20'] for r in measured),observation_proxy_gain_measured_trials=len(measured),
            matched45_visible_proxy_measured_trials=sum(r['wrist_visible_proxy_matched45'] is not None for r in ss),
            matched45_visibility_quality_valid_trials=sum(r['visibility_quality_matched45'] is True for r in ss))
        groups.append(g)
    definitions={'analysis_version':VERSION,'contact':'Any bilateral end-of-control-step contact. NOT grasp success.',
        'grasp':'In VLA phase, initial object-center lift>=0.05m AND bilateral contact continuously for2sim seconds (40 at20Hz).',
        'placement':'Original executed v2 predicate and40-step tray hold; no criterion changed by this analyzer.',
        'sequence':'Both grasp and placement; supplemental, does not replace the historical placement predicate.',
        'drop':'Candidate: after VLA50mm lift, both finger contacts absent, estimated vz<-0.15m/s and full footprint outside tray; OR after that lift world centerZ<0.85m. Sampled at control-step boundaries; video review remains useful.',
        'observation':'RGB area and red>=threshold are color proxies. Raw increase may reflect magnification. No true visibility improvement inferred without separately supplied same-pose hidden-leaf evaluation.',
        'paired_visibility':'Matched45 frame compares both methods at the same elapsed simulation time, including normal motion. Within-active initial-to-after contrast is separate.',
        'proxy_gain':'Auxiliary threshold: clip actual/reference texture-red ratios to[0,1] for summary gain>=0.20. Raw ratios retained. ratio_valid reference-area/replay-quality flag reported separately; no cases removed.',
        'causal_limit':'Observation intervention includes robot motion/posture and changed images; do not interpret it as an isolated information-only causal effect.',
        'time':'Steps/freq are simulation time. Legacy missing wall phase measurements are null, not estimated.'}
    summary={'status':'locked_main' if lock else 'development','trials':len(rows),'pairs':pairs,'groups':groups,'definitions':definitions,'red_evidence_threshold':red_threshold,
        'manifest_controls':{k:manifest[k] for k in ['model_id','model_revision','expert_delta_sha256','instruction','control_freq_hz','n_action_steps','max_steps','placement_evaluator_version']},
        'executed_source_validation':source_validation,'input_audit':input_audit,'all_results_retained':True}
    with (out/'trials.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if pairs:
        keys=list(pairs[0]);
        with (out/'paired_results.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(pairs)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(out/'trial_details.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    (out/'README.md').write_text('# Three-stage analysis\n\ntrials.csv retains every finished trial; groups are separate for clear/leaf and method. paired_results.csv joins the same case/seed/initial state, paired_images/links both videos and the available actual RGB views. Contact is not grasp. Stable grasp is50mm+2s bilateral hold; placement is the executed v2 criterion. RGB area is a proxy and cannot by itself prove improved visible surface. Hidden-leaf same-pose references are evaluation-only sidecars, never policy inputs. Main trials require --expect20; run after all20finish. No simulation, VLA or tuning is performed by this program.\n',encoding='utf-8')
    return {'output':str(out),'trials':len(rows),'pairs':len(pairs),'groups':groups}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out');p.add_argument('--expect',type=int);p.add_argument('--red-threshold',type=int,default=200);a=p.parse_args()
    root=Path(a.root);print(json.dumps(analyze(root,Path(a.out) if a.out else root/'three_stage_analysis',a.expect,a.red_threshold)))
