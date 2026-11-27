"""Casos de uso de movimientos puntuales con duracion."""

from typing import Any

from fastapi import HTTPException

from app.repositories.admin import AdminRepository
from app.repositories.movimientos import MovimientoRepository


RESERVED_CODE = 7
MIN_CODE = 0
MAX_CODE = 13


def validate_firmware_code(codigo: int) -> int:
    """Valida que el codigo sea compatible con el mapa 0-9 y 10-13 (A-D) del ESP."""
    value = int(codigo)
    if value == RESERVED_CODE:
        raise HTTPException(
            status_code=422,
            detail="El codigo 7 esta reservado para la demo local del dispositivo.",
        )
    if value < MIN_CODE or value > MAX_CODE:
        raise HTTPException(
            status_code=422,
            detail="El codigo debe estar entre 0 y 13 para ser compatible con el dispositivo.",
        )
    return value


class MovimientoService:
    def __init__(
        self,
        repository: MovimientoRepository | None = None,
        admin_repository: AdminRepository | None = None,
    ) -> None:
        self.repository = repository or MovimientoRepository()
        self.admin = admin_repository or AdminRepository()

    def _require_command(self, command_id: int) -> dict[str, Any]:
        command = self.repository.get_command(command_id)
        if command is None:
            raise HTTPException(status_code=404, detail="Comando no encontrado.")
        validate_firmware_code(command["codigo"])
        return command

    def _require_movement(self, movement_id: int) -> dict[str, Any]:
        movement = self.repository.get(movement_id)
        if movement is None:
            raise HTTPException(status_code=404, detail="Movimiento no encontrado.")
        return movement

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        command = self._require_command(int(values["id_comando"]))
        validate_firmware_code(command["codigo"])
        movement_id = self.repository.create(
            command_id=int(command["id_comando"]),
            nombre=values["nombre"],
            duracion_ms=int(values["duracion_ms"]),
        )
        return self._require_movement(movement_id)

    def list_for_vehicle(self, vehicle_id: int) -> list[dict[str, Any]]:
        return self.repository.list_for_vehicle(vehicle_id)

    def get(self, movement_id: int) -> dict[str, Any]:
        return self._require_movement(movement_id)

    def update(self, movement_id: int, values: dict[str, Any]) -> dict[str, Any]:
        self._require_movement(movement_id)
        if self.repository.update(
            movement_id,
            nombre=values["nombre"],
            duracion_ms=int(values["duracion_ms"]),
            activo=bool(values.get("activo", True)),
        ) == 0:
            raise HTTPException(status_code=404, detail="Movimiento no encontrado.")
        return self._require_movement(movement_id)

    def deactivate(self, movement_id: int) -> dict[str, Any]:
        movement = self._require_movement(movement_id)
        if self.repository.deactivate(movement_id) == 0:
            raise HTTPException(status_code=404, detail="Movimiento activo no encontrado.")
        return {"message": "Movimiento desactivado correctamente", "id": movement_id}
