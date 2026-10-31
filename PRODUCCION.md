# Weavers FBA — producción

Única guía de operación del panel. Reemplaza a `PRODUCTION.md` e `IMPLEMENTACION_PRODUCCION.md` (OIDC y Caddy ya no se usan).

## Dónde corre

| | |
|---|---|
| URL | https://fba.weaversnodes.org (Cloudflare → Traefik del servidor 163) |
| Servidor | `ubuntu@163.245.207.38 -p 1600`, código en `/home/ubuntu/weaverslogistic` |
| Datos vivos | `/home/ubuntu/weaverslogistic-data` (fuera del checkout; `WEAVERS_DATA_PATH` en `.env`) |
| Contenedores | `weaverslogistic-app` (Streamlit), `weaverslogistic-db` (Postgres 17), `worker` (solo para el escaneo) |
| Compose | `docker-compose.traefik.yml` |
| TLS | Let's Encrypt (httpChallenge) vía `loadbalancer-traefik`; renovación automática |
| Monitoreo | blackbox de `/home/ubuntu/monitoring` sondea `/_stcore/health` (Grafana) |

`docker-compose.prod.yml` + `deploy/Caddyfile` quedan como alternativa para un servidor sin Traefik.

## Secretos (solo en el servidor)

- `.env` (0600): `APP_DOMAIN`, `WEAVERS_DATA_PATH`, `WEAVERS_SESSION_SECRET`, `POSTGRES_PASSWORD`, `KEEPA_API_KEY`,
  `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `SP_API_REFRESH_TOKEN`, `SP_API_SELLER_ID`.
- `secrets/users.txt` (0640): un usuario por línea, `usuario hash-scrypt [totp:secreto]`.
- `secrets/github_token` (opcional): token de solo lectura si el repo es privado (lo usa `deploy/update.sh`).

## Usuarios y acceso

```bash
cd /home/ubuntu/weaverslogistic
# alta o cambio de contraseña (sin reinicio)
docker run --rm -it -v "$PWD/secrets:/s" --user 1000 weaverslogistic-app \
  python -m scripts.add_user /s/users.txt correo@dominio.com --generate
# lo mismo + 2FA: imprime el enlace otpauth:// para Google Authenticator / 1Password
docker run --rm -it -v "$PWD/secrets:/s" --user 1000 weaverslogistic-app \
  python -m scripts.add_user /s/users.txt correo@dominio.com --generate --totp
```

- Sesión: cookie firmada (HMAC) de 12 h. Cambiar la contraseña invalida las sesiones de ese usuario;
  el botón **En todos** (barra lateral) cierra la sesión en todos los dispositivos.
- Bloqueo de 15 min tras 5 intentos fallidos por usuario o IP (en memoria: se reinicia con el contenedor).
- Auditoría: tabla `auth_events` en Postgres; los últimos 50 accesos se ven en **Ajustes**.

## Tareas programadas (`deploy/crontab.txt`)

| Hora (UTC) | Script | Qué hace |
|---|---|---|
| cada hora :17 | `deploy/update.sh` | Si hay commits nuevos en `main` con CI verde (Pruebas + Imagen Docker): pull, build, prueba de humo contra la URL pública; si falla, vuelve al commit anterior. Log: `~/backups/weaverslogistic/update.log` |
| 14:00 | `deploy/discover.sh` | Escaneo diario de Google Trends + ranking en el contenedor `worker`. Log: `<datos>/discovery_log.txt` |
| 07:40 | `deploy/backup.sh` | `pg_dump` + datos + secretos en `~/backups/weaverslogistic`, 14 días, con verificación de lectura |

Instalar: `(crontab -l; cat deploy/crontab.txt) | crontab -`.

La tarea de Windows "Weavers FBA Discovery" (`scripts/run_discover.cmd`) queda **desactivada**: el servidor es la fuente
de los datos. Si se vuelve a activar, sus commits a `data/` ya no llegan al panel.

## Respaldos

En el servidor: `~/backups/weaverslogistic/db-AAAA-MM-DD.dump` y `files-AAAA-MM-DD.tgz`.
Copia fuera del servidor: la tarea de Windows "Weavers Backup Pull" (`deploy/pull_backups.ps1`) trae cada día el último
juego a `C:\jfmcs\backups\weaverslogistic` (corre cuando esa PC está encendida).

Restaurar:
```bash
docker compose -f docker-compose.traefik.yml exec -T db pg_restore -U weavers -d weavers --clean < db-FECHA.dump
tar xzf files-FECHA.tgz -C /tmp/restore   # copiar weaverslogistic-data/ y secrets/ a su lugar
```

## Despliegue manual

```bash
cd /home/ubuntu/weaverslogistic
git pull --ff-only
docker compose -f docker-compose.traefik.yml up -d --build app
```

## Dependencias

`requirements.txt` declara lo que usa el código; `requirements.lock` fija todas las versiones que se instalan en la
imagen (la base `python:3.14-slim` también va fijada por digest en el `Dockerfile`). Dependabot abre PRs semanales.
Regenerar el lock tras cambiar `requirements.txt`:
```bash
docker run --rm -v "$PWD/requirements.txt:/r.txt:ro" python:3.14-slim \
  sh -c "pip install -q -r /r.txt && pip freeze --all --exclude pip --exclude setuptools --exclude wheel"
```

## Amazon (SP-API) y Keepa

- **Keepa** (`KEEPA_API_KEY`): historial de BSR/precio y UPC de los ASIN de referencia.
- **SP-API**: aplicación privada en Seller Central con el rol *Product Listing* (catálogo, UPC y restricciones) y,
  para tarifas reales, *Pricing*. Variables `SP_API_LWA_CLIENT_ID/SECRET`, `SP_API_REFRESH_TOKEN` y `SP_API_SELLER_ID`
  (Merchant Token). Con ellas la página **Vender sin permiso** verifica cada ASIN contra tu cuenta.
- Sin estas claves el panel funciona con estimaciones y lo indica en cada página.

## Límites conocidos

- Los CSV de datos se escriben de forma atómica y con bloqueo, pero si dos personas editan la misma tabla a la vez
  gana el último que guarda.
- Google Trends limita por IP (~15-20 consultas por corrida); el escaneo se corta en el primer bloqueo y sigue al día siguiente.
- Las tarifas FBA, referral, PPC y devoluciones de `config.yaml` son estimadas hasta conectar la API de tarifas.
- La prueba de humo de `update.sh` es HTTP (health + cabecera HSTS por la URL pública); no inicia sesión.
- El monitoreo registra caídas en Grafana, pero el servidor no tiene Alertmanager: nadie recibe un aviso.
