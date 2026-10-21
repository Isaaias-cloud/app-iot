# IoT Car API — FastAPI + MySQL

API de la **Práctica 2.5: APIs para IoT en entorno Dev**. Expone CRUD para
vehículos, comandos y demos, consulta de estado e historial, y ejecución HTTP
de demos transmitidas por el WebSocket del vehículo. La lógica de persistencia se mantiene en los 21 stored procedures
existentes; no se modifican sus nombres ni las tablas de `vehiculo_iot`.

## Requisitos

- Python 3.11 o superior.
- MySQL/MariaDB accesible desde el equipo.
- Base de datos `vehiculo_iot` (o el nombre configurado) con las tablas y los
  21 stored procedures de la práctica.

## URL del Swagger UI
- https://api-iot-26.duckdns.org/docs
- http://3.223.103.55:8000/docs

## Dirección pública del web socket
- wss://api-iot-26.duckdns.org/ws/vehiculo/1

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
    ├── demo_execution.py   # Ejecución HTTP de demos
    └── hardware_ws.py      # WebSocket global por vehículo
```

## Documentación de la API

La API tiene 22 endpoints REST de negocio publicados en OpenAPI, el health
check `/` y tres alias de compatibilidad que el código registra pero oculta de
Swagger. También expone un WebSocket global por vehículo. En las rutas con `{id_...}`, los
ejemplos usan el valor `1`; sustitúyelo por el identificador real. Los ejemplos
de respuesta son ilustrativos y muestran la forma definida por los modelos
Pydantic; los valores y las columnas adicionales dependen de los stored
procedures y de los datos de MySQL. Los cuerpos JSON rechazan propiedades que
no estén especificadas.

### Health check

#### Consultar disponibilidad (`GET /`)
- **Descripción:** confirma que la aplicación está activa.
- **Rutas:**
  - Local: `http://localhost:8000/`
  - IP pública: `http://3.223.103.55:8000/`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {
    "status": "ok",
    "version": "2.1.0",
    "message": "IoT Car API lista"
  }
  ```

### Vehículos

#### Crear vehículo (`POST /vehiculos/`)
- **Descripción:** crea un vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/`
  - IP pública: `http://3.223.103.55:8000/vehiculos/`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/`
- **Body:** `nombre`, `modelo` y `microcontrolador` son textos de 1 a 100 caracteres; `descripcion`, de 1 a 500.
  ```json
  {
    "nombre": "Auto IoT",
    "modelo": "Modelo A",
    "descripcion": "Vehículo de prueba",
    "microcontrolador": "ESP32"
  }
  ```
- **Respuesta (201):**
  ```json
  {
    "id_vehiculo": 1,
    "nombre": "Auto IoT",
    "modelo": "Modelo A",
    "descripcion": "Vehículo de prueba",
    "microcontrolador": "ESP32",
    "activo": true
  }
  ```

#### Listar vehículos (`GET /vehiculos/`)
- **Descripción:** devuelve los vehículos registrados.
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/`
  - IP pública: `http://3.223.103.55:8000/vehiculos/`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  [
    {
      "id_vehiculo": 1,
      "nombre": "Auto IoT",
      "modelo": "Modelo A",
      "descripcion": "Vehículo de prueba",
      "microcontrolador": "ESP32",
      "activo": true
    }
  ]
  ```

#### Obtener vehículo (`GET /vehiculos/{id_vehiculo}`)
- **Descripción:** consulta un vehículo por su ID (entero mayor que cero).
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/1`
  - IP pública: `http://3.223.103.55:8000/vehiculos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {
    "id_vehiculo": 1,
    "nombre": "Auto IoT",
    "modelo": "Modelo A",
    "descripcion": "Vehículo de prueba",
    "microcontrolador": "ESP32",
    "activo": true
  }
  ```

#### Actualizar vehículo (`PUT /vehiculos/{id_vehiculo}`)
- **Descripción:** reemplaza los datos editables y el estado activo del vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/1`
  - IP pública: `http://3.223.103.55:8000/vehiculos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/1`
- **Body:** mismos límites de texto que al crear; `activo` es booleano.
  ```json
  {
    "nombre": "Auto IoT",
    "modelo": "Modelo A2",
    "descripcion": "Vehículo actualizado",
    "microcontrolador": "ESP32",
    "activo": true
  }
  ```
