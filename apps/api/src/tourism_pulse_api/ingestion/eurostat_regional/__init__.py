"""Official regional tourism-pressure indicators from Eurostat, for every
NUTS region - the tourism-pressure observatory's dataset.

- tourism_intensity: nights per 1,000 inhabitants (tour_occ_nin2, P_THAB)
- tourism_density: nights per km² (tour_occ_nin2, P_KM2)
- seasonality_peak_share: share of a year's nights falling in its
  busiest month, from monthly regional nights (tour_occ_nin2m); an even
  spread would be 1/12 ≈ 8.3%.

All three are size-independent, so regions of very different size are
comparable. Stored as RegionalIndicator reference data (like
PlaceDemographics), not as Signals: they are annual official statistics
describing structural pressure, not live tourism-activity readings.
"""
