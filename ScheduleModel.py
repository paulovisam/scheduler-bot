from pydantic import BaseModel
from typing import Optional, Any
class ScheduleModel(BaseModel):
    name: Optional[str]
    chat_id: Optional[Any]
    freq: Optional[str]
    time: Optional[str]
    step_day: Optional[int]
    message: Optional[str]