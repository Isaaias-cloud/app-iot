# IoT Car API — FastAPI + MySQL

API local para IoT con **3 integraciones** según las pruebas funcionales requeridas.

---

## Configuración de la Base de Datos

Edita el archivo `.env` (copia de `.env.example`) con tus datos reales:

```env
DB_HOST=localhost        # Host de MySQL (normalmente localhost)
DB_PORT=3306             # Puerto MySQL
DB_USER=root             # Tu usuario MySQL
DB_PASSWORD=             # Tu contraseña MySQL
DB_NAME=                 # ← FALTA: nombre de tu base de datos IoT
```

> **⚠️ Dato faltante:** el nombre de la base de datos (`DB_NAME`). Indícalo para completar la configuración.

---

## Estructura del proyecto

```
python-apis/
├── app/
│   ├── main.py               # FastAPI app principal
│   ├── config.py             # Variables de entorno
│   ├── database.py           # Pool MySQL + call_procedure()
│   ├── schemas.py            # Modelos Pydantic v2
│   └── routers/
│       ├── movimientos.py    # Prueba 1 (POST) + Prueba 2 (GET)
│       └── demo_ws.py        # Prueba 3 (WebSocket)
├── sql/
│   └── sp_faltante.sql       # Nota: sp_obtener_historial ya existe
├── test_ws_demo.py           # Cliente WS de prueba (CLI)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Arrancar el servidor

```bash
# 1. Copiar y editar .env
copy .env.example .env
# Editar DB_NAME y DB_PASSWORD

# 2. Levantar el servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentación interactiva: **http://localhost:8000/docs**

---

## Las 3 APIs

### Prueba 1 — POST `/vehiculos/{id_vehiculo}/comando`

Registra un movimiento individual. Llama a **dos** stored procedures:
1. `sp_actualizar_estado` → persiste en `estado_vehiculo`
2. `sp_registrar_historial` → inserta en `historial_comandos`

**Thunder Client:**
- Method: `POST`
- URL: `http://localhost:8000/vehiculos/1/comando`
- Body (JSON):
```json
{
  "id_comando": 2,
  "conectado": true,
  "origen": "api"
}
```
- Respuesta esperada (201):
```json
{
  "message": "Comando registrado correctamente",
  "id_vehiculo": 1,
  "id_comando": 2,
  "conectado": true,
  "origen": "api"
}
```

---

### Prueba 2 — GET `/vehiculos/{id_vehiculo}/historial`

Retorna los **últimos 10 movimientos** del vehículo usando `sp_obtener_historial`.
El SP ya ordena `DESC` — Python recorta a `[:10]` (no hay LIMIT en el SP).

**Thunder Client:**
- Method: `GET`
- URL: `http://localhost:8000/vehiculos/1/historial`

**Cómo verificar el límite:**
- Si hay > 10 registros en BD → el JSON devuelve exactamente 10
- Si hay < 10 registros → devuelve solo los disponibles

---

### Prueba 3 — WebSocket `/ws/demo`

Ejecuta una demo paso a paso **sin registrar historial**.

**Thunder Client (WebSocket):**
1. Conectar a: `ws://localhost:8000/ws/demo`
2. Enviar mensaje de inicio:
```json
{"action": "start", "id_demo": 1}
```

**Eventos que recibirás:**
| Evento | Descripción |
|--------|-------------|
| `demo_start` | Demo iniciada — incluye `total` de pasos |
| `movimiento` | Cada paso con `orden`, `comando`, `codigo`, `duracion_ms`, `pausa_ms` |
| `done` | Demo completada |

**Para detener a mitad:**
```json
{"action": "stop"}
```

> **⚠️ Sin historial:** el WebSocket NO llama a `sp_registrar_historial`.
> Verifica antes y después: `historial_comandos` no cambia durante la demo.

---

## Datos que debes configurar antes de las pruebas

| Variable | Valor necesario |
|----------|----------------|
| `DB_NAME` | Nombre de tu base de datos (p.ej. `iot_vehiculos`) |
| `DB_PASSWORD` | Tu contraseña de MySQL |
| `DB_USER` | Tu usuario MySQL (default: `root`) |
| Datos de prueba | Un `id_vehiculo` válido en tabla `vehiculos` |
| Datos de prueba | Un `id_comando` válido en tabla `comandos` |
| Datos de prueba | Un `id_demo` con movimientos en `demo_movimientos` |
