"""Posthoc CPU-only audit of the frozen20-trial leaf holdout.

No simulator, model, teacher, training, policy, condition selection, or tuning is
called here. Existing recordings/logs are analyzed with the previously used
metric implementation. Drop flags remain candidates until separately reviewed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path

OLD = Path('evaluation/initial')
ANALYZER = OLD / 'tools/analyze_three_stages.py'
ANALYZER_SHA256 = 'f93eb27491353317aedc20d6bd78d1e873a1fe0e306be6b9ae8aee822eab95bc'


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def is_true(value):
    return value is True or str(value).lower() == 'true'


def average(values):
    return sum(values) / len(values) if values else None


def category(no, yes):
    if no and yes:
        return 'both_success'
    if yes:
        return 'only_reobserve_success'
    if no:
        return 'only_no_reobserve_success'
    return 'both_failure'


def validate_fixed_adoption(protocol, lock):
    parent = read(OLD / 'main_comparison/LOCK.json')
    comparisons = {}
    for key in ('delta_sha256', 'source_sha256', 'asset_sha256', 'instruction',
                'n_action_steps', 'max_steps', 'control_freq_hz',
                'placement_evaluator', 'observer_profile', 'observer_rule', 'trigger_rule'):
        comparisons[key] = lock[key] == parent[key]
    for key in ('height_above_root_m', 'half_size_m'):
        comparisons['leaf_geometry.' + key] = lock['leaf_geometry'][key] == parent['leaf_geometry'][key]
    comparisons['base_model_revision'] = lock['base_model']['revision'] == parent['base_model']['revision']
    assert all(comparisons.values()), comparisons
    assert sha(ANALYZER) == ANALYZER_SHA256, 'Previously executed metric analyzer changed'
    execution = read(protocol / 'execution_status.json')
    assert execution.get('return_code') == 0, 'Holdout must finish successfully before postprocessing'
    assert execution['protocol_sha256'] == sha(protocol / 'LOCK.json')
    assert len(list((protocol / 'trials').glob('episode_*/result.json'))) == 20
    return comparisons


def formal_results(base, protocol, lock, comparisons):
    analysis = protocol / 'three_stage_analysis'
    source = read(analysis / 'summary.json')
    assert source['trials'] == 20 and len(source['pairs']) == 10
    groups_by = {(g['occlusion'], g['method']): g for g in source['groups']}
    assert set(groups_by) == {('leaf_visual', 'no_reobserve'), ('leaf_visual', 'reobserve')}
    assert all(g['trials'] == 10 for g in source['groups'])
    with (analysis / 'trials.csv').open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 20
    for row in rows:
        row['tray_containment_success'] = is_true(row['placement_success'])
        row['lift_bilateral_40step_success'] = is_true(row['grasp_success_50mm_2sec'])
        row['drop_confirmation_status'] = ('unreviewed_candidate' if is_true(row['drop_outside_candidate'])
                                           else 'no_flag_by20Hz_candidate_rule')
        row['confirmed_drop'] = None
        row['evaluation_scope'] = 'fixed_adopted_procedure_new_local_leaf_positions'
    with (protocol / 'results.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    pairs = []
    for pair in source['pairs']:
        result = dict(pair)
        result['tray_containment_category'] = category(pair['no_placement_success'], pair['yes_placement_success'])
        result['lift_bilateral_40step_category'] = category(pair['no_grasp_success'], pair['yes_grasp_success'])
        pairs.append(result)
    with (protocol / 'paired_results.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    groups = []
    for method in ('no_reobserve', 'reobserve'):
        group = dict(groups_by['leaf_visual', method])
        subset = [r for r in rows if r['method'] == method]
        group['tray_containment_success'] = group['placement_success']
        group['lift_bilateral_40step_success'] = group['grasp_success_50mm_2sec']
        group['confirmed_drop_trials'] = None
        group['drop_status'] = 'Candidate events only; review corresponding frames before claiming a drop count'
        group['actual_wrist_red_ge200_initial'] = sum(is_true(r['red_evidence_initial']) for r in subset)
        group['actual_wrist_red_ge200_matched45'] = sum(is_true(r['red_evidence_matched45']) for r in subset)
        group['actual_wrist_red_ge200_after_observation'] = sum(int(r['wrist_red_after_observation']) >= 200
                                                               for r in subset if r['wrist_red_after_observation'])
        for key in ('observation_wall_seconds', 'manipulation_wall_seconds', 'wall_seconds_including_reset'):
            group[key + '_mean'] = average([float(r[key]) for r in subset if r[key]])
        groups.append(group)
    old = read(OLD / 'main_comparison/results_summary.json')
    old_groups = {g['method']: g for g in old['groups'] if g['occlusion'] == 'leaf_visual'}
    assert old_groups['no_reobserve']['placement_success'] == 2
    assert old_groups['reobserve']['placement_success'] == 4
    no = groups[0]['tray_containment_success']
    yes = groups[1]['tray_containment_success']
    if yes > no:
        statement = (f'固定した採用版で、ローカルの学習・調整・過去評価に未使用と監査した葉あり10初期配置でも、'
                     f'再観察手順の追加によりトレー収容成功数が{no}/10から{yes}/10へ増えた。')
    elif yes == no:
        statement = (f'既存5条件の2/5→4/5という改善は確認済み。新しい葉あり10初期配置では'
                     f'両方式{no}/10で、収容成功数の増加は再現しなかった。')
    else:
        statement = (f'既存5条件の2/5→4/5という改善は確認済み。新しい葉あり10初期配置では'
                     f'なし{no}/10・あり{yes}/10で、収容成功数の増加は再現せず低下した。')
    result = {
        'status': 'completed_fixed20_holdout_posthoc', 'created_utc': utc(),
        'scope': 'New local initial apple positions, all leaf_visual; no crop/farm generalization claim',
        'primary_metric_name': 'Tray containment success / トレー収容成功',
        'primary_metric_definition': 'Executed v2: full mesh footprint in tray, supported bottom height, open command and joint aperture threshold,40 consecutive20Hz samples (2s equivalent)',
        'secondary_metric_definition': 'Initial-center lift>=50mm AND bilateral finger contact40 consecutive20Hz samples; separate from containment',
        'time_definition': 'Shared900step/45simsecond limit includes observation;40 sample endpoints span1.95s and represent40control intervals, not verified continuous substep2.000s',
        'groups': groups, 'pairs': pairs,
        'tray_containment_pair_categories': dict(Counter(p['tray_containment_category'] for p in pairs)),
        'lift_bilateral_40step_pair_categories': dict(Counter(p['lift_bilateral_40step_category'] for p in pairs)),
        'new_holdout_result_statement': statement,
        'existing5_leaf_result': {'status': 'confirmed_empirical_procedure_improvement',
            'no_reobserve_success': 2, 'reobserve_success': 4, 'trials_per_method': 5,
            'source': str(OLD / 'main_comparison/results_summary.json'),
            'source_sha256': sha(OLD / 'main_comparison/results_summary.json'),
            'not_pooled_with_new_holdout': True},
        'comparability_checks_against_adoption': comparisons,
        'protocol_sha256': sha(protocol / 'LOCK.json'),
        'checkpoint_sha256': lock['delta_sha256'], 'analysis_source_sha256': sha(ANALYZER),
        'no_conditions_replaced': True, 'all20_trials_retained': True, 'no_post_holdout_tuning': True,
        'new_model_or_simulator_actions_by_this_analysis': False,
        'causal_limit': 'Procedure includes additional motion, actual viewpoint, start posture, action timing and remaining manipulation budget. This is not isolated visual-information causality.',
        'generalization_limit': 'Narrow apple/tray workspace and synthetic collision-free leaf; unknown pretraining overlap; no unknown crop or real farm validation.',
        'visibility': {'normalized_visibility_not_recomputed': True,
                       'reason': 'Earlier exact post-motion replay did not pass strict quality. Use actual before/after and matched45 RGB only; pixel area changes with scale.'},
        'raw_analysis': 'three_stage_analysis/summary.json',
        'official_csv': 'results.csv', 'official_paired_csv': 'paired_results.csv'
    }
    dump(protocol / 'results_summary.json', result)
    return result


def figures(base, protocol, result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    out = protocol / 'figures'
    out.mkdir(exist_ok=True)
    colors = ['#2563eb', '#ea580c']
    labels = ['No additional observation', 'Reobservation procedure']
    old = result['existing5_leaf_result']
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.7))
    for ax, counts, n, title in [(axes[0], [old['no_reobserve_success'], old['reobserve_success']], 5,
                                  'Existing5 leaf conditions: confirmed result'),
                                 (axes[1], [g['tray_containment_success'] for g in result['groups']], 10,
                                  'New10 reserved leaf positions: fixed policy')]:
        ax.bar([0, 1], [v/n for v in counts], color=colors)
        for i, count in enumerate(counts):
            ax.text(i, count/n + .03, f'{count}/{n}', ha='center')
        ax.set(xticks=[0, 1], xticklabels=['No reobservation', 'Reobservation'], ylim=(0, 1.17),
               ylabel='Tray containment successes / all trials', title=title)
        ax.spines[['top','right']].set_visible(False)
    fig.subplots_adjust(bottom=.22, top=.83, wspace=.3)
    fig.text(.02, .025, 'Separate evaluations; no pooled score. Same frozen C/chunk10/v10 and v2 containment definition.\n'
             'Containment = tray support + open gripper +40samples (~2s); not necessarily stable/no-slip grasp transport.\n'
             'The procedure changes images, posture, approach and timing; visual-information-only causality is not established.', fontsize=8)
    for ext in ('png', 'svg'): fig.savefig(out/f'tray_containment_existing5_vs_new10.{ext}', dpi=180)
    plt.close(fig)
    fields = [('bilateral_contact_ever', 'Bilateral\ncontact'), ('lift50mm', 'Lift\n>=50mm'),
              ('lift_bilateral_40step_success', 'Lift+bilateral\n40step hold'),
              ('tray_containment_success', 'Tray containment\nopen+40step hold')]
    fig, ax = plt.subplots(figsize=(9, 4.8)); x = np.arange(len(fields)); width = .35
    for j, group in enumerate(result['groups']):
        pos = x + (j-.5)*width; counts = [group[k] for k, _ in fields]
        ax.bar(pos, [v/10 for v in counts], width, color=colors[j], label=labels[j])
        for xx, count in zip(pos, counts): ax.text(xx, count/10+.025, f'{count}/10', ha='center', fontsize=9)
    ax.set(xticks=x, xticklabels=[v for _, v in fields], ylim=(0, 1.2), ylabel='Fraction of all10 conditions',
           title='New10 leaf positions: contact, lift, hold and containment are distinct')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.2), ncol=2, frameon=False)
    ax.spines[['top','right']].set_visible(False); fig.subplots_adjust(top=.78, bottom=.23)
    fig.text(.02, .035, 'Contact is not grasp. Hold: initial-center lift>=50mm AND bilateral contact for40samples (~2s).\n'
             'Containment is the unchanged executed v2 predicate. Every success and failure remains in the denominator.', fontsize=8)
    for ext in ('png', 'svg'): fig.savefig(out/f'new10_stages.{ext}', dpi=180)
    plt.close(fig)
    pairs = result['pairs']; matrix = np.array([[int(p['no_placement_success']), int(p['yes_placement_success']),
                                               int(p['no_grasp_success']), int(p['yes_grasp_success'])] for p in pairs])
    fig, ax = plt.subplots(figsize=(8, 6.2)); ax.imshow(matrix, cmap='Greens', vmin=0, vmax=1, aspect='auto')
    ax.set(xticks=range(4), xticklabels=['Containment\nNo reobserve', 'Containment\nReobserve',
                                       'Lift+40step hold\nNo reobserve', 'Lift+40step hold\nReobserve'],
           yticks=range(len(pairs)), yticklabels=[p['case_id'] for p in pairs],
           title='Every paired new condition retained')
    for i in range(len(pairs)):
        for j in range(4): ax.text(j, i, 'Yes' if matrix[i,j] else 'No', ha='center', va='center', color='white' if matrix[i,j] else 'black')
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(out/f'new10_all_pairs.{ext}', dpi=180)
    plt.close(fig)
    dump(out/'FIGURE_NOTES.json', {'primary':'tray_containment_success', 'existing_evaluation_n_per_method':5,
        'new_evaluation_n_per_method':10, 'different_evaluations_not_pooled':True,
        'actual_RGB_pairs':'../three_stage_analysis/paired_images/', 'normalized_visibility_not_used':True,
        'source_results_sha256':sha(protocol/'results_summary.json')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('evaluation/relocated_apple'))
    args = parser.parse_args(); base = args.root; protocol = base/'holdout_comparison'
    status_file = base/'postprocess_status.json'; attempt = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = base/'postprocess_runs'/attempt; archive.mkdir(parents=True, exist_ok=False)
    if status_file.exists(): shutil.copy2(status_file, archive/'previous_status.json')
    status = {'started_utc':utc(), 'source_sha256':sha(__file__), 'policy_or_simulator_executed':False,
              'commands':[], 'root':str(base)}
    def save():
        dump(status_file, status); dump(archive/'status.json', status)
    def run(script, *params):
        command=[sys.executable,str(script),*map(str,params)]
        item={'command':command,'started_utc':utc()};status['commands'].append(item);save()
        print('POSTHOC_START',json.dumps(command),flush=True)
        proc=subprocess.run(command)
        item.update(return_code=proc.returncode,finished_utc=utc());save()
        if proc.returncode: raise RuntimeError(f'Posthoc subprocess failed: {command}')
    try:
        save(); lock=read(protocol/'LOCK.json'); comparisons=validate_fixed_adoption(protocol,lock)
        run(ANALYZER,'--root',protocol,'--expect','20')
        result=formal_results(base,protocol,lock,comparisons)
        figures(base,protocol,result)
        run('scripts/export_improvement_materials.py','--root',base)
        videos=read(base/'materials/video_validation.json')
        assert videos['all_full_decodes_passed'] and len(videos['videos'])==20
        assert all(v['role']=='VLA_main' for v in videos['videos'])
        run(OLD/'tools/review_drop_candidates.py','--root',protocol)
        status.update(return_code=0,formal_results=str(protocol/'results_summary.json'),
                      decoded_videos=20,decoded_frames=sum(v['frames'] for v in videos['videos']))
        print('HOLDOUT_POSTHOC_COMPLETED',json.dumps({'groups':result['groups'],
              'pair_categories':result['tray_containment_pair_categories']}),flush=True)
    except Exception:
        status.update(return_code=1,traceback=traceback.format_exc());raise
    finally:
        status['finished_utc']=utc();save()


if __name__=='__main__':
    main()
