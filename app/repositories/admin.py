"""Repositorios para el modelo administrativo de la migración 0001."""

from collections.abc import Iterable
from typing import Any

from app.database import transaction
from app.repositories.base import BaseRepository


class AdminRepository(BaseRepository):
    """Consultas parametrizadas sobre las tablas nuevas y sus tablas legacy."""

    def dashboard(self) -> dict[str, int]:
        tables = (
            "vehiculos",
            "unidades_vehiculo",
            "usuarios",
            "asignaciones_vehiculo",
            "demos",
            "auditoria",
        )
        result: dict[str, int] = {}
        for table in tables:
            row = self.fetch_one(f"SELECT COUNT(*) AS total FROM `{table}`")
            result[table] = int(row["total"] if row else 0)
        return result

    def list_models(self, limit: int, offset: int, search: str | None) -> list[dict[str, Any]]:
        query = """
            SELECT id_modelo, clave, nombre, descripcion, microcontrolador,
                   activo, creado_en, actualizado_en
            FROM modelos_vehiculo
            WHERE (%s IS NULL OR nombre LIKE CONCAT('%%', %s, '%%')
                   OR clave LIKE CONCAT('%%', %s, '%%'))
            ORDER BY id_modelo
            LIMIT %s OFFSET %s
        """
        return self.fetch_all(query, (search, search, search, limit, offset))

    def get_model(self, model_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_modelo, clave, nombre, descripcion, microcontrolador,
                   activo, creado_en, actualizado_en
            FROM modelos_vehiculo
            WHERE id_modelo = %s
            """,
            (model_id,),
        )

    def get_model_command(self, model_id: int, command_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_modelo, id_comando, codigo, nombre, permitido
            FROM modelo_comandos
            WHERE id_modelo = %s AND id_comando = %s
            """,
            (model_id, command_id),
        )

    def list_model_commands(self, model_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT id_modelo, id_comando, codigo, nombre, permitido
            FROM modelo_comandos
            WHERE id_modelo = %s
            ORDER BY codigo, id_comando
            """,
            (model_id,),
        )

    def update_model_command(self, model_id: int, command_id: int, permitido: bool) -> int:
        _, count = self.execute(
            """
            UPDATE modelo_comandos
            SET permitido = %s
            WHERE id_modelo = %s AND id_comando = %s
            """,
            (permitido, model_id, command_id),
        )
        return count

    def create_model(self, values: dict[str, Any]) -> int:
        last_id, _ = self.execute(
            """
            INSERT INTO modelos_vehiculo
                (clave, nombre, descripcion, microcontrolador, activo)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                values["clave"],
                values["nombre"],
                values.get("descripcion"),
                values.get("microcontrolador"),
                values.get("activo", True),
            ),
        )
        return int(last_id)

    def update_model(self, model_id: int, values: dict[str, Any]) -> int:
        _, count = self.execute(
            """
            UPDATE modelos_vehiculo
            SET nombre = %s,
                descripcion = %s,
                microcontrolador = %s,
                activo = %s
            WHERE id_modelo = %s
            """,
            (
                values["nombre"],
                values.get("descripcion"),
                values.get("microcontrolador"),
                values["activo"],
                model_id,
            ),
        )
        return count

    def list_units(self, limit: int, offset: int, inventory_state: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT u.id_vehiculo, u.id_modelo, u.identificador_unico,
                   u.estado_inventario, u.creado_en, u.actualizado_en,
                   v.nombre, v.modelo AS legacy_modelo, v.descripcion,
                   v.microcontrolador, v.activo,
                   m.clave AS modelo_clave, m.nombre AS modelo_nombre
            FROM unidades_vehiculo AS u
            JOIN vehiculos AS v ON v.id_vehiculo = u.id_vehiculo
            JOIN modelos_vehiculo AS m ON m.id_modelo = u.id_modelo
            WHERE (%s IS NULL OR u.estado_inventario = %s)
            ORDER BY u.id_vehiculo
            LIMIT %s OFFSET %s
            """,
            (inventory_state, inventory_state, limit, offset),
        )

    def get_unit(self, vehicle_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT u.id_vehiculo, u.id_modelo, u.identificador_unico,
                   u.estado_inventario, u.creado_en, u.actualizado_en,
                   v.nombre, v.modelo AS legacy_modelo, v.descripcion,
                   v.microcontrolador, v.activo,
                   m.clave AS modelo_clave, m.nombre AS modelo_nombre
            FROM unidades_vehiculo AS u
            JOIN vehiculos AS v ON v.id_vehiculo = u.id_vehiculo
            JOIN modelos_vehiculo AS m ON m.id_modelo = u.id_modelo
            WHERE u.id_vehiculo = %s
            """,
            (vehicle_id,),
        )

    def create_unit(self, values: dict[str, Any]) -> int:
        with transaction() as connection:
            model = self.fetch_one(
                "SELECT nombre, microcontrolador FROM modelos_vehiculo WHERE id_modelo = %s",
                (values["id_modelo"],),
                connection=connection,
            )
            if model is None:
                return 0
            vehicle_id, _ = self.execute(
                """
                INSERT INTO vehiculos
                    (nombre, modelo, descripcion, microcontrolador, activo)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    values["nombre"],
                    model["nombre"],
                    values.get("descripcion"),
                    model["microcontrolador"],
                    values.get("activo", True),
                ),
                connection=connection,
            )
            self.execute(
                """
                INSERT INTO unidades_vehiculo
                    (id_vehiculo, id_modelo, identificador_unico, estado_inventario)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    vehicle_id,
                    values["id_modelo"],
                    values["identificador_unico"],
                    values.get("estado_inventario", "INVENTARIO"),
                ),
                connection=connection,
            )
            return int(vehicle_id)

    def update_unit(self, vehicle_id: int, values: dict[str, Any]) -> int:
        with transaction() as connection:
            _, count = self.execute(
                """
                UPDATE unidades_vehiculo
                SET id_modelo = %s,
                    estado_inventario = %s,
                    identificador_unico = %s
                WHERE id_vehiculo = %s
                """,
                (
                    values["id_modelo"],
                    values["estado_inventario"],
                    values["identificador_unico"],
                    vehicle_id,
                ),
                connection=connection,
            )
            if count:
                self.execute(
                    "UPDATE vehiculos SET activo = %s WHERE id_vehiculo = %s",
                    (values["estado_inventario"] != "BAJA", vehicle_id),
                    connection=connection,
                )
            return count

    def list_clients(self, limit: int, offset: int, search: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT id_usuario, email, nombre, activo, email_verificado,
                   creado_en, actualizado_en
            FROM usuarios
            WHERE (%s IS NULL OR email LIKE CONCAT('%%', %s, '%%')
                   OR nombre LIKE CONCAT('%%', %s, '%%'))
            ORDER BY id_usuario
            LIMIT %s OFFSET %s
            """,
            (search, search, search, limit, offset),
        )

    def list_admins(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT u.id_usuario, u.nombre, u.email
            FROM usuarios AS u
            JOIN usuario_roles AS ur ON ur.id_usuario = u.id_usuario
            JOIN roles AS r ON r.id_rol = ur.id_rol
            WHERE r.codigo = 'ADMIN' AND r.activo = 1 AND u.activo = 1
            ORDER BY u.nombre, u.id_usuario
            """
        )

    def get_client(self, user_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_usuario, email, nombre, activo, email_verificado,
                   creado_en, actualizado_en
            FROM usuarios
            WHERE id_usuario = %s
            """,
            (user_id,),
        )

    def create_client(self, values: dict[str, Any]) -> int:
        with transaction() as connection:
            user_id, _ = self.execute(
                """
                INSERT INTO usuarios (email, nombre, password_hash, activo, email_verificado)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    values["email"],
                    values["nombre"],
                    values["password_hash"],
                    values.get("activo", True),
                    values.get("email_verificado", False),
                ),
                connection=connection,
            )
            role = self.fetch_one(
                "SELECT id_rol FROM roles WHERE codigo = 'USUARIO'",
                connection=connection,
            )
            if role is None:
                return 0
            self.execute(
                "INSERT INTO usuario_roles (id_usuario, id_rol) VALUES (%s, %s)",
                (user_id, role["id_rol"]),
                connection=connection,
            )
            return int(user_id)

    def update_client(self, user_id: int, values: dict[str, Any]) -> int:
        _, count = self.execute(
            """
            UPDATE usuarios
            SET nombre = %s, activo = %s, email_verificado = %s
            WHERE id_usuario = %s
            """,
            (values["nombre"], values["activo"], values["email_verificado"], user_id),
        )
        return count

    def list_assignments(self, limit: int, offset: int, vehicle_id: int | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT a.id_asignacion, a.id_vehiculo, a.id_usuario, a.tipo,
                   a.estado, a.inicia_en, a.finaliza_en, a.motivo,
                   u.email, u.nombre AS usuario_nombre,
                   v.nombre AS vehiculo_nombre
            FROM asignaciones_vehiculo AS a
            JOIN usuarios AS u ON u.id_usuario = a.id_usuario
            JOIN vehiculos AS v ON v.id_vehiculo = a.id_vehiculo
            WHERE (%s IS NULL OR a.id_vehiculo = %s)
            ORDER BY a.id_asignacion DESC
            LIMIT %s OFFSET %s
            """,
            (vehicle_id, vehicle_id, limit, offset),
        )

    def get_assignment(self, assignment_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT a.id_asignacion, a.id_vehiculo, a.id_usuario, a.tipo,
                   a.estado, a.inicia_en, a.finaliza_en, a.motivo,
                   u.email, u.nombre AS usuario_nombre,
                   v.nombre AS vehiculo_nombre
            FROM asignaciones_vehiculo AS a
            JOIN usuarios AS u ON u.id_usuario = a.id_usuario
            JOIN vehiculos AS v ON v.id_vehiculo = a.id_vehiculo
            WHERE a.id_asignacion = %s
            """,
            (assignment_id,),
        )

    def create_assignment(self, values: dict[str, Any]) -> int:
        last_id, _ = self.execute(
            """
            INSERT INTO asignaciones_vehiculo
                (id_vehiculo, id_usuario, tipo, estado, motivo, creado_por)
            VALUES (%s, %s, 'PROPIETARIO', 'ACTIVA', %s, %s)
            """,
            (
                values["id_vehiculo"],
                values["id_usuario"],
                values.get("motivo"),
                values.get("creado_por"),
            ),
        )
        return int(last_id)

    def revoke_assignment(self, assignment_id: int, reason: str | None) -> int:
        _, count = self.execute(
            """
            UPDATE asignaciones_vehiculo
            SET estado = 'REVOCADA', finaliza_en = CURRENT_TIMESTAMP(6),
                motivo = COALESCE(%s, motivo)
            WHERE id_asignacion = %s AND estado = 'ACTIVA'
            """,
            (reason, assignment_id),
        )
        return count

    def list_audit(self, limit: int, offset: int, resource_type: str | None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT id_auditoria, id_usuario, actor_tipo, accion, recurso_tipo,
                   recurso_id, detalle, ip_hash, creado_en
            FROM auditoria
            WHERE (%s IS NULL OR recurso_tipo = %s)
            ORDER BY id_auditoria DESC
            LIMIT %s OFFSET %s
            """,
            (resource_type, resource_type, limit, offset),
        )

    def list_my_vehicles(self, user_id: int, limit: int, offset: int, include_support: bool = False) -> list[dict[str, Any]]:
        if include_support:
            return self.fetch_all(
                """
                SELECT s.id_autorizacion AS id_asignacion, s.id_propietario AS id_usuario,
                       s.id_vehiculo, 'SOPORTE' AS estado, s.creado_en AS inicia_en,
                       s.expira_en AS finaliza_en, 'SOPORTE' AS acceso_tipo,
                       v.nombre AS vehiculo_nombre, u.identificador_unico,
                       u.estado_inventario, m.id_modelo, m.clave AS modelo_clave,
                       m.nombre AS modelo_nombre
                FROM autorizaciones_soporte AS s
                JOIN unidades_vehiculo AS u ON u.id_vehiculo = s.id_vehiculo
                JOIN vehiculos AS v ON v.id_vehiculo = s.id_vehiculo
                JOIN modelos_vehiculo AS m ON m.id_modelo = u.id_modelo
                WHERE s.id_admin = %s
                  AND s.estado = 'ACTIVA'
                  AND s.revocada_en IS NULL
                  AND s.expira_en > UTC_TIMESTAMP(6)
                ORDER BY s.expira_en ASC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
        return self.fetch_all(
            """
            SELECT a.id_asignacion, a.id_usuario, a.id_vehiculo,
                   a.estado, a.inicia_en, a.finaliza_en,
                   v.nombre AS vehiculo_nombre,
                   u.identificador_unico, u.estado_inventario,
                   m.id_modelo, m.clave AS modelo_clave, m.nombre AS modelo_nombre
            FROM asignaciones_vehiculo AS a
            JOIN unidades_vehiculo AS u ON u.id_vehiculo = a.id_vehiculo
            JOIN vehiculos AS v ON v.id_vehiculo = a.id_vehiculo
            JOIN modelos_vehiculo AS m ON m.id_modelo = u.id_modelo
            WHERE a.id_usuario = %s AND a.estado = 'ACTIVA'
            ORDER BY a.id_asignacion DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, limit, offset),
        )
