"""
Punto de entrada principal de la aplicación FastAPI.
Registra todos los routers (REST + WebSocket).
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    comandos,
    demo_execution,
    demos,
    estado,
    hardware_ws,
    movimientos,
    vehiculos,
)

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

# CORS permisivo para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(vehiculos.router)
app.include_router(comandos.router)
app.include_router(estado.router)
app.include_router(movimientos.router)
app.include_router(demos.router)
app.include_router(demo_execution.router)
app.include_router(hardware_ws.router)


@app.get("/", tags=["Health"])
def health():
    """Verifica que el servidor está corriendo."""
    return {"status": "ok", "version": "2.1.0", "message": "IoT Car API lista"}
