---
name: vivaslide
description: Plantilla oficial VivaSlide de Viva Consulting Empresas para presentaciones PowerPoint (.pptx) de nivel directorio. Úsala SIEMPRE que el usuario pida un deck, presentación, informe en slides, reporte para directorio, comité, gerencia o cliente de Viva Consulting / VIVA-GEX, o mencione "VivaSlide", "plantilla Viva", "formato Viva" o "estilo Viva Consulting" — aunque no diga "pptx". También cuando pida convertir un análisis (ventas, zonas, Q vs Q, YoY, KPIs, flujo de caja, rentabilidad) en una presentación ejecutiva. Clona las slides reales de la plantilla (portada, resumen ejecutivo con KPIs, divisores de sección, gráficos nativos, tablas, hallazgos, conclusiones y contraportada) y llena los datos sin romper el diseño.
---

# VivaSlide — plantilla oficial de Viva Consulting Empresas

La plantilla oficial está en `assets/vivaslide-template.pptx` (14 slides, 16:9 de 10" × 5.625",
fuente Calibri). Una vista de todas sus slides está en `assets/vivaslide-preview.jpg`; mírala antes de
planificar el deck.

Los decks VivaSlide **se construyen clonando slides de la plantilla y reemplazando su contenido**.
Así se conservan exactamente la marca, los logos, las imágenes, los colores y los gráficos nativos
(editables en PowerPoint). No recrees el diseño desde cero con pptxgenjs: siempre se nota la diferencia.

## Flujo de trabajo

1. **Datos primero.** Lee la fuente (Excel, CSV, base de datos) y calcula todas las cifras con código
   (pandas/openpyxl). Cada número del deck debe salir de los datos; nunca inventes ni redondees "a ojo".
   Si falta la fuente, pídela antes de armar nada: un deck de directorio con cifras inventadas es peor que no tener deck.
