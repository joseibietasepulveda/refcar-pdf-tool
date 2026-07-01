# Schemas del proyecto

Estos schemas separan el pipeline en tres capas:

1. `extraction.schema.json`
   - representa la salida literal por PDF;
   - guarda campos extraidos, evidencia, tablas y estado de extraccion;
   - identidad de cotizacion usa `identity.insurer_name` (no `insurer`).

2. `analysis.schema.json`
   - representa la normalizacion y analisis del caso completo;
   - junta **poliza actual (opcional)** + cotizaciones, o 4 cotizaciones sin poliza (`source_documents` minimo 3);
   - `current_policy` puede ser objeto o `null` (sin seguro vigente);
   - agrega comparaciones, etiquetas de mejora, extras, recomendacion e insight;
   - coberturas Refcar ampliadas en `currentPolicy` y `offerAnalysis`:
     - `rc`, `rc_emergente`, `rc_moral`, `rc_lucro_cesante`, `rc_exceso`
     - `auto_replacement`, `copago_reemplazo`
     - `workshop`, `reposicion_a_nuevo`, `perdida_total`
     - `assistance`, `asiento_pasajeros`, `defensa_penal`

3. `final-render.schema.json`
   - representa el payload final que recibe el renderer de PDF;
   - ya viene listo para pintar bloques, columnas, labels y textos finales.

Los archivos canonicos viven en `app/schemas/`; la carpeta `schemas/` en la raiz del repo se mantiene sincronizada.

## Flujo sugerido

`pdf(s) -> extraction -> analysis -> [editor manual] -> pdf comparativo Refcar`

## Reglas deterministicas (codigo, no schema)

- **Tablas en extraccion:** `pdf_reader.convert_tables_to_markdown` anexa tablas al texto del LLM.
- **HDI 11 cuotas:** `pipeline.postprocess_hdi_extractions` filtra otras modalidades antes del analisis.
- **11 cuotas en extraccion y analisis:** los prompts y `extraction_domain_instructions.md` obligan a **buscar en el PDF** la modalidad de 11 cuotas en cotizaciones; el PDF comparativo fija la etiqueta de cuotas base en **11 cuotas** y el texto de metodologia lo recuerda cuando aplica.
- **UF:** `uf_reference.apply_canonical_uf` tras el analisis.
- **Rol → badge PDF:** en Streamlit el rol por cotización (Básico / Equilibrado / Pro) alimenta `offer_tier_overrides` al generar el PDF; no hay columna Tier separada en la UI. En modo 4 cotizaciones, la cuarta oferta usa color café.
- **RC en exceso:** `rc_exceso` se extrae y compara como una capa adicional separada de la RC base; solo aplica cuando el documento la declara explícitamente.
- **Equivalencias UF:** `_analysis_to_render` calcula los valores CLP de `0`, `3`, `5` y `10 UF` usando `context.uf_value_used`; la plantilla no contiene montos fijos.
- **Póliza actual en PDF:** `current_policy.deductible_uf` alimenta la celda de deducible (`Mismo de hoy · X UF`); `current_policy.monthly_premium_uf` alimenta `UF/mes`; `current_policy.monthly_premium_clp` alimenta `CLP/mes`. El deducible nunca debe aparecer como prima mensual.
- **Pie editable:** `analysis.footer` permite editar `broker_name` y `broker_website`; `_analysis_to_render` los propaga al branding y a la firma inferior.

## Principio clave

El renderer (`comparativo.html` + `pdf_generator.py`) no interpreta PDFs ni decide logica de negocio.

Solo debe:

- leer el JSON de analisis (via `_analysis_to_render`);
- aplicar el template visual Refcar (3 o 4 columnas);
- generar el PDF final con WeasyPrint.

Documentacion detallada: [especificacion-formato-comparativo.md](../especificacion-formato-comparativo.md) seccion 9.
