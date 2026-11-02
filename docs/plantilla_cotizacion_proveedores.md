# Plantilla para cotizar con proveedores

*Weavers · FBA Trends — 02/11/2026. Para los 5 productos en empate técnico en Decisión.*

## El objetivo de cotizar

En Decisión hay 5 productos empatados porque **el costo, el pedido mínimo y el tiempo de entrega son supuestos**. Cada cotización reemplaza esos supuestos y desempata. Un producto **pasa** si:

1. **Costo puesto en Amazon ≤ costo objetivo** (tabla de abajo). Costo puesto = precio de fábrica + flete por unidad + arancel por unidad + preparación/etiquetas.
2. **El pedido mínimo es ≤ ~90 días de venta.** Si no, rota lento y Amazon lo cuenta como exceso.
3. **El tiempo de entrega es razonable** (producción + flete + recepción en Amazon). Con más días hace falta más stock de seguridad y baja la rotación.

## Los 5 productos

| # | Producto | Precio de venta | Costo objetivo (máx. puesto en Amazon) | Venta estimada | Pedido mínimo ideal | Nota |
|---|---|---|---|---|---|---|
| 1 | **Cat wrestling glove** (guante de juego para gatos) | $27.99 | **$7.24** | ~150/mes | ≤ 450 u. | Nicho nuevo, top 10 con pocas reseñas. Peso ~0.25 kg |
| 2 | **Dog grooming hammock** (hamaca de aseo para perros) | $34.99 | **$9.29** | ~125/mes | ≤ 375 u. | Riesgo: el top 3 se lleva 81% de las ventas (Kkiimatt). Peso del arnés ~0.49 kg; con soporte ~0.9 kg |
| 3 | **Bead organizer** (organizador de cuentas) | $25.99 | **$5.43** | ~150/mes | ≤ 450 u. | Peso por confirmar |
| 4 | **Dog cooling mat** (manta refrescante para perros) | $25.99 | **$5.43** | ~50/mes ahora (pico en verano) | ≤ 150 u. | Estacional: pedir antes del 27/02/2027. Las tallas S/M caben en <1 kg; la XL probablemente no |
| 5 | **Dog purse carrier** (bolso para llevar perro) | $38.99 | **$11.00** | ~100/mes | ≤ 300 u. | Riesgo: el top 3 se lleva 92% de las ventas |

*El costo objetivo da 25% de margen neto con las tarifas de Amazon estimadas. La venta es lo que vende hoy un vendedor nuevo en el top 10 × 50%. Todo es estimado hasta tener datos reales.*

## Cómo pedir las cotizaciones

1. **Dónde:** Alibaba.com. Busca el nombre en inglés y filtra por *Verified Supplier* y *Trade Assurance* (protege el pago).
2. **Cuántos:** **3 proveedores por producto**. Prioriza fabricantes (*Manufacturer*) con 3 o más años y buena tasa de respuesta.
3. **Cómo:** con el mensaje de abajo. Cambia lo que está entre [corchetes].
4. **Flete y arancel:** pide al proveedor precio **FOB** (puesto en el puerto chino) y, si lo ofrece, **DDP a un almacén de Amazon**. Pide aparte a un forwarder el flete marítimo y el **arancel según el código HTS** del producto. Los aranceles a productos chinos han cambiado mucho; no uses un número viejo.
5. **Anota todo** en `data/cotizaciones.csv` (hoja comparativa). La mejor cotización de cada producto pasa a la pestaña **Productos y rentabilidad**: columnas `costo_fabrica`, `flete_unidad`, `moq` y `dias_entrega`.

## Mensaje para el proveedor (en inglés)

> **Subject:** Quotation request – [PRODUCT NAME] – private label for Amazon US
>
> Hello [Supplier name],
>
> We are a US company (Delaware LLC) launching a private-label brand on Amazon US. We are interested in your [PRODUCT NAME] ([link to their listing]) and would like a quotation.
>
> **Please quote:**
> 1. Unit price at these quantities: **[MOQ], 300, 500 and 1,000 pcs** (FOB [port]). DDP price to an Amazon US warehouse too, if you offer it.
> 2. Your **MOQ**, and whether a lower first trial order is possible (we plan to reorder regularly).
> 3. **Production lead time** for the first order and for reorders.
> 4. **Product specs:** material, available sizes/colors, **unit weight (kg)** and **packaged dimensions (cm)**.
> 5. **Carton details:** units per carton, carton dimensions (cm) and gross weight (kg).
> 6. **Customization:** cost and MOQ for our **logo on the product** and a **custom retail box/polybag**.
> 7. **Samples:** cost and delivery time for 1–2 samples to [the US / Dominican Republic].
> 8. **Certifications or test reports** you have for this product (e.g. material safety reports).
> 9. Can you **label each unit with our Amazon FNSKU barcode** and mark cartons per Amazon FBA requirements? Is there a cost?
> 10. **Payment terms**, and whether you accept **Alibaba Trade Assurance**.
>
> [For the dog products: Please confirm the sizes (S/M/L) and the weight of each size.]
>
> Thank you, we look forward to your offer.
>
> [Your name]
> [Company name], [City, State]

## Preguntas extra por producto

Agrégalas al mensaje de ese producto:

- **Cat wrestling glove:** *"Is the glove material scratch- and bite-resistant? Please share the fabric type and whether the fingers/tails are stitched or glued."* (Lo que más critican las reseñas de este tipo de producto es que se rompe.)
- **Dog grooming hammock:** *"Please quote the hammock only and the hammock + stand version separately, with the weight of each. What is the maximum dog weight supported?"* (La versión con soporte puede pasar de 1 kg y cambiar la tarifa de Amazon.)
- **Bead organizer:** *"How many compartments, and are they removable? Is the lid tight enough that beads don't move between compartments when it is turned over?"*
- **Dog cooling mat:** *"Is it pressure-activated gel or cooling fabric? Please quote sizes S, M and L separately with the weight of each. Is it non-toxic and leak-proof?"* (Pide S y M; la XL probablemente supera 1 kg.)
- **Dog purse carrier:** *"What is the maximum pet weight? Does it have ventilation mesh and a safety leash clip inside?"*

## Cómo leer las respuestas

| Señal | Qué significa |
|---|---|
| **Responde rápido y completo** | Buena señal: así será también cuando haya un problema |
| **El precio baja mucho a 500–1,000 u.** | Bien para recompras, pero el primer pedido debe ser chico para rotar rápido |
| **Pedido mínimo > ~90 días de venta** | Negocia una "trial order" más chica o descarta |
| **No da peso ni medidas** | Sin eso no se puede calcular la tarifa de Amazon. Insiste |
| **Muestras caras o lentas** | Normal pagar algo de flete, pero no compres sin muestra |
| **Pide pago 100% por adelantado fuera de Trade Assurance** | Riesgo alto. Lo habitual es 30% de anticipo y 70% antes del envío |

**Siempre pide muestra** del finalista antes del pedido grande. Revisa calidad, medidas y peso reales, y compara con lo que critican las reseñas de 1–3 estrellas de la competencia.
