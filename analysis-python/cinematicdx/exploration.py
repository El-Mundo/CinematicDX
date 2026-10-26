"""Small, explicit measurement and control functions for exploratory research.

Nothing here infers narrative units, character identity, camera movement classes,
or historical film appearance. Callers must bind actual inputs and save receipts.
"""
from collections import defaultdict
import math

import numpy as np


def exposure_bins(starts, ends, values, *, start=150., end=750., width=1.):
    """Average finite measurements by actual overlapping presentation exposure.

    Missing values remove valid exposure, never become zero. Every source interval
    must have positive length and intervals may touch but must not overlap.
    """
    starts, ends, values = [np.asarray(x, dtype=np.float64) for x in (starts, ends, values)]
    if not (starts.ndim == ends.ndim == values.ndim == 1 and len(starts) == len(ends) == len(values)):
        raise ValueError('Aligned one-dimensional arrays required.')
    if not (np.isfinite(starts).all() and np.isfinite(ends).all() and (ends > starts).all()):
        raise ValueError('Finite positive source intervals required.')
    if len(starts)>1 and (np.diff(starts).min()<=0 or np.any(ends[:-1]>starts[1:]+1e-8)):
        raise ValueError('Source intervals must be ordered and nonoverlapping.')
    if not (math.isfinite(start) and math.isfinite(end) and end>start and width>0):
        raise ValueError('Invalid bin range.')
    left=np.arange(start,end,width,dtype=float); right=np.minimum(left+width,end)
    mean=np.full(len(left),np.nan);valid_exposure=np.zeros(len(left));support=np.zeros(len(left))
    finite=np.isfinite(values)
    for i,(a,b) in enumerate(zip(left,right)):
        w=np.maximum(0,np.minimum(ends,b)-np.maximum(starts,a))
        support[i]=w.sum(); w=w*finite;valid_exposure[i]=w.sum()
        if valid_exposure[i]>0:mean[i]=np.dot(w[finite],values[finite])/valid_exposure[i]
    return dict(starts=left,ends=right,values=mean,valid_exposure=valid_exposure,total_exposure=support)


def complete_hard_cut_runs(cuts, gradual, *, start=150., end=750.):
    """Hard-cut-bounded intervals only; split sequences at every gradual gap."""
    cuts=sorted(cuts,key=lambda c:c['playback_seconds'])
    times=[float(c['playback_seconds']) for c in cuts]
    if len(set(times))!=len(times) or any(not start<=t<end for t in times):
        raise ValueError('Unique in-coverage cut times required.')
    runs=[];current=[];excluded=[];intervals=[]
    for ca,cb in zip(cuts,cuts[1:]):
        a,b=ca['playback_seconds'],cb['playback_seconds']
        crossing=[g['transition_id'] for g in gradual if min(b,g['end_playback_seconds'])>max(a,g['start_playback_seconds'])]
        row=dict(interval_id=ca['cut_id']+'__'+cb['cut_id'],start_cut_id=ca['cut_id'],end_cut_id=cb['cut_id'],
                 start_seconds=a,end_seconds=b,duration_seconds=b-a)
        if crossing:
            if current:runs.append(current);current=[]
            excluded.append(dict(row,excluded_gradual_ids=crossing))
        else:current.append(row);intervals.append(row)
    if current:runs.append(current)
    return dict(runs=runs,intervals=intervals,excluded_cross_gradual_intervals=excluded,
                boundary_policy='Only two-hard-cut-bounded intervals; no window edges or gradual spans counted as complete shots.')


def sequence_statistics(runs):
    arrays=[np.log(np.asarray(run,dtype=float)) for run in runs if len(run)>0]
    if any(not np.isfinite(x).all() for x in arrays):raise ValueError('Positive finite durations required.')
    left=[x[:-1] for x in arrays if len(x)>1];right=[x[1:] for x in arrays if len(x)>1]
    if not left:return dict(adjacent_pair_count=0,mean_absolute_log_ratio=None,lag1_log_correlation=None)
    a,b=np.concatenate(left),np.concatenate(right)
    corr=float(np.corrcoef(a,b)[0,1]) if np.std(a)>1e-12 and np.std(b)>1e-12 else None
    return dict(adjacent_pair_count=len(a),mean_absolute_log_ratio=float(np.abs(b-a).mean()),lag1_log_correlation=corr)


