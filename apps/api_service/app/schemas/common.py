from pydantic import BaseModel

class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | None = None

class ErrorResponse(BaseModel):
    error: ErrorBody

class Envelope(BaseModel):
    data: dict
    meta: dict | None = None
