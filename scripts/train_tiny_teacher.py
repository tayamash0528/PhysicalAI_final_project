"""Saved-data/training/delta/inference smoke test. No placement claim."""
import argparse,hashlib,json,random,time,shutil
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import save_file,load_file
import run_rollout as rr
p=argparse.ArgumentParser();p.add_argument('--dataset');p.add_argument('--dataset-list');p.add_argument('--steps',type=int,default=20)
p.add_argument('--out',required=True);p.add_argument('--resume-delta',default=None)
p.add_argument('--trainable-fp32',action='store_true')
p.add_argument('--checkpoint-every',type=int,default=0)
p.add_argument('--batch-size',type=int,default=1)
p.add_argument('--learning-rate',type=float,default=1e-4)
p.add_argument('--train-projections-only',action='store_true',help='Freeze the96.7M expert; keep full parent expert tensors in every saved checkpoint')
a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,out/'executed_training_source.py')
path=Path(a.dataset_list or a.dataset)
dataset_spec=json.loads(path.read_text()) if a.dataset_list else {}
paths=[Path(p) for p in dataset_spec['episodes']] if a.dataset_list else [path]
episodes=[];dataset_bytes=0;data_hashes={};loaded_episodes={}
for ep_path in paths:
    # Repeated entries are explicit sampling weights, not new independent data.
    if str(ep_path) in loaded_episodes:
        episodes.append(loaded_episodes[str(ep_path)]);continue
    dm=json.loads((ep_path.parent/'dataset_manifest.json').read_text())
    if not dm['valid_successful_placement']:raise ValueError('Teacher placement not successful')
    data=np.load(ep_path);n=data['state'].shape[0]
    ep={'state':data['state'],'action':data['action'],'image':data['image'],'image2':data['image2'],'meta':dm}
    assert ep['state'].shape==(n,8) and ep['action'].shape==(n,7)
    assert ep['image'].shape==(n,256,256,3) and ep['image'].dtype==np.uint8
    assert dm['seed'] not in dm['held_out_evaluation_seeds'] and n>50
    dataset_bytes+=sum(ep[k].nbytes for k in ['state','action','image','image2'])
    if dataset_bytes>4*1024**3:raise RuntimeError('Preload memory budget exceeded')
    episodes.append(ep);loaded_episodes[str(ep_path)]=ep
    data_hashes[str(ep_path)]=hashlib.sha256(ep_path.read_bytes()).hexdigest();data.close()
focus_windows=dataset_spec.get('focus_windows',[]);focus_probability=float(dataset_spec.get('focus_probability',0))
assert 0<=focus_probability<=1
focus_indices=[]
for spec in focus_windows:
    ei=paths.index(Path(spec['episode']));lo=int(spec.get('start',0));hi=int(spec['stop_exclusive'])
    assert 0<=lo<hi<=len(episodes[ei]['state'])-50
    focus_indices.append((ei,lo,hi))
assert not focus_probability or focus_indices
focus_sample_count=0
random.seed(42);np.random.seed(42);torch.manual_seed(42)
meta=json.loads(Path('evidence/model.json').read_text());mp=meta['local_path']
cfg=rr.SmolVLAConfig.from_pretrained(mp);cfg.device='cuda';cfg.pretrained_path=Path(mp)
cfg.load_vlm_weights=False;cfg.n_action_steps=10;cfg.train_expert_only=True;cfg.freeze_vision_encoder=True
policy=rr.SmolVLAPolicy.from_pretrained(mp,config=cfg).to('cuda')
if a.trainable_fp32:
    for param in policy.parameters():
        if param.requires_grad:param.data=param.data.float()
if a.resume_delta:policy.load_state_dict(load_file(a.resume_delta),strict=False)
pre,post=rr.make_pre_post_processors(cfg,pretrained_path=mp,preprocessor_overrides={'device_processor':{'device':'cuda'}})
saved_delta_params={name:param for name,param in policy.named_parameters() if param.requires_grad}
if a.train_projections_only:
    for name,param in policy.named_parameters():
        if name.startswith('model.vlm_with_expert.lm_expert.'):param.requires_grad_(False)
params={name:param for name,param in policy.named_parameters() if param.requires_grad}
probe=next(iter(params));before=params[probe].detach().clone()
opt=torch.optim.AdamW(params.values(),lr=a.learning_rate,weight_decay=1e-10)
def batch(i,ei=0):
    ep=episodes[ei]
    b={'observation.state':torch.from_numpy(ep['state'][i]).float()[None],
       'action':torch.from_numpy(ep['action'][i:i+cfg.chunk_size]).float()[None],'task':[ep['meta']['task']]}
    for k in ['image','image2']:b[f'observation.images.{k}']=torch.from_numpy(ep[k][i]).permute(2,0,1).float().div(255)[None]
    return pre(b)
def sampled_batch(picks):
    b={'observation.state':torch.from_numpy(np.stack([episodes[e]['state'][i] for e,i in picks])).float(),
       'action':torch.from_numpy(np.stack([episodes[e]['action'][i:i+cfg.chunk_size] for e,i in picks])).float(),
       'task':[episodes[e]['meta']['task'] for e,i in picks]}
    for k in ['image','image2']:
        b[f'observation.images.{k}']=torch.from_numpy(np.stack([episodes[e][k][i] for e,i in picks])).permute(0,3,1,2).float().div(255)
    return pre(b)
