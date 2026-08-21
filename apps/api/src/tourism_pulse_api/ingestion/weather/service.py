"""Orchestration for turning one Open-Meteo observation into Signal rows.

One ingestion run writes multiple signals sharing the same observed_at:

  - four raw readings (temperature, humidity, precipitation, wind_speed),
    preserved as-fetched and never fed into a Pulse dimension directly
  - one derived `weather_comfort` signal (see `pulse.weather_comfort`),
    which *is* wired into the existing `environment` dimension

This keeps the raw readings recoverable/inspectable independently of the
derived score, per the "preserve raw data" principle.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.weather.parser import (
    OPEN_METEO_SOURCE_NAME,
    WeatherObservation,
)
from tourism_pulse_api.pulse.weather_comfort import (
    calculate_weather_comfort,
    precipitation_comfort,
    temperature_comfort,
    wind_comfort,
)

WEATHER_COMFORT_SIGNAL_TYPE = "weather_comfort"

# (signal_type, unit, value-getter) for each raw reading preserved as-is.
_RAW_SIGNAL_SPECS: list[tuple[str, str, Callable[[WeatherObservation], Decimal]]] = [
    ("temperature", "celsius", lambda obs: obs.temperature_c),
    ("humidity", "percent", lambda obs: obs.humidity_percent),
    ("precipitation", "mm", lambda obs: obs.precipitation_mm),
    ("wind_speed", "km/h", lambda obs: obs.wind_speed_kmh),
]


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    observed_at: str
    weather_description: str
    raw_readings: dict[str, str]
    comfort_score: float
    comfort_breakdown: dict[str, float]
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "observed_at": self.observed_at,
            "weather_description": self.weather_description,
            "raw_readings": self.raw_readings,
            "comfort_score": self.comfort_score,
            "comfort_breakdown": self.comfort_breakdown,
            "target_dimension": self.target_dimension,
        }


def build_preview(observation: WeatherObservation) -> IngestionPreview:
    comfort = calculate_weather_comfort(
        temperature_c=float(observation.temperature_c),
        precipitation_mm=float(observation.precipitation_mm),
        wind_speed_kmh=float(observation.wind_speed_kmh),
    )

    return IngestionPreview(
        source=OPEN_METEO_SOURCE_NAME,
        observed_at=observation.observed_at.isoformat(),
        weather_description=observation.weather_description,
        raw_readings={
            "temperature": f"{observation.temperature_c} celsius",
            "humidity": f"{observation.humidity_percent} percent",
            "precipitation": f"{observation.precipitation_mm} mm",
            "wind_speed": f"{observation.wind_speed_kmh} km/h",
        },
        comfort_score=comfort,
        comfort_breakdown={
            "temperature_comfort": temperature_comfort(float(observation.temperature_c)),
            "precipitation_comfort": precipitation_comfort(float(observation.precipitation_mm)),
            "wind_comfort": wind_comfort(float(observation.wind_speed_kmh)),
        },
        target_dimension="environment",
    )


def _upsert_signal(
    db: Session,
    *,
    place_id: int,
    signal_type: str,
    value: Decimal,
    unit: str,
    observed_at,
    source_url: str,
) -> tuple[Signal, bool]:
    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == signal_type,
            Signal.observed_at == observed_at,
            Signal.source == OPEN_METEO_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = value
        existing.unit = unit
        existing.source_url = source_url
        db.commit()
        db.refresh(existing)
        return existing, False

    signal = Signal(
        place_id=place_id,
        signal_type=signal_type,
        value=value,
        unit=unit,
        observed_at=observed_at,
        source=OPEN_METEO_SOURCE_NAME,
        source_url=source_url,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, True


def upsert_weather_signals(
    db: Session,
    *,
    place_id: int,
    observation: WeatherObservation,
    source_url: str,
) -> list[tuple[Signal, bool]]:
    """Idempotently write one weather observation as raw + comfort Signal rows.

    Returns a list of (signal, created) pairs, one per signal_type written.
    Re-running this with the same observation and place is a no-op beyond
    refreshing the stored values - it never creates a duplicate row for the
    same (place_id, signal_type, observed_at, source).
    """
    results = [
        _upsert_signal(
            db,
            place_id=place_id,
            signal_type=signal_type,
            value=getter(observation),
            unit=unit,
            observed_at=observation.observed_at,
            source_url=source_url,
        )
        for signal_type, unit, getter in _RAW_SIGNAL_SPECS
    ]

    comfort = calculate_weather_comfort(
        temperature_c=float(observation.temperature_c),
        precipitation_mm=float(observation.precipitation_mm),
        wind_speed_kmh=float(observation.wind_speed_kmh),
    )

    results.append(
        _upsert_signal(
            db,
            place_id=place_id,
            signal_type=WEATHER_COMFORT_SIGNAL_TYPE,
            value=Decimal(str(round(comfort, 2))),
            unit="percent",
            observed_at=observation.observed_at,
            source_url=source_url,
        )
    )

    return results
