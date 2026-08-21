"""YouTube Data API v3 search-interest ingestion.

Uses `search.list`'s `pageInfo.totalResults` as a search-interest /
demand-side signal for a destination - see `parser.py`/`service.py` for
details. `videos.list` view/comment-count statistics are a natural next
step (noted in `parser.py`'s docstring) but not built this round: this
adapter's job is to prove the raw-archive + data-quality + lineage
pipeline (see `ingestion.raw_archive`, `data_quality`, `pulse.lineage`)
works end-to-end for a brand-new source, not to be a complete YouTube
integration.
"""
