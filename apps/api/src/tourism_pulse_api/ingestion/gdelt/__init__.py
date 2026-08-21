"""GDELT DOC 2.0 API news ingestion - a fully open source, no key and no
partnership required (https://api.gdeltproject.org), unlike Booking.com/
Airbnb (see ingestion.booking / ingestion.airbnb).

Two independent signal types, one per CLI `--mode`, so a single run never
makes more than one request (GDELT asks callers to stay under one
request per 5 seconds - see client.py):

  mentions   ArtList mode - how many articles matched a destination
             query, capped at the API's own maxrecords limit. See
             pulse.news_mentions.

  sentiment  TimelineTone mode - average tone of matching coverage over
             the query window, most recent point in the series. See
             pulse.news_sentiment.
"""
