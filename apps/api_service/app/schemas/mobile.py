from pydantic import BaseModel


class StartRentalRequest(BaseModel):
    telegram_user_id: int
    username: str | None = None
    first_name: str | None = None
    vehicle_id: str


class StartReturnInspectionRequest(BaseModel):
    telegram_user_id: int
    username: str | None = None
    first_name: str | None = None
