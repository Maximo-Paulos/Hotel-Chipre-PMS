from pydantic import BaseModel
from datetime import datetime

class InvitationToken(BaseModel):
    hotel_id: int
    email: str
    role: str
    exp: datetime | None = None
