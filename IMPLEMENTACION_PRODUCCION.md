# Weavers Logistic — Guía de implementación de producción

> Versión inicial: 16 octubre 2026. **Esta rama es un punto de partida y NO debe considerarse producción aprobada hasta validar los controles al final.** La rama `main` no se ha modificado.

## 1. Alcance real

El producto actual usa **Streamlit + Python**, Google Trends, Keepa, archivos CSV, ranking heurístico, calculadora FBA y escenarios de inversión. Esta rama añade:
- Inicio de sesión OIDC con `st.login` y allowlist de correo, negando acceso si la configuración falta.
- Consulta de catálogo estadounidense por Amazon Selling Partner API (SP-API), con refresco LWA en el backend.
- Modelo SQL para guardar snapshots de consultas con actor, fuente, fecha y organización (implementación inicial).
- Docker Compose con Caddy/HTTPS y PostgreSQL, más checks CI de seguridad y pruebas unitarias del análisis.
- Una guía para habilitar proveedores, publicar y operar.

**No implementado aún:** flujo self-service OAuth de onboarding de múltiples vendedores, sincronización de pedidos/ventas/reportes reales, autorización por roles dentro de cada organización, migración de todos los CSV a PostgreSQL, un scheduler de fuentes en producción, reportes avanzados integrados, UI rediseñada y pruebas E2E desplegadas. Una lista allowlist sirve para una consola privada de un operador, **no** para SaaS multiempresa.

## 2. Prerrequisitos

- Dominio propio con registros A/AAAA apuntando al servidor, puertos 80/443 accesibles.
- VPS Linux actualizado, Docker Engine y plugin Docker Compose; DNS público válido.
- Cuenta en un proveedor OIDC como Google Workspace, Auth0 o Microsoft Entra.
- Cuenta profesional Amazon Seller Central elegible para SP-API y aplicación privada autorizada.
- Suscripción Keepa API (opcional). Google Trends es orientativo y está sujeto a límites.
- Copias de seguridad externas cifradas y almacenamiento cifrado/controles de acceso al servidor.

## 3. Obtener el código

```bash
git clone https://github.com/infoboy27/weaverslogistic.git
cd weaverslogistic
git switch feat/production-auth-amazon-spapi
cp .env.production.example .env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
chmod 600 .env .streamlit/secrets.toml
```

No publiques, adjuntes ni subas `.env` o `secrets.toml`. Cambia todas las variables de ejemplo.

## 4. Login seguro OIDC

1. En el proveedor de identidad, crea una aplicación web **OpenID Connect**.
2. Configura URI de redirección exacta `https://research.tudominio.com/oauth2callback`.
3. Coloca en `.streamlit/secrets.toml` valores reales para:
   `redirect_uri`, `cookie_secret`, `client_id`, `client_secret` y `server_metadata_url`.
4. Genera `cookie_secret` mediante un gestor criptográfico o `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
5. En `.env`: `WEAVERS_ALLOWED_EMAILS=tu-correo@tu-dominio.com`; para más usuarios separa con comas.
6. **No pongas** `WEAVERS_AUTH_MODE=disabled` ni `WEAVERS_ALLOW_INSECURE_LOCAL=1` en producción; Compose establece `required`.
7. Comprueba login, rechazo de otro correo, expiración/cierre de sesión y ruta `/oauth2callback`.

Para un sistema multiusuario real añade base de datos de usuarios, roles, MFA en el proveedor, invitaciones, sesiones y límites de acceso por organización. Un email validado no equivale a roles de negocio.

## 5. Conectar Amazon Seller Central

La dirección de login normal es **sellercentral.amazon.com**, no se necesita compartir contraseña. SP-API se habilita en Amazon a través de registro y autorización de una aplicación.

1. Entra en Seller Central / Solution Provider Portal y confirma elegibilidad.
2. Crea o registra una **aplicación privada** para tu propia cuenta vendedora.
3. Solicita únicamente los roles/permisos exigidos para las operaciones que se usarán (Catálogo; y más adelante Precios, Reportes, Inventario y Fees cuando sean autorizados).
4. Realiza la autorización de la aplicación de vendedor y genera el **refresh token LWA** según el flujo oficial vigente; guarda los identificadores sin publicarlos.
5. Define en el host:
   ```env
   SP_API_LWA_CLIENT_ID=...
   SP_API_LWA_CLIENT_SECRET=...
   SP_API_REFRESH_TOKEN=...
   ```
6. Usa la pestaña «Amazon Seller Central» del dashboard y busca un término de Amazon US. Se consulta `GET /catalog/2022-04-01/items`; el cliente renueva el token vía `https://api.amazon.com/auth/o2/token`.
7. Confirma permisos, cabeceras, región, timeouts, restricciones y cuotas aplicables desde la documentación oficial actual. Si devuelve 403, **no eludas** permisos; valida el rol de la app y autorizaciones.

La búsqueda de catálogo NO equivale a conocer las ventas privadas de terceros. Para tener **ventas propias** será necesario construir después los conectores de Reports/Orders y su autorización. Para Brand Analytics o datos similares hace falta elegibilidad y roles específicos, cuando estén disponibles.

### Amazon y el estudio de mercado

Fuentes y calidad:
| Fuente | Sirve para | Precaución |
| --- | --- | --- |
| SP-API Catálogo | ASIN, títulos, categorías, imágenes autorizadas | No da ventas de competidores |
| SP-API de tu cuenta (futuro) | Tus ventas, inventario, tarifas si autorizadas | Requiere roles y endpoints adicionales |
| Keepa | Histórico de precios, BSR y vendedores | BSR no equivale a ventas exactas |
| Google Trends | Interés relativo y estacionalidad | No es volumen de ventas |
| Cotizaciones proveedores | Costo real y MOQ | Requiere confirmación por escrito |
| Importación manual CSV | Proyecciones y datos externos legítimos | Anotar procedencia y fecha |

