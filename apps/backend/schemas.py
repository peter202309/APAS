from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class FlightPrice(BaseModel):
    date: str
    price: float
    currency: str
    is_cheapest: bool = False

class ScraperTask(BaseModel):
    trip_type: str = "round_trip"  # "round_trip" or "one_way"
    origin: str
    destination: str
    start_date: str
    routing_codes: Optional[str] = None  # e.g., "C:MU+"
    extension_codes: Optional[str] = None
    nights: int = 7  # Duration for calendar view
    stops: str = "No limit"  # "Nonstop only", "Up to 1 stop", etc.
    cabin: str = "Cheapest available"
    currency: Optional[str] = None
    sales_city: Optional[str] = None
    adults: int = 1
    extra_stops: str = "No limit"  # "No limit", "No extra stops", "Up to 1 extra stop", "Up to 2 extra stops"

class ScraperResult(BaseModel):
    task: ScraperTask
    month: str
    prices: List[FlightPrice]
    timestamp: str
    status: str = "success"
    message: Optional[str] = None

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    task_id: Optional[str] = None
