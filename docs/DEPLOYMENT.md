# Etapa 8 — Despliegue seguro y hardware

Este runbook asume Ubuntu en EC2, el backend en
`/opt/vehiculo-iot/python-apis`, un usuario de servicio `iot-api` y un servicio
systemd llamado `vehiculo-iot.service`. Ajusta únicamente esas rutas si la
instalación existente usa otros nombres.

## 1. Preparar tokens de dispositivo

Genera un secreto independiente por vehículo. No lo escribas en el repositorio,
logs, comandos compartidos ni el frontend:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

En el `.env` privado de producción del backend:

```dotenv
DEVICE_TOKENS={"1":"<secreto-generado-para-el-vehiculo-1>"}
```

Protege el archivo:

```bash
sudo chown iot-api:iot-api /opt/vehiculo-iot/python-apis/.env
sudo chmod 600 /opt/vehiculo-iot/python-apis/.env
```

El token no tiene expiración de JWT, pero solo es válido para el
`id_vehiculo` configurado. Para rotarlo, cambia el valor en EC2 y en el secreto
local del dispositivo, reinicia el servicio y reconecta el hardware.

## 2. Actualizar el backend en EC2

```bash
cd /opt/vehiculo-iot/python-apis
git status --short
git fetch origin
git pull --ff-only origin main
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m compileall -q app
python -m pytest -q
sudo systemctl daemon-reload
sudo systemctl restart vehiculo-iot.service
sudo systemctl --no-pager --full status vehiculo-iot.service
```

La unidad systemd debe cargar el `.env` privado y no incluir secretos literales.
Ejemplo de `/etc/systemd/system/vehiculo-iot.service`:

```ini
[Unit]
Description=Vehiculo IoT FastAPI
After=network-online.target
Wants=network-online.target

[Service]
User=iot-api
Group=iot-api
WorkingDirectory=/opt/vehiculo-iot/python-apis
EnvironmentFile=/opt/vehiculo-iot/python-apis/.env
ExecStart=/opt/vehiculo-iot/python-apis/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Después de modificar la unidad:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vehiculo-iot.service
```

## 3. Verificación de producción

```bash
curl --fail-with-body https://api-iot-26.duckdns.org/health/db
curl --fail-with-body -I https://api-iot-26.duckdns.org/docs
sudo journalctl -u vehiculo-iot.service -n 100 --no-pager
```

`/health/db` debe responder con estado saludable y `/docs` debe estar publicado
por HTTPS. Nunca pegues el contenido de `.env` en tickets o logs.

## 4. Frontend en GitHub Pages

El frontend detecta automáticamente producción cuando no está en
`localhost`/`127.0.0.1`. En producción usa:

```text
REST: https://api-iot-26.duckdns.org
WSS:  wss://api-iot-26.duckdns.org
```

Para validar localmente se conserva `?env=local`, que usa
`http://127.0.0.1:8000` y `ws://127.0.0.1:8000`.

Publicación desde el repositorio de frontend:

```bash
cd front-end
git status --short
git add -A
git commit -m "Deploy frontend seguro de Etapa 8"
git push origin main
```

En GitHub, configura Pages para publicar la rama/directorio que corresponda al
repositorio. Luego comprueba:

```text
https://isaaias-cloud.github.io/carrito-iot-control/
```

El backend debe mantener en `CORS_ORIGINS` el origen exacto
`https://isaaias-cloud.github.io`.

## 5. Firmware ESP8266/ESP32

Este repositorio no contiene `.ino`, `.cpp` ni `platformio.ini`. El contrato
mínimo de conexión para un firmware externo es:

```cpp
#include <WebSocketsClient.h>
#include "secrets.h" // archivo local, excluido de Git

WebSocketsClient socket;

void setupSocket() {
  String path = "/ws/vehiculo/1?device_token=" + String(DEVICE_TOKEN_VEHICULO_1);
  socket.beginSSL("api-iot-26.duckdns.org", 443, path.c_str());
  socket.onEvent(onWebSocketEvent);
}

void loop() {
  socket.loop();
}
```

`secrets.h` debe existir únicamente en la máquina de compilación y contener el
token del vehículo correspondiente. El firmware debe conservar su lógica actual
de pines, motores, pala y la prioridad física de `codigo = 0` (`DETENER`). El
servidor entrega comandos al socket `DISPOSITIVO`; la telemetría JSON enviada
por el dispositivo se difunde únicamente a los clientes autorizados del mismo
vehículo, por ejemplo:

```json
{"event":"telemetria","id_vehiculo":1,"bateria":93,"conectado":true}
```

## 6. Prueba física supervisada — vehículo 1

1. Configura el token de vehículo 1 en EC2 y en el firmware fuera de Git.
2. Reinicia el backend y confirma `/health/db` y `/docs`.
3. Conecta el ESP8266/ESP32 a:
   `wss://api-iot-26.duckdns.org/ws/vehiculo/1?device_token=<token>`.
4. Confirma que el handshake se acepta y que el dispositivo aparece separado
   del cliente web en el canal del vehículo 1.
5. Desde CONTROL, prueba primero `DETENER` (`codigo = 0`), después un movimiento
   breve y finalmente otra vez `DETENER`, bajo supervisión presencial.
6. Envía telemetría con `id_vehiculo = 1` y confirma que llega al cliente del
   vehículo 1, pero no al cliente del vehículo 2.
7. Prueba el token de vehículo 1 contra `/ws/vehiculo/2`; debe rechazarse con
   `403`. Cierra el hardware y verifica el evento `DEVICE_DISCONNECTED` en
   `auditoria` mediante el panel administrativo o una consulta autorizada.

## 7. Rollback seguro

El rollback debe conservar el respaldo y evitar `git reset --hard` sobre cambios
locales no auditados:

```bash
cd /opt/vehiculo-iot/python-apis
git log --oneline -5
git revert <commit-de-despliegue-con-problemas>
git push origin main
git pull --ff-only origin main
. .venv/bin/activate
python -m pip install -r requirements.txt
sudo systemctl restart vehiculo-iot.service
curl --fail-with-body https://api-iot-26.duckdns.org/health/db
```

Para frontend, revierte el commit publicado en su repositorio y vuelve a
publicar Pages:

```bash
cd front-end
git revert <commit-de-frontend-con-problemas>
git push origin main
```

Si el problema es un token, no reviertas código: rota únicamente el secreto en
EC2 y en el dispositivo, reinicia el servicio y repite la prueba supervisada.
