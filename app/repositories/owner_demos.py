"""Persistencia de demos privadas y sus pasos, aislada por propietario."""

from typing import Any

from app.database import transaction
from app.repositories.base import BaseRepository


class OwnerDemoRepository(BaseRepository):
    def _owner_model(self, connection: Any, user_id: int, vehicle_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT u.id_modelo
            FROM asignaciones_vehiculo AS a
            JOIN unidades_vehiculo AS u ON u.id_vehiculo = a.id_vehiculo
            WHERE a.id_usuario = %s AND a.id_vehiculo = %s
              AND a.estado = 'ACTIVA' AND a.finaliza_en IS NULL
            LIMIT 1
            """,
            (user_id, vehicle_id),
            connection=connection,
        )

    def list_demos(self, user_id: int, vehicle_id: int | None = None) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.activo,
                   dc.alcance, dc.id_usuario, dc.duracion_max_ms, dc.max_pasos,
                   COUNT(dm.id_demo_movimiento) AS pasos,
                   COALESCE(SUM(dm.duracion_ms + dm.pausa_ms), 0) AS duracion_total_ms
            FROM demos AS d
            JOIN demos_control AS dc ON dc.id_demo = d.id_demo
            LEFT JOIN demo_movimientos AS dm ON dm.id_demo = d.id_demo
            WHERE dc.alcance = 'USUARIO' AND dc.id_usuario = %s
              AND (%s IS NULL OR d.id_vehiculo = %s)
            GROUP BY d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.activo,
                     dc.alcance, dc.id_usuario, dc.duracion_max_ms, dc.max_pasos
            ORDER BY d.id_demo DESC
            """,
            (user_id, vehicle_id, vehicle_id),
        )

    def get_demo(self, demo_id: int, user_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.activo,
                   dc.alcance, dc.id_usuario, dc.duracion_max_ms, dc.max_pasos,
                   COUNT(dm.id_demo_movimiento) AS pasos,
                   COALESCE(SUM(dm.duracion_ms + dm.pausa_ms), 0) AS duracion_total_ms
            FROM demos AS d
            JOIN demos_control AS dc ON dc.id_demo = d.id_demo
            LEFT JOIN demo_movimientos AS dm ON dm.id_demo = d.id_demo
            WHERE d.id_demo = %s AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
            GROUP BY d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.activo,
                     dc.alcance, dc.id_usuario, dc.duracion_max_ms, dc.max_pasos
            """,
            (demo_id, user_id),
        )

    def get_demo_scope(self, demo_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT d.id_demo, d.id_vehiculo, dc.alcance, dc.id_usuario,
                   dc.duracion_max_ms, dc.max_pasos
            FROM demos AS d
            JOIN demos_control AS dc ON dc.id_demo = d.id_demo
            WHERE d.id_demo = %s
            """,
            (demo_id,),
        )

    def create_demo(self, values: dict[str, Any], user_id: int) -> int:
        with transaction() as connection:
            if self._owner_model(connection, user_id, values["id_vehiculo"]) is None:
                return 0
            demo_id, _ = self.execute(
                "INSERT INTO demos (id_vehiculo, nombre, descripcion, activo) VALUES (%s, %s, %s, 1)",
                (values["id_vehiculo"], values["nombre"], values.get("descripcion")),
                connection=connection,
            )
            self.execute(
                """
                INSERT INTO demos_control
                    (id_demo, alcance, id_usuario, id_modelo, duracion_max_ms, max_pasos)
                SELECT %s, 'USUARIO', %s, u.id_modelo, %s, %s
                FROM unidades_vehiculo AS u
                WHERE u.id_vehiculo = %s
                """,
                (
                    demo_id,
                    user_id,
                    values.get("duracion_max_ms", 300000),
                    values.get("max_pasos", 100),
                    values["id_vehiculo"],
                ),
                connection=connection,
            )
            return int(demo_id or 0)

    def update_demo(self, demo_id: int, user_id: int, values: dict[str, Any]) -> int:
        with transaction() as connection:
            demo = self.fetch_one(
                """
                SELECT d.id_demo, COUNT(dm.id_demo_movimiento) AS pasos,
                       COALESCE(SUM(dm.duracion_ms + dm.pausa_ms), 0) AS duracion_total_ms
                FROM demos AS d
                JOIN demos_control AS dc ON dc.id_demo = d.id_demo
                LEFT JOIN demo_movimientos AS dm ON dm.id_demo = d.id_demo
                WHERE d.id_demo = %s AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
                GROUP BY d.id_demo
                """,
                (demo_id, user_id),
                connection=connection,
            )
            if demo is None:
                return 0
            if int(demo["pasos"]) > values["max_pasos"] or int(demo["duracion_total_ms"]) > values["duracion_max_ms"]:
                return -1
            _, count = self.execute(
                "UPDATE demos SET nombre = %s, descripcion = %s, activo = %s WHERE id_demo = %s",
                (values["nombre"], values.get("descripcion"), values.get("activo", True), demo_id),
                connection=connection,
            )
            self.execute(
                "UPDATE demos_control SET duracion_max_ms = %s, max_pasos = %s WHERE id_demo = %s AND id_usuario = %s",
                (values["duracion_max_ms"], values["max_pasos"], demo_id, user_id),
                connection=connection,
            )
            return count

    def delete_demo(self, demo_id: int, user_id: int) -> int:
        with transaction() as connection:
            _, count = self.execute(
                "DELETE FROM demos_control WHERE id_demo = %s AND alcance = 'USUARIO' AND id_usuario = %s",
                (demo_id, user_id),
                connection=connection,
            )
            if count:
                self.execute("DELETE FROM demos WHERE id_demo = %s", (demo_id,), connection=connection)
            return count

    def list_movements(self, demo_id: int, user_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT dm.id_demo_movimiento, dm.id_demo, dm.orden, dm.id_comando,
                   c.nombre AS comando, c.codigo, dm.duracion_ms, dm.pausa_ms
            FROM demo_movimientos AS dm
            JOIN demos AS d ON d.id_demo = dm.id_demo
            JOIN demos_control AS dc ON dc.id_demo = d.id_demo
            JOIN comandos AS c ON c.id_comando = dm.id_comando
            WHERE dm.id_demo = %s AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
            ORDER BY dm.orden
            """,
            (demo_id, user_id),
        )

    def _command_allowed(self, connection: Any, demo_id: int, command_id: int) -> bool:
        row = self.fetch_one(
            """
            SELECT 1 AS permitido
            FROM demos AS d
            JOIN unidades_vehiculo AS u ON u.id_vehiculo = d.id_vehiculo
            JOIN modelo_comandos AS mc ON mc.id_modelo = u.id_modelo AND mc.id_comando = %s
            JOIN comandos AS c ON c.id_comando = mc.id_comando
            WHERE d.id_demo = %s AND mc.permitido = 1 AND c.activo = 1
            """,
            (command_id, demo_id),
            connection=connection,
        )
        return row is not None

    def add_movement(self, demo_id: int, user_id: int, values: dict[str, Any]) -> int:
        with transaction() as connection:
            meta = self.fetch_one(
                """
                SELECT dc.max_pasos, dc.duracion_max_ms
                FROM demos_control AS dc
                WHERE dc.id_demo = %s AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
                """,
                (demo_id, user_id),
                connection=connection,
            )
            if meta is None:
                return 0
            if not self._command_allowed(connection, demo_id, values["id_comando"]):
                return -1
            current = self.fetch_one(
                "SELECT COUNT(*) AS pasos, COALESCE(SUM(duracion_ms + pausa_ms), 0) AS total FROM demo_movimientos WHERE id_demo = %s",
                (demo_id,),
                connection=connection,
            )
            if int(current["pasos"]) >= int(meta["max_pasos"]):
                return -2
            new_total = int(current["total"]) + values["duracion_ms"] + values.get("pausa_ms", 0)
            if new_total > int(meta["duracion_max_ms"]):
                return -3
            movement_id, _ = self.execute(
                """
                INSERT INTO demo_movimientos (id_demo, id_comando, orden, duracion_ms, pausa_ms)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (demo_id, values["id_comando"], values["orden"], values["duracion_ms"], values.get("pausa_ms", 0)),
                connection=connection,
            )
            return int(movement_id or 0)

    def update_movement(self, movement_id: int, user_id: int, values: dict[str, Any]) -> int:
        with transaction() as connection:
            old = self.fetch_one(
                """
                SELECT dm.id_demo, dm.duracion_ms AS old_duracion, dm.pausa_ms AS old_pausa,
                       dc.max_pasos, dc.duracion_max_ms
                FROM demo_movimientos AS dm
                JOIN demos_control AS dc ON dc.id_demo = dm.id_demo
                WHERE dm.id_demo_movimiento = %s AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
                """,
                (movement_id, user_id),
                connection=connection,
            )
            if old is None:
                return 0
            if not self._command_allowed(connection, int(old["id_demo"]), values["id_comando"]):
                return -1
            current = self.fetch_one(
                "SELECT COALESCE(SUM(duracion_ms + pausa_ms), 0) AS total FROM demo_movimientos WHERE id_demo = %s",
                (old["id_demo"],),
                connection=connection,
            )
            new_total = int(current["total"]) - int(old["old_duracion"]) - int(old["old_pausa"])
            new_total += values["duracion_ms"] + values.get("pausa_ms", 0)
            if new_total > int(old["duracion_max_ms"]):
                return -3
            _, count = self.execute(
                """
                UPDATE demo_movimientos
                SET id_comando = %s, orden = %s, duracion_ms = %s, pausa_ms = %s
                WHERE id_demo_movimiento = %s
                """,
                (values["id_comando"], values["orden"], values["duracion_ms"], values.get("pausa_ms", 0), movement_id),
                connection=connection,
            )
            return count

    def delete_movement(self, movement_id: int, user_id: int) -> int:
        _, count = self.execute(
            """
            DELETE dm FROM demo_movimientos AS dm
            JOIN demos_control AS dc ON dc.id_demo = dm.id_demo
            WHERE dm.id_demo_movimiento = %s AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
            """,
            (movement_id, user_id),
        )
        return count

    def list_movements_for_owner_movement(self, movement_id: int, user_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT dm.id_demo_movimiento, dm.id_demo, dm.orden, dm.id_comando,
                   c.nombre AS comando, c.codigo, dm.duracion_ms, dm.pausa_ms
            FROM demo_movimientos AS dm
            JOIN demos_control AS dc ON dc.id_demo = dm.id_demo
            JOIN comandos AS c ON c.id_comando = dm.id_comando
            WHERE dm.id_demo_movimiento = %s
              AND dc.alcance = 'USUARIO' AND dc.id_usuario = %s
            """,
            (movement_id, user_id),
        )
