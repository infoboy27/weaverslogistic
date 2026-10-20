# Weavers Logistic — despliegue seguro y conexión Amazon

## Estado y límites

El dashboard Streamlit funciona como analizador de productos FBA, no como un ERP multiusuario.
Esta rama agrega **autenticación OIDC obligatoria por defecto** y un adaptador de lectura de
catálogo Amazon SP-API. **No es una certificación de producción completa**: aún se necesita
probar el despliegue, permisos SP-API, monitoreo, protección de datos y aislamiento multiusuario.

## Login OIDC

1. Configura un proveedor OpenID Connect (Google Workspace, Auth0 o Entra ID).
2. Crea el archivo privado `.streamlit/secrets.toml` a partir de
   `.streamlit/secrets.toml.example`. Registra exactamente `https://TU_DOMINIO/oauth2callback`.
3. Configura en el servidor `WEAVERS_ALLOWED_EMAILS=correo@dominio.com`.
   La lista es **obligatoria**. Si está vacía, se deniega acceso.
4. Habilita HTTPS mediante un proxy inverso confiable. Evita acceso directo público al puerto 8501.
5. Genera un cookie_secret aleatorio, largo y exclusivo. Nunca guardes secretos en GitHub.

Para pruebas *locales exclusivamente*: `WEAVERS_AUTH_MODE=disabled` junto con
`WEAVERS_ALLOW_INSECURE_LOCAL=1`. **NUNCA** usar estos valores en producción.
La autorización se aplica antes de procesar datos o mostrar el panel.

## Amazon Selling Partner API (cuenta propia)

Para aplicación privada de un único vendedor:
- Solicita/activa cuenta profesional Seller Central y acceso SP-API como desarrollador.
- Registra una aplicación privada y autorízala desde Solution Provider Portal.
- Asigna los roles mínimos (por ejemplo Product Listing para catálogo; Pricing para precios),
  y revisa permisos de Amazon para cada operación.
- Añade al entorno del servidor: `SP_API_LWA_CLIENT_ID`,
  `SP_API_LWA_CLIENT_SECRET`, `SP_API_REFRESH_TOKEN`.
- Entra en la pestaña **Amazon SP-API** y consulta un término. No expongas refresh tokens al navegador.
- La API no concede ventas de competidores ni Brand Analytics automáticamente.
  Brand Analytics requiere sus permisos y elegibilidad correspondientes.

## Checklist antes de exponer a usuarios externos

- CI y pruebas exitosas en la rama.
- El proxy expone solo HTTPS, limita requests y agrega headers de seguridad.
- Persistencia protegida: los CSV compartidos actuales no aíslan vendedores/usuarios.
- Mover ajustes y cachés a PostgreSQL con registros por organización + RBAC antes de multi-tenant.
- Secret manager, rotación de credenciales, backups y restauración probada.
- Logs sanitizados, monitoreo, alerta y análisis de dependencias.
- Validación de estimaciones con comisiones, tarifas FBA y ventas reales de tu cuenta.
- Revisión legal y de uso permitido de cada proveedor de datos.
