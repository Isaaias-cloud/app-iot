# IoT Car API — FastAPI + MySQL

API de la **Práctica 2.5: APIs para IoT en entorno Dev**. Expone CRUD para
vehículos, comandos y demos, consulta de estado e historial, y una demo por
WebSocket. La lógica de persistencia se mantiene en los 21 stored procedures
existentes; no se modifican sus nombres ni las tablas de `vehiculo_iot`.

## Requisitos

- Python 3.11 o superior.
- MySQL/MariaDB accesible desde el equipo.
- Base de datos `vehiculo_iot` (o el nombre configurado) con las tablas y los
  21 stored procedures de la práctica.

## Configuración y ejecución local

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` y `DB_NAME`.
`APP_HOST` y `APP_PORT` controlan el servidor; también puedes pasarlos a
Uvicorn directamente.

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La documentación OpenAPI está disponible en
<http://localhost:8000/docs> y el health check en
<http://localhost:8000/>.

## Organización

```text
app/
├── main.py                 # Aplicación y registro de routers
├── config.py               # Variables de entorno
├── database.py             # Pool, llamadas a SP y transacciones
├── services.py             # Servicios orientados a dominio
├── schemas.py              # Modelos Pydantic v2
└── routers/
    ├── vehiculos.py        # sp_crear/obtener/actualizar/eliminar_vehiculo
    ├── comandos.py         # sp_crear/obtener/actualizar/eliminar_comando
    ├── estado.py           # sp_actualizar_estado y sp_obtener_estado
    ├── movimientos.py      # Pruebas 1 y 2
    ├── demos.py            # Demos y movimientos de demo
    └── demo_ws.py          # Prueba 3 por WebSocket
```

## Endpoints REST

| Área | Endpoints |
|---|---|
| Vehículos | `POST/GET /vehiculos/`, `GET/PUT/DELETE /vehiculos/{id_vehiculo}` |
| Comandos | `POST /comandos/`, `GET /comandos/vehiculo/{id_vehiculo}`, `PUT/DELETE /comandos/{id_comando}` |
| Estado | `PUT/GET /estado/vehiculo/{id_vehiculo}` |
| Historial | `POST /vehiculos/{id_vehiculo}/comando`, `GET /vehiculos/{id_vehiculo}/historial` |
| Demos | `POST/GET /demos/`, `PUT/DELETE /demos/{id_demo}`, `/demos/movimiento` y `/demos/{id_demo}/movimientos` |

Los cuerpos exactos y las respuestas están documentados en Swagger. Los
tiempos `duracion_ms` y `pausa_ms` deben ser enteros no negativos.

Los cuerpos de escritura coinciden con los parámetros de los procedimientos:

- Vehículo: `nombre`, `modelo`, `descripcion`, `microcontrolador`; en PUT se agrega `activo`.
- Comando: en POST `id_vehiculo`, `nombre`, `codigo`, `descripcion`; en PUT `nombre`, `codigo`, `descripcion`, `activo`.
- Demo: en POST `id_vehiculo`, `nombre`, `descripcion`; en PUT `nombre`, `descripcion`, `activo`.
- Movimiento demo: `id_demo`, `id_comando`, `orden`, `duracion_ms`, `pausa_ms`; en PUT se omite `id_demo`.

## Guía de las tres pruebas funcionales

### 1. Movimiento individual y transacción

```http
POST http://localhost:8000/vehiculos/1/comando
Content-Type: application/json
```

```json
{"id_comando": 2, "conectado": true, "origen": "API"}
```

El endpoint ejecuta `sp_actualizar_estado` y
`sp_registrar_historial` en la misma transacción MySQL. Si el segundo SP
falla, el cambio de estado también se revierte.

### 2. Historial limitado

```http
GET http://localhost:8000/vehiculos/1/historial
```

Se ejecuta `sp_obtener_historial`, que debe devolver los registros más nuevos
primero. La API conserva únicamente `rows[:10]`, por lo que la respuesta nunca
contiene más de 10 movimientos.

### 3. Demo por WebSocket

Conecta a `ws://localhost:8000/ws/demo` y envía:

```json
{"action":"start", "id_demo":1, "id_vehiculo":1}
```

Si `sp_obtener_movimientos_demo` ya devuelve `id_vehiculo`, el campo del
mensaje puede omitirse. El servidor ordena por `orden`, actualiza el estado con
`sp_actualizar_estado` antes de emitir cada movimiento, respeta
`duracion_ms` y `pausa_ms`, y envía `done` al finalizar. Nunca ejecuta
`sp_registrar_historial`, por lo que el historial no cambia durante la demo.

Eventos principales:

- `demo_start`: contiene `id_demo` y el total de pasos.
- `movimiento`: contiene paso, orden, comando, código y tiempos.
- `done`: demo completada.
- `stopped`: reproducción cancelada después de `{"action":"stop"}`.

## Comprobaciones rápidas

```powershell
python -m compileall app
python -c "from app.main import app; print(len(app.routes), 'rutas cargadas')"
```

La comprobación de endpoints que requieren MySQL debe ejecutarse con la base
de datos y los stored procedures disponibles.
