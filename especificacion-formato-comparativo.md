# Especificacion del formato comparativo

## Objetivo de este documento

Separar el PDF final de comparacion en dos capas:

- `estructura fija`: layout, bloques, orden y reglas visuales/editoriales;
- `campos variables`: datos que deben extraerse o derivarse desde:
  - la poliza actual;
  - la cotizacion 1;
  - la cotizacion 2;
  - la cotizacion 3.

Este documento sirve como base para:

- definir el `schema` del proyecto;
- decidir que va por codigo y que va por agentes;
- construir el renderer del PDF final;
- construir el parser documental.

## Vision general

El PDF final no es una simple concatenacion de PDFs de entrada (tipicamente cotizaciones, mas poliza actual si existe). Es una pieza comercial y comparativa que:

- puede usar la poliza actual como `baseline` (opcional en plantilla Refcar);
- homogeniza la comparacion por deducible;
- recalcula mensualidades en pesos usando una UF comun;
- clasifica si una cobertura `mejora`, `queda igual` o eventualmente `empeora`;
- sintetiza informacion tecnica de aseguradoras en lenguaje comercial;
- prioriza una recomendacion por sobre las otras alternativas.

Por lo tanto, hay tres tipos de contenido en el PDF final:

- `contenido fijo`: siempre aparece y siempre en el mismo orden;
- `contenido variable extraido`: sale de los 4 PDFs de entrada;
- `contenido variable derivado/editorial`: se calcula o redacta a partir de los datos extraidos.

## 1. Estructura fija del PDF

## 1.1 Encabezado institucional

Bloque fijo.

Elementos:

- logo principal del corredor o marca;
- logo secundario;
- fecha en esquina superior derecha;
- linea horizontal de separacion.

Reglas:

- el branding deberia ser configurable;
- la fecha puede ser automatica o editable;
- este bloque no depende del contenido tecnico de las polizas.

## 1.2 Titulo principal

Bloque fijo con texto variable.

Formato:

- `Detalle Comparativo — {marca} {modelo} {anio}`

Campos variables:

- marca;
- modelo;
- anio.

Fuente principal:

- preferentemente poliza actual;
- fallback a la opcion recomendada o a la primera cotizacion consistente.

## 1.3 Franja de identificacion del caso

Bloque fijo con etiquetas fijas y valores variables.

Formato:

- `Asegurado: ...`
- `Vehiculo: ...`
- `Patente: ...`
- `Uso: ...`

Campos variables:

- nombre asegurado;
- vehiculo corto;
- patente;
- uso.

Fuentes:

- poliza actual;
- cotizaciones nuevas para validar consistencia.

## 1.4 Bloque pedagogico "Que es el deducible"

Bloque fijo en ubicacion y funcion.

Componentes:

- pregunta fija;
- texto explicativo breve.

Este contenido puede ser:

- texto fijo parametrizable;
- editable desde configuracion;
- no necesita salir de los PDFs.

Funcion:

- traducir el concepto para cliente final;
- preparar el resto de la lectura;
- justificar por que el deducible es la llave de comparacion.

## 1.5 Bloque "Tu seguro hoy"

Bloque fijo en posicion, estructura y etiquetas.

Formato general:

- titulo fijo: `TU SEGURO HOY — {aseguradora/producto}`
- linea resumen con:
  - deducible actual;
  - prima mensual UF;
  - prima mensual CLP;
  - RC;
  - auto de reemplazo;
  - taller;
  - asistencia.

Funcion:

- definir el baseline comercial;
- permitir comparar ahorro y mejora contra la situacion actual.

## 1.6 Franja explicativa de comparacion

Bloque fijo con texto parcialmente variable.

Contenido base:

- se informa que los precios se muestran comparando las versiones de las nuevas cotizaciones con el mismo deducible que tiene hoy el cliente;
- se agrega un insight comercial corto sobre la recomendacion.

Este bloque tiene dos capas:

- una capa fija de explicacion metodologica;
- una capa variable de insight o tesis comercial.

## 1.7 Cuerpo principal de comparacion en columnas

Bloque fijo en estructura, no en contenido.

Debe haber columnas segun el modo:

- columna alternativa 1;
- columna alternativa 2;
- columna alternativa 3.

La primera puede o no ser la recomendada, pero el layout actual pone arriba la recomendada.

Cada columna mantiene la misma anatomia:

1. etiqueta comercial corta derivada del **rol** asignado en Streamlit por cotizacion (`Básico`, `Equilibrado`, `Pro` → badges tipo `④ OPCIÓN ECONÓMICA`, `★ MEJOR OPERACIONAL`, `+ OPCIÓN PREMIUM`). No existe selector de Tier separado en la UI; el rol alimenta `offer_tier_overrides` en el render. En JSON de analisis, `commercial_tier` debe ser coherente con el `document_role` de cada extraccion;
2. nombre del producto;
3. insignia de recomendacion si corresponde;
4. precio mensual en UF;
5. precio mensual estimado en CLP;
6. deducible comparado + modalidad/cuotas;
7. ahorro mensual vs hoy;
8. bloque de comparacion de coberturas:
   - responsabilidad civil;
   - auto de reemplazo;
   - taller;
   - asistencia;
