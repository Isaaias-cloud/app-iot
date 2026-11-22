"""Catálogo y reservas exclusivas de exhibición."""

from typing import Any

from app.database import transaction
from app.repositories.base import BaseRepository


class GuestRepository(BaseRepository):
    def expire_due(self) -> None:
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

    def exhibition_catalog(self) -> list[dict[str, Any]]:
        self.expire_due()
        return self.fetch_all(
            """
            SELECT u.id_vehiculo, v.nombre AS vehiculo_nombre,
                   u.identificador_unico, m.id_modelo, m.clave AS modelo_clave,
                   m.nombre AS modelo_nombre,
                   CASE WHEN r.id_reserva IS NULL THEN 'DISPONIBLE' ELSE 'OCUPADA' END AS estado,
                   r.expira_en AS libera_en
            FROM unidades_vehiculo AS u
            JOIN vehiculos AS v ON v.id_vehiculo = u.id_vehiculo
            JOIN modelos_vehiculo AS m ON m.id_modelo = u.id_modelo
            LEFT JOIN reservas_exhibicion AS r
              ON r.id_vehiculo = u.id_vehiculo
             AND r.estado = 'ACTIVA' AND r.liberada_en IS NULL
             AND r.expira_en > UTC_TIMESTAMP(6)
            WHERE u.estado_inventario = 'EXHIBICION'
            ORDER BY u.id_vehiculo
            """
        )

    def reserve(self, vehicle_id: int, token_hash_value: str) -> dict[str, Any] | None:
        with transaction() as connection:
            unit = self.fetch_one(
                """
                SELECT id_vehiculo FROM unidades_vehiculo
                WHERE id_vehiculo = %s AND estado_inventario = 'EXHIBICION'
                FOR UPDATE
                """,
                (vehicle_id,),
                connection=connection,
            )
            if unit is None:
                return None
            active = self.fetch_one(
                """
                SELECT id_reserva FROM reservas_exhibicion
                WHERE id_vehiculo = %s AND estado = 'ACTIVA'
                  AND liberada_en IS NULL AND expira_en > UTC_TIMESTAMP(6)
                LIMIT 1
                """,
                (vehicle_id,),
                connection=connection,
            )
            if active is not None:
                return {"conflict": True}
            session_id, _ = self.execute(
                """
                INSERT INTO sesiones_invitado (token_hash, id_vehiculo, inicia_en, expira_en, estado)
                VALUES (%s, %s, UTC_TIMESTAMP(6), DATE_ADD(UTC_TIMESTAMP(6), INTERVAL 300 SECOND), 'ACTIVA')
                """,
                (token_hash_value, vehicle_id),
                connection=connection,
            )
            session = self.fetch_one(
                """
                SELECT inicia_en, expira_en
                FROM sesiones_invitado
                WHERE id_sesion_invitado = %s
                """,
                (session_id,),
                connection=connection,
            )
            self.execute(
                """
                INSERT INTO reservas_exhibicion
                    (id_vehiculo, id_sesion_invitado, inicia_en, expira_en, estado)
                VALUES (%s, %s, %s, %s, 'ACTIVA')
                """,
                (vehicle_id, session_id, session["inicia_en"], session["expira_en"]),
                connection=connection,
            )
            return self.fetch_one(
                """
                SELECT id_sesion_invitado, id_vehiculo, inicia_en, expira_en
                FROM sesiones_invitado WHERE id_sesion_invitado = %s
                """,
                (session_id,),
                connection=connection,
            )

    def replace_token_hash(self, session_id: int, token_hash_value: str) -> None:
        self.execute(
            "UPDATE sesiones_invitado SET token_hash = %s WHERE id_sesion_invitado = %s",
            (token_hash_value, session_id),
        )
