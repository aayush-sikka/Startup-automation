from pydantic import BaseModel
from typing import Optional, List

class Startup(BaseModel):
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
