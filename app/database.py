"""
Módulo de conexión a base de datos MySQL/MariaDB.
Usa mysql-connector-python para llamar stored procedures.
"""

import mysql.connector
from mysql.connector import pooling
from app.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Pool de conexiones para mejor rendimiento
_pool: pooling.MySQLConnectionPool | None = None


def get_pool() -> pooling.MySQLConnectionPool:
    """Inicializa y retorna el pool de conexiones (singleton)."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="iot_pool",
            pool_size=5,
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True,
        )
    return _pool


def get_connection():
    """Obtiene una conexión del pool."""
    return get_pool().get_connection()


def call_procedure(proc_name: str, args: tuple = ()):
    """
    Ejecuta un stored procedure y retorna todas las filas del primer result set.

    Args:
        proc_name: Nombre del stored procedure.
        args: Tupla de argumentos posicionales.

    Returns:
        Lista de diccionarios con los resultados.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.callproc(proc_name, args)
        results = []
        for result in cursor.stored_results():
            results = result.fetchall()
        cursor.close()
        return results
    finally:
        conn.close()

