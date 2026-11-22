"""Primitivas comunes para repositorios MySQL.

Los routers no ejecutan SQL. Los repositorios reciben valores ya validados y
usan siempre consultas parametrizadas. La capa conserva el pool existente y no
interfiere con los stored procedures de las rutas legacy.
"""

from collections.abc import Iterable
from typing import Any

from mysql.connector import Error as MySQLError

from app.database import get_connection, http_database_error


class BaseRepository:
    """Operaciones SQL pequeñas y reutilizables."""

    def fetch_all(
        self,
        query: str,
        params: Iterable[Any] = (),
        *,
        connection: Any | None = None,
    ) -> list[dict[str, Any]]:
        owns_connection = connection is None
        conn = connection
        cursor = None
        try:
            conn = conn or get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return list(cursor.fetchall())
        except MySQLError as exc:
            raise http_database_error(exc) from exc
        finally:
            if cursor is not None:
                cursor.close()
            if owns_connection and conn is not None:
                conn.close()

    def fetch_one(
        self,
        query: str,
        params: Iterable[Any] = (),
        *,
        connection: Any | None = None,
    ) -> dict[str, Any] | None:
        rows = self.fetch_all(query, params, connection=connection)
        return rows[0] if rows else None

    def execute(
        self,
        query: str,
        params: Iterable[Any] = (),
        *,
        connection: Any | None = None,
    ) -> tuple[int | None, int]:
        """Ejecuta una escritura y devuelve ``(lastrowid, rowcount)``."""
        owns_connection = connection is None
        conn = connection
        cursor = None
        try:
            conn = conn or get_connection()
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            if owns_connection:
                conn.commit()
            return cursor.lastrowid, cursor.rowcount
        except MySQLError as exc:
            if not owns_connection and conn is not None:
                conn.rollback()
            raise http_database_error(exc) from exc
        finally:
            if cursor is not None:
                cursor.close()
            if owns_connection and conn is not None:
                conn.close()
