# Drop candidate review (unconfirmed)

These are diagnostic still frames from existing MP4s, not an edited film and not new trials. Every candidate sample is retained in candidate_times.csv. Consecutive samples within1second are grouped for contact sheets; no candidate samples are discarded from the time list. Context images surround the first and last sample of each cluster.

A logged contact/velocity/height flag is a candidate, NOT a visually confirmed drop. Inspect the original recording and frames, then fill manual_review.csv. confirmed_drop is intentionally blank; this tool never changes metrics or trial outcomes. A supported release or temporary contact loss may trigger a candidate. No confirmed count is supplied.

Video frame0 is initial state. Telemetry stepN (after actionN) corresponds to video frameN+1 and elapsed simulated time(N+1)/20. Input source is trial_details.json; world height criteria remain those of the already executed analysis.
