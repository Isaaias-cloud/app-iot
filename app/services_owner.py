"""Casos de uso de demos privadas del propietario."""

from typing import Any

from fastapi import HTTPException, status

from app.repositories.owner_demos import OwnerDemoRepository


def _not_found(message: str = "Demo privada no encontrada.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


class OwnerDemoService:
    def __init__(self, repository: OwnerDemoRepository | None = None) -> None:
        self.repository = repository or OwnerDemoRepository()

    def list(self, user_id: int, vehicle_id: int | None = None) -> list[dict[str, Any]]:
        return self.repository.list_demos(user_id, vehicle_id)

    def create(self, user_id: int, values: dict[str, Any]) -> dict[str, Any]:
        demo_id = self.repository.create_demo(values, user_id)
        if demo_id == 0:
            raise HTTPException(status_code=403, detail="Debes ser propietario activo de la unidad.")
        result = self.repository.get_demo(demo_id, user_id)
        if result is None:
            raise _not_found("La demo privada no pudo recuperarse después de crearla.")
        return result

    def get(self, user_id: int, demo_id: int) -> dict[str, Any]:
        result = self.repository.get_demo(demo_id, user_id)
        if result is None:
            raise _not_found()
        return result

    def update(self, user_id: int, demo_id: int, values: dict[str, Any]) -> dict[str, Any]:
        updated = self.repository.update_demo(demo_id, user_id, values)
        if updated == 0:
            raise _not_found()
        if updated < 0:
            raise HTTPException(status_code=422, detail="Los límites nuevos son menores que los pasos o duración actuales.")
        return self.get(user_id, demo_id)

    def delete(self, user_id: int, demo_id: int) -> dict[str, Any]:
        if self.repository.delete_demo(demo_id, user_id) == 0:
            raise _not_found()
        return {"message": "Demo privada eliminada correctamente", "id": demo_id}

    def movements(self, user_id: int, demo_id: int) -> list[dict[str, Any]]:
        self.get(user_id, demo_id)
        return self.repository.list_movements(demo_id, user_id)

    def add_movement(self, user_id: int, demo_id: int, values: dict[str, Any]) -> dict[str, Any]:
        movement_id = self.repository.add_movement(demo_id, user_id, values)
        if movement_id == 0:
            raise _not_found()
        if movement_id == -1:
            raise HTTPException(status_code=403, detail="El comando no está permitido para el modelo de la unidad.")
        if movement_id == -2:
            raise HTTPException(status_code=422, detail="La demo alcanzó el máximo de pasos permitido.")
        if movement_id == -3:
            raise HTTPException(status_code=422, detail="La duración total de la demo no puede superar 300000 ms.")
        rows = self.repository.list_movements(demo_id, user_id)
        return next((row for row in rows if int(row["id_demo_movimiento"]) == movement_id), {"id_demo_movimiento": movement_id})

    def update_movement(self, user_id: int, movement_id: int, values: dict[str, Any]) -> dict[str, Any]:
        updated = self.repository.update_movement(movement_id, user_id, values)
        if updated == 0:
            raise _not_found("Paso de demo privada no encontrado.")
        if updated == -1:
            raise HTTPException(status_code=403, detail="El comando no está permitido para el modelo de la unidad.")
        if updated == -3:
            raise HTTPException(status_code=422, detail="La duración total de la demo no puede superar 300000 ms.")
        rows = self.repository.list_movements_for_owner_movement(movement_id, user_id)
        return rows or {"id_demo_movimiento": movement_id}

    def delete_movement(self, user_id: int, movement_id: int) -> dict[str, Any]:
        if self.repository.delete_movement(movement_id, user_id) == 0:
            raise _not_found("Paso de demo privada no encontrado.")
        return {"message": "Paso eliminado correctamente", "id": movement_id}
