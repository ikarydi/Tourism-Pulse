from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChartType = Literal["line", "bar", "scatter", "heatmap", "map", "table"]
Collapse = Literal["latest", "avg", "sum", "max", "min"]


class QuerySpec(BaseModel):
    """Which catalog metrics, for which places, on which time grid."""

    metrics: list[str] = Field(min_length=1, max_length=4)
    # None = every place (optionally narrowed by place_type).
    places: list[int] | None = None
    place_type: Literal["destination", "country"] | None = None
    grain: Literal["day", "month", "year"] = "month"
    start: date | None = None
    end: date | None = None


class ChartSpec(BaseModel):
    """How to draw a query result. x=place charts fold each place's time
    series to one value with `collapse`."""

    type: ChartType = "line"
    x: Literal["time", "place"] = "time"
    collapse: Collapse = "latest"
    color: Literal["place", "metric"] | None = None


class ViewSpec(BaseModel):
    query: QuerySpec
    chart: ChartSpec = ChartSpec()


class MetricRead(BaseModel):
    id: str
    label: str
    group: str
    unit: str
    grain: str
    aggregation: str
    description: str
    source: str


class PlaceRefRead(BaseModel):
    id: int
    name: str
    place_type: str
    country_code: str | None = None


class CatalogRead(BaseModel):
    metrics: list[MetricRead]
    places: list[PlaceRefRead]


class QueryRowRead(BaseModel):
    metric: str
    place_id: int
    period: date | None
    value: float


class QueryResultRead(BaseModel):
    metrics: list[MetricRead]
    places: list[PlaceRefRead]
    rows: list[QueryRowRead]
    truncated: bool
    # Latest period present in the result - the data-freshness label.
    data_through: date | None = None
    notes: list[str] = []


class SavedViewCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    spec: ViewSpec
    pinned: bool = True


class SavedViewUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    spec: ViewSpec | None = None
    pinned: bool | None = None
    position: int | None = None


class SavedViewRead(BaseModel):
    id: int
    title: str
    description: str | None
    spec: ViewSpec
    pinned: bool
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AskResponse(BaseModel):
    title: str
    spec: ViewSpec
    explanation: str
