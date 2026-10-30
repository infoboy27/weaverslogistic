# Guía de estudio: ventas y rotación de inventario

*Weavers · FBA Trends — investigación del 30/10/2026. Primero retail en general (tiendas físicas, supermercados, moda), después lo propio de Amazon y al final qué llevar a la plataforma.*

> **Sobre los números.** Las fórmulas son estándar. Los rangos de referencia ("benchmarks") vienen en su mayoría de blogs de empresas de software y no coinciden entre sí, así que van marcados como **orientativos**. Lo más sólido son los estudios académicos (agotados, reseñas, precios terminados en 9) y las reglas que publica Amazon. Aun así, las cifras de Amazon de esta guía salen de terceros: hay que confirmarlas en Seller Central.

---

## 1. La ecuación de ventas

Todo vendedor experto descompone la venta en palancas que se pueden mover por separado:

**Ventas = Tráfico × Conversión × Ticket promedio (× Recompra)**

| Palanca | En una tienda física | En Amazon |
|---|---|---|
| Tráfico | Gente que entra (contador de personas) | Sesiones: impresiones en la búsqueda × clics (CTR) |
| Conversión | Compras ÷ visitantes | *Unit Session Percentage* = unidades ÷ sesiones |
| Ticket | Monto promedio por compra | Precio × unidades por orden (packs, bundles) |
| Recompra | Clientes que vuelven | Consumibles, *Subscribe & Save*, marca |

**Regla de oro:** mira las palancas juntas, no por separado. Si un descuento sube la conversión pero baja el ticket, la venta por visitante puede bajar. Ejemplo de Ariadne: con 800 visitantes y un ticket de $75, la venta por visitante es de $15. Si la conversión sube a 25% pero el ticket cae a $50 por el descuento, baja a $12.50.

**Diagnóstico rápido:**
- Hay tráfico pero pocas ventas: el problema está en la conversión (fotos, precio, reseñas, oferta).
- Hay ventas pero tickets pequeños: el problema está en el ticket (packs, venta cruzada).
- Pocas visitas: el problema es la visibilidad.

---

## 2. Métricas de rotación (las que usan los compradores de retail)

| Métrica | Fórmula | Qué dice | Referencia orientativa |
|---|---|---|---|
| **Rotación de inventario** (*turnover*) | Costo de lo vendido ÷ inventario promedio a costo | Cuántas veces al año "vacías y rellenas" el estante | Supermercado 14–20×, moda 4–6×, electrónica 8–12× (una sola fuente) |
| **Días de inventario** (DIO) | 365 ÷ rotación | Cuántos días dura el stock | Rotación 8× ≈ 46 días |
| **Sell-through** | Unidades vendidas ÷ unidades recibidas (mismo periodo) | Qué % de lo que compraste ya se vendió | ≥80% se considera fuerte; 40–80% sano según el rubro |
| **Semanas de cobertura** (WOS) | Stock actual ÷ venta semanal promedio | Cuántas semanas aguanta el stock al ritmo actual | 6–8 semanas con reposición continua |
| **GMROI** | Margen bruto anual ÷ inventario promedio a costo | Cuántos dólares de margen da cada dólar metido en inventario | ~3.0 como referencia general; varía mucho por rubro |

### La métrica clave: GMROI une margen y rotación

**GMROI = (margen ÷ costo) × rotación.** Por eso un producto de margen bajo que rota mucho puede ganarle a uno de margen alto que se queda en el almacén. Es la métrica que responde a tu pregunta de "¿de qué sirve el margen si no se vende?". Su límite: no incluye costos operativos (publicidad, almacenaje, personal), así que en FBA se calcula con la ganancia **después** de las tarifas de Amazon.

### Rotación ≠ unidades vendidas

La rotación es la **venta relativa al stock que tienes**, no las unidades sueltas. Si de dos productos siempre compras "2 meses de stock", los dos rotan igual: 6 veces al año. Lo que cambia la rotación es:
- **Cuánto compras de una vez:** el pedido mínimo del proveedor frente a lo que vendes. Si el mínimo son 100 unidades y vendes 250 al mes, rotas rápido; si vendes 25 al mes, el stock dura 4 meses.
- **Cuánto tarda la reposición:** con más tiempo de entrega necesitas más stock de seguridad, y eso baja la rotación.
- **Si el producto se estanca:** el stock que no sale baja la rotación de todo.

**Las unidades absolutas importan por otra razón.** Más unidades al mes dan más ganancia total y, en Amazon, mejor posición en la búsqueda (sección 6).

---

## 3. Disponibilidad: no quedarse sin stock

### Lo que cuesta un agotado (evidencia académica)

