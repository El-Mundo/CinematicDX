"""Label-blind, CPU gradual-transition candidates from timestamped gray features.

This is a small rule-based prototype, not an exact reproduction of a published
detector. Scores describe heuristic fit and are never probabilities. No labels,
filenames, reference intervals, media paths or evaluation outcomes are consumed.
"""

import copy
import math
import time

import numpy as np


class GradualError(ValueError):
    """Feature coordinates or a declared detector configuration are invalid."""


DEFAULT_CONFIG = {
    "preset": "default", "enable_fades": True, "enable_dissolves": True,
    "analysis_width": 16, "analysis_height": 12, "scan_stride_seconds": 0.12,
    "durations_seconds": [0.48, 0.8, 1.2, 1.6, 2.4, 3.2, 4.8],
    "endpoint_mean_seconds": 0.08, "min_transition_seconds": 0.4, "max_transition_seconds": 5.0,
    "endpoint_rms_min": 0.06, "blend_residual_max": 0.20,
    "alpha_time_r2_min": 0.75, "intermediate_fraction_min": 0.35,
    "alpha_monotonic_fraction_min": 0.80, "alpha_backward_tolerance": 0.05,
    "max_step_fraction": 0.35, "alpha_start": 0.05, "alpha_end": 0.95,
    "fade_black_mean_max": 12/255, "fade_black_std_max": 0.04,
    "black_hold_min_seconds": 0.08, "fade_r2_min": 0.80,
    "fade_mean_amplitude_min": 0.08, "fade_std_amplitude_min": 0.01,
    "fade_monotonic_fraction_min": 0.80, "fade_mean_backward_tolerance": 0.01,
    "fade_std_backward_tolerance": 0.005,
    "nms_iou_threshold": 0.30, "nms_containment_threshold": 0.60,
    "motion_diagnostics": True, "motion_reject": False,
    "motion_response_min": 0.30, "motion_shift_min_pixels": 1.0,
    "motion_aligned_error_ratio_max": 0.55,
}


def configuration_presets():
    """The baseline and three predeclared combined configurations; never auto-select."""
    default = copy.deepcopy(DEFAULT_CONFIG)
    baseline = dict(copy.deepcopy(default), preset="fade_only_baseline", enable_dissolves=False)
    lenient = dict(copy.deepcopy(default), preset="lenient", endpoint_rms_min=0.04,
                   blend_residual_max=0.30, alpha_time_r2_min=0.65,
                   intermediate_fraction_min=0.25, alpha_monotonic_fraction_min=0.70,
                   max_step_fraction=0.45, fade_black_mean_max=16/255,
                   fade_r2_min=0.70, fade_mean_amplitude_min=0.06)
    strict = dict(copy.deepcopy(default), preset="strict", endpoint_rms_min=0.08,
                  blend_residual_max=0.12, alpha_time_r2_min=0.85,
                  intermediate_fraction_min=0.45, alpha_monotonic_fraction_min=0.90,
                  max_step_fraction=0.25, fade_black_mean_max=8/255,
                  fade_r2_min=0.90, fade_mean_amplitude_min=0.10)
    return {"fade_only_baseline": baseline, "default": default, "lenient": lenient, "strict": strict}


