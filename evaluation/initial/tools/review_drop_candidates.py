"""CPU-only diagnostic frames from saved MP4s. NEVER confirms a drop automatically.

Reads existing three_stage_analysis/trial_details.json after main completion.
No policy, simulation, score edits or video editing are performed.
"""
import argparse,csv,json,math
from pathlib import Path
from PIL import Image,ImageDraw

def clusters(steps,gap):
    groups=[]
    for step in sorted(set(steps)):
        if not groups or step-groups[-1][-1]>gap:groups.append([step])
        else:groups[-1].append(step)
    return groups

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--details');p.add_argument('--out');p.add_argument('--context-seconds',type=float,default=1.0);a=p.parse_args()
    root=Path(a.root);details=Path(a.details) if a.details else root/'three_stage_analysis/trial_details.json'
    out=Path(a.out) if a.out else root/'drop_candidate_review';out.mkdir(parents=True,exist_ok=False)
    trialroot=root/'trials' if (root/'trials').is_dir() else root
    items=json.loads(details.read_text(encoding='utf-8-sig'));manifest=json.loads((trialroot/'manifest.json').read_text());hz=float(manifest['control_freq_hz'])
    all_points=[];reviews=[];index=[]
    for item in items:
        episode=item['episode'];ep=trialroot/episode;result=json.loads((ep/'result.json').read_text());video=ep/'rollout.mp4'
        drop=set(map(int,item.get('drop_candidate_steps',[])));below=set(map(int,item.get('below_table_steps',[])));union=sorted(drop|below)
        assert all(0<=step<result['steps'] for step in union)
        for step in union:
            all_points.append({'episode':episode,'case':item['case'],'method':result['method'],'occlusion':result['occlusion'],'telemetry_step_zero_based':step,
                'video_frame':step+1,'elapsed_sim_seconds':(step+1)/hz,'drop_candidate':step in drop,'below_table_candidate':step in below,'video':str(video),'manual_status':'unreviewed_candidate'})
        if not union:continue
        import imageio.v2 as iio
        reader=iio.get_reader(str(video));fps=float(reader.get_meta_data()['fps']);assert abs(fps-hz)<1e-6
        group_gap=max(1,round(hz));groups=clusters(union,group_gap)
        for event_id,group in enumerate(groups):
            label=f'{episode}_event_{event_id:02d}';folder=out/label;folder.mkdir()
            context=round(a.context_seconds*fps);half=round(context/2)
            anchors={group[0]+1,group[-1]+1};frames=sorted(set(max(0,min(result['steps'],anchor+offset)) for anchor in anchors for offset in [-context,-half,0,half,context]))
            banner=75;cellheight=312;sheet=Image.new('RGB',(1024,banner+cellheight*math.ceil(len(frames)/2)),'white');draw=ImageDraw.Draw(sheet)
            draw.text((5,5),'UNREVIEWED DROP CANDIDATE - NOT A CONFIRMED DROP',fill='#b91c1c')
            draw.text((5,23),f'{episode} / {item["case"]} / {result["method"]} / {result["occlusion"]}',fill='black')
            draw.text((5,41),f'Candidate log steps {group[0]}..{group[-1]} ; all individual samples retained in candidate_times.csv',fill='black')
            for j,frame in enumerate(frames):
                image=Image.fromarray(reader.get_data(frame));image.save(folder/f'frame_{frame:04d}.png')
                col=j%2;row=j//2;x=col*512;y=banner+row*cellheight;logstep=frame-1
                flagged=logstep in union;draw.text((x+4,y+2),f'frame {frame} / t={frame/fps:.2f}s / log step {logstep if frame else "initial"}',fill='#b91c1c' if flagged else 'black')
                draw.text((x+4,y+16),'CANDIDATE SAMPLE' if flagged else 'context frame',fill='#b91c1c' if flagged else 'black')
                sheet.paste(image.resize((512,280)),(x,y+31))
            target=out/f'{label}_contact_sheet.png';sheet.save(target)
            reviews.append({'episode':episode,'case':item['case'],'method':result['method'],'occlusion':result['occlusion'],'candidate_first_log_step':group[0],
                'candidate_last_log_step':group[-1],'elapsed_sim_start_seconds':(group[0]+1)/hz,'elapsed_sim_end_seconds':(group[-1]+1)/hz,
                'candidate_types':'+'.join(x for x,values in [('drop',drop),('below_table',below)] if any(s in values for s in group)),
                'candidate_samples':len(group),'contact_sheet':str(target),'video':str(video),'manual_review_status':'unreviewed','confirmed_drop':'','review_note':''})
            index.append({'episode':episode,'event':event_id,'candidate_steps':group,'extracted_video_frames':frames,'contact_sheet':str(target)})
        reader.close()
    point_fields=['episode','case','method','occlusion','telemetry_step_zero_based','video_frame','elapsed_sim_seconds','drop_candidate','below_table_candidate','video','manual_status']
    review_fields=['episode','case','method','occlusion','candidate_first_log_step','candidate_last_log_step','elapsed_sim_start_seconds','elapsed_sim_end_seconds','candidate_types','candidate_samples','contact_sheet','video','manual_review_status','confirmed_drop','review_note']
    for name,rows,fields in [('candidate_times.csv',all_points,point_fields),('manual_review.csv',reviews,review_fields)]:
        with (out/name).open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    metadata={'source_details':str(details),'trial_count':len(items),'candidate_sample_count':len(all_points),'candidate_event_clusters':len(reviews),'events':index,
        'auto_confirmed_drops':False,'core_or_scores_modified':False,'simulation_or_policy_executed':False,'frame_mapping':'Video frame0 is initial image. Post-action telemetry log stepN maps to MP4 frameN+1; elapsed=(N+1)/20sec.'}
    (out/'index.json').write_text(json.dumps(metadata,indent=2))
    (out/'README.md').write_text('# Drop candidate review (unconfirmed)\n\nThese are diagnostic still frames from existing MP4s, not an edited film and not new trials. Every candidate sample is retained in candidate_times.csv. Consecutive samples within1second are grouped for contact sheets; no candidate samples are discarded from the time list. Context images surround the first and last sample of each cluster.\n\nA logged contact/velocity/height flag is a candidate, NOT a visually confirmed drop. Inspect the original recording and frames, then fill manual_review.csv. confirmed_drop is intentionally blank; this tool never changes metrics or trial outcomes. A supported release or temporary contact loss may trigger a candidate. No confirmed count is supplied.\n\nVideo frame0 is initial state. Telemetry stepN (after actionN) corresponds to video frameN+1 and elapsed simulated time(N+1)/20. Input source is trial_details.json; world height criteria remain those of the already executed analysis.\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'trial_count':len(items),'candidate_samples':len(all_points),'clusters':len(reviews),'automatic_confirmation':False}))

if __name__=='__main__':main()
