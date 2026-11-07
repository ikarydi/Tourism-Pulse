from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str

    # Optional: required only for the Ticketmaster events ingestion command.
    # Kept out of source control - set via .env or the environment.
    ticketmaster_api_key: str | None = None

    # Optional: required only for the YouTube search-interest ingestion
    # command. Free tier available at https://console.cloud.google.com/
    # (enable the YouTube Data API v3).
    youtube_api_key: str | None = None

    # Optional: required only for ingestion.reddit. Create a "script" app at
    # https://www.reddit.com/prefs/apps (free for non-commercial use).
    # Reddit asks for "<platform>:<app id>:<version> (by /u/<username>)".
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "server:tourism-pulse:1.0 (research; non-commercial)"

    # Optional: required only for ingestion.bluesky. An app password from
    # Bluesky's Settings > Privacy and security > App passwords.
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None

    # Booking.com/Airbnb have no accessible public API - these settings
    # exist so wiring real partner credentials later is a client.py diff,
    # not a new settings field. Unused today (ingestion.booking/airbnb are
    # scaffolds that always raise SourceNotConfiguredError).
    booking_api_key: str | None = None
    airbnb_api_key: str | None = None

    # Optional: only needed for higher OpenSky Network rate limits/time
    # resolution. Anonymous (unauthenticated) requests still work at a
    # lower quota - see ingestion.opensky.client. Create an API client at
    # https://opensky-network.org/ (account settings) for these.
    opensky_client_id: str | None = None
    opensky_client_secret: str | None = None

    # Optional: required only for the OpenAQ air-quality ingestion
    # command. Free tier available at https://explore.openaq.org/register.
    openaq_api_key: str | None = None

    # Optional: required only for pulse.narrative's LLM-written insight
    # paragraph (spec section 24: "LLMs handle explanation, synthesis" -
    # the Pulse engine itself stays deterministic regardless). Free
    # signup at https://console.groq.com - chosen over a paid provider
    # deliberately. Narrative is simply omitted (not an error) when unset,
    # same pattern as every other optional external dependency above.
    groq_api_key: str | None = None
    # Groq's model lineup turns over - llama-3.3-70b-versatile (the
    # original choice here) has since been retired from their catalog.
    # gpt-oss-120b (OpenAI's open-weight model, Groq-hosted) is the
    # current pick: strong general-purpose text quality for short
    # analyst-style synthesis, large context window, still free-tier
    # eligible. Re-check https://console.groq.com/docs/models if this
    # 404s again with "model_not_found".
    narrative_model: str = "openai/gpt-oss-120b"
    # How long a stored narrative stays valid before routers/pulse.py
    # regenerates it on the next persist=true call - bounds LLM spend to
    # roughly one call per place per window, not one per page view.
    narrative_refresh_hours: int = 6

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
