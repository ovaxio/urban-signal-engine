from pydantic import BaseModel
from typing import List, Optional

class SignalValues(BaseModel):
    traffic:   float
    weather:   float
    event:     float
    transport: float

class ScoreComponents(BaseModel):
    risk:      float
    anomaly:   float
    conv:      float
    spread:    float
    phi:       float

class ZoneScore(BaseModel):
    zone_id:     str
    zone_name:   str
    urban_score: int
    level:       str
    signals:     SignalValues
    components:  ScoreComponents
    top_causes:  List[str]
    timestamp:   str

class ZoneDetail(ZoneScore):
    explanation: str
    neighbors:   List["ZoneScore"]

class ForecastPoint(BaseModel):
    horizon_min:  int
    urban_score:  int
    level:        str

class ZoneForecast(BaseModel):
    zone_id:   str
    zone_name: str
    current:   int
    forecast:  List[ForecastPoint]

class HealthResponse(BaseModel):
    status:    str
    zones:     int
    cache_age: Optional[int]