- **Respuesta (200):**
  ```json
  {"message": "Operación realizada correctamente", "id": 1}
  ```

#### Eliminar vehículo (`DELETE /vehiculos/{id_vehiculo}`)
- **Descripción:** elimina el vehículo indicado.
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/1`
  - IP pública: `http://3.223.103.55:8000/vehiculos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {"message": "Vehículo eliminado correctamente", "id": 1}
  ```

### Comandos

#### Crear comando (`POST /comandos/`)
- **Descripción:** registra un comando asociado a un vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/comandos/`
  - IP pública: `http://3.223.103.55:8000/comandos/`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/comandos/`
- **Body:** `id_vehiculo` debe ser mayor que cero, `codigo` de 0 a 65535; textos de 1 a 100 (`nombre`) o de 1 a 500 (`descripcion`).
  ```json
  {
    "id_vehiculo": 1,
    "nombre": "Avanzar",
    "codigo": 2,
    "descripcion": "Mover el vehículo hacia adelante"
  }
  ```
- **Respuesta (201):**
  ```json
  {"message": "Comando creado", "id_comando": 2}
  ```

#### Listar comandos de un vehículo (`GET /comandos/vehiculo/{id_vehiculo}`)
- **Descripción:** consulta los comandos asociados al vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/comandos/vehiculo/1`
  - IP pública: `http://3.223.103.55:8000/comandos/vehiculo/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/comandos/vehiculo/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  [
    {
      "id_comando": 2,
      "id_vehiculo": 1,
      "nombre": "Avanzar",
      "codigo": 2,
      "descripcion": "Mover el vehículo hacia adelante",
      "activo": true
    }
  ]
  ```

#### Actualizar comando (`PUT /comandos/{id_comando}`)
- **Descripción:** actualiza nombre, código, descripción y estado activo.
- **Rutas:**
  - Local: `http://localhost:8000/comandos/2`
  - IP pública: `http://3.223.103.55:8000/comandos/2`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/comandos/2`
- **Body:** `codigo` debe estar entre 0 y 65535; `nombre` y `descripcion` son textos no vacíos con máximo de 100 y 500 caracteres, respectivamente.
  ```json
  {
    "nombre": "Avanzar",
    "codigo": 2,
    "descripcion": "Avanzar actualizado",
    "activo": true
  }
  ```
- **Respuesta (200):**
  ```json
  {"message": "Operación realizada correctamente", "id": 2}
  ```

#### Eliminar comando (`DELETE /comandos/{id_comando}`)
- **Descripción:** elimina el comando indicado.
- **Rutas:**
  - Local: `http://localhost:8000/comandos/2`
  - IP pública: `http://3.223.103.55:8000/comandos/2`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/comandos/2`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {"message": "Comando eliminado correctamente", "id": 2}
  ```

### Estado del vehículo

#### Actualizar estado (`PUT /estado/vehiculo/{id_vehiculo}`)
- **Descripción:** establece el comando actual y el estado de conexión del vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/estado/vehiculo/1`
  - IP pública: `http://3.223.103.55:8000/estado/vehiculo/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/estado/vehiculo/1`
- **Body:** `id_comando` debe ser mayor que cero.
  ```json
  {"id_comando": 2, "conectado": true}
  ```
- **Respuesta (200):**
  ```json
  {"message": "Operación realizada correctamente", "id": 1}
  ```

