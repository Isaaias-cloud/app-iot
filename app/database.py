"""Acceso seguro y reutilizable a los stored procedures de MySQL.

Los procedimientos de lectura y escritura se ejecutan mediante el mismo pool.
La función :func:`transaction` permite agrupar varios procedimientos en una
transacción real, que es necesaria para el endpoint de movimiento individual.
"""

from contextlib import contextmanager
from collections.abc import Iterator
import logging
import threading
import time
from typing import Any

from fastapi import HTTPException
from mysql.connector import Error as MySQLError, PoolError, pooling

from app.config import (
    DB_CONNECT_TIMEOUT,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)


_pool: pooling.MySQLConnectionPool | None = None
_pool_lock = threading.Lock()
logger = logging.getLogger(__name__)

POOL_SIZE = 20
POOL_ACQUIRE_RETRIES = 8
POOL_ACQUIRE_DELAY_S = 0.15


def _http_database_error(exc: MySQLError) -> HTTPException:
    """Traduce errores MySQL frecuentes a respuestas HTTP accionables."""
    errno = getattr(exc, "errno", None)
    message = str(exc)

    if errno == 1062:
        return HTTPException(
            status_code=409,
            detail=f"Conflicto: ya existe un recurso con esos datos ({message})",
        )

    if errno in {1451, 1452}:
        return HTTPException(
            status_code=400,
            detail=f"Referencia inválida: el recurso relacionado no existe o está en uso ({message})",
        )

    return HTTPException(status_code=400, detail=f"Error de base de datos: {message}")


def http_database_error(exc: MySQLError) -> HTTPException:
    """Punto de extensión público para repositorios SQL nuevos."""
    return _http_database_error(exc)


def get_pool() -> pooling.MySQLConnectionPool:
    """Inicializa y retorna el pool de conexiones (singleton seguro entre hilos)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pooling.MySQLConnectionPool(
                    pool_name="iot_pool",
                    pool_size=POOL_SIZE,
                    pool_reset_session=True,
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    connection_timeout=DB_CONNECT_TIMEOUT,
                    # Las operaciones independientes se confirman automáticamente.
                    # Las operaciones agrupadas usan transaction(), que desactiva esto.
                    autocommit=True,
                )
    return _pool


def get_connection():
    """Obtiene una conexión del pool esperando brevemente ante picos de carga."""
    pool = get_pool()
    for attempt in range(POOL_ACQUIRE_RETRIES):
        try:
            return pool.get_connection()
        except PoolError:
            if attempt == POOL_ACQUIRE_RETRIES - 1:
                raise
            time.sleep(POOL_ACQUIRE_DELAY_S)


def check_database_connection() -> bool:
    """Comprueba la conectividad real con MySQL ejecutando ``SELECT 1``.

    La conexión siempre se devuelve al pool, incluso si RDS está inaccesible.
    Los errores de autenticación, red y timeout se registran sin propagarse para
    que el endpoint de diagnóstico pueda responder con HTTP 503 sin derribar la
    aplicación.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        return result is not None and result[0] == 1
    except (MySQLError, OSError, TimeoutError) as exc:
        logger.warning("Database health check failed: %s", type(exc).__name__)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def call_procedure(
    proc_name: str,
    args: tuple[Any, ...] = (),
    connection: Any | None = None,
) -> list[dict[str, Any]]:
    """Ejecuta un stored procedure y devuelve sus filas.

    ``connection`` es opcional: cuando se proporciona, el llamador controla el
    commit/rollback. Esto permite encadenar varios SP sin perder atomicidad.
    """
    owns_connection = connection is None
    conn = None
    cursor = None
    try:
        conn = connection or get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.callproc(proc_name, args)

        return _consume_result_sets(cursor)
    except MySQLError as exc:
        raise _http_database_error(exc) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if owns_connection and conn is not None:
            conn.close()


def _consume_result_sets(cursor: Any) -> list[dict[str, Any]]:
    """Drena todos los result sets producidos por ``CALL`` con ``fetchall``."""
    rows: list[dict[str, Any]] = []
    for result in cursor.stored_results():
        rows.extend(result.fetchall())
    return rows


def call_procedure_one(
    proc_name: str,
    args: tuple[Any, ...] = (),
    connection: Any | None = None,
) -> dict[str, Any] | None:
    """Ejecuta un SP y devuelve la primera fila usando ``fetchone``.

    Se utiliza para procedimientos que retornan un escalar, como
    ``SELECT LAST_INSERT_ID() AS id_comando``. Los registros restantes de cada
    result set también se consumen antes de cerrar cursor/conexión.
    """
    owns_connection = connection is None
    conn = None
    cursor = None
    first_row: dict[str, Any] | None = None
    try:
        conn = connection or get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.callproc(proc_name, args)

        for result in cursor.stored_results():
            row = result.fetchone()
            if first_row is None and row is not None:
                first_row = row
            # Drenar cualquier fila restante del mismo result set.
            result.fetchall()
        return first_row
    except MySQLError as exc:
        raise _http_database_error(exc) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if owns_connection and conn is not None:
            conn.close()


@contextmanager
def transaction() -> Iterator[Any]:
    """Entrega una conexión transaccional y hace commit o rollback automático."""
    try:
        conn = get_connection()
    except MySQLError as exc:
        raise _http_database_error(exc) from exc
    previous_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = previous_autocommit
        conn.close()


def call_transactional(procedures: list[tuple[str, tuple[Any, ...]]]) -> None:
    """Ejecuta una lista de SP en una única transacción.

    Si cualquiera falla, todos los cambios de la conexión se revierten.
    """
    with transaction() as conn:
        for proc_name, args in procedures:
            call_procedure(proc_name, args, connection=conn)