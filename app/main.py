"""
Punto de entrada principal de la aplicación FastAPI.
Registra todos los routers (REST + WebSocket).
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import movimientos, demo_ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

app = FastAPI(
    title="IoT Car API",
    description=(
        "API para gestión de vehículos IoT con 3 integraciones:\n\n"
        "| Prueba | Método | URL | Stored Procedure |\n"
        "|--------|--------|-----|------------------|\n"
        "| 1 | `POST` | `/vehiculos/{id}/comando` | `sp_actualizar_estado` + `sp_registrar_historial` |\n"
        "| 2 | `GET`  | `/vehiculos/{id}/historial` | `sp_obtener_historial` (top 10) |\n"
        "| 3 | `WS`   | `/ws/demo` | `sp_obtener_movimientos_demo` (sin historial) |\n"
    ),
    version="2.0.0",
)

# CORS permisivo para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(movimientos.router)
app.include_router(demo_ws.router)


@app.get("/", tags=["Health"])
def health():
    """Verifica que el servidor está corriendo."""
    return {"status": "ok", "version": "2.0.0", "message": "IoT Car API lista"}
