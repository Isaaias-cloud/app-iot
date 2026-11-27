"""Persistencia de movimientos puntuales con duracion (tabla 0002)."""

from typing import Any

from app.repositories.base import BaseRepository

_SELECT = """
    SELECT m.id_movimiento, m.id_comando, m.nombre, m.duracion_ms, m.activo,
           c.id_vehiculo, c.codigo, c.nombre AS comando
    FROM movimientos AS m
    JOIN comandos AS c ON c.id_comando = m.id_comando
"""


class MovimientoRepository(BaseRepository):
    """SQL parametrizado sobre `movimientos`; nunca interpreta el codigo del ESP."""

    def get_command(self, command_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id_comando, id_vehiculo, nombre, codigo, activo
            FROM comandos WHERE id_comando = %s
            """,
            (command_id,),
        )

    def list_for_vehicle(self, vehicle_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(
            _SELECT + " WHERE c.id_vehiculo = %s AND m.activo = 1 ORDER BY m.id_movimiento",
            (vehicle_id,),
        )

    def get(self, movement_id: int) -> dict[str, Any] | None:
        return self.fetch_one(_SELECT + " WHERE m.id_movimiento = %s", (movement_id,))

    def create(self, *, command_id: int, nombre: str, duracion_ms: int) -> int:
        last_id, _ = self.execute(
            """
            INSERT INTO movimientos (id_comando, nombre, duracion_ms, activo)
            VALUES (%s, %s, %s, 1)
            """,
            (command_id, nombre, duracion_ms),
        )
        return int(last_id)

    def update(self, movement_id: int, *, nombre: str, duracion_ms: int, activo: bool) -> int:
        _, count = self.execute(
            """
            UPDATE movimientos
            SET nombre = %s, duracion_ms = %s, activo = %s
            WHERE id_movimiento = %s
            """,
            (nombre, duracion_ms, activo, movement_id),
        )
        return count

    def deactivate(self, movement_id: int) -> int:
        """Desactiva sin borrar: conserva el historial y las demos que lo referencien."""
        _, count = self.execute(
            "UPDATE movimientos SET activo = 0 WHERE id_movimiento = %s AND activo = 1",
            (movement_id,),
        )
        return count