#### Obtener estado (`GET /estado/vehiculo/{id_vehiculo}`)
- **Descripción:** devuelve el estado actual del vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/estado/vehiculo/1`
  - IP pública: `http://3.223.103.55:8000/estado/vehiculo/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/estado/vehiculo/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {
    "id_vehiculo": 1,
    "id_comando": 2,
    "conectado": true,
    "fecha_hora": "2026-10-20T12:30:00"
  }
  ```

### Movimientos e historial

#### Ejecutar comando en vehículo (`POST /vehiculos/{id_vehiculo}/comando`)
- **Descripción:** actualiza el estado y registra el movimiento en el historial dentro de una sola transacción MySQL; si una operación falla, ambas se revierten.
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/1/comando`
  - IP pública: `http://3.223.103.55:8000/vehiculos/1/comando`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/1/comando`
- **Body:** `id_comando` debe ser mayor que cero; `conectado` es booleano; `origen` es texto de 1 a 30 caracteres y, si se omite, vale `MANUAL`.
  ```json
  {
    "id_comando": 2,
    "conectado": true,
    "origen": "API"
  }
  ```
- **Respuesta (201):**
  ```json
  {
    "message": "Comando registrado correctamente",
    "id_vehiculo": 1,
    "id_comando": 2,
    "conectado": true,
    "origen": "API"
  }
  ```

#### Consultar historial (`GET /vehiculos/{id_vehiculo}/historial`)
- **Descripción:** devuelve como máximo los diez movimientos más recientes del vehículo.
- **Rutas:**
  - Local: `http://localhost:8000/vehiculos/1/historial`
  - IP pública: `http://3.223.103.55:8000/vehiculos/1/historial`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/vehiculos/1/historial`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  [
    {
      "id_historial": 10,
      "id_vehiculo": 1,
      "comando": "Avanzar",
      "codigo": 2,
      "id_comando": 2,
      "fecha_hora": "2026-10-20T12:30:00",
      "origen": "API"
    }
  ]
  ```

### Demos

#### Crear demo (`POST /demos/`)
- **Descripción:** crea una demo para el vehículo indicado.
- **Rutas:**
  - Local: `http://localhost:8000/demos/`
  - IP pública: `http://3.223.103.55:8000/demos/`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/`
- **Body:** `id_vehiculo` debe ser mayor que cero; `nombre` y `descripcion` son textos no vacíos, de hasta 100 y 500 caracteres.
  ```json
  {
    "id_vehiculo": 1,
    "nombre": "Recorrido corto",
    "descripcion": "Demostración de avance y giro"
  }
  ```
- **Respuesta (201):**
  ```json
  {
    "id_demo": 1,
    "id_vehiculo": 1,
    "nombre": "Recorrido corto",
    "descripcion": "Demostración de avance y giro",
    "activo": true
  }
  ```

#### Listar demos del vehículo (`GET /demos/vehiculo/{id_vehiculo}`)
- **Descripción:** lista las demos asociadas al vehículo. No existe un `GET /demos/` general.
- **Rutas:**
  - Local: `http://localhost:8000/demos/vehiculo/1`
  - IP pública: `http://3.223.103.55:8000/demos/vehiculo/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/vehiculo/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  [
    {
      "id_demo": 1,
      "id_vehiculo": 1,
      "nombre": "Recorrido corto",
      "descripcion": "Demostración de avance y giro",
      "activo": true
    }
  ]
  ```

#### Actualizar demo (`PUT /demos/{id_demo}`)
- **Descripción:** actualiza nombre, descripción y estado activo de la demo.
- **Rutas:**
  - Local: `http://localhost:8000/demos/1`
  - IP pública: `http://3.223.103.55:8000/demos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/1`
- **Body:** `nombre` y `descripcion` son textos no vacíos, de hasta 100 y 500 caracteres.
  ```json
  {
    "nombre": "Recorrido actualizado",
    "descripcion": "Demo editada",
    "activo": true
  }
  ```
- **Respuesta (200):**
  ```json
  {"message": "Operación realizada correctamente", "id": 1}
  ```

#### Eliminar demo (`DELETE /demos/{id_demo}`)
- **Descripción:** elimina la demo indicada.
- **Rutas:**
  - Local: `http://localhost:8000/demos/1`
  - IP pública: `http://3.223.103.55:8000/demos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {"message": "Demo eliminada correctamente", "id": 1}
  ```

#### Agregar movimiento a una demo (`POST /demos/movimiento`)
- **Descripción:** agrega un comando ordenado a la secuencia de la demo.
- **Rutas:**
  - Local: `http://localhost:8000/demos/movimiento`
  - IP pública: `http://3.223.103.55:8000/demos/movimiento`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/movimiento`
- **Body:** ambos IDs deben ser mayores que cero; `orden` debe ser al menos 1; `duracion_ms` y `pausa_ms` aceptan enteros de 0 a 86 400 000.
  ```json
  {
    "id_demo": 1,
    "id_comando": 2,
    "orden": 1,
    "duracion_ms": 1000,
    "pausa_ms": 250
  }
  ```
- **Respuesta (201):**
  ```json
  {
    "id_demo_movimiento": 1,
    "id_demo": 1,
    "orden": 1,
    "id_comando": 2,
    "comando": "Avanzar",
    "codigo": 2,
    "duracion_ms": 1000,
    "pausa_ms": 250
  }
  ```

#### Listar movimientos de una demo (`GET /demos/{id_demo}/movimientos`)
- **Descripción:** devuelve los pasos programados para la demo.
- **Rutas:**
  - Local: `http://localhost:8000/demos/1/movimientos`
  - IP pública: `http://3.223.103.55:8000/demos/1/movimientos`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/1/movimientos`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  [
    {
      "id_demo_movimiento": 1,
      "id_demo": 1,
      "orden": 1,
      "id_comando": 2,
      "comando": "Avanzar",
      "codigo": 2,
      "duracion_ms": 1000,
      "pausa_ms": 250
    }
  ]
  ```

