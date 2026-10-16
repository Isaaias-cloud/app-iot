"""Servicios de dominio para encapsular el uso de stored procedures.

Los routers solo traducen HTTP/WebSocket a operaciones de dominio. Las clases
de este módulo centralizan los nombres y argumentos de los 21 procedimientos,
lo que evita duplicar SQL o detalles de conexión entre endpoints.
"""

from typing import Any

from fastapi import HTTPException

from app.database import call_procedure, call_procedure_one, call_transactional


def _require_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convierte una consulta sin resultados en un 404 consistente."""
    if not rows:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return rows


class ProcedureService:
    """Fachada base para consultas y comandos almacenados."""

    @staticmethod
    def fetch(proc_name: str, *args: Any) -> list[dict[str, Any]]:
        return call_procedure(proc_name, tuple(args))

    @staticmethod
    def execute(proc_name: str, *args: Any) -> list[dict[str, Any]]:
        return call_procedure(proc_name, tuple(args))


class VehicleService(ProcedureService):
    def create(
        self,
        nombre: str,
        modelo: str,
        descripcion: str,
        microcontrolador: str,
    ) -> list[dict[str, Any]]:
        return self.execute(
            "sp_crear_vehiculo",
            nombre,
            modelo,
            descripcion,
            microcontrolador,
        )

    def list(self) -> list[dict[str, Any]]:
        return self.fetch("sp_obtener_vehiculos")

    def get(self, id_vehiculo: int) -> list[dict[str, Any]]:
        return _require_rows(self.fetch("sp_obtener_vehiculo", id_vehiculo))

    def update(
        self,
        id_vehiculo: int,
        nombre: str,
        modelo: str,
        descripcion: str,
        microcontrolador: str,
        activo: bool,
    ) -> None:
        self.execute(
            "sp_actualizar_vehiculo",
            id_vehiculo,
            nombre,
            modelo,
            descripcion,
            microcontrolador,
            activo,
        )

    def delete(self, id_vehiculo: int) -> None:
        self.execute("sp_eliminar_vehiculo", id_vehiculo)


class CommandService(ProcedureService):
    def create(
        self,
        id_vehiculo: int,
        nombre: str,
        codigo: int,
        descripcion: str,
    ) -> int:
        row = call_procedure_one(
            "sp_crear_comando",
            (id_vehiculo, nombre, codigo, descripcion),
        )
        if row is None:
            raise HTTPException(
                status_code=500,
                detail="sp_crear_comando no devolvió id_comando",
            )

        id_comando = row.get("id_comando")
        if id_comando is None:
            id_comando = row.get("LAST_INSERT_ID()")
        if id_comando is None:
            raise HTTPException(
                status_code=500,
                detail="El resultado de sp_crear_comando no contiene id_comando",
            )
        return int(id_comando)

    def list_for_vehicle(self, id_vehiculo: int) -> list[dict[str, Any]]:
        return self.fetch("sp_obtener_comandos_vehiculo", id_vehiculo)

    def update(
        self,
        id_comando: int,
        nombre: str,
        codigo: int,
        descripcion: str,
        activo: bool,
    ) -> None:
        self.execute(
            "sp_actualizar_comando",
            id_comando,
            nombre,
            codigo,
            descripcion,
            activo,
        )

    def delete(self, id_comando: int) -> None:
        self.execute("sp_eliminar_comando", id_comando)


class StateService(ProcedureService):
    def update(
        self,
        id_vehiculo: int,
        id_comando: int,
        conectado: bool,
    ) -> None:
        self.execute("sp_actualizar_estado", id_vehiculo, id_comando, conectado)

    def get(self, id_vehiculo: int) -> list[dict[str, Any]]:
        return _require_rows(self.fetch("sp_obtener_estado", id_vehiculo))


class HistoryService(ProcedureService):
    def send_command_transactionally(
        self,
        id_vehiculo: int,
        id_comando: int,
        conectado: bool,
        origen: str,
    ) -> None:
        call_transactional(
            [
                ("sp_actualizar_estado", (id_vehiculo, id_comando, conectado)),
                ("sp_registrar_historial", (id_vehiculo, id_comando, origen)),
            ]
        )

    def list(self, id_vehiculo: int, limit: int = 10) -> list[dict[str, Any]]:
        # El SP retorna DESC; el recorte conserva exactamente los 10 más recientes.
        return _require_rows(self.fetch("sp_obtener_historial", id_vehiculo))[:limit]


class DemoService(ProcedureService):
    def create(self, id_vehiculo: int, nombre: str, descripcion: str) -> list[dict[str, Any]]:
        return self.execute("sp_crear_demo", id_vehiculo, nombre, descripcion)

    def list_for_vehicle(self, id_vehiculo: int) -> list[dict[str, Any]]:
        return _require_rows(self.fetch("sp_obtener_demos", id_vehiculo))

    def update(
        self,
        id_demo: int,
        nombre: str,
        descripcion: str,
        activo: bool,
    ) -> None:
        self.execute("sp_actualizar_demo", id_demo, nombre, descripcion, activo)

    def delete(self, id_demo: int) -> None:
        self.execute("sp_eliminar_demo", id_demo)

    def add_movement(
        self,
        id_demo: int,
        id_comando: int,
        orden: int,
        duracion_ms: int,
        pausa_ms: int,
    ) -> list[dict[str, Any]]:
        return self.execute(
            "sp_agregar_movimiento_demo",
            id_demo,
            id_comando,
            orden,
            duracion_ms,
            pausa_ms,
        )

    def list_movements(self, id_demo: int) -> list[dict[str, Any]]:
        return _require_rows(self.fetch("sp_obtener_movimientos_demo", id_demo))

    def update_movement(
        self,
        id_demo_movimiento: int,
        id_comando: int,
        orden: int,
        duracion_ms: int,
        pausa_ms: int,
    ) -> None:
        self.execute(
            "sp_actualizar_movimiento_demo",
            id_demo_movimiento,
            id_comando,
            orden,
            duracion_ms,
            pausa_ms,
        )

    def delete_movement(self, id_demo_movimiento: int) -> None:
        self.execute("sp_eliminar_movimiento_demo", id_demo_movimiento)
