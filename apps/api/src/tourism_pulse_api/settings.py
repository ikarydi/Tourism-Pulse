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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()