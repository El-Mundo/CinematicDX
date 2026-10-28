"""Film-level descriptive studio summaries; no frame-level significance tests."""
from collections import defaultdict
import numpy as np


def resolve_job_film_keys(jobs,documents,overrides,valid_keys):
    """Apply explicit hash-bound derived identities without editing source claims."""
    bindings={b['job_id']:b for b in overrides.get('bindings',[])};result=[]
    for original in jobs:
        job=dict(original,original_film_key=original['film_key'])
        binding=bindings.get(job['job_id'])
        if binding:
            if binding['original_film_key']!=original['film_key']:raise ValueError('Override source claim changed.')
            if binding['film_key'] not in valid_keys:raise ValueError('Override needs an existing stable film key.')
            if job['job_id'] not in documents or documents[job['job_id']]['video_version_id']!=binding['expected_video_version_id']:
                raise ValueError('Identity override is not bound to the measured file bytes.')
            job.update(film_key=binding['film_key'],linkage_status=binding['validation_status'])
        result.append(job)
    if set(bindings)-{j['job_id'] for j in jobs}:raise ValueError('Override contains an unknown source job.')
    return result


def weighted_quantiles(values,weights,quantiles=(.25,.5,.75)):
    v,w=np.asarray(values,float),np.asarray(weights,float);okay=np.isfinite(v)&np.isfinite(w)&(w>0)
    v,w=v[okay],w[okay]
    if not len(v):return [None for _ in quantiles]
    order=np.argsort(v);v,w=v[order],w[order];positions=(np.cumsum(w)-w/2)/w.sum()
    return [float(x) for x in np.interp(quantiles,positions,v)]


def weighted_mean(values,weights):
    v,w=np.asarray([np.nan if x is None else x for x in values],float),np.asarray(weights,float)
    ok=np.isfinite(v)&np.isfinite(w)&(w>0)
    return float(np.dot(v[ok],w[ok])/w[ok].sum()) if ok.any() else None


def year_cell_residuals(films):
    cells=defaultdict(list)
    for film in films:
        if film['eligible'] and film.get('mean_abs_change_30s_z') is not None:
            cells[(film['year'],film['colour'],film['film_type'])].append(film)
    result={};details=[]
    for key,members in cells.items():
        studios={s['studio_id'] for f in members for s in f['studios']}
        enough=len(members)>=5 and len(studios)>=2
        mean=float(np.mean([f['mean_abs_change_30s_z'] for f in members]))
        details.append(dict(year=key[0],colour=key[1],film_type=key[2],film_n=len(members),studio_n=len(studios),usable=enough,mean_change_30s_z=mean))
        for film in members:result[film['film_key']]=dict(residual=film['mean_abs_change_30s_z']-mean if enough else None,cell_n=len(members),cell_usable=enough)
    return result,details


def group_statistics(films,studio_id,*,predicate=None,single_studio=False):
    predicate=predicate or (lambda f:True)
    metadata=[f for f in films if any(s['studio_id']==studio_id for s in f['studios']) and predicate(f)
              and (not single_studio or len(f['studios'])==1)]
    available=[f for f in metadata if f['video_available']]
    measured=[f for f in metadata if f['measured']]
    eligible=[f for f in metadata if f['eligible']]
    weights=[next(s['fractional_weight'] for s in f['studios'] if s['studio_id']==studio_id) for f in eligible]
    n=len(eligible);total=sum(weights)
    result=dict(metadata_member_films=len(metadata),available_member_films=len(available),measured_member_films=len(measured),
        eligible_member_films=n,missing_video_member_films=len(metadata)-len(available),quality_or_linkage_excluded_member_films=len(measured)-n,
        metadata_fractional_films=sum(next(s['fractional_weight'] for s in f['studios'] if s['studio_id']==studio_id) for f in metadata),
        eligible_fractional_films=total,effective_film_n=total**2/sum(w*w for w in weights) if weights else 0,
        coproduct_eligible_member_films=sum(len(f['studios'])>1 for f in eligible),
        eligible_mean_year=weighted_mean([f['year'] for f in eligible],weights),
        eligible_bw_fraction=weighted_mean([f['colour']=='B&W' for f in eligible],weights),
        eligible_feature_fraction=weighted_mean([f['film_type']=='Feature' for f in eligible],weights))
    for metric in ['mean_abs_change_10s_z','mean_abs_change_30s_z','mean_abs_change_60s_z','core_10_90_mean_abs_change_30s_z','gray_roi_time_mean','gray_roi_temporal_sd',
                   'roi_spatial_contrast_mean','year_colour_type_residual','full_vs_roi_profile_correlation']:
        values=[f.get(metric) for f in eligible]
        result[metric+'__mean']=weighted_mean(values,weights)
        q=weighted_quantiles([np.nan if v is None else v for v in values],weights)
        for name,value in zip(['q25','median','q75'],q):result[metric+'__'+name]=value
        result[metric+'__film_n']=sum(v is not None and np.isfinite(v) for v in values)
    return result


def grouped_profile(films,profiles,studio_id,*,predicate=None):
    members=[f for f in films if f['eligible'] and (predicate is None or predicate(f)) and any(s['studio_id']==studio_id for s in f['studios'])]
    output=[]
    for index in range(100):
        values=[profiles[f['film_key']][index] for f in members]
        weights=[next(s['fractional_weight'] for s in f['studios'] if s['studio_id']==studio_id) for f in members]
        q25,median,q75=weighted_quantiles(values,weights)
        output.append(dict(position_bin=index,position_start_fraction=index/100,position_end_fraction=(index+1)/100,
             studio_z_mean=weighted_mean(values,weights),studio_z_q25=q25,studio_z_median=median,studio_z_q75=q75,
             film_n=sum(np.isfinite(v) for v in values)))
    return output
