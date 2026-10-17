from datetime import date

from pydantic import BaseModel, Field


class BusinessClockRead(BaseModel):
    hotel_id: int = Field(gt=0)
    business_date: date
    hotel_timezone: str
    simulation_enabled: bool