9. bloque de extras destacados;
10. mini tabla de deducibles alternativos, solo en la recomendada;
11. resumen editorial final.

## 1.8 Mini tabla de deducibles alternativos

Bloque fijo opcional.

En el ejemplo, solo aparece en la opcion recomendada.

Estructura:

- lista de deducibles alternativos;
- precio mensual en UF para cada deducible;
- cuando hay UF de referencia en contexto (o CLP ya calculado en JSON), tambien estimacion **CLP** en la misma fila de la tabla del PDF;
- marca del deducible actual;
- marca de la `PROPUESTA`.

Funcion:

- transformar la recomendacion en accion comercial;
- mostrar que hay una mejor combinacion precio/riesgo;
- usar el presupuesto actual como ancla.

## 1.9 Bloques de resumen final por alternativa

Bloque fijo en el cierre del documento.

Siempre hay tres cajas o parrafos de cierre, uno por alternativa.

Funcion:

- sintetizar la tesis comercial de cada opcion;
- no repetir datos;
- dejar una conclusion de venta.

## 1.10 Pie de pagina

Bloque fijo.

Elementos:

- UF usada para el calculo;
- fecha de referencia de la UF;
- disclaimer de vigencia / inspeccion / aprobacion;
- nombre comercial del corredor;
- sitio web u otra firma institucional.

## 2. Campos variables que hay que extraer

## 2.1 Campos de cabecera del caso

Campos:

- `case_date`
- `insured_name`
- `vehicle_make`
- `vehicle_model`
- `vehicle_year`
- `vehicle_display_name`
- `plate`
- `usage`

Fuentes:

- principalmente poliza actual;
- validacion cruzada con las cotizaciones del set.

Notas:

- `vehicle_display_name` puede ser derivado como `{marca} {modelo} {anio}`;
- la patente puede venir inconsistente en documentos viejos o de muestra, por lo que conviene permitir override manual.

## 2.2 Campos de la poliza actual

Campos estructurales:

- `current_insurer`
- `current_product_name`
- `current_policy_number`
- `current_deductible_uf`
- `current_total_premium_uf_annual`
- `current_installment_value_uf`
- `current_installment_count`
- `current_payment_method`
- `current_monthly_premium_uf`
- `current_monthly_premium_clp`

Campos de comparacion:

- `current_rc_summary`
- `current_rc_type`
- `current_auto_replacement_summary`
- `current_workshop_summary`
- `current_assistance_summary`
- `current_assistance_tier`
- `current_feature_highlights`

Campos utiles de soporte:

- `current_has_brand_workshop`
- `current_has_intelligent_deductible`
- `current_has_zero_km_or_new_replacement`
- `current_auto_replacement_days`
- `current_auto_replacement_copay`
- `current_rc_amount_uf`
- `current_rc_mode`

Fuente:

- poliza anterior.

### 2.2.1 Coberturas plantilla Refcar (implementadas en `analysis.schema.json`)

Ademas de RC general, auto de reemplazo, taller y asistencia, la plantilla Refcar exige filas dedicadas mapeadas a `comparisonResult` en `current_policy` y en cada `offer`:

| Campo schema | Etiqueta en PDF |
|--------------|-----------------|
| `rc_emergente` | RC Emergente |
| `rc_moral` | RC Daño Moral |
| `rc_lucro_cesante` | RC Lucro Cesante |
| `rc_exceso` | RC en Exceso |
| `copago_reemplazo` | Copago Auto Reemplazo |
| `reposicion_a_nuevo` | Reposición a Nuevo |
| `perdida_total` | Umbral Pérdida Total |
| `asiento_pasajeros` | Asiento Pasajeros |
| `defensa_penal` | Defensa Penal |

## 2.3 Campos de cada cotizacion nueva

Para cada alternativa:

- `quote_key`
- `insurer`
- `product_name`
- `commercial_tier`
- `recommended`

Datos de precio:

- `available_deductibles`
- `selected_comparison_deductible_uf`
- `selected_payment_method`
- `selected_installment_count`
- `selected_monthly_premium_uf`
- `selected_monthly_premium_clp`
- `selected_annual_premium_uf`
- `monthly_savings_vs_current_clp`

Datos de cobertura:

- `rc_summary`
- `rc_amount_uf`
- `rc_mode`
- `auto_replacement_summary`
- `auto_replacement_days`
- `auto_replacement_copay`
- `workshop_summary`
- `has_brand_workshop`
- `assistance_summary`
- `assistance_tier`
- `feature_highlights`
- `extra_highlights`

Datos extendidos:

- `has_intelligent_deductible`
- `has_zero_km_or_new_replacement`
- `passenger_coverage_summary`
- `defense_summary`
- `travel_assistance_summary`
- `accessory_theft_summary`
- `key_reimbursement_summary`
- `home_fire_summary`

Fuente:

- cada cotizacion del set.

## 2.4 Tabla de precios por deducible (todas las columnas en plantilla Refcar)