El estudio más citado es el de **Gruen, Corsten y Bharadwaj (2002)**. Reúne 52 estudios, 29 países y 72,000 compradores. Cuando el cliente no encuentra el producto:

| Reacción | % |
|---|---|
| Se va a otra tienda | 31% |
| Compra otra marca | 26% |
| Compra otro producto de la misma marca | 19% |
| Pospone la compra | 15% |
| No compra nada | 9% |

En promedio, los agotados cuestan **~4% de las ventas**. En Amazon es peor: el cliente cambia de vendedor con un clic y, además, pierdes posición en la búsqueda (sección 6).

### Cuándo y cuánto reponer

- **Clasificación ABC:** los productos A son ~20% del catálogo y hacen ~70–80% de la venta. Merecen revisión frecuente, más stock de seguridad y datos precisos. Los B y C llevan reglas más simples. La versión **ABC/XYZ** suma qué tan variable es la demanda.
- **Punto de reorden (ROP)** = venta diaria promedio × días de entrega + stock de seguridad. Los días de entrega se cuentan de punta a punta: fabricación, flete, aduana y recepción.
- **Stock de seguridad:**
  - Si solo varía la demanda: **SS = Z × σ_demanda × √(días de entrega)**.
  - Si también varían los tiempos de entrega: **SS = Z × √(L̄·σd² + D̄²·σL²)**.
  - Z = 1.65 para 95% de nivel de servicio. Para la mayoría de los negocios, 95–98% es el equilibrio entre costo y disponibilidad.
- **Valida contra tu historia:** pregúntate si con ese stock de seguridad te habrías quedado sin stock en los últimos 6 meses.

---

## 4. Compras: comprar bien es la mitad de vender

- **Presupuesto de compra (*open-to-buy*, OTB):** cuánto puedes comprar en un periodo sin salirte del plan. Se calcula con las ventas planeadas, el stock al inicio y al final, las rebajas planeadas y lo que ya está pedido. Se actualiza cada vez que cambia el pronóstico.
- **Rebajas planeadas, no de pánico:** define de antemano en qué fechas revisas (inicio, mitad y fin de temporada) y con qué indicadores: sell-through, semanas de cobertura, tiempo de temporada que queda y margen mínimo aceptable.
- **El stock viejo no mejora con el tiempo:** se mueve a propósito con descuento, packs u otro canal. Si hay mucho, te quedas sin dinero para comprar lo que sí se vende.
- **Lo que pasó alimenta la próxima compra:** lo que se rebajó y lo que no se vendió corrige el siguiente pedido.

---

## 5. Palancas de venta con evidencia

| Palanca | Qué dice la evidencia | Qué tan sólido es |
|---|---|---|
| **Reseñas** | Con 5 reseñas, la probabilidad de compra es **270% mayor** que con 0 (Spiegel Research Center, Northwestern). El efecto es mayor en productos caros (+380%) que en baratos (+190%). Después de las primeras 5 reseñas, cada reseña extra aporta mucho menos. Un 5.0 perfecto genera desconfianza; 4.2–4.7 convence más. | Alto, aunque viene de un solo retailer |
| **Precios terminados en 9** | Efecto del dígito izquierdo (Thomas y Morwitz 2005): $2.99 se percibe mucho más barato que $3.00, pero solo cuando cambia el primer dígito ($22.99 frente a $23.00 casi no se nota). En una prueba de MIT y Chicago, $39 vendió más que $34 y que $44. | Alto en tiendas físicas; posiblemente menor en línea |
| **Promociones** | Parte de la "subida" es venta adelantada o robada a otros productos. Hay que medir desde varias semanas antes hasta 4–8 semanas después para ver la venta realmente nueva. | Medio (literatura de los 90 más estudios recientes) |
| **Surtido** | El famoso estudio de las mermeladas (6 opciones vendieron más que 24) **no se replicó bien**: el efecto promedio es casi cero. Reducir opciones ayuda sobre todo en productos complejos o difíciles de comparar. La razón fuerte para tener menos variantes es operativa: menos complejidad, menos rebajas y menos capital inmovilizado. | Bajo como palanca de venta |
| **Agotados** | Ver sección 3: ~4% de la venta perdida, y 31% de los clientes se va a otra tienda. | Alto |

---

## 6. Lo propio de Amazon

### El volante de velocidad

```
más ventas/día ─▶ mejor posición en la búsqueda ─▶ más visitas ─▶ más ventas/día
       ▲                                                              │
       └──────────── conversión alta + stock disponible ◀─────────────┘
```