policy.train();torch.cuda.reset_peak_memory_stats();times=[];losses=[];begin=time.perf_counter()
def save_delta(folder,step):
    folder.mkdir(parents=True,exist_ok=True)
    tmp=folder/'expert_delta.tmp.safetensors'
    save_file({k:v.detach().cpu().contiguous() for k,v in saved_delta_params.items()},str(tmp),
        metadata={'base_model':meta['repo_id'],'base_revision':meta['revision'],
                  'trainable_precision':'float32' if a.trainable_fp32 else 'original','steps':str(step)})
    tmp.replace(folder/'expert_delta.safetensors')
    rr.dump(folder/'checkpoint.json',{'steps':step,'dataset':str(path),'trainable_fp32':a.trainable_fp32,
        'learning_rate':a.learning_rate,'resume_delta':a.resume_delta,'train_projections_only':a.train_projections_only,
        'mean_recent_loss':float(np.mean(losses[-100:])), 'ready':True})
with (out/'training.jsonl').open('w') as log:
    for step in range(a.steps):
        picks=[]
        for _ in range(a.batch_size):
            if focus_indices and random.random()<focus_probability:
                ei,lo,hi=random.choice(focus_indices);i=random.randrange(lo,hi);focus_sample_count+=1
            else:
                ei=random.randrange(len(episodes)) if len(episodes)>1 else 0
                i=random.randrange(len(episodes[ei]['state'])-cfg.chunk_size)
            picks.append((ei,i))
        b=batch(i,ei) if a.batch_size==1 else sampled_batch(picks);opt.zero_grad(set_to_none=True)
        torch.cuda.synchronize();t=time.perf_counter()
        with torch.autocast('cuda',dtype=torch.bfloat16):loss,details=policy(b)
        if not torch.isfinite(loss):raise RuntimeError('Non-finite loss')
        loss.backward();gn=torch.nn.utils.clip_grad_norm_(params.values(),10.0);opt.step();torch.cuda.synchronize()
        elapsed=time.perf_counter()-t;times.append(elapsed);losses.append(float(loss))
        row={'step':step,'episode_index':ei,'teacher_frame':i,'sampled_windows':picks,'loss':float(loss),'grad_norm':float(gn),'seconds':elapsed,
             'peak_gpu_bytes':torch.cuda.max_memory_allocated()}
        log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
        if a.checkpoint_every and (step+1)%a.checkpoint_every==0:
            save_delta(out/'checkpoints'/f'step_{step+1:06d}',step+1)
save_file({k:v.detach().cpu().contiguous() for k,v in saved_delta_params.items()},str(out/'expert_delta.safetensors'),
          metadata={'base_model':meta['repo_id'],'base_revision':meta['revision'],
                    'trainable_precision':'float32' if a.trainable_fp32 else 'original'})
change=float((params[probe].detach()-before).abs().max());policy.eval();policy.reset()
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16,enabled=a.trainable_fp32):
    prediction=post(policy.select_action(batch(0)))
assert prediction.shape==(1,7) and torch.isfinite(prediction).all()
result={'status':'saved_data_training_inference_smoke_completed','base_model':meta['repo_id'],'base_revision':meta['revision'],
    'dataset':str(path),'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'data_files_sha256':data_hashes,
    'training_seed':[ep['meta']['seed'] for ep in loaded_episodes.values()],
    'held_out_evaluation_seeds':dm['held_out_evaluation_seeds'],'episodes':len(loaded_episodes),
    'sampling_entries':len(episodes),'sampling_frames_with_repetitions':sum(len(ep['state']) for ep in episodes),
    'focus_probability':focus_probability,'focus_windows':focus_windows,'actual_focus_sample_count':focus_sample_count,
    'frames':sum(len(ep['state']) for ep in loaded_episodes.values()),'preloaded_dataset_bytes':dataset_bytes,'steps':a.steps,
    'resume_delta':a.resume_delta,'resume_delta_sha256':hashlib.sha256(Path(a.resume_delta).read_bytes()).hexdigest() if a.resume_delta else None,
    'batch_size':a.batch_size,'sampled_windows':a.steps*a.batch_size,'chunk_size':cfg.chunk_size,'trainable_parameters':sum(x.numel() for x in params.values()),
    'train_projections_only':a.train_projections_only,'saved_delta_tensors':len(saved_delta_params),
    'saved_delta_parameters':sum(x.numel() for x in saved_delta_params.values()),
    'trainable_precision':'float32' if a.trainable_fp32 else 'original_mixed_bfloat16_float32',
    'precision':'bfloat16 autocast','optimizer':f'AdamW lr={a.learning_rate}','learning_rate':a.learning_rate,'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated(),
    'peak_gpu_reserved_bytes':torch.cuda.max_memory_reserved(),'mean_step_seconds':sum(times)/len(times),
    'wall_seconds':time.perf_counter()-begin,'first_loss':losses[0],'last_loss':losses[-1],
    'probe_parameter':probe,'probe_max_change':change,'inference_action':prediction.cpu().tolist(),
    'simulation_evaluation':'not run by this script','placement_success_claim':False,
    'normalization':'unchanged base-checkpoint mean/std; teacher action in OSC units'}
rr.dump(out/'result.json',result);print(json.dumps(result),flush=True)