En la plantilla anterior solo la columna recomendada mostraba la mini tabla de deducibles. En **Refcar**, cada columna de oferta incluye la matriz **Precio mensual según deducible** (filas tipicas: 0, 3, 5 y 10 UF con prima UF y CLP).

Campos en `analysis.schema.json` → `offers[].deductible_options[]`:

- `deductible_uf`
- `monthly_premium_uf`
- `monthly_premium_clp`
- `is_same_as_current` (marca fila igual al deducible de hoy)
- `is_proposed` (marca la propuesta comercial del corredor)

Fuente:

- tabla de primas de cada cotizacion (extraida con tablas markdown + LLM).

## 2.5 Campos del pie

Campos:

- `uf_value_used`
- `uf_reference_date`
- `quote_validity_note`
- `inspection_approval_note`
- `broker_signature_name`
- `broker_website`

Fuente:

- parcialmente de internet o servicio UF;
- parcialmente configuracion editable del corredor (`analysis.footer.broker_name`, `analysis.footer.broker_website`);
- parcialmente texto legal fijo.

### 2.5.1 Equivalencias CLP de deducible

La franja explicativa superior conserva las referencias `0`, `3`, `5` y `10 UF`, pero sus equivalencias CLP no son literales ni constantes. `_analysis_to_render` las calcula en cada render multiplicando `context.uf_value_used` por cada referencia y luego aplica formato chileno mediante `_fmt_clp`.

Ejemplo con `UF = $40.594`:

| Referencia | Equivalencia renderizada |
|------------|--------------------------|
| `0 UF` | `$0` |
| `3 UF` | `$121.782` |
| `5 UF` | `$202.970` |
| `10 UF` | `$405.940` |

## 3. Campos derivados y no literales

Esta seccion es critica, porque muchos elementos del PDF final no salen literal de ningun PDF de entrada.

## 3.1 Prima mensual en CLP normalizada

No debe confiarse ciegamente en los pesos impresos en cada cotizacion porque:

- pueden usar otra UF;
- pueden usar otra fecha;
- pueden tener otro numero de cuotas o modalidad destacada.

Conviene derivar:

- `monthly_premium_clp = monthly_premium_uf * uf_value_used`

Esto asegura consistencia visual en todo el comparativo.

## 3.2 Ahorro mensual vs hoy

Campo derivado:

- `monthly_savings_vs_current_clp = current_monthly_premium_clp - selected_monthly_premium_clp`

Notas:

- puede ser ahorro o sobrecosto;
- la UI deberia soportar ambos casos;
- el copy cambia si el resultado es positivo o negativo.

## 3.3 Etiqueta comercial del producto

Ejemplos:

- `PREMIUM`
- `INTERMEDIA`

Esto no suele venir textual en la cotizacion.

Puede salir de:

- configuracion manual del corredor;
- reglas por producto;
- override editable en interfaz.

## 3.4 Resumen corto de RC

Ejemplos:

- `UF 5.000 total`
- `UF 2.000 por subseccion (DE + DM + LC)`
- `UF 2.000 limite unico combinado`

Este texto es derivado.

Requiere interpretar:

- si la RC es limite unico combinado;
- si tiene subsecciones separadas;
- si existe exceso sobre RC base;
- cual es el monto comercialmente relevante.

## 3.5 Juicio de mejora / igual / peor

Cada una de estas comparaciones es derivada:

- `rc_comparison_label`
- `auto_replacement_comparison_label`
- `workshop_comparison_label`
- `assistance_comparison_label`

Valores posibles:

- `MEJORA`
- `IGUAL`
- `PEOR`
- opcionalmente `MIXTO`

Esto exige reglas comparativas, no extraccion literal.

## 3.6 Resumen de auto de reemplazo

Ejemplos:

- `Ilimitado · copago $4.000/dia`
- `Hasta 90 dias · copago $4.000/dia`
- `60 dias`

Esto requiere sintetizar:

- dias;
- copago;
- categoria de vehiculo;
- restricciones relevantes.

## 3.7 Resumen de taller

Ejemplos:

- `De marca`
- `De marca, sin restriccion de antiguedad`

Esto puede salir de:

- cobertura explicita;
- clausula de taller de marca;
- interpretacion editorial si la poliza lo expresa juridicamente.

## 3.8 Resumen de asistencia

Ejemplos:

- `Premium`
- `Premium + viaje internacional familiar`
- `Intermedia · solida en ruta`

Este es uno de los campos mas editoriales del documento.

Puede requerir:

- taxonomia manual de niveles de asistencia;
- deteccion de extras fuertes;
- copy corto generado desde reglas.

## 3.9 Extras destacados

Ejemplos:

- `Reposicion a nuevo 24 meses`
- `Deducible inteligente`
- `Asiento pasajero UF 250`
- `Defensa penal UF 300`
- `Reembolso de llaves`
- `Incendio hogar UF 200`

Estos extras salen de una lista mayor de coberturas y se filtran.

O sea, aqui no solo se extrae:

- tambien se prioriza.

## 3.10 Insight del bloque verde

Ejemplo del caso:

