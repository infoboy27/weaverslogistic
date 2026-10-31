# FBA Trends

Panel para elegir productos de Amazon FBA: detecta tendencias (Google Trends), calcula la rentabilidad por unidad y reparte un presupuesto inicial pequeño entre los mejores candidatos.

## Ejecutar

```bash
.venv/Scripts/streamlit run app.py
```

Pruebas: `.venv/Scripts/python -m pytest -q tests`

## Keepa

1. Suscripción a la API en keepa.com → API (es de pago; se cobra por tokens por minuto).
2. Copia `.env.example` como `.env` y pon `KEEPA_API_KEY=tu_clave`. El `.env` no se comparte (está en `.gitignore`).
3. Reinicia el panel.

Cada ASIN consulta cuesta tokens; las respuestas se guardan en `data/keepa/` y solo se vuelven a pedir pasadas 24 h. En `data/candidates.csv`, la columna `asins_competidores` (separados por espacio) hace que las reseñas de la competencia, la mediana de precio y las ventas del mercado se llenen solas.

## Descubrimiento diario

Una tarea programada de Windows ("Weavers FBA Discovery", 10:00, o al encender si estaba apagada) ejecuta
`scripts/run_discover.cmd`:

1. Toma ~4 categorías semilla de `data/seeds.csv` (cada una se repite cada 30 días) y pide a Google Trends sus búsquedas **en aumento** de los últimos 12 meses en EE.UU.
2. Filtra basura (dominios, tiendas, "near me", preguntas, términos genéricos).
3. Escanea hasta 10 términos nuevos con el análisis normal (5 años, ajuste vs mercado) y los agrega a `data/keywords.csv`.
4. Re-calcula el ranking y mide volumen para hasta 4 finalistas nuevos (el volumen queda en `data/volume.csv`).

Google bloquea la conexión tras ~15-20 consultas; la corrida se detiene al primer bloqueo y sigue al día siguiente.
Log: `data/discovery_log.txt`. Google Shopping (gprop=froogle) se probó y no devuelve consultas relacionadas.

## Pestañas

- **Tendencias**: consulta Google Trends (5 años, EE.UU.) o sube el CSV que descargas de trends.google.com. Si Google bloquea la consulta automática (error 429, pasa seguido), usa el CSV. Clasifica cada keyword como *Emergente*, *Estacional*, *Estacional en crecimiento*, *Moda pasajera*, *Estable* o *En declive*. Para las estacionales calcula **hasta qué fecha hay que hacer el pedido a fábrica**.
- **Competencia**: top 10 orgánico de Amazon por keyword (reseñas, precio, "bought in past month", marca, anuncios) con resumen y veredicto Accesible / Media / Difícil. Guía de qué revisar dentro de la pestaña. Las capturas crudas van en `data/raw_search/*.json` y se cargan con `.venv/Scripts/python -m scripts.ingest_search`.
- **Amazon (Keepa)**: historial de BSR (ranking de ventas), precio, número de vendedores, reseñas y "comprado el mes pasado" de cualquier ASIN. Pega los 10 primeros ASINs de tu keyword (o búscalos por término) y mira si el mercado está acelerando (BSR bajando) o saturándose (más vendedores, precio cayendo).
- **Productos y rentabilidad**: precio, costos y tarifas → ganancia neta, margen, ROI, precio de equilibrio y score. Si falta el costo, muestra el **costo máximo puesto en Amazon** que permite el margen objetivo (tope para negociar con proveedores).
- **Presupuesto**: reparte el capital con reserva, tope por producto, MOQ y un máximo de N meses de ventas en la primera orden.
- **Supuestos**: todo lo que es estimado y hay que verificar.

## Archivos

- `config.yaml`: tarifas, supuestos, tiempos de entrega y reglas de presupuesto. Lo marcado `estimado: true` **no es un dato verificado**.
- `data/candidates.csv`: tus productos candidatos (precio real de Amazon; costo pendiente hasta tener cotización).
- `data/trends/`: series de Google Trends guardadas.
- `fba_trends/`: `trends.py` (clasificación), `profit.py` (rentabilidad), `budget.py` (presupuesto), `scoring.py`, `collect.py`.

## Límites conocidos

- Google Trends mide interés **relativo**, no volumen. Hay que confirmar la demanda en Amazon antes de comprar.
- Los pesos del score y los umbrales de clasificación son heurísticos y no están validados con ventas reales.
- La integración con Keepa está probada con datos sintéticos en el formato oficial; falta probarla con una clave real. La búsqueda por término (`/search`) es la parte menos verificada.
- Siguiente fuente de datos: Amazon Brand Analytics (cuando haya Brand Registry).


## Preparación para producción

Consulta [IMPLEMENTACION_PRODUCCION.md](IMPLEMENTACION_PRODUCCION.md) para la instalación HTTPS, login OIDC, Amazon SP-API, PostgreSQL y la checklist de seguridad. Los cambios se revisan en [PR #1](https://github.com/infoboy27/weaverslogistic/pull/1).