def shuffled_sequence_controls(runs, *, draws=1999, seed=20261026):
    rng=np.random.default_rng(seed)
    observed=sequence_statistics(runs)
    null=[sequence_statistics([rng.permutation(r).tolist() for r in runs]) for _ in range(draws)]
    return observed,null


def interval_mean(series, a, b, *, min_valid_fraction=.95):
    if b<=a:return float('nan')
    w=np.maximum(0,np.minimum(series['ends'],b)-np.maximum(series['starts'],a))
    valid=np.isfinite(series['values'])
    fractions=np.divide(series['valid_exposure'],series['ends']-series['starts'])
    effective=w*fractions*valid
    if effective.sum() < min_valid_fraction*(b-a):return float('nan')
    return float(np.dot(effective[valid],series['values'][valid])/effective.sum())


def changes_at(series, centers, *, window=5., exclusion=1., min_valid_fraction=.95):
    rows=[]
    for c in centers:
        before=interval_mean(series,c-window,c-exclusion,min_valid_fraction=min_valid_fraction)
        after=interval_mean(series,c+exclusion,c+window,min_valid_fraction=min_valid_fraction)
        rows.append(dict(center_seconds=float(c),before=before,after=after,signed_change=after-before,absolute_change=abs(after-before)))
    return rows


def circular_centers(centers, *, start=150., end=750., window=5., min_shift=30):
    """Common shifts preserve circular onset spacing; no window crosses an edge.

    This is a descriptive conditional reference, not a test of random event labels
    in nonstationary film data and not independent observations.
    """
    accepted=[];offsets=[]
    for offset in range(min_shift,int(end-start)-min_shift+1):
        shifted=start+(np.asarray(centers)-start+offset)%(end-start)
        if ((shifted-window>=start)&(shifted+window<=end)).all():
            accepted.append(shifted);offsets.append(offset)
    return np.asarray(accepted),offsets


def cut_matched_centers(centers, cuts, gradual, *, start=150., end=750., window=5.,
                        jitter=0., draws=1999, seed=20261026):
    """Reference cut positions control ordinary editing discontinuities.

    Keep event-to-cut offsets; no event onset is snapped to a cut. Sample without
    replacement within a draw and third. Overlapping control windows are allowed
    and reported; draws and windows are not independent research samples.
    """
    region=lambda t:min(2,max(0,int((t-start)/(end-start)*3)))
    cut_times=np.asarray([c['playback_seconds'] for c in cuts],float)
    selected=[];excluded=[]
    for i,c in enumerate(centers):
        near_gradual=any(g['start_playback_seconds']-1<=c<=g['end_playback_seconds']+1 for g in gradual)
        j=int(np.argmin(np.abs(cut_times-c)))
        if not near_gradual and abs(cut_times[j]-c)<=1:
            selected.append(dict(event_index=i,event_seconds=float(c),cut_seconds=float(cut_times[j]),
                                 event_to_cut_offset=float(c-cut_times[j]),region=region(c)))
        else:excluded.append(dict(event_index=i,event_seconds=float(c),reason='gradual_nearby_or_no_hard_cut_within_1s'))
    pools={}
    for group in range(3):
        pools[group]=[float(t) for t in cut_times if region(t)==group and start+window+2<=t<=end-window-2
                      and all(abs(t-c)>=2*window+2 for c in centers)
                      and all(min(t+window+2,g['end_playback_seconds'])<=max(t-window-2,g['start_playback_seconds']) for g in gradual)]
    needed={g:sum(s['region']==g for s in selected) for g in range(3)}
    if not selected or any(len(pools[g])<needed[g] for g in range(3)):
        return dict(status='BLOCKED',reason='Insufficient same-third non-event cut controls without reuse.',
                    selected_events=selected,excluded_events=excluded,pools=pools,needed=needed,centers=None)
    rng=np.random.default_rng(seed);matrix=np.empty((draws,len(selected)))
    for k in range(draws):
        assignments={g:iter(rng.choice(pools[g],size=needed[g],replace=False).tolist()) for g in range(3)}
        for j,s in enumerate(selected):matrix[k,j]=next(assignments[s['region']])+s['event_to_cut_offset']+jitter
    overlaps=[]
    for row in matrix:
        overlaps.append(sum(abs(row[i]-row[j])<2*window for i in range(len(row)) for j in range(i)))
    return dict(status='PROVISIONAL',selected_events=selected,excluded_events=excluded,pools=pools,needed=needed,centers=matrix,
                control_window_overlap_pairs_per_draw_mean=float(np.mean(overlaps)),
                windows_independent=False,no_reuse_within_draw=True,control_centers_include_event_to_cut_offset=True)