- **Las ventas de cada día se miden por palabra clave.** Amazon no publica su algoritmo, pero vendedores y herramientas coinciden: la **velocidad de venta**, la **conversión** y el **CTR** por palabra clave son las señales principales.
- **Precio y publicidad influyen de forma indirecta.** El precio mueve la conversión y el Buy Box. La publicidad (PPC) aporta ventas, y esas ventas ayudan a la posición orgánica.
- **Quedarse sin stock es lo peor que puede pasar.** La velocidad cae a cero y la posición se pierde rápido; recuperarla es lento y suele requerir publicidad o promoción después de reponer.

### Las dos paredes del inventario FBA

Amazon castiga tener **poco** y tener **demasiado**. Las cifras son de fuentes de terceros y hay que confirmarlas en Seller Central:

| Límite | Regla (según fuentes de terceros) | Qué implica |
|---|---|---|
| **Piso: tarifa por inventario bajo** | Se cobra si la cobertura histórica (30 y 90 días) baja de **~28 días**. Se calcula por cada código de producto (FNSKU). | Reponer antes: punto de reorden con 35–60 días de margen |
| **Techo: exceso** | El stock con más de **90 días** de cobertura cuenta como exceso y baja tu puntaje IPI | No mandar más de ~2–3 meses de venta |
| **Puntaje IPI** | Si cae del umbral (citado como **~400**), Amazon limita tu espacio de almacenamiento. Depende del exceso, el sell-through, el stock varado y el % de tiempo con stock. | Rotar bien es una condición para poder crecer |
| **Recargo por stock viejo** | Se suma a partir de ~181 o ~271 días, según la fuente | Lo que no se vende en 6 meses sale caro |

**Tu zona de trabajo en FBA: tener entre ~1 y ~3 meses de venta en Amazon.** Por eso la plataforma limita el primer pedido a 2 meses de stock.

### Indicadores para seguir

- **Conversión de sesiones** (*Unit Session %*): los promedios citados van de 5–12%, y por categoría de 10–20%. Menos de ~8% suele indicar un problema en la ficha. Amazon no publica un promedio oficial.
- **TACoS** (publicidad ÷ venta total): no hay un benchmark creíble. Lo sano es que **baje con el tiempo**, porque significa que crece la venta orgánica.
- **Margen de los vendedores** (Jungle Scout, varios años): ~2/3 tienen más de 10% de margen y ~1/3 más de 20%. Es margen por producto, antes de los costos generales del negocio.

---

## 7. Buenas prácticas de los que venden mucho

**Antes de comprar**
1. Elegir por **ganancia total y rotación juntas**, no solo por margen o solo por unidades.
2. Confirmar la demanda con datos de ventas reales, no solo con búsquedas.
3. Negociar un pedido mínimo bajo para el primer lote: así rotas rápido y arriesgas poco.
4. Calcular el punto de reorden y el stock de seguridad **antes** del primer pedido.

**Al lanzar**
5. Conseguir las primeras ~5 reseñas lo antes posible, por vías permitidas (en Amazon: programa *Vine* y solicitudes desde Seller Central). Es la palanca de conversión más fuerte.
6. Precio terminado en 9 y justo bajo un umbral ($24.99, no $25.49).
7. Publicidad al inicio para ganar velocidad. Medir el TACoS y esperar que baje.

**Operando**
8. **Nunca quedarse sin stock** en los productos A: reponer cuando queden ~35–60 días de cobertura.
9. **Nunca mandar más de ~90 días** de cobertura a Amazon: cuida el IPI y los recargos.
10. Revisar cada semana: ventas por día, cobertura, conversión, TACoS y reseñas nuevas.
11. Rebajar a tiempo lo que no rota, con fechas de revisión fijadas antes.
12. Medir las promociones con lo que pasa antes y después, no solo durante.
13. Lo que pasó en este ciclo corrige el próximo pedido.

---

## 8. Siguiente paso: qué llevar a la plataforma (borrador para discutir)

| Concepto | ¿Lo tenemos? | Qué falta |
|---|---|---|
| Velocidad de venta (unidades/mes de un vendedor nuevo) | ✅ estimada con el top 10 de Amazon | Historial real (Keepa o reportes de la cuenta) |
| GMROI por producto | ❌ | Calcularlo con margen, costo y rotación esperada. **Candidato a reemplazar "Rotación / Ganancia"** como prioridad principal |
| Rotación real (según el pedido mínimo) | ❌ | Pedido mínimo real por proveedor; hoy se supone 100 |
| Punto de reorden y stock de seguridad | ❌ | Tiempo de entrega real y su variación (proveedor + flete) |
| Banda de cobertura de 28–90 días | Parcial (máx. 2 meses en el primer pedido) | Alerta de cuándo reponer y de exceso |
| Agotados y su riesgo | ❌ | Avisar cuando la cobertura proyectada sea menor que el tiempo de entrega |
| Conversión, CTR, TACoS | ❌ | Datos de la cuenta (Business Reports / SP-API) una vez activa |
| Reseñas y rating del nicho | ✅ en el top 10 | Meta de "5 primeras reseñas" en el plan de lanzamiento |
| Promoción y estacionalidad | ✅ fechas especiales | Medir antes y después cuando haya ventas propias |