- `Con HDI MAX, por lo que pagas hoy incluso podrias bajar el deducible a 3 UF y mejorar todas las coberturas.`

Esto es 100% derivado.

Necesita:

- detectar la recomendada;
- comparar precio actual vs opciones de deducible de la recomendada;
- construir una frase comercial corta.

## 3.11 Resumen editorial final por columna

Ejemplos:

- `HDI MAX es el mejor equilibrio del set...`
- `FID es la opcion con mas extras...`
- `Zurich es la alternativa mas economica...`

Estos textos son editoriales.

Idealmente salen de:

- plantillas;
- reglas;
- campos derivados;
- edicion manual opcional.

No conviene depender de un LLM libre para esto en cada corrida.

## 4. Reglas de negocio visibles en este formato

## 4.1 La poliza actual (opcional desde plantilla Refcar)

La plantilla **Refcar** admite dos modos de operacion:

| Modo | Entradas | PDF resultante |
|------|----------|----------------|
| Con seguro vigente | 1 poliza actual + 3 cotizaciones | 4 columnas: «Tu seguro hoy» + 3 ofertas |
| Sin seguro vigente | 3 cotizaciones o 4 cotizaciones | Solo ofertas nuevas; con 4 cotizaciones la cuarta columna usa color café |

**Con poliza actual** se habilita:

- baseline de deducible (`context.base_deductible_uf`);
- ahorro o sobrecosto mensual vs hoy;
- etiquetas MEJORA / IGUAL / PEOR / MIXTO por cobertura;
- columna «Tu seguro hoy» en el PDF.

**Sin poliza actual** (`current_policy: null` en `analysis.schema.json`):

- el comparativo se arma solo con cotizaciones; puede operar con 3 o 4 propuestas;
- las etiquetas de comparacion son relativas al set de propuestas;
- no se muestra ahorro vs hoy ni badges de mejora/peor;
- los textos **En simple** comparan contra el set completo: más barata, más completa, mejor equilibrio o más cara con mejores coberturas.

## 4.2 La comparacion principal se hace al mismo deducible

Regla:

- primero se busca en cada cotizacion la opcion con el mismo deducible del seguro actual;
- esa opcion es la usada para la comparacion principal.

## 4.3 La recomendada puede usar una propuesta distinta

Aunque la comparacion principal sea a igual deducible, la opcion recomendada puede mostrar una mejor combinacion alternativa.

Ejemplo:

- comparo todo a 10 UF;
- pero propongo contratar la recomendada a 3 UF porque cuesta menos que el seguro actual.

## 4.4 El documento no compara todas las coberturas

Prioriza:

- RC;
- auto de reemplazo;
- taller;
- asistencia;
- extras destacados.

Eso sugiere que el `schema` de comparacion no debe intentar mostrar todas las clausulas de la cotizacion.

## 4.5 Hay una taxonomia comercial encima del dato tecnico

Conceptos como:

- `Premium`
- `Intermedia`
- `solida en ruta`
- `mejor equilibrio`
- `opcion con mas extras`

son una capa comercial adicional.

Esto sugiere que el sistema necesita:

- datos tecnicos;
- reglas de interpretacion;
- overrides manuales.

## 5. Propuesta de separacion tecnica

## 5.1 Estructura fija del renderer

Deberia vivir en codigo como template.

Incluye:

- layout general;
- estilos;
- tipografias;
- colores;
- posiciones;
- rotulos;
- orden de bloques;
- tratamiento visual de recomendada;
- estilos de mejora/igual/peor;
- pie de pagina.

## 5.2 Datos de entrada del renderer

Deberian venir en un JSON ya limpio.

El renderer no deberia:

- abrir PDFs;
- interpretar clausulas;
- decidir si algo mejora;
- buscar equivalencias de deducible.

El renderer solo deberia:

- recibir datos ya preparados;
- imprimirlos en el formato correcto.

## 5.3 Parser documental

Debe encargarse de:

- leer la poliza actual;
- leer las cotizaciones;
- detectar aseguradora y producto;
- extraer precios por deducible;
- extraer coberturas clave;
- extraer medios de pago y cuotas;
- extraer extras potenciales.

## 5.4 Capa de reglas de negocio

Debe encargarse de:

- homologar deducibles;
- elegir la opcion de comparacion;
- calcular CLP con UF comun;
- calcular ahorro;
- clasificar mejora/igual/peor;
- construir resumentes tecnicos cortos;
- preparar los extras destacados;
- preparar textos editoriales plantillados.

## 5.5 Capa manual o de revision

Debe permitir editar:

- recomendada (definida en carga por radio; editable indirectamente via JSON si aplica);
- insight del bloque verde;
- extras destacados;
- resumen final por alternativa;
- algun dato puntual extraido incorrectamente.

Ya **no** se edita en UI un Tier comercial separado del rol: la etiqueta de columna viene del rol asignado al subir PDFs.

## 6. Campos que probablemente necesiten override manual