2. **Storyline.** Escribe primero la lista de slides con el título-hallazgo de cada una (ver "Estilo de
   redacción"), y elige qué slide de la plantilla clona cada una (ver "Catálogo").
3. **Spec JSON + build.**
   ```bash
   python3 scripts/vivaslide.py inspect                    # nombres de shapes de la plantilla
   python3 scripts/vivaslide.py build spec.json -o deck.pptx
   ```
   El formato del spec está documentado al inicio de `scripts/vivaslide.py`. El script clona slides
   (también las que tienen gráficos, con su Excel embebido), reemplaza textos conservando el formato,
   reescribe datos de gráficos y tablas, cambia el pie de página y renumera "k/N" solo.
   Requiere `pip install python-pptx`.
4. **QA visual obligatorio.** Convierte a PDF/JPG (si existe el skill `pptx`, usa su
   `scripts/office/soffice.py`; si LibreOffice da "source file could not be loaded", instala
   `libreoffice-impress`) y revisa cada slide: texto desbordado, títulos en 3 líneas, KPI que salta de
   línea, decoraciones mal ubicadas y restos de texto de la plantilla. Revisa también las cifras
   contra los datos. Busca restos con:
   `markitdown deck.pptx | grep -iE "Lima Este|Lima Sur|Callao|geograf|zona|Agosto 2026"` (y "Idrato" si el cliente no es Grupo Idrato).
   Los retoques que el script no cubre (colores de celdas, formato de etiquetas, ejes, colores por punto) se hacen en un
   segundo paso con python-pptx/lxml sobre el `.pptx` generado.

## Catálogo de slides de la plantilla

`from` = número de slide a clonar. Los nombres de shapes son los que aparecen en el `inspect`.

| from | Tipo | Shapes a editar | Notas |
|---|---|---|---|
| 1 | **Portada** (foto edificios + logo) | `Text 2` sobrelínea (MAYÚS, ámbar) · `Text 3` título "Cliente — Tema" · `Text 4` subtítulo · `Text 5` "Director del Proyecto: Luis Vallejos · Viva Consulting Empresas · Mes Año" | Título ≤ 55 caracteres |
| 2 | **Alcance y metodología**: banda + 3 tarjetas + notas | `Text 4` header · `Text 11` banda · tarjetas `Text 14/15/16`, `19/20/21`, `24/25/26` (etiqueta, valor, descripción) · `Text 29` "NOTAS DE LECTURA" · `Text 30` viñetas (lista) | Úsala siempre: fuente, periodo y cómo se calculó |
| 3 | **Resumen ejecutivo**: mensaje + 4 KPI + "qué habilita" | `Text 4` header · `Text 11` mensaje principal (fondo navy, texto ámbar) · KPI `Text 14/15/16`, `19/20/21`, `24/25/26`, `29/30/31` (valor, "0N · etiqueta", nota) · `Text 34` etiqueta caja · `Text 35` implicancia | Valor KPI ≤ 9 caracteres (a 20pt hace salto de línea con más) |
| 4 | **Divisor de sección** (número gigante) | `Text 0` número "01" · `Text 3` "SECCIÓN 01" · `Text 4` título · `Text 5` bajada | La línea `Shape 2` está pensada para títulos de 2 líneas; con título de 1 línea, agrega `"delete": ["Shape 2"]` |
| 5 | **Gráfico de barras horizontales agrupadas** (2 series) a ancho completo | `Text 2` "Fuente: …" · `Text 3` título-hallazgo · `Text 7` unidad (p. ej. "S/ · Ene–Jul") · `Chart 0` · `Text 9` lectura bajo el gráfico | Título ≤ 90 caracteres (2 líneas máx.) |
| 6 | **Tabla de detalle** | `Text 4` header · `Text 11` banda · `Table 0` (la primera fila es el encabezado y la última el TOTAL) · `Text 12` nota metodológica | Hasta ~12 filas y 8 columnas. Los colores de cada celda vienen fijos de la plantilla (verde/rojo por fila): recolorea las columnas de variación según el signo |
| 7 | **Barras horizontales agrupadas de %** (participación) | igual que la slide 5 | Para share / mix en pp. Formato de etiqueta `0.0"%"` (pasa 52.8, no 0.528) |
| 8 | **Barras horizontales de 1 serie** (crecimiento %, verde) | igual que la slide 5 | Formato de etiqueta `+#,##0"%"`: para valores que no son crecimiento (p. ej. alcance) cámbialo a `0"%"` en el XML del gráfico |
| 9 | **Dos gráficos de columnas lado a lado + 3 KPI** | `Text 4` header · `Text 11` banda · `Text 12` / `Text 13` títulos de gráfico · `Chart 0` / `Chart 1` · KPI `Text 16/17`, `20/21`, `24/25` | Los dos gráficos traen el eje Y fijo en máx. 95: borra `<c:max>` de `c:valAx/c:scaling` o las barras se cortan. El gráfico derecho pinta la serie 2 en verde |
| 10 | **Dona + 3 tarjetas** Riesgo / Oportunidad / Alerta | `Text 3` título · `Text 7` total · `Chart 0` · tarjetas `Text 10/11/12`, `15/16/17`, `20/21/22` | Etiquetas de % en texto oscuro: ponlas en blanco si la primera porción es navy |
| 11 | Divisor de sección (variante) | — | Tiene "SECCIÓN 02" superpuesto al título; **usa la slide 4** para todos los divisores |
| 12 | **Hallazgos**: 5 tarjetas + "En una frase" | `Text 11` banda · tarjetas `Text 14/15/16`, `19/20/21`, `24/25/26`, `29/30/31`, `34/35/36` · `Text 38/39` caja navy | `Text 4` header (cámbialo: trae "HALLAZGOS · LO QUE MUESTRA LA GEOGRAFÍA DE VENTA") · hechos verificables numerados |
| 13 | **Conclusiones y decisiones** | `Text 4` header · `Text 11` banda · `Text 12` recomendaciones (lista; un elemento por párrafo) · `Text 13` firma | 4–6 recomendaciones accionables |
| 14 | **Contraportada** (contacto Viva) | — | Siempre al final, sin cambios |

Se puede clonar la misma slide varias veces (p. ej. la 5 para cada gráfico de barras). Si sobra una
tarjeta, elimina su grupo completo (fondo `Shape N`, barra superior `Shape N+1` y sus textos) con `delete`,
no dejes la tarjeta vacía.

## Sistema visual (por si necesitas agregar algún elemento)

| Token | Hex | Uso |
|---|---|---|
| Navy profundo | `0F1A45` | Barra de header, pie, caja "En una frase" |
| Navy noche | `040C20` | Banda de portada, número en caja ámbar |
| Azul marca | `1B2A6B` | Serie principal / año actual, KPI neutro, divisores |
| Azul medio | `002060` | Bloque lateral de las slides de gráfico |
| Azul claro serie | `8090C0` | Serie del año anterior (gráficos de barras) |
| Ámbar | `FBB800` | Número de sección, mensaje clave, paginación |
| Ámbar oscuro | `E09900` | Línea inferior, acentos de banda |
| Verde | `1A7A3C` | Positivo / crecimiento / oportunidad |
| Rojo | `B22222` | Negativo / riesgo / alerta |
| Texto principal | `1A1E2E` | Títulos |
| Texto cuerpo | `3D4A5C` | Párrafos |
| Gris secundario | `8A98A8` | Fuentes, pie, notas |
| Borde tarjeta | `E1E6EF` | Contorno de tarjetas y tablas |
| Fondo banda | `EDF1FB` | Banda de subtítulo y caja de lectura |

Tipografía: Calibri en todo el deck. Header de sección 12.5pt bold MAYÚS blanco; título de slide de
gráfico 16pt bold; KPI 20pt bold; cuerpo 8–10pt; fuente/pie 7pt. Respeta los tamaños de la plantilla.

Semántica de color en KPIs y tarjetas: azul = dato neutro, verde = mejora, rojo = deterioro o riesgo,
ámbar = valor o precio. Cambia el color de la barra superior y del valor juntos si cambia el signo.
Para cambiar el color de un run, edita el XML de la slide (`<a:srgbClr val="…"/>`) después del build o
con python-pptx (`run.font.color.rgb`).

## Estilo de redacción (estándar Viva para directorio)

- **El título es la conclusión, con su cifra.** "Lima Este consolida su liderazgo: sube de 50.6% a 52.8%
  de participación", no "Participación por zona". El header de las slides de sección va en MAYÚS con el formato
  `TEMA · MENSAJE CORTO`.
- **Pirámide:** portada → alcance/metodología → resumen ejecutivo → secciones (divisor + evidencia) →
  hallazgos → conclusiones y decisiones → contraportada.
- **Siempre fuente y unidad:** `Fuente: <base> · <qué mide> · <periodo> (<unidad>)` arriba de cada gráfico, y la
  unidad en `Text 7`.
- **La lectura bajo el gráfico** agrega lo que el gráfico no muestra: causa, base pequeña, matiz.
- **Honestidad analítica:** declara las limitaciones (datos sin asignar, bases pequeñas que inflan %, cambios
  de criterio) en la slide de alcance y en las notas.
- **Formato peruano:** `S/ 1,234`, `S/ 467 K`, `S/ 1.2 M`; porcentajes con un decimal en participación
  (52.8%) y enteros en crecimiento (+35%); variaciones de share en `pp`; signo explícito (+/–).
- Pie de página: `VIVA CONSULTING EMPRESAS  ·  ANÁLISIS CORPORATIVO · <CLIENTE> · <TEMA> · DIRECTORIO  ·  CONFIDENCIAL`
  (se pasa como `"footer"` en el spec).
- Recomendaciones: verbo en infinitivo + objeto + por qué con su cifra ("Proteger Lima Este: es el 53% del negocio…").
