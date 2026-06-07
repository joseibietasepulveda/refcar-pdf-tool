# Plan de ejecucion

## 1. Objetivo del MVP

Construir una herramienta local para uso interno del corredor de seguros que permita:

- iniciar sesion;
- subir tres PDF de cotizaciones (`inicial`, `medio`, `pro`);
- seleccionar cual de los tres planes se recomienda;
- generar automaticamente un PDF final con un formato comercial fijo y consistente;
- abrir una vista de edicion manual del documento antes de descargarlo o enviarlo por WhatsApp.

El objetivo principal del MVP no es "usar IA para todo", sino reducir tiempo operativo, iteraciones manuales y costo de tokens. La mayor parte del trabajo debe resolverse con codigo deterministico y una capa acotada de IA solo donde realmente aporte valor.

## 2. Principios de producto y tecnologia

- `code-first`: el formateo final del PDF debe vivir en codigo, no en prompts largos.
- `structured data first`: primero extraer los datos clave de cada PDF a JSON; despues renderizar el PDF final desde una plantilla.
- `LLM as fallback`: usar modelos solo para extraccion dificil, normalizacion ambigua o recomendaciones de copy, no para maquetar el PDF entero.
- `human-in-the-loop`: el usuario siempre puede editar antes de descargar.
- `evaluation-driven`: cada cambio de agente o modelo debe medirse por costo, precision y tiempo total.

## 3. Arquitectura recomendada para el MVP local

### Frontend local

- App web local con login.
- Dashboard con formulario para:
  - subir PDFs de cotizacion (minimo 3) y poliza actual opcional;
  - asignar **rol** por archivo (Básico / Equilibrado / Pro / Póliza actual);
  - marcar **una** cotización ganadora (control radio, no checkboxes múltiples);
  - agregar observaciones manuales opcionales.
- Vista de resultado con:
  - preview del PDF final;
  - campos editables del contenido estructurado;
  - descarga del PDF;
  - futura opcion de guardar version.

### Backend local

- API con autenticacion.
- Pipeline de ingesta de PDFs.
- Extraccion a JSON por aseguradora.
- Motor de validacion y normalizacion.
- Generador de PDF final desde template HTML/CSS o libreria PDF.
- Registro de ejecuciones para comparar calidad, tiempo y costo por modelo/agente.

### Pipeline documental

1. Upload de 3 PDFs.
2. Deteccion de aseguradora y tipo de documento.
3. Extraccion de texto/tablas.
4. Parsing deterministico por reglas.
5. Fallback con LLM si faltan campos o el PDF viene muy desordenado.
6. Construccion de un JSON canonico comun.
7. Render del PDF final usando template fijo.
8. Edicion manual antes de descargar.

## 4. Fases de ejecucion

## Fase 0. Descubrimiento y dataset

Objetivo: entender bien los documentos reales y definir el contrato de datos.

Entregables:

- 3-10 sets reales de ejemplo:
  - `barato`;
  - `medio`;
  - `caro`;
  - `resultado final esperado`.
- inventario de aseguradoras y variaciones de formato;
- lista de campos obligatorios y opcionales;
- primer esquema JSON canonico.

Tareas:

- pedirte un primer set de 4 PDFs reales;
- identificar si los PDFs tienen texto seleccionable o son escaneados;
- documentar los campos que siempre deben aparecer en el PDF final;
- definir reglas de negocio de la recomendacion.

Riesgo principal:

- si los PDFs cambian mucho entre aseguradoras o entre meses, necesitaremos parsers por proveedor y version.

## Fase 1. Contrato de datos y template final

Objetivo: sacar el formato final del mundo del prompt y llevarlo a codigo.

Entregables:

- `schema` JSON de cotizacion canonica;
- mapping por aseguradora;
- diseño del PDF final;
- template reproducible del documento de salida.

Tareas:

- comparar los 3 PDFs originales con el PDF final esperado;
- definir secciones del documento final;
- decidir si el PDF final se genera desde HTML/CSS + Playwright o desde React PDF / pdf-lib;
- modelar valores como:
  - aseguradora;
  - precio;
  - coberturas;
  - deducible;
  - vigencia;
  - restricciones;
  - observaciones;
  - recomendacion.

## Fase 2. MVP local funcional

Objetivo: tener la herramienta operativa en local de punta a punta.

Entregables:

- login simple;
- pantalla de upload de PDFs (min. 3 cotizaciones; modo alternativo de 4 cotizaciones sin poliza);
- asignacion de rol y seleccion unica de recomendado;
- procesamiento automatico;
- pantalla de preview/edicion (sin Tier duplicado en UI);
- descarga del PDF final.

