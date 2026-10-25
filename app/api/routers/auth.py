from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.api.dependencies import get_authentication_service
from app.services.authentication_service import (
    AuthenticationError,
    AuthenticationService,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> TokenResponse:
    try:
        _, access_token = service.login(
            email=form.username,
            password=form.password,
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return TokenResponse(
        access_token=access_token,
    )