- nombre corto del seguro actual;
- nombre comercial corto de la aseguradora;
- nivel de asistencia (`premium`, `intermedia`, etc.);
- texto editorial del insight principal;
- texto editorial de los tres resumentes inferiores;
- orden final de las columnas (fijado por posicion de subida);
- marca de `recomendada` (en carga: radio de ganador unico);
- `PROPUESTA` de deducible alternativa.

La etiqueta comercial de columna (badge) se deriva del **rol** en carga, no de un override manual de Tier en el editor.

## 7. Recomendacion de schema de salida para el comparativo

```json
{
  "meta": {
    "date_label": "Abril 2026",
    "uf_value_used": 39947.6,
    "uf_reference_date": "2026-04-17"
  },
  "insured": {
    "name": "Francisco Jose Soto Simpson",
    "vehicle_make": "Suzuki",
    "vehicle_model": "Jimny",
    "vehicle_year": 2025,
    "plate": "TWHW86",
    "usage": "Particular"
  },
  "current_policy": {
    "insurer": "BCI",
    "product_name": "Classic",
    "deductible_uf": 10,
    "monthly_premium_uf": 1.00,
    "monthly_premium_clp": 39948,
    "rc_summary": "UF 1.500",
    "auto_replacement_summary": "60 dias",
    "workshop_summary": "Taller de marca",
    "assistance_summary": "Intermedia"
  },
  "comparison_context": {
    "base_deductible_uf": 10,
    "methodology_note": "",
    "main_insight_note": ""
  },
  "offers": [
    {
      "position": 1,
      "recommended": true,
      "commercial_tier": "Premium",
      "insurer": "HDI",
      "product_name": "MAX",
      "comparison_deductible_uf": 10,
      "payment_method": "PAT",
      "installments": 11,
      "monthly_premium_uf": 0.68,
      "monthly_premium_clp": 27164,
      "monthly_savings_vs_current_clp": 12784,
      "rc": {
        "summary": "UF 5.000 total",
        "comparison_label": "MEJORA"
      },
      "auto_replacement": {
        "summary": "Ilimitado · copago $4.000/dia",
        "comparison_label": "MEJORA"
      },
      "workshop": {
        "summary": "De marca, sin restriccion de antiguedad",
        "comparison_label": "IGUAL"
      },
      "assistance": {
        "summary": "Premium",
        "comparison_label": "MEJORA"
      },
      "deductible_options": [],
      "extra_highlights": [],
      "summary_note": ""
    }
  ],
  "footer": {
    "validity_note": "",
    "broker_name": "Convision Corredores de Seguros SpA",
    "broker_website": "www.convision.cl"
  }
}
```

## 8. Conclusiones practicas

1. El PDF final usa una plantilla **Refcar** fija en codigo (HTML/CSS + WeasyPrint), alineada al PDF de referencia del cliente.
2. La mayor complejidad sigue en la transformacion de 3–4 PDFs heterogeneos a un JSON unificado (`analysis.schema.json`).
3. La poliza actual es **opcional**: sin ella el flujo opera con 3 cotizaciones o con el modo dedicado de 4 cotizaciones.
4. Una parte relevante del comparativo no es extraccion literal, sino interpretacion y redaccion comercial controlada.
5. El pipeline implementado separa:
   - extraccion documental (con tablas markdown, busqueda de **11 cuotas** en prompts y reglas HDI);
   - analisis LLM (coberturas Refcar ampliadas; primas/cuotas alineadas a modalidad 11 cuando consta en extraccion);
   - reglas deterministicas post-extraccion (UF, filtro 11 cuotas HDI);
   - render del PDF (cuotas base fijas en **11 cuotas**, sin linea de ejecutivo/a en cabecera);
   - editor manual y regeneracion instantanea sin nuevas llamadas al modelo.

## 9. Implementacion actual en el repositorio (`app/`)

Esta seccion enlaza la especificacion funcional con el codigo vigente tras la adaptacion **plantilla Refcar** y el despliegue Railway (junio 2026). Referencia visual del cliente: `PLANTILLA_BASE_Detalle_Comparativo_Refcar.pdf`.

### 9.1 Stack y ejecucion

- **Lenguaje:** Python 3.
- **Interfaz:** Streamlit (`app/web_app.py`) con flujo directo (ver 9.2.1), usable localmente y desplegada en Railway.
- **Login:** pantalla Refcar con logo corporativo; credenciales por `REFCAR_LOGIN_USER` y `REFCAR_LOGIN_PASSWORD`; sesion Streamlit con token firmado en URL para reconexiones.
- **Lanzador macOS:** `app/Ejecutar Herramienta Seguros.command`.
  - Arranca Streamlit en `http://localhost:8501` (`--server.port 8501`).
  - **Antes de iniciar**, libera el puerto 8501: detecta procesos en escucha con `lsof` y los cierra (`kill`, luego `kill -9` si persisten). Evita quedar colgado si quedó una instancia anterior abierta.
  - Instala dependencias la primera vez; lee `OPENROUTER_API_KEY` desde `MI_OPENROUTER_KEY.txt` si no está en el entorno.
