"""Normalizes a GDACS disaster-alert severity reading into a 0-1 Pulse
Engine input for the `risk` dimension.

Unlike every other normalizer in this codebase, this one inverts
polarity. Every Pulse dimension is "higher = stronger/healthier tourism
conditions" (see pulse.interpretation: a dimension >=70 is reported as
"strong"), so a HIGH GDACS alert score (an active earthquake/flood/
wildfire) must produce a LOW normalized value, not a high one - the
normalized number represents "how much this dimension currently favors
tourism", not "how severe the hazard is". The raw `disaster_alert_severity`
Signal itself still stores the true, unmodified GDACS alertscore (0 = no
current alert) so it reads naturally in the database/CLI preview and
lineage - only this normalization step flips it for the engine.
"""

# GDACS's own alert-level scale (see alertscore in the API docs): Green
# ~1, Orange ~2, Red ~3. Used as the ceiling below - kept here rather
# than in ingestion.gdacs.parser since every other pulse normalizer is
# self-contained (no pulse module imports from ingestion.*).
MAX_ALERT_SCORE = 3.0


def normalize_disaster_alert_severity(alert_score: float) -> float:
    clamped = max(0.0, min(alert_score, MAX_ALERT_SCORE))
    return 1.0 - (clamped / MAX_ALERT_SCORE)
