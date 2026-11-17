# Digital gray-level analysis across the corpus, grouped by studio

On 2026-10-26, the user explicitly authorised coverage of the entire corpus. This scope supersedes the initial 30-minute limit while retaining source-protection requirements and prohibitions on paid computation, uploads and model downloads.

## Scope and identity

Associate 732 metadata records with 454 readable videos using existing keys. The 450 unique-filename matches remain provisional identities; the 4 ambiguous same-name matches use earlier assistant opening-title review records and rechecked SHA. The 278 records without local video remain in studio coverage counts. Specific production.name values identify production institutions; category is only the original grouping and cannot substitute for studio identity. Names such as 东北/长春 and 上海/天马/海燕 retain separate entries rather than automatically merging historical institutions.

The preceding numbers describe the pre-run filename-association inventory. Complete-file SHA and opening-title inspection later established that 《永恒的友谊.mp4》 was a byte-identical duplicate of 《延安游击队》. Final coverage is 453 valid video associations and 279 records lacking valid video. Derived identity corrections and the initial conservative 452-film inclusion results are both preserved without altering the original inventory. See REPORT.md and the experiment directory's identity_overrides.json.

Co-productions receive fractional 1/k weights, totalling 1 per film. Separately report sensitivity restricted to films with a single production institution. Multiple sources or byte-identical copies of the same film are not independent films. Original videos and metadata remain read-only, with no database connection or pushes.

## Measurements

Apply the same approximately 1Hz reference-frame sampling (NONREF) to every video, retaining original PTS/time_base. This is neither shot detection nor frame-complete ground truth at 1Hz. Resize to width<=160, preserve encoded aspect ratio, and apply a fixed crop of 5% on each side and 10% at top/bottom. Full-frame means provide a sensitivity check. Do not normalise histograms frame by frame or claim to reconstruct historical lighting.

Time weights use bounded temporal-representation intervals around the nearest observation, capped at 5 seconds. This sampling approximation is not the actual exposure of every decoded frame. Sparse regions remain missing. Inadequate coverage or anomalous sampling frequency triggers complete-decoding 1Hz fallback only on quality grounds, without choosing algorithms by effect size.

The primary change measure is the mean absolute difference between adjacent 30-second gray-level means divided by the film's temporal gray-level standard deviation. Retain raw digital means, temporal variation, spatial contrast, central 10–90% sensitivity and 100 film-relative position intervals. Relative position does not establish narrative-act structure.

Studio aggregates give films equal weight with fractional co-production weights, preventing longer films or films with more frames from dominating. Report between-film dispersion without treating frames as independent samples. Stratify by year, colour format and film type, listing missing/failed/unknown records and small studio samples separately. Independent narrative annotations are unavailable across the corpus, so corpus-wide narrative correspondence cannot be claimed.

## Completed sampling preflight

Use fixed 60-second clips at 25%/50%/75% in 8 films. The original keyframe-only proposal passed only 21/24 clips; 《烈火中永生》 has sparse keyframes. Negative results and original code are archived. Error thresholds were not relaxed.

Switch to uniform approximately 1Hz reference-frame sampling throughout complete films, retaining the original criteria: in at least 90% of clips, clip-mean and 30-second-bin-mean errors must be <=0.02, with temporal-representation coverage>=0.98. All 24/24 passed. Against complete-decoding 1Hz sampling, the median 30-second mean error was 0.000313 and the maximum 0.002252. This validates sampling for relatively slow digital gray-level curves, not historical-brightness calibration or frame-level/instantaneous-event accuracy.

Data and configuration: research-local/studio-luminance/corpus-20261026T083348Z. Record research judgements after actual corpus-wide output, without assuming which studio is brighter, darker or more variable.

## Additional post-run diagnostic (separate from the pre-run protocol)

The first sampled contact sheets showed a mismatch between the B&W label and multicoloured images in 《刘三姐》. Subsequently, check ROI chroma at fixed 20%/50%/80% positions in each of 453 films. Thresholds were written into the script before this corpus-wide diagnostic, but it remains a post-result source-quality check rather than preregistration of the main analysis. Flags occur in 14 B&W-labelled videos, including nearly monochrome purple/green casts, so these are not necessarily 14 incorrect labels. Use only exclusion sensitivity: do not relabel them as Colour, change the main analysis films or select favourable results. Preserve original images and numbers, assistant observations and metadata separately.