- **Control de versiones/despliegue:** repositorio Git en la raíz del proyecto, conectado a GitHub/Railway. Rama estable `main`. `.gitignore` excluye claves, `.env`, `app/runs/` y archivos sensibles.
- **Railway:** `Dockerfile` en la raiz + `railway.json`; el contenedor usa `$PORT` y variables de entorno del servicio.
- **LLM:** OpenRouter (`httpx`). Modelo unico configurado en `app/src/config.py`. Clave: `OPENROUTER_API_KEY` en `.env` o `app/MI_OPENROUTER_KEY.txt`.
  - La interfaz no expone selector de modelo; usa **Estándar** → `google/gemini-3.1-flash-lite`.
  - `DEFAULT_PRIMARY_MODEL` es `google/gemini-3.1-flash-lite`: version estable y economica para produccion.
  - `OpenRouterClient.fetch_model_prices()` consulta `/models` antes de ejecutar el pipeline y obtiene tarifas, parametros soportados y limite de salida publicado para el modelo estándar.
  - Si el modelo soporta `response_format`, las llamadas se envian con modo JSON y `provider.require_parameters = true`.
  - En `analysis`, el cliente usa hasta **65.536 tokens** de salida cuando el modelo lo permite. Si OpenRouter informa `finish_reason = "length"` o devuelve JSON incompleto, el cliente reintenta con mas margen cuando existe capacidad disponible.
  - Las metricas agregan tokens, tiempo y costo de los reintentos pagados; tambien guardan cantidad de intentos, `finish_reason`, `thinking_tokens` y el modelo resuelto que OpenRouter devuelve. La tabla visible de historial muestra solo id de corrida, fecha y segundos.
  - La aplicacion no expone una cadena automatica de fallback entre modelos diferentes.
- **Lectura de PDF:** `pdfplumber` (`app/src/pdf_reader.py`): texto plano + **tablas convertidas a Markdown** anexadas al contexto del modelo.
- **Schemas JSON:** `app/schemas/extraction.schema.json`, `analysis.schema.json`, `final-render.schema.json` (copia sincronizada en `schemas/`).

### 9.2 Pipeline

Orquestado en `app/src/pipeline.py`:

**Extraccion**

- Una llamada LLM por PDF con `build_extraction_prompt` (`app/src/prompts.py`) + `extraction_domain_instructions.md`. Ambos obligan a **buscar la modalidad de 11 cuotas** en cotizaciones cuando el PDF la declara.
- `read_pdf` concatena al texto una seccion `## Tablas Estructuradas Extraídas del PDF` generada por `convert_tables_to_markdown`, preservando filas/columnas de primas por deducible y cuotas.

**Reglas deterministicas post-extraccion (antes del analisis)**

| Regla | Modulo | Comportamiento |
|-------|--------|----------------|
| HDI 11 cuotas | `pipeline.postprocess_hdi_extractions` | Si la aseguradora es HDI y hay opciones con `installments == 11`, se eliminan del JSON las opciones con otras cuotas (p. ej. 12). El analisis solo ve la modalidad de 11 cuotas (ej. UF 0,74 en ded. 10 UF, no UF 0,68 de 12 cuotas). |
| UF canonica | `uf_reference.apply_canonical_uf` | Tras el analisis, recalcula CLP y ahorros con la UF fijada. |

**Analisis**

- Una llamada LLM con `build_analysis_prompt` → `analysis.schema.json`.
- `source_documents`: minimo **3** documentos (3 cotizaciones; poliza actual opcional). El modo sin poliza permite 4 cotizaciones.
- `current_policy`: puede ser objeto completo o **`null`** si no hay seguro vigente.
- Coberturas obligatorias ampliadas (plantilla Refcar): ademas de `rc`, `auto_replacement`, `workshop`, `assistance`, el schema exige `rc_emergente`, `rc_moral`, `rc_lucro_cesante`, `rc_exceso`, `copago_reemplazo`, `reposicion_a_nuevo`, `perdida_total`, `asiento_pasajeros`, `defensa_penal` (cada una como `comparisonResult` con `summary` + `label`). `rc_exceso` es una capa adicional separada que opera tras agotar la RC base y no debe inferirse desde un LUC.

### 9.2.1 Interfaz Streamlit — maquina de estados

Flujo en `app/web_app.py` (`st.session_state.step`):

```mermaid
flowchart LR
  upload --> editor[editor]
  editor --> editor
```

| Fase | Paso | Que hace el usuario |
|------|------|---------------------|
| 1 | `upload` | Elige modo: **Póliza actual + cotizaciones** o **4 cotizaciones sin póliza actual**. Sube PDFs, asigna rol y ganador (el rol define tambien la etiqueta comercial de columna). La app usa el modelo estándar fijo. La UF se consulta automáticamente con reintentos/cache; el ingreso manual queda como respaldo desplegable. Boton **Iniciar Extraccion Documental** con estado inmediato de carga. |
| 2 | `editor` | Formulario por expanders: Asegurado/UF, Tu Seguro Hoy (si aplica), ofertas (sin selector Tier), Recomendacion. Edita cualquier campo del JSON de analisis. |
| 3 | (dentro de `editor`) | Boton **Generar PDF**: render local con WeasyPrint **sin nuevas llamadas al LLM**. Descarga inmediata. |