Tareas:

- construir frontend local;
- construir backend y storage local;
- guardar archivos y JSON intermedios;
- implementar un parser base;
- generar el PDF final desde template;
- agregar logs y trazabilidad por ejecucion.

Decision recomendada:

- mantener el login simple para el MVP: usuario y password administrados por base de datos local.

## Fase 3. Capa de agentes y comparacion de modelos

Objetivo: probar agentes/modelos sin poner en riesgo costo ni consistencia.

Entregables:

- interfaz para elegir estrategia de procesamiento;
- tabla comparativa por corrida;
- benchmark por aseguradora;
- politica de fallback.

Estado parcial implementado:

- la interfaz de cliente expone dos perfiles centralizados en `MODEL_PROFILES`: **Estándar** → `google/gemini-3.1-flash-lite` y **Pro** → `google/gemini-3.1-pro-preview`;
- el modelo por defecto para produccion es **Estándar**, estable y economico;
- `OpenRouterClient.fetch_model_prices()` consulta `/models` y el historial registra el costo estimado de la corrida;
- para evitar JSON cortado, el cliente usa modo JSON cuando el modelo lo soporta, adapta el maximo de salida de `analysis` hasta **65.536 tokens**, reintenta si recibe `finish_reason = "length"` o JSON incompleto y contabiliza el costo de esos intentos;
- el historial persiste extracciones + analisis, registra `thinking_tokens` y modelo resuelto, y colapsa duplicados exactos heredados de reruns anteriores sin borrar los archivos fuente;
- sigue pendiente definir una cadena automatica de fallback entre modelos distintos cuando una familia no este disponible.

Estrategia:

- `Pipeline A`: solo codigo/reglas.
- `Pipeline B`: codigo + LLM chico para extraer campos faltantes.
- `Pipeline C`: codigo + agente mas potente para PDFs complejos.

Metricas a medir:

- porcentaje de campos correctamente extraidos;
- tiempo total por documento;
- costo estimado por corrida;
- numero de correcciones manuales;
- tasa de regeneracion;
- similitud con el PDF objetivo.

Regla clave:

- el sistema no debe llamar a un modelo caro por defecto. Solo si falla el parser deterministico o si la confianza es baja.

## Fase 4. Endurecimiento operativo

Objetivo: volver el sistema vendible como servicio mensual.

Entregables:

- manejo de errores y reintentos;
- versionado de templates;
- auditoria de cambios manuales;
- exportacion limpia;
- backups de configuracion;
- panel de administracion basico.

Tareas:

- registrar cada PDF subido y cada salida;
- detectar cuando cambia el formato de una aseguradora;
- separar configuracion por cliente si luego hay mas de uno;
- preparar despliegue web posterior.

## Fase 5. Migracion a web

Objetivo: pasar del MVP local a un producto multiusuario.

Entregables:

- autenticacion segura;
- almacenamiento cloud;
- colas para procesamiento;
- panel web multiusuario;
- control de costos por cliente.

Cambios esperables:

- mover archivos a object storage;
- mover procesamiento pesado a workers;
- separar frontend y backend;
- preparar monitoreo y billing.

Criterio inicial de despliegue para el primer cliente:

- usar Vercel como destino de la version web;
- guardar `OPENROUTER_API_KEY` como variable de entorno exclusiva del backend, sin exponerla al frontend;
- comenzar sin limite interno de corridas: el uso esperado es de unas **100 corridas por mes**. El costo historico observado rondaba **USD 0,02 por corrida**, pero debe recalibrarse con registros nuevos porque antes no incluia la llamada final de analisis;
- cargar inicialmente **USD 20** en OpenRouter y revisar el saldo de forma periodica;
- mantener las metricas de costo por corrida para detectar cambios de precio o consumo antes de ajustar la politica.

Nota tecnica: el MVP Streamlit + WeasyPrint vigente no se despliega en Vercel sin adaptacion. La migracion debe separar la interfaz web del procesamiento Python o mover el pipeline a un servicio compatible con tareas de mayor duracion.

## 5. Stack sugerido

## Opcion recomendada

- Frontend: `Next.js` o `React` con interfaz web local.
- Backend: `Node.js` con API server.
- Base de datos: `SQLite` en MVP local.
- Auth: tabla local de usuarios con sesiones.
- PDFs:
  - extraccion: `pdfplumber`, `pdf-parse`, `PyMuPDF` o combinacion;
  - OCR fallback: `Tesseract` o servicio posterior;
  - generacion final: HTML/CSS + `Playwright` para imprimir a PDF.

