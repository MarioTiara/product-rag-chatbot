

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    id: str
    display_name: str | None = None
    email: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(frozen=True)