#### Actualizar movimiento de demo (`PUT /demos/movimiento/{id_demo_movimiento}`)
- **Descripción:** cambia comando, orden, duración y pausa de un paso existente.
- **Rutas:**
  - Local: `http://localhost:8000/demos/movimiento/1`
  - IP pública: `http://3.223.103.55:8000/demos/movimiento/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/movimiento/1`
- **Body:** `id_comando` debe ser mayor que cero; `orden` al menos 1; los tiempos, enteros de 0 a 86 400 000. No se envía `id_demo`.
  ```json
  {
    "id_comando": 2,
    "orden": 1,
    "duracion_ms": 1200,
    "pausa_ms": 300
  }
  ```
- **Respuesta (200):**
  ```json
  {"message": "Operación realizada correctamente", "id": 1}
  ```

#### Eliminar movimiento de demo (`DELETE /demos/movimientos/{id_demo_movimiento}`)
- **Descripción:** elimina el paso indicado de la demo.
- **Rutas:**
  - Local: `http://localhost:8000/demos/movimientos/1`
  - IP pública: `http://3.223.103.55:8000/demos/movimientos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/movimientos/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {"message": "Movimiento de demo eliminado correctamente", "id": 1}
  ```

#### Ejecutar demo (`POST /demos/ejecutar`)
- **Descripción:** obtiene los movimientos con `sp_obtener_movimientos_demo`, los ordena por `orden`, los transmite al WebSocket global del vehículo y actualiza el estado con `sp_actualizar_estado`. No registra historial.
- **Rutas:**
  - Local: `http://localhost:8000/demos/ejecutar`
  - IP pública: `http://3.223.103.55:8000/demos/ejecutar`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/ejecutar`
- **Body:** `id_demo` es obligatorio; `id_vehiculo` puede omitirse si el procedimiento devuelve ese dato. El vehículo debe tener activa su conexión `WS /ws/vehiculo/{id_vehiculo}`.
  ```json
  {"id_demo": 1, "id_vehiculo": 1}
  ```
- **Respuesta (200):**
  ```json
  {
    "message": "Ejecución de DEMO completada correctamente",
    "id_demo": 1,
    "id_vehiculo": 1,
    "total_movimientos": 2,
    "movimientos_ejecutados": 2
  }
  ```
- Cada evento `movimiento` enviado al vehículo contiene el comando, código, orden, `duracion_ms` y `pausa_ms`. La API espera la duración de cada paso y la pausa configurada entre pasos antes de completar la petición.

### Alias de compatibilidad

Estas rutas funcionan, pero están marcadas `include_in_schema=False` y por eso
no aparecen en Swagger. Sus respuestas y cuerpos son los mismos que los de la
ruta principal indicada.

#### Agregar movimiento (`POST /demos/movimientos`)
- **Descripción:** alias de compatibilidad para agregar un comando a una demo.
- **Rutas:**
  - Local: `http://localhost:8000/demos/movimientos`
  - IP pública: `http://3.223.103.55:8000/demos/movimientos`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/movimientos`
- **Body:**
  ```json
  {
    "id_demo": 1,
    "id_comando": 2,
    "orden": 1,
    "duracion_ms": 1000,
    "pausa_ms": 250
  }
  ```
- **Respuesta (201):**
  ```json
  {
    "id_demo_movimiento": 1,
    "id_demo": 1,
    "orden": 1,
    "id_comando": 2,
    "comando": "Avanzar",
    "codigo": 2,
    "duracion_ms": 1000,
    "pausa_ms": 250
  }
  ```

#### Actualizar movimiento (`PUT /demos/movimientos/{id_demo_movimiento}`)
- **Descripción:** alias de compatibilidad para actualizar el movimiento indicado.
- **Rutas:**
  - Local: `http://localhost:8000/demos/movimientos/1`
  - IP pública: `http://3.223.103.55:8000/demos/movimientos/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/movimientos/1`