def _configuration(supplied):
    if supplied is not None and not isinstance(supplied, dict):
        raise GradualError("config must be a dictionary.")
    unknown = set(supplied or {})-set(DEFAULT_CONFIG)
    if unknown:
        raise GradualError("Unknown configuration fields: "+", ".join(sorted(unknown)))
    config = dict(copy.deepcopy(DEFAULT_CONFIG), **copy.deepcopy(supplied or {}))
    for key in ("enable_fades", "enable_dissolves", "motion_diagnostics", "motion_reject"):
        if type(config[key]) is not bool:
            raise GradualError(key+" must be boolean.")
    for key in ("analysis_width", "analysis_height"):
        if type(config[key]) is not int or config[key] <= 0:
            raise GradualError(key+" must be a positive integer.")
    for key, value in config.items():
        if key in ("preset", "durations_seconds", "analysis_width", "analysis_height") or type(value) is bool:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise GradualError(key+" must be a finite nonnegative number.")
    for key in ("scan_stride_seconds", "endpoint_mean_seconds", "min_transition_seconds",
                "max_transition_seconds", "blend_residual_max", "endpoint_rms_min"):
        if config[key] <= 0:
            raise GradualError(key+" must be positive.")
    if config["min_transition_seconds"] >= config["max_transition_seconds"]:
        raise GradualError("Transition duration limits are inconsistent.")
    if not 0 < config["alpha_start"] < config["alpha_end"] < 1:
        raise GradualError("Alpha refinement thresholds must satisfy 0 < start < end < 1.")
    durations = config["durations_seconds"]
    if not isinstance(durations, (list, tuple)) or not durations or any(
            isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value)
            or not config["min_transition_seconds"] <= value <= config["max_transition_seconds"] for value in durations):
        raise GradualError("durations_seconds must contain finite durations inside the declared limits.")
    config["durations_seconds"] = list(durations)
    return config


