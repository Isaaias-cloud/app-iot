"""Pruebas aisladas de Etapa 4; no requieren conexión a RDS."""

import pytest
from fastapi import HTTPException

from app.routers.hardware_ws import ConnectionManager
from app.services_admin import hash_password
from app.services_auth import AuthService
from app.security import AuthContext, authorize_vehicle, require_allowed_command


class FakeAuthRepository:
    def __init__(self, password_hash: str):
        self.password_hash = password_hash
        self.next_id = 10
        self.sessions = {}
        self.audit = []

    def find_user_by_email(self, email):
        if email.lower() != "a@example.com":
            return None
        return {
            "id_usuario": 1,
            "email": email,
            "nombre": "User A",
            "password_hash": self.password_hash,
            "activo": 1,
            "email_verificado": 1,
        }

    def create_session(self, **values):
        self.next_id += 1
        self.sessions[self.next_id] = values
        return self.next_id

    def replace_session_token(self, session_id, token_hash_value):
        self.sessions[session_id]["token_hash_value"] = token_hash_value

    def add_audit(self, **values):
        self.audit.append(values)


def test_login_valid_and_invalid(monkeypatch):
    monkeypatch.setattr("app.tokens.JWT_SECRET", "x" * 64)
    fake = FakeAuthRepository(hash_password("correct-password"))
    service = AuthService(fake)

    result = service.login("a@example.com", "correct-password", "test-client")
    assert result["token_type"] == "bearer"
    assert result["access_token"]
    assert result["refresh_token"]
    assert any(item["action"] == "LOGIN_SUCCESS" for item in fake.audit)

    with pytest.raises(HTTPException) as error:
        service.login("a@example.com", "wrong-password", "other-client")
    assert error.value.status_code == 401
    assert any(item["action"] == "LOGIN_FAILED" for item in fake.audit)


def test_user_a_cannot_access_user_b_vehicle(monkeypatch):
    monkeypatch.setattr(
        "app.security.access_repository.vehicle_access",
        lambda *args: {
            "id_vehiculo": 7,
            "estado_inventario": "VENDIDA",
            "es_propietario": False,
            "tiene_soporte": False,
            "tiene_reserva": False,
        },
    )
    context = AuthContext(user_id=1, roles=frozenset({"USUARIO"}))
    with pytest.raises(HTTPException) as error:
        authorize_vehicle(context, 7)
    assert error.value.status_code == 403


def test_admin_sold_vehicle_requires_support(monkeypatch):
    resource = {
        "id_vehiculo": 7,
        "estado_inventario": "VENDIDA",
        "es_propietario": False,
        "tiene_soporte": False,
        "tiene_reserva": False,
    }
    monkeypatch.setattr("app.security.access_repository.vehicle_access", lambda *args: resource)
    admin = AuthContext(user_id=99, roles=frozenset({"ADMIN"}))
    with pytest.raises(HTTPException) as error:
        authorize_vehicle(admin, 7)
    assert error.value.status_code == 403

    resource["tiene_soporte"] = True
    assert authorize_vehicle(admin, 7)["id_vehiculo"] == 7


def test_command_not_allowed_for_model(monkeypatch):
    monkeypatch.setattr("app.security.access_repository.allowed_command", lambda *args: None)
    with pytest.raises(HTTPException) as error:
        require_allowed_command(7, 999)
    assert error.value.status_code == 403


def test_wss_vehicle_isolation():
    manager = ConnectionManager()
    one = object()
    two = object()
    manager.active_connections[1] = [one]
    manager.active_connections[2] = [two]
    assert manager.subscribers_for_vehicle(1) == (one,)
    assert manager.subscribers_for_vehicle(2) == (two,)
    assert one not in manager.subscribers_for_vehicle(2)

