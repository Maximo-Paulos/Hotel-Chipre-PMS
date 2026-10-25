from pydantic import BaseModel


class CompanyHotelCurrencyRead(BaseModel):
    default_currency: str
