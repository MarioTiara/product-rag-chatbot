from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    id: str
    display_name: str | None = None
    email: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = ConfigDict(frozen=True)