- **Body:**
  ```json
  {
    "id_comando": 2,
    "orden": 1,
    "duracion_ms": 1200,
    "pausa_ms": 300
  }
  ```
- **Respuesta (200):**
  ```json
  {"message": "Operación realizada correctamente", "id": 1}
  ```

#### Eliminar movimiento (`DELETE /demos/movimiento/{id_demo_movimiento}`)
- **Descripción:** alias de compatibilidad para eliminar el movimiento indicado.
- **Rutas:**
  - Local: `http://localhost:8000/demos/movimiento/1`
  - IP pública: `http://3.223.103.55:8000/demos/movimiento/1`
  - Dominio (HTTPS): `https://api-iot-26.duckdns.org/demos/movimiento/1`
- **Body:** No aplica.
- **Respuesta (200):**
  ```json
  {"message": "Movimiento de demo eliminado correctamente", "id": 1}
  ```

### WebSockets

Los WebSockets no usan un método HTTP de aplicación ni cuerpo HTTP JSON: se
establece la conexión y luego se intercambian mensajes JSON. Para la IP se usa
`ws://`; el dominio HTTPS requiere `wss://`.

#### Monitorear vehículo (`WS /ws/vehiculo/{id_vehiculo}`)
- **Descripción:** envía el estado actual al conectar y notifica nuevos movimientos registrados para ese vehículo.
- **Rutas:**
  - Local: `ws://localhost:8000/ws/vehiculo/1`
  - IP pública: `ws://3.223.103.55:8000/ws/vehiculo/1`
  - Dominio seguro: `wss://api-iot-26.duckdns.org/ws/vehiculo/1`
- **Mensaje del cliente:** no se requiere un mensaje de aplicación; la conexión queda abierta para recibir eventos.
- **Ejemplo de evento inicial:**
  ```json
  {
    "event": "estado_actual",
    "id_vehiculo": 1,
    "estado": {
      "id_vehiculo": 1,
      "id_comando": 2,
      "conectado": true,
      "fecha_hora": "2026-10-20T12:30:00"
    }
  }
  ```
- **Ejemplo de evento de movimiento:**
  ```json
  {
    "event": "nuevo_movimiento",
    "id_vehiculo": 1,
    "id_comando": 2,
    "conectado": true,
    "origen": "API",
    "timestamp": "2026-10-20T18:30:00+00:00"
  }
  ```

#### Evento de demo enviado por este canal
La ejecución se inicia mediante `POST /demos/ejecutar`; cada movimiento se
transmite a las conexiones del vehículo por este WebSocket:

```json
{
  "event": "nuevo_movimiento",
  "id_demo": 1,
  "id_vehiculo": 1,
  "paso": 1,
  "total": 2,
  "orden": 1,
  "id_comando": 2,
  "comando": "Avanzar",
  "codigo": 2,
  "conectado": true,
  "origen": "DEMO",
  "duracion_ms": 1000,
  "pausa_ms": 250
}
```

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

### 3. Ejecución HTTP de DEMO

Conecta el vehículo a `ws://localhost:8000/ws/vehiculo/1` y envía:

```http
POST http://localhost:8000/demos/ejecutar
Content-Type: application/json
```

```json
{"id_demo": 1, "id_vehiculo": 1}
```

Si `sp_obtener_movimientos_demo` devuelve `id_vehiculo`, ese campo del cuerpo
puede omitirse. La API transmite cada movimiento en orden por el WebSocket del
vehículo, ejecuta `sp_actualizar_estado` por paso y respeta `duracion_ms` y
`pausa_ms` entre movimientos. No ejecuta `sp_registrar_historial`, por lo que
la DEMO no agrega registros al historial de comandos.

## Comprobaciones rápidas

```powershell
python -m compileall app
python -c "from app.main import app; print(len(app.routes), 'rutas cargadas')"
```

La comprobación de endpoints que requieren MySQL debe ejecutarse con la base
de datos y los stored procedures disponibles.
