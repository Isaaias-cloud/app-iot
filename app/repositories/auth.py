"""Persistencia de usuarios, sesiones y auditoría de autenticación."""

import json
from datetime import datetime, timezone
from typing import Any

from app.database import transaction
from app.repositories.base import BaseRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthRepository(BaseRepository):
    def create_user_with_role(
        self,
        *,
        email: str,
        name: str,
        password_hash: str,
        role_code: str,
    ) -> int:
        with transaction() as connection:
            user_id, _ = self.execute(
                """
                INSERT INTO usuarios (email, nombre, password_hash, activo, email_verificado)
                VALUES (%s, %s, %s, 1, 1)
                """,
                (email, name, password_hash),
                connection=connection,
            )
            role = self.fetch_one(
                "SELECT id_rol FROM roles WHERE codigo = %s AND activo = 1",
                (role_code,),
                connection=connection,
            )
            if role is None:
                raise RuntimeError(f"El rol {role_code} no está configurado.")
            self.execute(
                "INSERT INTO usuario_roles (id_usuario, id_rol) VALUES (%s, %s)",
                (user_id, role["id_rol"]),
                connection=connection,
            )
            return int(user_id)

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_usuario, email, nombre, password_hash, activo, email_verificado
            FROM usuarios
            WHERE LOWER(email) = LOWER(%s)
            """,
            (email,),
        )

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_usuario, email, nombre, activo, email_verificado,
                   creado_en, actualizado_en
            FROM usuarios
            WHERE id_usuario = %s
            """,
            (user_id,),
        )

    def get_roles(self, user_id: int) -> frozenset[str]:
        rows = self.fetch_all(
            """
            SELECT r.codigo
            FROM usuario_roles AS ur
            JOIN roles AS r ON r.id_rol = ur.id_rol
            WHERE ur.id_usuario = %s AND r.activo = 1
            """,
            (user_id,),
        )
        return frozenset(str(row["codigo"]) for row in rows)

    def create_session(
        self,
        *,
        user_id: int,
        token_type: str,
        token_hash_value: str,
        expires_at: datetime,
        ip_hash: str | None = None,
        user_agent: str | None = None,
    ) -> int:
        last_id, _ = self.execute(
            """
            INSERT INTO sesiones_usuario
                (id_usuario, tipo, token_hash, expira_en, ip_hash, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, token_type, token_hash_value, expires_at, ip_hash, user_agent),
        )
        return int(last_id)

    def get_active_session(self, session_id: int, token_hash_value: str) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT s.id_sesion, s.id_usuario, s.tipo, s.expira_en,
                   u.email, u.nombre, u.activo
            FROM sesiones_usuario AS s
            JOIN usuarios AS u ON u.id_usuario = s.id_usuario
            WHERE s.id_sesion = %s
              AND s.token_hash = %s
              AND s.revocada_en IS NULL
              AND s.expira_en > UTC_TIMESTAMP(6)
              AND u.activo = 1
            """,
            (session_id, token_hash_value),
        )

    def replace_session_token(self, session_id: int, token_hash_value: str) -> None:
        self.execute(
            "UPDATE sesiones_usuario SET token_hash = %s WHERE id_sesion = %s",
            (token_hash_value, session_id),
        )

    def touch_session(self, session_id: int) -> None:
        self.execute(
            "UPDATE sesiones_usuario SET ultimo_uso_en = UTC_TIMESTAMP(6) WHERE id_sesion = %s",
            (session_id,),
        )

    def revoke_session(self, session_id: int, user_id: int) -> int:
        _, count = self.execute(
            """
            UPDATE sesiones_usuario
            SET revocada_en = UTC_TIMESTAMP(6)
            WHERE id_sesion = %s AND id_usuario = %s AND revocada_en IS NULL
            """,
            (session_id, user_id),
        )
        return count

    def revoke_token_hash(self, token_hash_value: str) -> int:
        _, count = self.execute(
            """
            UPDATE sesiones_usuario
            SET revocada_en = UTC_TIMESTAMP(6)
            WHERE token_hash = %s AND revocada_en IS NULL
            """,
            (token_hash_value,),
        )
        return count

    def revoke_user_refresh_sessions(self, user_id: int) -> int:
        _, count = self.execute(
            """
            UPDATE sesiones_usuario
            SET revocada_en = UTC_TIMESTAMP(6)
            WHERE id_usuario = %s AND tipo = 'REFRESH' AND revocada_en IS NULL
            """,
            (user_id,),
        )
        return count

    def add_audit(
        self,
        *,
        user_id: int | None,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        detail_payload = (
            json.dumps(detail, ensure_ascii=False, default=str)
            if detail is not None and not isinstance(detail, str)
            else detail
        )
        self.execute(
            """
            INSERT INTO auditoria
                (id_usuario, actor_tipo, accion, recurso_tipo, recurso_id, detalle)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, actor_type, action, resource_type, resource_id, detail_payload),
        )


class AccessRepository(BaseRepository):
    """Consultas de autorización por vehículo, demo y comando."""

    def vehicle_access(self, vehicle_id: int, user_id: int, role: str, guest_session_id: int | None) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT
                u.id_vehiculo,
                u.estado_inventario,
                EXISTS(
                    SELECT 1 FROM asignaciones_vehiculo AS a
                    WHERE a.id_vehiculo = u.id_vehiculo
                      AND a.id_usuario = %s AND a.estado = 'ACTIVA'
                      AND a.finaliza_en IS NULL
                ) AS es_propietario,
                EXISTS(
                    SELECT 1 FROM autorizaciones_soporte AS s
                    WHERE s.id_vehiculo = u.id_vehiculo
                      AND s.id_admin = %s
                      AND s.estado = 'ACTIVA'
                      AND s.revocada_en IS NULL
                      AND s.expira_en > UTC_TIMESTAMP(6)
                ) AS tiene_soporte,
                EXISTS(
                    SELECT 1
                    FROM reservas_exhibicion AS r
                    WHERE r.id_vehiculo = u.id_vehiculo
                      AND r.id_sesion_invitado = %s
                      AND r.estado = 'ACTIVA'
                      AND r.liberada_en IS NULL
                      AND r.expira_en > UTC_TIMESTAMP(6)
                ) AS tiene_reserva
            FROM unidades_vehiculo AS u
            WHERE u.id_vehiculo = %s
            """,
            (user_id, user_id, guest_session_id or 0, vehicle_id),
        )

    def demo_vehicle(self, demo_id: int) -> int | None:
        row = self.fetch_one("SELECT id_vehiculo FROM demos WHERE id_demo = %s", (demo_id,))
        return int(row["id_vehiculo"]) if row else None

    def demo_scope(self, demo_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT dc.alcance, dc.id_usuario
            FROM demos_control AS dc
            WHERE dc.id_demo = %s
            """,
            (demo_id,),
        )

    def is_company_demo(self, demo_id: int) -> bool:
        scope = self.demo_scope(demo_id)
        return scope is not None and scope.get("alcance") == "EMPRESA"

    def command_by_code(self, vehicle_id: int, code: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT c.id_comando, c.codigo, c.nombre
            FROM comandos AS c
            JOIN modelo_comandos AS mc ON mc.id_comando = c.id_comando
            JOIN unidades_vehiculo AS u ON u.id_modelo = mc.id_modelo
            WHERE u.id_vehiculo = %s AND c.codigo = %s
              AND mc.permitido = 1 AND c.activo = 1
            LIMIT 1
            """,
            (vehicle_id, code),
        )

    def movement_vehicle(self, movement_id: int) -> int | None:
        row = self.fetch_one(
            """
            SELECT d.id_vehiculo
            FROM demo_movimientos AS dm
            JOIN demos AS d ON d.id_demo = dm.id_demo
            WHERE dm.id_demo_movimiento = %s
            """,
            (movement_id,),
        )
        return int(row["id_vehiculo"]) if row else None

    def allowed_command(self, vehicle_id: int, command_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT c.id_comando, c.codigo, c.nombre
            FROM comandos AS c
            JOIN modelo_comandos AS mc ON mc.id_comando = c.id_comando
            JOIN unidades_vehiculo AS u ON u.id_modelo = mc.id_modelo
            WHERE u.id_vehiculo = %s
              AND c.id_comando = %s
              AND mc.permitido = 1
              AND c.activo = 1
            """,
            (vehicle_id, command_id),
        )

    def support_authorization(self, vehicle_id: int, owner_id: int, admin_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_autorizacion, id_vehiculo, id_propietario, id_admin,
                   motivo, creado_en, expira_en, revocada_en, estado
            FROM autorizaciones_soporte
            WHERE id_vehiculo = %s
              AND id_propietario = %s
              AND id_admin = %s
              AND estado = 'ACTIVA'
              AND revocada_en IS NULL
              AND expira_en > UTC_TIMESTAMP(6)
            ORDER BY id_autorizacion DESC
            LIMIT 1
            """,
            (vehicle_id, owner_id, admin_id),
        )

    def is_admin(self, user_id: int) -> bool:
        row = self.fetch_one(
            """
            SELECT 1 AS allowed
            FROM usuario_roles AS ur
            JOIN roles AS r ON r.id_rol = ur.id_rol
            WHERE ur.id_usuario = %s AND r.codigo = 'ADMIN' AND r.activo = 1
            LIMIT 1
            """,
            (user_id,),
        )
        return row is not None

    def list_support_authorizations(self, vehicle_id: int, owner_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT id_autorizacion, id_vehiculo, id_propietario, id_admin,
                   motivo, creado_en, expira_en, revocada_en, estado
            FROM autorizaciones_soporte
            WHERE id_vehiculo = %s AND id_propietario = %s
            ORDER BY id_autorizacion DESC
            """,
            (vehicle_id, owner_id),
        )

    def create_support_authorization(
        self,
        *,
        vehicle_id: int,
        owner_id: int,
        admin_id: int,
        reason: str,
        expires_at: datetime,
    ) -> int:
        last_id, _ = self.execute(
            """
            INSERT INTO autorizaciones_soporte
                (id_vehiculo, id_propietario, id_admin, motivo, expira_en, estado)
            VALUES (%s, %s, %s, %s, %s, 'ACTIVA')
            """,
            (vehicle_id, owner_id, admin_id, reason, expires_at),
        )
        return int(last_id)

    def revoke_support_authorization(self, authorization_id: int, owner_id: int) -> int:
        _, count = self.execute(
            """
            UPDATE autorizaciones_soporte
            SET estado = 'REVOCADA', revocada_en = UTC_TIMESTAMP(6)
            WHERE id_autorizacion = %s
              AND id_propietario = %s
              AND estado = 'ACTIVA'
            """,
            (authorization_id, owner_id),
        )
        return count

    def get_support_authorization(self, authorization_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_autorizacion, id_vehiculo, id_propietario, id_admin,
                   motivo, creado_en, expira_en, revocada_en, estado
            FROM autorizaciones_soporte
            WHERE id_autorizacion = %s
            """,
            (authorization_id,),
        )

    def guest_context(self, token_hash_value: str) -> dict[str, Any] | None:
        self.expire_guest_records()
        return self.fetch_one(
            """
            SELECT id_sesion_invitado, id_vehiculo, expira_en
            FROM sesiones_invitado
            WHERE token_hash = %s
              AND estado = 'ACTIVA'
              AND expira_en > UTC_TIMESTAMP(6)
            """,
            (token_hash_value,),
        )

    def expire_guest_records(self) -> None:
        self.execute(
            """
            UPDATE reservas_exhibicion
            SET estado = 'EXPIRADA', liberada_en = COALESCE(liberada_en, UTC_TIMESTAMP(6))
            WHERE estado = 'ACTIVA' AND expira_en <= UTC_TIMESTAMP(6)
            """
        )
        self.execute(
            """
            UPDATE sesiones_invitado
            SET estado = 'EXPIRADA', desconectada_en = COALESCE(desconectada_en, UTC_TIMESTAMP(6))
            WHERE estado = 'ACTIVA' AND expira_en <= UTC_TIMESTAMP(6)
            """
        )

    def guest_session_by_id(self, session_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_sesion_invitado, id_vehiculo, expira_en, estado
            FROM sesiones_invitado
            WHERE id_sesion_invitado = %s
            """,
            (session_id,),
        )

    def release_guest_session(self, session_id: int, state: str) -> dict[str, Any] | None:
        session = self.guest_session_by_id(session_id)
        if session is None:
            return None
        self.execute(
            """
            UPDATE reservas_exhibicion
            SET estado = %s, liberada_en = COALESCE(liberada_en, UTC_TIMESTAMP(6))
            WHERE id_sesion_invitado = %s AND estado = 'ACTIVA'
            """,
            (state, session_id),
        )
        self.execute(
            """
            UPDATE sesiones_invitado
            SET estado = %s, desconectada_en = COALESCE(desconectada_en, UTC_TIMESTAMP(6))
            WHERE id_sesion_invitado = %s AND estado = 'ACTIVA'
            """,
            (state, session_id),
        )
        return session