def correlation(a,b):
    a,b=np.asarray(a,float),np.asarray(b,float);mask=np.isfinite(a)&np.isfinite(b)
    if mask.sum()<3 or np.std(a[mask])<1e-12 or np.std(b[mask])<1e-12:return None
    return float(np.corrcoef(a[mask],b[mask])[0,1])


def rankdata(x):
    x=np.asarray(x);order=np.argsort(x,kind='stable');ranks=np.empty(len(x),float)
    i=0
    while i<len(x):
        j=i+1
        while j<len(x) and x[order[j]]==x[order[i]]:j+=1
        ranks[order[i:j]]=(i+j-1)/2;i=j
    return ranks


def spearman(a,b):
    a,b=np.asarray(a,float),np.asarray(b,float);ok=np.isfinite(a)&np.isfinite(b)
    return correlation(rankdata(a[ok]),rankdata(b[ok]))


def image_pair_features(prev,nxt,dt, *, cv2):
    """Pixel displacement/activity at the supplied digital resolution, not camera labels."""
    prev,nxt=np.asarray(prev,np.uint8),np.asarray(nxt,np.uint8)
    if prev.ndim!=2 or prev.shape!=nxt.shape or not dt>0:raise ValueError('Aligned gray frames and positive dt required.')
    a,b=prev.astype(np.float32)/255,nxt.astype(np.float32)/255
    corr=correlation(a.ravel(),b.ravel())
    flow=cv2.calcOpticalFlowFarneback(prev,nxt,None,.5,3,15,3,5,1.2,0)
    magnitude=np.linalg.norm(flow,axis=2);translation=np.median(flow.reshape(-1,2),axis=0)
    residual=np.linalg.norm(flow-translation,axis=2);diag=math.hypot(*prev.shape)
    return dict(mad=float(np.mean(np.abs(b-a))),flicker_one_minus_correlation=None if corr is None else 1-corr,
                flow_median_diagonals_per_second=float(np.median(magnitude)/diag/dt),
                flow_p90_diagonals_per_second=float(np.quantile(magnitude,.9)/diag/dt),
                flow_residual_p90_diagonals_per_second=float(np.quantile(residual,.9)/diag/dt),
                median_flow_dx_pixels=float(translation[0]),median_flow_dy_pixels=float(translation[1]),
                global_translation_diagonals_per_second=float(np.linalg.norm(translation)/diag/dt),
                previous_gray_std=float(a.std()),next_gray_std=float(b.std()))


def dct_descriptor(gray, *, cv2):
    small=cv2.resize(np.asarray(gray,np.float32)/255,(32,32),interpolation=cv2.INTER_AREA)
    # A constant image has no configuration descriptor. Do not normalise tiny
    # floating-point DCT roundoff into an invented unit-length pattern.
    if np.std(small,dtype=np.float64)<1e-6:return np.full(63,np.nan)
    coefficients=cv2.dct(small)[:8,:8].ravel()[1:]
    norm=np.linalg.norm(coefficients)
    return coefficients/norm if norm>1e-8 else np.full(63,np.nan)


def dhash_descriptor(gray, *, cv2):
    small=cv2.resize(np.asarray(gray),(9,8),interpolation=cv2.INTER_AREA)
    return (small[:,1:]>small[:,:-1]).ravel()


def auc(positive_scores,negative_scores):
    pos,neg=np.asarray(positive_scores,float),np.asarray(negative_scores,float)
    pos=pos[np.isfinite(pos)];neg=neg[np.isfinite(neg)]
    if not len(pos) or not len(neg):return None
    comparison=pos[:,None]-neg[None,:]
    return float(((comparison>0)+.5*(comparison==0)).mean())


def null_summary(observed, values):
    values=np.asarray(values,dtype=float);values=values[np.isfinite(values)]
    if not len(values) or observed is None or not np.isfinite(observed):
        return dict(observed=None if observed is None or not np.isfinite(observed) else float(observed),valid_control_count=len(values),control_median=None,control_q025=None,control_q975=None,fraction_controls_le_observed=None)
    return dict(observed=float(observed),valid_control_count=len(values),control_median=float(np.median(values)),
                control_q025=float(np.quantile(values,.025)),control_q975=float(np.quantile(values,.975)),
                fraction_controls_le_observed=float((values<=observed).mean()),
                interpretation='Descriptive conditional reference rank; not a calibrated p-value or confidence interval.')
