"""Pruebas aisladas de propiedad, soporte y demos privadas de Etapa 6."""

import pytest
from fastapi import HTTPException

from app.security import AuthContext, authorize_vehicle
from app.services_owner import OwnerDemoService


class FakeOwnerDemoRepository:
    def __init__(self):
        self.next_id = 40
        self.demos = {}
        self.movement_result = 41

    def create_demo(self, values, user_id):
        if values["id_vehiculo"] != 7 or user_id != 1:
            return 0
        self.next_id += 1
        self.demos[self.next_id] = {"id_demo": self.next_id, "id_usuario": user_id, **values}
        return self.next_id

    def get_demo(self, demo_id, user_id):
        demo = self.demos.get(demo_id)
        return demo if demo and demo["id_usuario"] == user_id else None

    def update_demo(self, *args, **kwargs):
        return 0

    def delete_demo(self, *args, **kwargs):
        return 0

    def list_demos(self, *args, **kwargs):
        return []

    def list_movements(self, *args, **kwargs):
        return []

    def add_movement(self, *args, **kwargs):
        return self.movement_result

    def update_movement(self, *args, **kwargs):
        return 0

    def delete_movement(self, *args, **kwargs):
        return 0

    def list_movements_for_owner_movement(self, *args, **kwargs):
        return {"id_demo_movimiento": 41}


def test_private_demo_creation_and_isolation():
    repository = FakeOwnerDemoRepository()
    service = OwnerDemoService(repository)
    created = service.create(1, {"id_vehiculo": 7, "nombre": "Ruta propia", "descripcion": None})
    assert created["id_usuario"] == 1

    with pytest.raises(HTTPException) as error:
        service.get(2, created["id_demo"])
    assert error.value.status_code == 404


def test_private_demo_rejects_command_outside_model():
    repository = FakeOwnerDemoRepository()
    repository.movement_result = -1
    service = OwnerDemoService(repository)
    with pytest.raises(HTTPException) as error:
        service.add_movement(1, 40, {"id_comando": 999, "orden": 1, "duracion_ms": 100, "pausa_ms": 0})
    assert error.value.status_code == 403


def test_support_revocation_blocks_admin_again(monkeypatch):
    resource = {
        "id_vehiculo": 7,
        "estado_inventario": "VENDIDA",
        "es_propietario": False,
        "tiene_soporte": True,
        "tiene_reserva": False,
    }
    monkeypatch.setattr("app.security.access_repository.vehicle_access", lambda *args: resource)
    admin = AuthContext(user_id=99, roles=frozenset({"ADMIN"}))
    assert authorize_vehicle(admin, 7)["id_vehiculo"] == 7
    resource["tiene_soporte"] = False
    with pytest.raises(HTTPException) as error:
        authorize_vehicle(admin, 7)
    assert error.value.status_code == 403
