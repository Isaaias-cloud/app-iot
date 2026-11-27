"""
Punto de entrada principal de la aplicación FastAPI.
Registra todos los routers (REST + WebSocket).
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import check_database_connection
from app.config import CORS_ORIGINS
from app.routers import (
    admin,
    auth,
    comandos,
    demo_execution,
    demos,
    estado,
    hardware_ws,
    guest,
    movimientos,
    movimientos_config,
    me,
    owner_demos,
    vehiculos,
)
from app.schemas import DatabaseHealthErrorResponse, DatabaseHealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

app = FastAPI(
    title="IoT Car API",
    description=(
        "API REST y WebSocket para gestión de vehículos IoT mediante 21 stored procedures.\n\n"
        "| Prueba | Método | URL | Comportamiento |\n"
        "|--------|--------|-----|----------------|\n"
        "| 1 | `POST` | `/vehiculos/{id}/comando` | Estado + historial en una transacción |\n"
        "| 2 | `GET`  | `/vehiculos/{id}/historial` | Últimos 10 movimientos |\n"
        "| 3 | `POST` | `/demos/ejecutar` | Demo transmitida por WebSocket, sin historial |\n"
    ),
    version="2.1.0",
)

# CORS permite consultas desde GitHub Pages y otros clientes web públicos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    allow_credentials=False,
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(vehiculos.router)
app.include_router(comandos.router)
app.include_router(estado.router)
app.include_router(movimientos.router)
app.include_router(movimientos_config.router)
app.include_router(demos.router)
app.include_router(demo_execution.router)
app.include_router(hardware_ws.router)
app.include_router(guest.router)
app.include_router(admin.router)
app.include_router(me.router)
app.include_router(owner_demos.router)
app.include_router(auth.router)


@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
def health():
    """Verifica que el servidor está corriendo."""
    return {"status": "ok", "version": "2.1.0", "message": "IoT Car API lista"}

@app.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    responses={
        503: {
            "model": DatabaseHealthErrorResponse,
            "description": "La instancia MySQL/RDS no está disponible.",
        }
    },
    status_code=200,
    tags=["Health"],
    summary="Verificar conectividad con RDS MySQL",
)
def database_health() -> DatabaseHealthResponse | JSONResponse:
    """Ejecuta ``SELECT 1`` y reporta si RDS MySQL responde.

    Los fallos de red, autenticación o timeout se convierten en HTTP 503 con un
    cuerpo seguro; no se exponen credenciales ni detalles internos de MySQL.
    """
    if check_database_connection():
        return DatabaseHealthResponse()

    return JSONResponse(
        status_code=503,
        content=DatabaseHealthErrorResponse(
            detail="No se pudo establecer conexión con la base de datos RDS."
        ).model_dump(),
    )
