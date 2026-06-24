from fastapi import APIRouter, HTTPException

from auth_services.authentication import signup, login

router = APIRouter(prefix="/auth", tags=["Auth"])


from pydantic import BaseModel


class SignupRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/signup")
def signup_user(payload: SignupRequest):
    return signup(
        email=payload.email,
        name=payload.name,
        password=payload.password
    )


@router.post("/login")
def login_user(payload: LoginRequest):
    return login(
        email=payload.email,
        password=payload.password
    )