No uses scraping que infrinja términos de plataformas. Cada métrica debe conservar `source`, `observed_at`, `is_estimate`, `method` y, si es viable, enlace al origen.

## 6. Despliegue Docker

Edita `.env`:
```env
APP_DOMAIN=research.tudominio.com
WEAVERS_ALLOWED_EMAILS=tu-correo@dominio.com
POSTGRES_PASSWORD=CONTRASENA_ALEATORIA_LARGA
SP_API_LWA_CLIENT_ID=
SP_API_LWA_CLIENT_SECRET=
SP_API_REFRESH_TOKEN=
KEEPA_API_KEY=
```

Ejecuta:
```bash
python scripts/check_production.py
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 app
```

**Nota:** `check_production.py` solo verifica entorno del proceso que lo ejecuta. Si usas `.env` en lugar de variables exportadas, carga ese entorno de manera segura antes de llamarlo (sin imprimir secretos). No sustituye pruebas E2E.

Caddy obtiene TLS automáticamente si el DNS, la conectividad y el dominio son correctos. Mantén 8501 y 5432 sin publicar; solo 80/443 deben estar expuestos. Los archivos de tendencias/CSV actuales se mantienen en el volumen bind `./data`; restringe permisos en host y planea migración transaccional.

El volumen Postgres conserva consultas de catálogo. Por ahora se inicializa la tabla cuando se realiza la primera consulta autenticada; las migraciones formales deben implementarse con Alembic al ampliar el esquema.

## 7. Seguridad y observabilidad

- GitHub Actions: `ci-cd.yml` ejecuta pytest/build; `security.yml` escanea dependencias (pip-audit) y Python (Bandit).
- Mantén protegido `main` con PR, revisión y checks requeridos antes de merge.
- No almacenes refresh/access tokens en tablas, logs, UI, CSV ni GitHub; usa vault/secrets manager para despliegues críticos.
- Establece MFA en el proveedor OIDC; HTTPS; rate limits en proxy o WAF; rotación de secretos; política de mínimos privilegios.
- Agrega alertas: disponibilidad HTTPS, tasa 401/403/429, errores 5xx, latencia y cuota API.
- Las consultas SP-API requieren manejo robusto de 429/Retry-After, retries con backoff, telemetría y presupuestos de cuota: **pendiente**.
- Evalúa PII y cumplimiento de las políticas de protección de datos de Amazon si más adelante incorporas pedidos de clientes.
- La opción experimental que deshabilita auth está pensada solo para tests locales: no exponer un servidor bajo esas variables.
- **Importante:** las rutas de archivos CSV existentes son compartidas; no invites a múltiples clientes hasta aislarlas por organización y probar autorización de lectura/escritura.

## 8. Copias de seguridad / restauración

Ejemplo básico (ejecutar desde el host, con un destino protegido):
```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U weavers -Fc weavers > weavers-db.dump
tar -czf weavers-data.tar.gz data/
```
Cifra los archivos antes de moverlos a un almacén externo y elimina copias locales sin protección. Prueba la restauración en una instancia aislada, documenta RPO/RTO y automatiza una política de retención. No presupongas backups del volumen Docker.

## 9. Pruebas y aceptación

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app.py fba_trends scripts
```

Checklist antes de abrir a internet:
- [ ] CI de test, build y seguridad completamente verde.
- [ ] OIDC en HTTPS: login válido, allowlist denegando usuarios no invitados, logout, cookies.
- [ ] Secretos fuera de Git y verificados; accesos auditables, permisos mínimos y MFA.
- [ ] SP-API real devuelve búsqueda válida y rechaza correctamente roles insuficientes.
- [ ] Snapshots en DB guardados y recuperables bajo la organización correcta.
- [ ] PostgreSQL respaldado y restaurado; CSV respaldados; discos con espacio.
- [ ] Pruebas de carga, healthchecks, monitoreo y alertas.
- [ ] Revisar tarifas FBA, PPC, impuestos, aranceles y costos logísticos reales.
- [ ] Etiquetar proyecciones como **estimadas**, no garantizadas.
- [ ] Revisar cumplimiento, seguridad de endpoints, actualización de imágenes y dependencias.

## 10. Plan pendiente para convertirlo en SaaS comercial

Fase A — **consolidación**: corregir fallos CI, seguridad del contenedor, esquema DB con Alembic, auditoría central y caching; sustituir persistencia CSV por repositorios.

Fase B — **motor real**: conectores de Amazon Orders, Reports, Product Fees/Pricing de tu cuenta; Keepa con cuotas; ingestión con worker/scheduler, métricas con fecha, deduplicación, validación e idempotencia; simulaciones netas pesimista/base/optimista.

Fase C — **SaaS**: organizaciones, RBAC, invitaciones, API backend, flujos OAuth para cada vendedor, KMS/vault, rate limiting por tenant, billing, logging y tests E2E.

Fase D — **experiencia**: dashboard profesional responsive, búsquedas guardadas, ranking explicable, alertas, comparativas ASIN/keyword, reportes PDF/CSV e informes exportables con trazabilidad.

## Enlaces

- [Repositorio](https://github.com/infoboy27/weaverslogistic)
- [PR de preparación](https://github.com/infoboy27/weaverslogistic/pull/1)
- [Amazon SP-API](https://developer-docs.amazon.com/sp-api/)
- [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication)
- [Keepa API](https://keepa.com/#!api)

**Regla final:** estar configurado no significa estar validado. Un release se aprueba solo tras verificación en el dominio real y autorización efectiva de proveedores.
