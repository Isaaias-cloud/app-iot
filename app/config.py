"""Configuración de la aplicación.

Los valores sensibles no tienen fallback embebido. En producción deben
provenir de variables de entorno/secret manager; ``.env`` solo se carga para
desarrollo local y nunca debe publicarse.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── Base de datos ──────────────────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
DB_USER     = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME", "vehiculo_iot")
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

# ── Servidor ───────────────────────────────────────────────────────────────────
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# ── Autenticación ──────────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ISSUER = os.getenv("JWT_ISSUER", "iot-car-api")
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
REFRESH_TOKEN_TTL_SECONDS = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "604800"))
LOGIN_RATE_LIMIT_MAX = int(os.getenv("LOGIN_RATE_LIMIT_MAX", "5"))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60"))


def _load_device_tokens() -> dict[int, str]:
    """Carga el mapa vehículo → secreto sin incluir credenciales en el código."""
    raw = os.getenv("DEVICE_TOKENS", "").strip()
    if not raw:
        return {}
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DEVICE_TOKENS debe ser un objeto JSON válido") from exc
    if not isinstance(values, dict):
        raise RuntimeError("DEVICE_TOKENS debe ser un objeto JSON vehículo → token")

    tokens: dict[int, str] = {}
    for vehicle_id, token in values.items():
        try:
            parsed_vehicle_id = int(vehicle_id)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("DEVICE_TOKENS contiene un id_vehiculo inválido") from exc
        if parsed_vehicle_id <= 0 or not isinstance(token, str) or not token.strip():
            raise RuntimeError("DEVICE_TOKENS contiene un token vacío o un vehículo inválido")
        tokens[parsed_vehicle_id] = token
    if len(tokens) != len(values):
        raise RuntimeError("DEVICE_TOKENS contiene ids de vehículo duplicados")
    if len(set(tokens.values())) != len(tokens):
        raise RuntimeError("DEVICE_TOKENS no puede reutilizar el mismo secreto entre vehículos")
    return tokens


DEVICE_TOKENS = _load_device_tokens()

# Lista separada por comas. Nunca se usa como sustituto de autorización.
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
)

