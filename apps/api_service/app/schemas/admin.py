from typing import Optional
from pydantic import BaseModel

class UpdateAdminCaseStatusRequest(BaseModel):
    status: str
    resolved_note: Optional[str] = None
