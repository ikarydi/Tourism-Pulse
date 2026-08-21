"""Data quality checks and quarantine (spec section 14).

Separate from `pulse/` on purpose: this package answers "is this data
trustworthy enough to store" (an ingestion/governance concern, spec
sections 13-14), while `pulse/` answers "how do we score it once stored"
(Pulse math). Keeping them apart preserves that domain boundary.
"""
