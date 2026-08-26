# BACKLOG — Hallazgos para v2 (reportes comerciales)

Este documento registra mejoras y hallazgos identificados durante el
desarrollo del tracker público (abril 2026) que NO se implementan en
la versión gratuita, pero son relevantes para los reportes comerciales
del producto FRIS.

El tracker público cumple su rol como portafolio técnico y base
metodológica. Los reportes comerciales deben ir más profundo en las
dimensiones listadas acá.

---

## 1. Desagregación estacional de correlaciones

**Problema:** el tracker calcula correlación mensual agregada de todo
el año (1981-2025). Esto esconde heterogeneidad estacional.

**Hipótesis:** en NEA la correlación ENSO-precipitación probablemente
es fuerte en octubre-marzo (primavera-verano) y débil o nula en
abril-septiembre.

**Implementación v2:** recalcular correlaciones por trimestre o por
estación para cada región. Tabla de salida: región × trimestre × lag
× r × p-value.

**Valor comercial:** permite decirle al cliente "en su zona, el ENSO
importa en este trimestre y no importa en aquel", en vez de un r
promedio difícil de accionar.

---

## 2. Validación cruzada con ERA5

**Problema:** CHIRPS está marcado como "fuente única" en el dashboard.
Viola parcialmente el principio de rigor de datos del proyecto.

**Implementación v2:** pipeline paralelo que baja ERA5 mensual vía
Copernicus CDS API, agrega por las mismas 5 regiones y calcula
correlación. Reportar acuerdo/desacuerdo por región.

**Nota operativa:** ERA5 requiere registro gratis en CDS y tarda más
en descarga. Correr una vez, cachear, no incluir en pipeline
automático del dashboard.

**Valor comercial:** permite presentar correlaciones como "validadas
con dos fuentes independientes", lo que sube significativamente el
nivel de rigor percibido por clientes institucionales.

---

## 3. ~~Parseo del pronóstico IRI / NOAA~~ (PARCIALMENTE RESUELTO)

**Estado:** Implementado en Phase 2.3 (agosto 2026). El dashboard ahora
embebe las visualizaciones SVG del IRI/CCSR directamente (histograma de
probabilidades + pluma de modelos). URLs auto-calculadas por fecha.

**Pendiente v2:** IRI no expone datos como JSON/API — las probabilidades
numéricas por fase siguen sin ser parseables. Para reportes comerciales,
considerar OCR o scraping controlado con validación manual.

**Valor comercial:** ya parcialmente cubierto por la integración visual.

---

## 4. Desagregación por variables hídricas adicionales

**Problema:** el tracker solo correlaciona ENSO con precipitación.
Para varios tipos de cliente la variable relevante es otra.

**Implementación v2:** agregar series históricas de caudales de la
Base de Datos Hidrológica Integrada (BDHI) del Instituto Nacional del
Agua, correlacionarlas con ENSO por cuenca. Hacer lo mismo con niveles
de embalses clave (Yacyretá, Salto Grande, etc.) si los datos están
disponibles públicamente.

**Tipos de cliente que lo necesitan:**
- Hidroeléctricas: caudal de ríos que alimentan sus embalses.
- Bancos con cartera agro: anomalía de lluvia acumulada por campaña.
- Aseguradoras: probabilidad de eventos extremos (no solo media).

**Valor comercial:** diferencia el reporte FRIS de cualquier análisis
genérico ENSO-precipitación.

---

## 5. Capa de modelo económico parametrizable

**Problema:** un reporte que dice "en su región el ENSO correlaciona
r=0.22 con la lluvia" no se paga USD 2-5K. Un reporte que dice "bajo
el pronóstico actual su operación tiene 65% probabilidad de estar
dentro de rango, 20% déficit moderado, 15% déficit severo, y el
impacto esperado sobre su margen es X" sí se paga.

**Implementación v2:** desarrollar un marco paramétrico donde cada
tipo de cliente (agro, hidro, seguro, banco) tenga una función de
impacto económico entre la variable hídrica correspondiente y su
métrica de negocio (rendimiento por hectárea, generación eléctrica,
ratio siniestralidad, probabilidad de default).

**Nota:** esto es el producto real. Las primeras iteraciones serán
artesanales, cliente por cliente. El marco paramétrico surge después
de 3-5 casos documentados.

**Valor comercial:** es lo que transforma FRIS de "consultoría de
análisis" a "consultoría de decisión".

---

## Próximas decisiones pendientes

- Priorización: cuando se cierre el primer cliente, el scope del
  primer entregable va a dictar qué punto de este backlog se
  implementa primero.
- No implementar nada de este backlog antes de tener un cliente
  pagando. El tracker público ya cumple su función.

---

*Ultima actualizacion: 2026-08-26*
*Proxima revision: al cerrar primer cliente.*
