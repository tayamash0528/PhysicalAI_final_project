"""既存対照と追加6試行の保存ログだけを集計する。推論・実験は行わない。"""
import csv,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

D=Path(__file__).resolve().parent
ROOT=D.parents[1]
OLD=ROOT/'evaluation/relocated_apple/holdout_comparison'
WORK=D/'hidden_workspace'
NEW=WORK/'runs/hidden6_v3'
CASES=['new_leaf_00','new_leaf_04','new_leaf_07']
FONT=r'C:\Windows\Fonts\BIZ-UDGothicR.ttc'

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def lines(p):return [json.loads(s) for s in p.read_text().splitlines() if s]
def truth(v):return v is True or v=='True'
def number(v):return None if v is None or v=='' else int(v)
def when(v):return None if number(v) is None else (number(v)+1)/20
def quat(v):
    v=np.asarray(v);angle=np.linalg.norm(v)
    return [0.,0.,0.,1.] if angle<1e-12 else [*(v*(math.sin(angle/2)/angle)),math.cos(angle/2)]
def save(n,obj):
    p=D/n;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    old=list(csv.DictReader((OLD/'results.csv').open(encoding='utf-8-sig')))
    hidden=list(csv.DictReader((WORK/'analysis_v3/trials.csv').open(encoding='utf-8-sig')))
    assert len(hidden)==6
    rows=[];sources={};display_audits=[]
    for visible,entries,base in [(True,old,OLD/'trials'),(False,hidden,NEW)]:
        for item in entries:
            if item['case_id'] not in CASES:continue
            ep=base/item['episode'];result=load(ep/'result.json');actions=lines(ep/'actions.jsonl')
            move=number(item['observation_steps'])>0;k=int(item['observation_steps'])
            key=(item['case_id'],visible,move);sources[key]=ep
            assert k in [0,45] and result['steps']<=900
            first=actions[k]['state_input'][0]
            posefile=ep/'diagnostic/operation_start.json'
            pose=load(posefile) if posefile.exists() else {'eef_position_world_m':first[:3],
                 'wrist_quaternion_xyzw':quat(first[3:6]),'source':'旧対照のstate_input軸角から復元（float32丸めあり）'}
            tele=lines(ep/'arm_telemetry.jsonl');evaluation=lines(ep/'evaluation_only.jsonl')
            assert len(tele)==len(evaluation)==len(actions)==result['steps']
            if not visible:
                audit=load(ep/'diagnostic/leaf_display_audit.json')
                assert audit['simulator_state_unchanged'] and audit['all_four_rng_states_unchanged']
                assert audit['model_numeric_arrays_changed']==['geom_rgba'] and not audit['data_numeric_arrays_changed']
                display_audits.append(dict(case_id=item['case_id'],move=move,**audit))
                assert not result['reobservation_decision']['diagnostic_raw_rgb_trigger']
                assert bool(result['setup_only']['diagnostic_force_observation'])==move
            stage_keys={'approach':'first_approach_step','bilateral_contact':'first_bilateral_contact_step',
                        'lift50mm':'first_lift50mm_step','hold40':'first_grasp_hold2sec_step',
                        'release_inside':'first_release_inside_tray_step'}
            times={name+'_s':when(item[field]) for name,field in stage_keys.items()}
            times['containment_s']=result['steps']/20 if result['project_success'] else None
            row={'case_id':item['case_id'],'leaf_display':'表示あり' if visible else '表示なし',
                 'observation_motion':'45step通常判断' if visible and move else '45step強制（診断）' if move else 'なし',
                 'leaf_visible':visible,'physical_scene_kind':'leaf_visual','motion':move,'forced_motion':move and not visible,
                 'origin':'保存済み対照' if visible else '追加診断','episode':item['episode'],
                 'seed':result['seed'],'initial_state_sha256':result['initial_state_sha256'],
                 'bilateral_contact':truth(item['bilateral_contact_ever']),'lift50mm':truth(item['lift50mm']),
                 'hold40':truth(item['grasp_success_50mm_2sec']),'containment':truth(item['placement_success']),
                 **times,'failure_stage':item['failure_stage'],'steps':result['steps'],'sim_seconds':result['steps']/20,
                 'observation_steps':k,'vla_steps':result['vla_steps'],
                 'max_lift_m':float(item['max_lift_m']),
                 'max_hold_s':float(item['max_lift_bilateral_hold_seconds']),
                 'operation_start_position_world_m':pose['eef_position_world_m'],
                 'operation_start_wrist_quaternion_xyzw':pose['wrist_quaternion_xyzw'],
                 'operation_start_state8':first,'operation_start_sim_seconds':k/20,
                 'leaf_contact_sample_count':sum(bool(t.get('leaf_contacts')) for t in tele),
                 'video':str(ep/'rollout.mp4'),'log_directory':str(ep),
                 'initial_fixed_rgb':str(ep/'reobservation/before_image.png'),
                 'initial_wrist_rgb':str(ep/'reobservation/before_image2.png'),
                 'observation_end_wrist_rgb':str(ep/'reobservation/after_image2.png') if move else None,
                 'evaluator_version':result['placement_evaluator_version'],
                 'checkpoint_sha256':load(base/'manifest.json')['expert_delta_sha256']}
            for name,t in times.items():row[name.removesuffix('_s')+'_vla_relative_s']=None if t is None else t-k/20
            assert row['leaf_contact_sample_count']==0
            assert row['checkpoint_sha256']=='67a1dd9044c21f4b13de96afca496099e02f9531b624879f151fc3996e991ac2'
            assert row['evaluator_version']=='v2_open_command_and_75mm_gap_40_steps'
            rows.append(row)
    rows.sort(key=lambda r:(CASES.index(r['case_id']),not r['leaf_visible'],r['motion']))
    assert len(rows)==12
    with (D/'factorial_diagnostic.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    contrast=[]
    for case in CASES:
        for move in [False,True]:
            oldep=sources[case,True,move];newep=sources[case,False,move]
            olda=lines(oldep/'actions.jsonl');newa=lines(newep/'actions.jsonl');k=45 if move else 0
            a,b=olda[k],newa[k]
            state_error=float(np.max(np.abs(np.asarray(a['state_input'])-np.asarray(b['state_input']))))
            observe_error=max([float(np.max(np.abs(np.asarray(x['applied_action'])-np.asarray(y['applied_action'])))) for x,y in zip(olda[:k],newa[:k])] or [0.])
            assert state_error==0 and observe_error==0,(case,move,state_error,observe_error)
            contrast.append(dict(case_id=case,motion=move,initial_state_matches=load(oldep/'result.json')['initial_state_sha256']==load(newep/'result.json')['initial_state_sha256'],
                policy_start_state8_max_difference=state_error,observation_action_max_difference=observe_error,
                policy_start_rgb_hashes_equal=a['image_sha256']==b['image_sha256'],
                first_vla_normalized_action_max_difference=float(np.max(abs(np.asarray(a['normalized_action'])-np.asarray(b['normalized_action'])))),
                first_vla_applied_action_max_difference=float(np.max(abs(np.asarray(a['applied_action'])-np.asarray(b['applied_action']))))))
        # VLA開始時の実画像。移動ありは2.25秒、なしは0秒であることを明示。
        canvas=Image.new('RGB',(1024,680),'#f5f8f6');draw=ImageDraw.Draw(canvas)
        f=ImageFont.truetype(FONT,18);ft=ImageFont.truetype(FONT,26)
        draw.text((12,8),case+'：VLA開始時の実画像（固定／手首）',font=ft,fill='#173f38')
        for col,(visible,move) in enumerate([(True,False),(False,False),(True,True),(False,True)]):
            ep=sources[case,visible,move];label=('葉表示あり' if visible else '葉表示なし')+'\n'+('移動あり 2.25秒' if move else '移動なし 0秒')
            draw.text((col*256+5,48),label,font=f,fill='#173f38')
            for row,view in enumerate(['image','image2']):
                p=ep/'reobservation'/f'{"after" if move else "before"}_{view}.png'
                canvas.paste(Image.open(p).convert('RGB'),(col*256,110+row*270))
        canvas.save(D/f'{case}_operation_start_images.png')
    save('input_state_motion_contrasts.json',contrast)
    save('display_change_audits.json',display_audits)
    save('diagnostic_summary.json',dict(posthoc_selected=True,generalization_evaluation=False,
        existing_comparison_results_unchanged=True,rows=rows,new_valid_vla_runs=13,main_hidden_trials=6,preliminary_hidden_trials_with_cache_side_effect=6,
        control_reproducibility=load(D/'control_reproducibility.json'),
        display_and_rng_guards_passed=True,within_motion_state_and_observation_actions_exact=True,
        contact_is_not_grasp=True,definitions={'contact':'VLA区間の任意の制御終端で両指接触',
        'lift':'開始時果実中心から50mm以上','hold':'50mm以上かつ両指接触を40制御step連続',
        'containment':'採用v2判定の開放・トレー内・支持条件を40step連続','times':'rollout開始からのsim秒。初回到達は(step+1)/20。相対VLA時刻もCSVへ保存。'}))
    (WORK/'analysis_v3/README.md').write_text('# 診断6試行の段階別集計\n\n採用済みanalyze_three_stages.pyのコピーで保存ログを集計した。元の判定は変更していない。物理モデルのocclusion名はleaf_visualのままだが、本6試行は葉表示を消した診断条件。移動あり側は45stepを強制しており、通常の再観察あり方式とは区別する。全12条件の対応と解釈は診断ルートの報告・factorial_diagnostic.csvを参照。\n',encoding='utf-8')
    for r in rows:print(r['case_id'],r['leaf_display'],r['observation_motion'],r['bilateral_contact'],r['lift50mm'],r['hold40'],r['containment'],r['failure_stage'])

if __name__=='__main__':main()
