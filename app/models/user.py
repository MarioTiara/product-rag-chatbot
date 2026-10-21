from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    id: str
    username: str
    hashed_password: str
    is_active: bool = True

    model_config = ConfigDict(frozen=True)