## Alternativa si priorizamos velocidad sobre uniformidad de stack

- Frontend: `Next.js`.
- Backend parser: `Python` para extraccion de PDFs.
- Orquestacion: API HTTP o job runner entre Node y Python.

Esto puede ser mejor si los PDFs vienen complejos, porque Python tiene mejor ecosistema para parsing documental.

## 6. Backlog priorizado

## Prioridad alta

- definir schema canonico;
- recibir ejemplos reales;
- construir template final en codigo;
- hacer upload de 3 PDFs;
- generar primer PDF final reproducible;
- habilitar edicion manual;
- descargar PDF.

## Prioridad media

- login y sesiones;
- historial de corridas;
- score de confianza por campo;
- seleccion de estrategia/agente;
- comparador entre versiones.

## Prioridad futura

- integracion con WhatsApp;
- envio automatico;
- firma visual del corredor;
- multiempresa;
- panel de metrics y billing.

## 7. Riesgos y mitigaciones

- `Riesgo`: PDFs distintos por aseguradora.
  - `Mitigacion`: parser por proveedor + contrato JSON comun.
- `Riesgo`: PDFs escaneados o con mala calidad.
  - `Mitigacion`: OCR fallback y cola de revision manual.
- `Riesgo`: costo de tokens sube mucho.
  - `Mitigacion`: parser deterministico primero, modelo pequeno despues, modelo caro solo por excepcion.
- `Riesgo`: inconsistencia del resultado final.
  - `Mitigacion`: template fijo en codigo y validacion por schema.
- `Riesgo`: exceso de correcciones manuales.
  - `Mitigacion`: guardar cambios manuales para aprender reglas futuras.

## 8. Orden exacto de trabajo recomendado

1. Conseguir 1 set real de `3 PDFs + 1 PDF final esperado`.
2. Definir `schema` JSON canonico.
3. Construir template final del PDF.
4. Implementar parser para 1 aseguradora o 1 tipo de documento.
5. Conectar upload -> parse -> JSON -> template -> PDF.
6. Agregar editor manual y descarga.
7. Medir tiempo/costo/calidad.
8. Repetir con mas aseguradoras.
9. Recién despues comparar agentes/modelos.
10. Cuando el flujo local sea estable, migrar a web.

## 9. Siguiente paso inmediato

El siguiente paso que mas desbloquea el proyecto es que me compartas el primer set real de:

- PDF barato;
- PDF medio;
- PDF caro;
- PDF final esperado.

Con eso podemos construir:

- el `schema` real;
- el parser inicial;
- el template de salida;
- la primera version del flujo local.

## 10. Estado actual vs plan (mayo 2026)

El repositorio ya implementa un MVP local distinto al stack sugerido en la seccion 5, pero alineado a los principios de producto:

| Plan original | Implementado hoy |
|---------------|------------------|
| Login | Pendiente (Streamlit sin auth) |
| Upload 3 PDFs + poliza | Streamlit: min. 3 cotizaciones, poliza opcional; modo alternativo de 4 cotizaciones sin poliza |
| Marcar recomendado | **Radio** de ganador unico entre cotizaciones |
| Rol / tier comercial | Solo **Rol** en carga; el rol define badge PDF (`offer_tier_overrides`) |
| Parser deterministico | LLM + reglas post-extraccion (HDI 11 cuotas, UF canonica) |
| Template PDF en codigo | `comparativo.html` + WeasyPrint |
| Editor manual | Expanders por seccion; sin selector Tier por oferta |
| 11 cuotas | Prompts + PDF con **Cuotas base: 11 cuotas**; busqueda explicita en extraccion |
| RC en exceso | Campo `rc_exceso` separado de RC base en extraccion, analisis, editor y PDF |
| Equivalencias UF | Referencias `0 / 3 / 5 / 10 UF` calculadas dinamicamente con la UF canonica de cada corrida |
| Pie del corredor | Editable en Streamlit y consumido por el renderer (`broker_name`, `broker_website`) |
| Regenerar PDF | Se puede editar y volver a generar durante la misma sesion; no requiere reiniciar Streamlit |

Archivos clave: `app/web_app.py`, `app/src/pipeline.py`, `app/src/prompts.py`, `app/templates/comparativo.html`. Detalle en `context.md` y `especificacion-formato-comparativo.md` seccion 9.