---

## Fuentes

**Académicas o primarias**
- Gruen, Corsten y Bharadwaj, estudio de agotados (2002), citado en [Univ. Regensburg — Stock-out management](https://epub.uni-regensburg.de/21309/1/Diskussionsbeitrag_Stock-out__management.pdf) y [Emerald (Corsten y Gruen 2003)](https://www.emeraldinsight.com/doi/abs/10.1108/09590550310507731)
- [Spiegel Research Center — How Online Reviews Influence Sales](https://spiegel.medill.northwestern.edu/How-Online-Reviews-Influence-Sales)
- [Psychological pricing — Wikipedia](https://en.wikipedia.org/wiki/Psychological_pricing) (Thomas y Morwitz 2005; Stiving y Winer 1997)
- [Psychology Today — Is choice overload a real thing?](https://www.psychologytoday.com/us/blog/pop-psych/201602/is-choice-overload-real-thing) (réplicas de Iyengar y Lepper)
- [Massey Marketing Bulletin — promociones](https://marketing-bulletin.massey.ac.nz/V2/MB_V2_N1_Hoek.pdf), [GERAD — Optimal Retail Price Promotions](https://www.gerad.ca/papers/G-2003-72.pdf)

**Práctica retail (orientativas)**
- [Cleverence — rotación por industria](https://www.cleverence.com/articles/for-business/retail-inventory-turnover-ratio-by-industry-5823/), [fffinstill — inventory turnover retail](https://fffinstill.com/learning/concepts/inventory-turnover-retail)
- [Shopify — GMROI](https://www.shopify.com/ca/blog/gmroi), [SPS Commerce — GMROI](https://www.spscommerce.com/community/articles/what-is-gross-margin-return-on-inventory-investment-gmroi), [Toolio — GMROI](https://www.toolio.com/post/the-complete-guide-to-gmroi-for-retail-brands)
- [Shopify — sell-through](https://www.shopify.com/blog/sell-through-rate), [Toolio — fórmulas de retail](https://toolio.com/post/fundamental-retail-math-formulas)
- [Cleverence — punto de reorden y stock de seguridad](https://www.cleverence.com/articles/for-business/how-to-calculate-reorder-point-with-safety-stock-5829/)
- [Ariadne — ventas por visitante](https://www.ariadne.inc/resources/blogs/sales-per-visitor-retail/), [StoreTraffic — la ecuación del retail](https://storetraffic.com/retailing/what-is-the-retail-equation/)
- [Fit Small Business — open-to-buy](https://fitsmallbusiness.com/open-to-buy-planning/), [Retail Doctor — el stock no mejora con la edad](https://www.retaildoc.com/blog/retail-consultant-tip-merchandise-doesnt-get-better-with-age)

**Amazon (terceros: confirmar en Seller Central)**
- [Seller Labs — cómo se calcula el IPI](https://www.sellerlabs.com/knowledge-base/how-amazon-calculates-your-ipi-score-and-how-to-raise-it/), [Nova Analytics — límites de capacidad 2026](https://novadata.io/resources/news/amazon-fba-capacity-limits-q1-2026-reset)
- [FBA Tactics — tarifa por inventario bajo](https://fbatactics.com/guides/low-inventory-level-fee/), [Beancount — cambios de tarifas FBA 2026](https://beancount.io/blog/2026/07/10/amazon-2026-fba-fee-overhaul-aged-inventory-low-inventory-fee-guide)
- [SellerSprite — agotados y posición](https://www.sellersprite.com/en/blog/The-Impact-of-Out-of-Stock-on-Keyword-Rankings), [InventoryHero — agotados en Amazon](https://www.inventoryhero.ai/blog/out-of-stock-amazon-ranking)
- [Nova Data — buena conversión](https://novadata.io/amazon-kpi/growth/good-conversion-rate), [SellerSprite — Unit Session %](https://www.sellersprite.com/en/blog/Unit-Session-Percentage-The-Truth-About-Traffic)
- [Jungle Scout 2023, cap. 1](https://www.junglescout.com/wp-content/uploads/2022/12/How-to-Sell-on-Amazon-FBA-Jungle-Scout-2023-Chapter-1.pdf), [EcomCrew — informe de Jungle Scout](https://www.ecomcrew.com/e496-amazon-seller-report/)