**Entrada minima:** 3 cotizaciones. **Entrada tipica con baseline:** 1 poliza + 3 cotizaciones. **Modo alternativo:** exactamente 4 cotizaciones sin poliza actual.

- Rol por archivo (Básico / Equilibrado / Pro / Póliza actual): para cotizaciones, la misma etiqueta alimenta `offer_tier_overrides` en el PDF.
- Un solo **ganador** (seleccion unica tipo radio entre cotizaciones) → columna con borde verde Refcar y badge recomendada.

**Modalidad 11 cuotas:** en extraccion y analisis se instruye buscar en cada PDF de cotizacion la fila u opcion de **11 cuotas** como referencia principal de prima y cuotas; el PDF comparativo muestra **Cuotas base: 11 cuotas** y el bloque de metodologia indica que las cotizaciones reflejan esa modalidad cuando el documento la declara.

### 9.3 Valor de la UF

Prioridad (`resolve_reference_uf`):

1. Manual en sidebar Streamlit si el usuario activa **Ingresar UF manualmente**.
2. Consulta automática a `https://mindicador.cl/api/uf` con `timeout`, `User-Agent`, reintentos y backoff corto.
3. Cache local (`app/runs/uf_reference_cache.json`) con la ultima UF valida obtenida.
4. `UF_REFERENCE_CLP` / `UF_REFERENCE_DATE` en `.env` como respaldo operativo.

Si todas las fuentes automaticas fallan, la interfaz muestra el error y pide activar **Ingresar UF manualmente**. No se intenta inferir la UF desde PDFs para produccion porque es menos estable y puede mezclar valores historicos de las aseguradoras.

### 9.4 Plantilla PDF Refcar (`comparativo.html`)

- **Formato:** A4 landscape.
- **Tipografia (mayo 2026):** cuerpo `10.8px`; coberturas, tablas y editorial `9.5px`; nombre de producto `13px`; footer `8px`. `line-height` compacto (`1.15` en body) para mantener densidad tipo plantilla Refcar.
- **Espaciado:** layout denso tipo plantilla Refcar — cabeceras de columna `70px`, separación horizontal entre columnas `9px`, tabla de precios con `min-height: 112px` y filas de cobertura compactas (`4.5px 12px` de padding).
- **Layout PDF (WeasyPrint):** página A4 landscape con `body` flex vertical de altura fija; columnas en `<table class="columns-table">`; coberturas en `<table class="coverages-table">` con bordes contenidos. Cada `.col-inner` reserva `110px` inferiores y su `.editorial-section` se fija con `position: absolute; bottom: 0`, manteniendo alineadas las lineas superiores de «En simple». El footer es un bloque final separado de `21px`.
- **Colores de columna por posicion** (no por tier comercial). El orden de columnas sigue la **posicion de subida** (1, 2, 3); la recomendada no se reordena al frente.

| Columna | Color cabecera | Hex |
|---------|----------------|-----|
| Tu seguro hoy (si hay poliza) | Gris | `#6B7280` |
| Oferta posicion 1 | Azul marino | `#0F1B5C` |
| Oferta posicion 2 | Celeste | `#1FB5E8` |
| Oferta posicion 3 | Naranja | `#F97316` |

- **Acento recomendada:** borde y badge verde `#7DD13F` (solo marca visual de recomendada; no define el color de cabecera).
- **Badges comerciales** (`+ OPCIÓN PREMIUM`, `★ MEJOR OPERACIONAL`, etc.): derivados del **rol** asignado a cada cotización en Streamlit (misma etiqueta Básico/Equilibrado/Pro); independientes del color de columna.
- **Layout columnas:**
  - Con `current_policy`: 4 columnas (Tu seguro hoy + 3 ofertas).
  - Sin `current_policy`: 3 o 4 columnas de ofertas. La cuarta usa café.
- **Cabecera:** franja institucional, metadatos asegurado/vehiculo, barra celeste con **UF referencia**, **Cuotas base: 11 cuotas** (fijo) y **fecha** (sin campo de ejecutivo/a comercial), explicacion de deducible con equivalencias CLP (0 / 3 / 5 / 10 UF) calculadas dinamicamente con la UF de referencia.
- **Por columna de oferta:**
  - Tabla **Precio mensual segun deducible** (hasta 4 filas reales: 0, 3, 5, 10 UF) en **todas** las columnas. Sin filas vacias de padding; la altura uniforme la garantiza el contenedor de la tabla.
  - Tabla de coberturas (`.coverages-table`) separada visualmente de la tabla de precios.
  - Filas de cobertura alineadas: RC emergente, RC moral, RC lucro cesante, **RC en exceso**, auto reemplazo, copago, taller, reposicion a nuevo, perdida total, asistencia, asiento pasajeros, defensa penal.
  - Badges MEJORA/IGUAL/PEOR solo si existe poliza actual.
  - Bloque **En simple** (resumen editorial completo, sin recorte) y extras destacados.
- **Render:** `_analysis_to_render` en `pdf_generator.py` mapea `analysis.schema.json` → variables Jinja. Asigna `column_theme` (`azul` / `celeste` / `naranja`) por `position` y ordena ofertas solo por posicion.

