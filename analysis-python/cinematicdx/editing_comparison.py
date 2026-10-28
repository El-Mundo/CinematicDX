"""Film-level conditional permutation reference, never frame-level significance."""
from collections import defaultdict
import numpy as np


def bounded_roundoff_copy(features):
    """Correct only machine-epsilon range overshoot; keep raw arrays untouched."""
    result=dict(features);changes={};limit=8*np.finfo(np.float64).eps
    for name in ['roi_mean','roi_std']:
        values=np.asarray(features[name],float)
        if not np.isfinite(values).all() or np.any(values < -limit) or np.any(values > 1+limit):
            raise ValueError('Substantive/nonfinite range error; epsilon repair is not permitted.')
        indices=np.flatnonzero((values<0)|(values>1))
        if len(indices):
            repaired=np.clip(values,0,1);result[name]=repaired
            changes[name]=[dict(index=int(i),raw=float(values[i]),corrected=float(repaired[i])) for i in indices]
    return result,dict(tolerance=limit,changes=changes,raw_arrays_modified=False)


def transient_return_flags(times,images,cut_times):
    """Flag brief A-B-A-like gray changes, without labelling or deleting a cut.

    A genuine brief insert can also return; source flashes/motion need review.
    This diagnostic must never be reported as independently verified false cuts.
    """
    t=np.asarray(times,float);gray=np.asarray(images)
    if len(t)!=len(gray) or gray.ndim!=3:raise ValueError('Aligned image observations required.')
    result=[]
    for cut in cut_times:
        if cut-.12<t[0] or cut+.12>t[-1]:continue
        left=int(np.searchsorted(t,cut-.12));right=int(np.searchsorted(t,cut+.12))
        a=gray[left].astype(float)/255;b=gray[right].astype(float)/255
        baseline=float(np.abs(a-b).mean())
        peak=max(float(np.abs(image.astype(float)/255-a).mean()) for image in gray[left:right+1])
        if baseline<=.03 and peak>=.10:result.append(dict(cut_playback_seconds=float(cut),
            support_start_seconds=float(t[left]),support_end_seconds=float(t[right]),endpoint_mad=baseline,peak_mad=peak,
            interpretation='Possible transient return or true brief insert; not verified flash/false positive.'))
    return result


def conditional_studio_reference(films,*,metric='primary_cut_candidates_per_minute',seed=20261026,permutations=999,include_width=False):
    # Single-production records avoid sharing one film between test groups.
    pool=[f for f in films if f['measured'] and len(f['studios'])==1]
    counts=defaultdict(int)
    for f in pool:counts[f['studios'][0]['studio_id']]+=1
    pool=[f for f in pool if counts[f['studios'][0]['studio_id']]>=10]
    cells=defaultdict(list)
    for film in pool:
        key=(film['year'],film['film_type'],film['colour'])
        if include_width:key+=(film['source_width'],)
        cells[key].append(film)
    cells={key:members for key,members in cells.items() if len(members)>=5 and len({f['studios'][0]['studio_id'] for f in members})>=2}
    result=dict(status='PROVISIONAL',metric=metric,single_production_only=True,minimum_initial_studio_n=10,
        cell_fields=['year','film_type','metadata_colour']+(['source_width'] if include_width else []),
        minimum_cell_n=5,minimum_cell_studios=2,seed=seed,permutations=permutations,
        interpretation='Conditional exchangeability reference for the observed digital copies. Unknown source/genre/history differences remain; no causal studio effect or population sampling claim.')
    if not cells:
        return dict(result,status='BLOCKED',reason='No matching cells under the frozen criteria.',film_n=0)
    ordered=[f for members in cells.values() for f in members];labels=[f['studios'][0]['studio_id'] for f in ordered]
    studio_ids=sorted(set(labels));codes=np.asarray([studio_ids.index(g) for g in labels]);values=np.asarray([f[metric] for f in ordered],float)
    indices=[];offset=0
    for members in cells.values():indices.append(np.arange(offset,offset+len(members)));offset+=len(members)
    residual=values.copy()
    for cell in indices:residual[cell]-=residual[cell].mean()
    n=np.bincount(codes,minlength=len(studio_ids));total=float(np.dot(residual,residual))
    if total<=1e-15:return dict(result,status='BLOCKED',reason='No residual variation.',film_n=len(ordered))
    def statistic(y):
        sums=np.bincount(codes,weights=y,minlength=len(studio_ids))
        return float(np.sum(sums*sums/n)/total)
    observed=statistic(residual);rng=np.random.default_rng(seed);null=[]
    for _ in range(permutations):
        shuffled=residual.copy()
        for cell in indices:shuffled[cell]=rng.permutation(residual[cell])
        null.append(statistic(shuffled))
    return dict(result,film_n=len(ordered),cell_n=len(cells),studio_n=len(studio_ids),
        observed_between_studio_residual_share=observed,null_median=float(np.median(null)),
        null_q025=float(np.quantile(null,.025)),null_q975=float(np.quantile(null,.975)),
        null_at_least_observed_fraction=(1+sum(v>=observed-1e-15 for v in null))/(1+len(null)),
        numerator_policy='One-sided conditional reference tail with+1 correction; exploratory, not a causal or random-sample probability.',
        film_keys=[f['film_key'] for f in ordered],studio_sample_sizes={sid:int(n[i]) for i,sid in enumerate(studio_ids)},null_statistics=null)