def _features(features, config):
    if not isinstance(features, dict):
        raise GradualError("features must be a dictionary, not a path.")
    required = ("gray_cache", "playback_seconds", "source_seconds", "frame_delta_seconds", "pts", "next_pts",
                "evaluation_mask", "roi_mean", "roi_std", "adjacent_mad")
    if any(key not in features for key in required):
        raise GradualError("Missing required feature arrays: "+", ".join(key for key in required if key not in features))
    gray = np.asarray(features["gray_cache"])
    if gray.ndim != 3 or gray.dtype != np.uint8 or len(gray) < 3:
        raise GradualError("gray_cache must be an N,H,W uint8 array with at least three frames.")
    count, height, width = gray.shape
    if height % config["analysis_height"] or width % config["analysis_width"]:
        raise GradualError("Cache dimensions must divide evenly into the requested analysis shape.")
    arrays = {}
    for key in required[1:]:
        array = np.asarray(features[key])
        if array.ndim != 1 or len(array) != count:
            raise GradualError(key+" must be a one-dimensional array matching gray_cache.")
        arrays[key] = array
    if arrays["evaluation_mask"].dtype != np.bool_ or not np.any(arrays["evaluation_mask"]):
        raise GradualError("evaluation_mask must be boolean with nonempty evaluation coverage.")
    for key in ("pts", "next_pts"):
        if not np.issubdtype(arrays[key].dtype, np.integer):
            raise GradualError(key+" must contain integer source ticks.")
    for key in ("playback_seconds", "source_seconds", "frame_delta_seconds", "roi_mean", "roi_std"):
        array = np.asarray(arrays[key], dtype=np.float64)
        if not np.all(np.isfinite(array)):
            raise GradualError(key+" contains nonfinite values.")
        arrays[key] = array
    t = arrays["playback_seconds"]
    if np.any(np.diff(t) <= 0) or np.any(arrays["frame_delta_seconds"] <= 0):
        raise GradualError("Presentation times must increase and frame durations must be positive.")
    if np.any(arrays["next_pts"] <= arrays["pts"]):
        raise GradualError("next_pts must follow pts for every decoded frame.")
    if not np.allclose(np.diff(t), arrays["frame_delta_seconds"][:-1], rtol=0, atol=1e-6):
        raise GradualError("Frame intervals disagree with presentation timestamps.")
    offset = arrays["source_seconds"]-t
    if not np.allclose(offset, offset[0], rtol=0, atol=1e-6):
        raise GradualError("Source and playback coordinates need a common constant origin.")
    if np.any(arrays["roi_mean"] < 0) or np.any(arrays["roi_mean"] > 1) or np.any(arrays["roi_std"] < 0) or np.any(arrays["roi_std"] > 1):
        raise GradualError("ROI mean/std must use the declared 0--1 scale.")
    valid = np.asarray(features.get("valid_mask", np.isfinite(arrays["adjacent_mad"])), dtype=bool)
    if valid.shape != (count,):
        raise GradualError("valid_mask must match the frame count.")
    mad = np.asarray(arrays["adjacent_mad"], dtype=np.float64)
    if np.any(~np.isfinite(mad[valid])) or np.any(mad[valid] < 0):
        raise GradualError("Valid adjacent MAD values must be finite and nonnegative.")
    arrays["adjacent_mad"] = mad
    arrays["valid_mask"] = valid
    h, w = config["analysis_height"], config["analysis_width"]
    reduced = gray.reshape(count,h,height//h,w,width//w).mean(axis=(2,4),dtype=np.float32)/np.float32(255)
    arrays["images"] = reduced
    arrays["vectors"] = reduced.reshape(count,-1)
    if "evaluation_overlap_seconds" in features:
        overlap = np.asarray(features["evaluation_overlap_seconds"], dtype=np.float64)
        if overlap.shape != (count,) or np.any(~np.isfinite(overlap)) or np.any(overlap < 0) or np.any(overlap-arrays["frame_delta_seconds"] > 1e-6):
            raise GradualError("evaluation_overlap_seconds must describe valid frame/coverage intersections.")
        arrays["evaluation_overlap_seconds"] = overlap
    return arrays


def _r2(t, y, weights):
    weights = weights/weights.sum()
    time_mean, mean = np.dot(weights,t), np.dot(weights,y)
    centered = t-time_mean
    denominator = np.dot(weights,centered*centered)
    total = np.dot(weights,(y-mean)**2)
    if denominator <= 1e-15 or total <= 1e-12:
        return -1.0, 0.0
    slope = np.dot(weights,centered*(y-mean))/denominator
    residual = y-(mean+slope*centered)
    return float(1-np.dot(weights,residual*residual)/total), float(slope)


def _monotonic(y, delta_t, tolerance, increasing=True):
    differences = np.diff(y) if increasing else -np.diff(y)
    return float(np.dot(delta_t,differences >= -tolerance)/delta_t.sum()) if len(differences) else 0.0


def _interval(arrays, start, stop):
    """start/stop are Python frame slice indices; end uses the last next_pts."""
    last = stop-1
    return {"start_frame_index":int(start),"end_frame_index_exclusive":int(stop),
            "start_pts":int(arrays["pts"][start]),"end_pts":int(arrays["next_pts"][last]),
            "start_playback_seconds":float(arrays["playback_seconds"][start]),
            "end_playback_seconds":float(arrays["playback_seconds"][last]+arrays["frame_delta_seconds"][last]),
            "start_source_seconds":float(arrays["source_seconds"][start]),
            "end_source_seconds":float(arrays["source_seconds"][last]+arrays["frame_delta_seconds"][last])}


def _in_evaluation(arrays, start, stop):
    mask = arrays.get("evaluation_overlap_seconds", arrays["evaluation_mask"])
    return bool(np.any(mask[start:stop] > 0))


def _fade_candidates(arrays, config, rejected):
    t, dt = arrays["playback_seconds"], arrays["frame_delta_seconds"]
    mean, std = arrays["roi_mean"], arrays["roi_std"]
    black = (mean <= config["fade_black_mean_max"]) & (std <= config["fade_black_std_max"])
    edges = np.diff(np.r_[False,black,False].astype(np.int8))
    holds, candidates = [], []
    for first, stop in zip(np.flatnonzero(edges==1), np.flatnonzero(edges==-1)):
        duration = float(dt[first:stop].sum())
        if duration+1e-9 < config["black_hold_min_seconds"]:
            continue
        holds.append({**_interval(arrays,first,stop),"duration_seconds":duration,
                      "mean_level":float(np.average(mean[first:stop],weights=dt[first:stop])),
                      "overlaps_evaluation":_in_evaluation(arrays,first,stop)})
        for predicted_type, anchor in (("fade_out",first),("fade_in",stop-1)):
            # Candidate durations are a label-independent dense grid, unlike the
            # independent seven-duration endpoint-mixing scan.
            targets = np.arange(config["min_transition_seconds"],config["max_transition_seconds"]+1e-9,
                                config["scan_stride_seconds"])
            bounds = set()
            for duration_target in targets:
                if predicted_type=="fade_out":
                    start = int(np.searchsorted(t,t[anchor]-duration_target,side="left"))
                    end = anchor
                else:
                    start = anchor
                    end = int(np.searchsorted(t,t[anchor]+duration_target,side="left"))
                if start < 0 or end >= len(t) or end-start < 3 or (start,end) in bounds:
                    continue
                bounds.add((start,end))
                span = t[end]-t[start]
                if not config["min_transition_seconds"]-1e-6 <= span <= config["max_transition_seconds"]+1e-6 or not _in_evaluation(arrays,start,end+1):
                    continue
                sign = 1 if predicted_type=="fade_in" else -1
                mean_amplitude = sign*(mean[end]-mean[start])
                contrast_amplitude = sign*(std[end]-std[start])
                if mean_amplitude < config["fade_mean_amplitude_min"] or contrast_amplitude < config["fade_std_amplitude_min"]:
                    rejected["fade_amplitude"] = rejected.get("fade_amplitude",0)+1
                    continue
                weights = dt[start:end+1]
                mean_r2, mean_slope = _r2(t[start:end+1],mean[start:end+1],weights)
                std_r2, std_slope = _r2(t[start:end+1],std[start:end+1],weights)
                monotonic = min(_monotonic(mean[start:end+1],np.diff(t[start:end+1]),config["fade_mean_backward_tolerance"],sign>0),
                                _monotonic(std[start:end+1],np.diff(t[start:end+1]),config["fade_std_backward_tolerance"],sign>0))
                if (mean_r2 < config["fade_r2_min"] or std_r2 < config["fade_r2_min"]
                        or mean_slope*sign <= 0 or std_slope*sign <= 0
                        or monotonic < config["fade_monotonic_fraction_min"]):
                    rejected["fade_trend_fit"] = rejected.get("fade_trend_fit",0)+1
                    continue
                score = max(0,mean_r2)*max(0,std_r2)*monotonic*min(1.0,mean_amplitude/0.2)
                candidates.append({**_interval(arrays,start,end+1),"predicted_type":predicted_type,
                    "score":float(score),"score_kind":"heuristic_fit_not_probability","branch":"fade",
                    "metrics":{"mean_r2":mean_r2,"std_r2":std_r2,"monotonic_fraction":monotonic,
                               "mean_amplitude":float(mean_amplitude),"std_amplitude":float(contrast_amplitude)},
                    "quality_flags":["near_black_threshold_endpoint_not_certified_photographic_black"]})
    return holds,candidates


def _motion(first,last,config):
    if not config["motion_diagnostics"] and not config["motion_reject"]:
        return {"status":"not_requested","translation_explanation":False}
    try:
        import cv2
    except (ImportError,OSError):
        return {"status":"unavailable","translation_explanation":False}
    height,width = first.shape
    shift,response = cv2.phaseCorrelate(first.astype(np.float32),last.astype(np.float32))
    dx,dy = float(shift[0]),float(shift[1])
    if not all(math.isfinite(value) for value in (dx,dy,response)):
        return {"status":"nonfinite_motion_estimate","translation_explanation":False}
    aligned = cv2.warpAffine(last.astype(np.float32),np.array([[1,0,-dx],[0,1,-dy]],dtype=np.float32),
                             (width,height),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    margin = int(math.ceil(max(abs(dx),abs(dy))))+1
    if margin*2 >= min(height,width):
        return {"status":"insufficient_common_support","shift_pixels":[dx,dy],"response":float(response),
                "translation_explanation":False}
    region = (slice(margin,-margin),slice(margin,-margin))
    unaligned_error = float(np.sqrt(np.mean((first[region]-last[region])**2)))
    aligned_error = float(np.sqrt(np.mean((first[region]-aligned[region])**2)))
    ratio = aligned_error/unaligned_error if unaligned_error > 1e-12 else None
    explains = (response >= config["motion_response_min"] and math.hypot(dx,dy) >= config["motion_shift_min_pixels"]
                and ratio is not None and ratio < config["motion_aligned_error_ratio_max"])
    return {"status":"performed","shift_pixels":[dx,dy],"response":float(response),
            "unaligned_rms":unaligned_error,"aligned_rms":aligned_error,"aligned_error_ratio":ratio,
            "translation_explanation":bool(explains),"pixel_units":"reduced_analysis_image"}


def _dissolve_candidates(arrays,config,rejected):
    t,dt,x = arrays["playback_seconds"],arrays["frame_delta_seconds"],arrays["vectors"]
    grid = np.arange(t[0],t[-1],config["scan_stride_seconds"])
    starts = np.unique(np.searchsorted(t,grid,side="left"))
    candidates,scan_count = [],0
    for start in starts:
        for duration in config["durations_seconds"]:
            end = int(np.searchsorted(t,t[start]+duration,side="left"))
            if end >= len(t) or end-start < 3:
                continue
            span = t[end]-t[start]
            if not config["min_transition_seconds"] <= span <= config["max_transition_seconds"]+1e-6 or not _in_evaluation(arrays,start,end+1):
                continue
            scan_count += 1
            first_stop = min(end,int(np.searchsorted(t,t[start]+config["endpoint_mean_seconds"],side="right")))
            last_start = max(start+1,int(np.searchsorted(t,t[end]-config["endpoint_mean_seconds"],side="left")))
            first = np.average(x[start:first_stop],axis=0,weights=dt[start:first_stop])
            last = np.average(x[last_start:end+1],axis=0,weights=dt[last_start:end+1])
            difference = last-first
            denominator = float(np.dot(difference,difference))
            endpoint_rms = math.sqrt(denominator/len(difference))
            if endpoint_rms < config["endpoint_rms_min"]:
                rejected["endpoint_rms"] = rejected.get("endpoint_rms",0)+1
                continue
            frames,weights = x[start:end+1],dt[start:end+1]
            raw_alpha = np.einsum("ij,j->i",frames-first,difference,optimize=False)/denominator
            alpha = np.clip(raw_alpha,0,1)
            reconstruction = first+alpha[:,None]*difference
            residual = float(np.sqrt(np.average(np.mean((frames-reconstruction)**2,axis=1),weights=weights))/endpoint_rms)
            if residual > config["blend_residual_max"]:
                rejected["blend_residual"] = rejected.get("blend_residual",0)+1
                continue
            r2,slope = _r2(t[start:end+1],alpha,weights)
            occupancy = float(np.average((alpha>0.15)&(alpha<0.85),weights=weights))
            monotonic = _monotonic(alpha,np.diff(t[start:end+1]),config["alpha_backward_tolerance"])
            mad = arrays["adjacent_mad"][start+1:end+1]
            valid = arrays["valid_mask"][start+1:end+1]
            changes = mad[valid]
            if len(changes)==0 or not np.isfinite(changes).all():
                changes = np.mean(np.abs(np.diff(frames,axis=0)),axis=1)
            spike = float(changes.max()/changes.sum()) if changes.sum()>1e-12 else 1.0
            if r2 < config["alpha_time_r2_min"] or slope <= 0 or occupancy < config["intermediate_fraction_min"] or monotonic < config["alpha_monotonic_fraction_min"] or spike > config["max_step_fraction"]:
                rejected["alpha_trajectory_or_spike"] = rejected.get("alpha_trajectory_or_spike",0)+1
                continue
            middle = np.flatnonzero((alpha>=config["alpha_start"])&(alpha<=config["alpha_end"]))
            if len(middle)<2:
                rejected["no_alpha_refinement_support"] = rejected.get("no_alpha_refinement_support",0)+1
                continue
            refined_start,refined_stop = start+int(middle[0]),start+int(middle[-1])+1
            interval = _interval(arrays,refined_start,refined_stop)
            refined_duration = interval["end_playback_seconds"]-interval["start_playback_seconds"]
            if not config["min_transition_seconds"]-1e-6 <= refined_duration <= config["max_transition_seconds"]+1e-6:
                rejected["refined_duration"] = rejected.get("refined_duration",0)+1
                continue
            image_shape = arrays["images"].shape[1:]
            motion = _motion(first.reshape(image_shape),last.reshape(image_shape),config)
            if config["motion_reject"] and motion["translation_explanation"]:
                rejected["translation_explanation"] = rejected.get("translation_explanation",0)+1
                continue
            correlation_denominator = float(np.linalg.norm(first-first.mean())*np.linalg.norm(last-last.mean()))
            correlation = float(np.dot(first-first.mean(),last-last.mean())/correlation_denominator) if correlation_denominator>1e-12 else None
            endpoint_variance = (float(np.var(first))+float(np.var(last)))/2
            variance_dip = max(0.0,1-float(np.min(np.var(frames,axis=1)))/endpoint_variance) if endpoint_variance>1e-12 else 0.0
            score = max(0.0,1-residual/config["blend_residual_max"])*max(0,r2)*monotonic*occupancy
            flags = ["static_endpoint_mixing_approximation"]
            if motion["translation_explanation"]:
                flags.append("translation_can_explain_change_motion_not_rejected_in_primary")
            if motion["status"] not in ("performed","insufficient_common_support"):
                flags.append("motion_diagnostic_"+motion["status"])
            if correlation is not None and correlation>=0.98:
                flags.append("high_endpoint_correlation_photometric_change_explanation_possible")
            first_black = first.mean()<=config["fade_black_mean_max"] and first.std()<=config["fade_black_std_max"]
            last_black = last.mean()<=config["fade_black_mean_max"] and last.std()<=config["fade_black_std_max"]
            predicted_type = ("unknown_gradual" if first_black and last_black else "fade_in" if first_black
                              else "fade_out" if last_black else "dissolve")
            if first_black or last_black:
                flags.append("near_black_endpoint_type_from_mixing_model_not_general_dissolve")
            candidates.append({**interval,"predicted_type":predicted_type,"branch":"endpoint_mixing",
                "score":float(score),"score_kind":"heuristic_fit_not_probability",
                "unrefined_start_playback_seconds":float(t[start]),"unrefined_end_playback_seconds":float(t[end]),
                "metrics":{"endpoint_rms":endpoint_rms,"normalized_blend_rms_residual":residual,
                    "alpha_time_r2":r2,"alpha_intermediate_time_fraction":occupancy,
                    "alpha_monotonic_time_fraction":monotonic,"maximum_step_fraction":spike,
                    "variance_dip_auxiliary":variance_dip,"endpoint_correlation":correlation},
                "motion":motion,"quality_flags":flags})
    return candidates,scan_count


def _nms(candidates,config):
    ordered = sorted(candidates,key=lambda item:(-item["score"],
        -(item["end_playback_seconds"]-item["start_playback_seconds"]),item["start_playback_seconds"],item["candidate_id"]))
    accepted,suppressed = [],[]
    for candidate in ordered:
        suppressor = None
        for previous in accepted:
            intersection = max(0,min(candidate["end_playback_seconds"],previous["end_playback_seconds"])
                -max(candidate["start_playback_seconds"],previous["start_playback_seconds"]))
            duration = candidate["end_playback_seconds"]-candidate["start_playback_seconds"]
            other_duration = previous["end_playback_seconds"]-previous["start_playback_seconds"]
            union = duration+other_duration-intersection
            if intersection>0 and (intersection/union>=config["nms_iou_threshold"] or intersection/min(duration,other_duration)>=config["nms_containment_threshold"]):
                suppressor = previous["candidate_id"]
                break
        if suppressor is None:
            accepted.append(candidate)
        else:
            suppressed.append({"candidate_id":candidate["candidate_id"],"suppressed_by":suppressor,"reason":"overlapping_interval_nms"})
    return sorted(accepted,key=lambda item:(item["start_playback_seconds"],item["candidate_id"])),suppressed


def detect_gradual_candidates(features, *, config=None):
    """Consume worker feature arrays and return interval predictions without I/O.

    gray_cache is N,48,64 uint8 (other evenly divisible cache shapes also work).
    Coordinates and frame intervals come directly from playback_seconds,
    source_seconds, pts, next_pts and frame_delta_seconds. evaluation_mask is
    point membership, and optional evaluation_overlap_seconds retains partial
    edge-frame exposure. ROI mean/std/MAD use 0--1 units. Context is scanned, but
    only candidates intersecting evaluation coverage are returned; output clipping
    and edge censoring belong to the caller. No frame rate is inferred.
    """
    started = time.perf_counter()
    config = _configuration(config)
    arrays = _features(features,config)
    rejected,candidates,holds = {},[],[]
    if config["enable_fades"]:
        holds,fade_candidates = _fade_candidates(arrays,config,rejected)
        candidates.extend(fade_candidates)
    scanned = 0
    if config["enable_dissolves"]:
        dissolve_candidates,scanned = _dissolve_candidates(arrays,config,rejected)
        candidates.extend(dissolve_candidates)
    candidates.sort(key=lambda item:(item["start_playback_seconds"],item["end_playback_seconds"],item["predicted_type"],-item["score"]))
    for index,candidate in enumerate(candidates,1):
        candidate["candidate_id"] = "gradual-candidate-%06d"%index
        candidate["validation_status"] = "unreviewed_algorithmic_prediction"
    predictions,suppressed = _nms(candidates,config)
    return {"schema_version":1,"artifact_kind":"label_blind_gradual_interval_candidates","config":config,
        "predictions":predictions,"candidates":candidates,"suppressed_candidates":suppressed,"black_holds":holds,
        "diagnostics":{"frame_count":len(arrays["playback_seconds"]),"endpoint_mixing_windows_scanned":scanned,
            "candidate_count_before_nms":len(candidates),"prediction_count_after_nms":len(predictions),
            "rejection_counts":rejected,"elapsed_seconds":time.perf_counter()-started,
            "evaluation_exposure_seconds":float(np.sum(arrays.get("evaluation_overlap_seconds",
                arrays["frame_delta_seconds"]*arrays["evaluation_mask"])))},
        "score_definition":"heuristic fit score; not a calibrated probability or historical authenticity measure",
        "limitations":["Only the supplied feature coverage is scanned; references and labels are never consumed.",
            "The linear model applies to decoded digital gray values, not a recovered historical optical mixing process.",
            "Motion, blur and photometric change can mimic the model; motion is diagnostic unless the explicit ablation rejects it.",
            "Variance dip is an auxiliary metric, never a necessary dissolve condition.",
            "Near-black thresholds and linear fade trends may miss nonlinear, noisy or non-black fades.",
            "A partial fade window without a witnessed near-black endpoint can remain ambiguous with a dissolve or lighting change.",
            "Alpha refinement and NMS are heuristic; interval extent and transition type require separate evaluation.",
            "All configurations must be reported; this API neither scores against labels nor selects the best preset."]}