### 9.5 Persistencia y metricas

- Corridas en `app/runs/` (`run_store.py`): extracciones, analisis, metricas, ruta del PDF generado.
- El historial web visible muestra solo `run_id`, `fecha` y `tiempo_s`. Tokens, costo, modelo resuelto y detalles de intentos quedan persistidos internamente en los JSON de corrida, pero no se exponen en la tabla del cliente.
- Si la extraccion ya existe y falla el analisis, la app conserva los archivos intermedios y permite reintentar el paso de analisis sin volver a cargar PDFs ni rehacer toda la extraccion.
- Un PDF solo se renderiza y registra al pulsar explicitamente **Generar PDF**. Mostrar o descargar un PDF ya generado no crea una corrida nueva.
- Boton volver a cargar PDFs reinicia el flujo sin recargar la pagina completa.
- Dentro de una misma sesion Streamlit, el usuario puede editar campos y pulsar **Generar PDF** cuantas veces necesite; cada render toma los valores actuales del editor y no requiere cerrar la terminal.
- Streamlit detecta cambios de codigo durante desarrollo. Si una vista abierta conserva una version anterior, recargar el navegador suele bastar; reiniciar `Ejecutar Herramienta Seguros.command` es el ultimo recurso.

### 9.6 Dependencias clave

`streamlit`, `pdfplumber`, `httpx`, `jsonschema`, `jinja2`, `weasyprint`, `pandas`, `python-dotenv`. macOS: `brew install pango` + `DYLD_LIBRARY_PATH=/opt/homebrew/lib` si aplica.

### 9.7 Archivos tocados en la adaptacion Refcar

| Archivo | Rol |
|---------|-----|
| `app/schemas/analysis.schema.json` | Poliza opcional, coberturas Refcar incluida `rc_exceso`, pie editable, `minItems: 3` |
| `app/schemas/final-render.schema.json` | Contrato sincronizado con el payload real: columnas, coberturas Refcar, pie y equivalencias UF dinamicas |
| `app/src/pdf_reader.py` | Tablas → Markdown en el prompt |
| `app/src/pipeline.py` | Filtro HDI 11 cuotas |
| `app/src/number_utils.py` | Parser de numeros chilenos usado por el editor manual |
| `app/src/prompts.py` | Coberturas Refcar incluida `rc_exceso`; busqueda 11 cuotas; `commercial_tier` alineado a `document_role` |
| `app/templates/comparativo.html` | Layout landscape Refcar; tipografia, espaciado, colores por posicion, tabla sin filas fantasma, editorial completo; fila RC en Exceso; equivalencias UF dinamicas; sin linea Ejecutiva en subcabecera |
| `app/src/pdf_generator.py` | Mapeo 3/4 columnas, `column_theme`, orden por `position`, cuotas base **11 cuotas**, RC en exceso, pie editable y calculo CLP para `0 / 3 / 5 / 10 UF` |
| `app/web_app.py` | Login Refcar; flujo directo; modelo estándar fijo; UF automática resiliente con respaldo manual; carga con **Rol** + **radio ganador** (sin Tier); estado inmediato al iniciar extraccion; reintento de analisis; editor con RC en Exceso y pie del corredor; generar PDF reutilizable en la misma sesion |
| `app/Ejecutar Herramienta Seguros.command` | Lanzador macOS; libera puerto 8501 antes de Streamlit |
| `Dockerfile` / `railway.json` | Despliegue Railway desde GitHub, con puerto tomado de `$PORT` y dependencias de sistema para WeasyPrint |
| `.gitignore` (raiz) | Excluye claves, `.env`, `app/runs/`, entornos virtuales |

### 9.8 Despliegue web Railway

- Destino de la primera entrega: Railway conectado al repositorio GitHub `joseibietasepulveda/refcar-pdf-tool`.
- El servicio usa el `Dockerfile` de la raiz y respeta el puerto que Railway entrega en `$PORT`.
- `OPENROUTER_API_KEY` debe configurarse como variable de entorno exclusiva del backend y nunca quedar incluida en codigo ni en el navegador.
- Credenciales de login: `REFCAR_LOGIN_USER` y `REFCAR_LOGIN_PASSWORD` como variables de entorno. El usuario default local es `felipe_carmona`; la clave productiva debe vivir solo en Railway.
- Opcionales operativos: `UF_REFERENCE_CLP` y `UF_REFERENCE_DATE` para respaldo manual de UF si `mindicador.cl` deja de responder.
- Supuesto inicial de consumo: unas **100 corridas por mes**, con **USD 20** cargados en OpenRouter y revision periodica manual del saldo. La referencia historica de cerca de **USD 0,02 por corrida** debe recalibrarse con registros nuevos: el historial anterior omitía la llamada final de analisis.
- En la primera entrega no se considera necesario imponer un limite interno de corridas, pero se mantienen metricas internas de costo para detectar desvios.
- No se deben subir PDFs reales, `.env`, `app/runs/` ni archivos de ejemplo sensibles al repositorio.
