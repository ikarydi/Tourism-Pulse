"""Local communities per curated place. A place's posts are the union of
its subreddits' posts. Unknown or private subreddits are skipped with a
warning, so a wrong name here costs a log line, not a run."""

SUBREDDITS: dict[str, tuple[str, ...]] = {
    "Amsterdam": ("Amsterdam",),
    "Athens": ("athens",),
    "Barcelona": ("Barcelona",),
    "Budapest": ("budapest",),
    "Crete": ("crete",),
    "Dubrovnik": ("dubrovnik",),
    "Lisbon": ("lisboa", "lisbon"),
    "Prague": ("Prague",),
    "Venice": ("venice",),
}
