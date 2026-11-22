"""Endpoints de autenticación y sesiones."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas import (
    AuthUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    UserSessionResponse,
)
from app.security import AuthContext, get_auth_context
from app.services_auth import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
    responses={
        401: {"description": "Credenciales o sesión inválida."},
        429: {"description": "Límite de intentos excedido."},
        422: {"description": "Error de validación."},
    },
)
service = AuthService()


def _rate_key(request: Request, email: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{email.strip().lower()}"


@router.post("/login", response_model=UserSessionResponse, status_code=status.HTTP_200_OK)
def login(body: LoginRequest, request: Request):
    return service.login(body.email, body.password, _rate_key(request, body.email))


@router.post("/refresh", response_model=UserSessionResponse)
def refresh(body: RefreshRequest):
    return service.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, context: AuthContext = Depends(get_auth_context)):
    service.logout(context, body.refresh_token)
    return None


@router.get("/me", response_model=AuthUserResponse)
def me(context: AuthContext = Depends(get_auth_context)):
    return service.me(context)
