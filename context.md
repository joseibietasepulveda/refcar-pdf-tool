# Contexto del proyecto

## Nombre tentativo

Herramienta de armado de propuestas de seguros automotrices.

## Resumen ejecutivo

Se necesita una herramienta web sencilla que reduzca trabajo manual en la transformacion de PDFs de cotizacion de aseguradoras, con poliza actual opcional, en un unico PDF comercial y consistente para enviar por WhatsApp al cliente final.

Hoy el proceso depende de copiar PDFs a Claude o ChatGPT para que "rearmen" el contenido en un formato deseado. Eso genera tres problemas:

- demasiadas iteraciones;
- alto consumo de tokens;
- resultados inconsistentes.

La estrategia del producto debe ser mover el formateo y la estructura final a codigo, y usar IA solo como apoyo acotado para extraccion o normalizacion cuando sea necesario.

## Problema de negocio

El corredor recibe referidos de terceros. Luego conversa por WhatsApp con el potencial cliente, entra a plataformas de aseguradoras con su cuenta de corredor, descarga varias cotizaciones PDF y arma manualmente una propuesta final.

Ese proceso consume mucho tiempo operativo y no escala bien.

Problemas concretos del flujo actual:

- el armado final depende de prompts y modelos generativos;
- el resultado cambia entre ejecuciones;
- el costo variable por token es alto;
- se requiere mucha correccion manual;
- no existe una herramienta interna estandarizada.

## Objetivo del producto

Crear un MVP web operativo que permita:

- autenticarse;
- subir tres PDFs de cotizaciones mas una poliza actual opcional, o usar el modo de cuatro cotizaciones sin poliza;
- seleccionar el plan recomendado (una sola cotizacion ganadora);
- generar automaticamente un PDF final con formato fijo;
- editar manualmente el resultado antes de descargarlo.

Reglas de comparacion ya implementadas en el MVP:

- **11 cuotas:** en extraccion y analisis se busca en cada PDF de cotizacion la modalidad de **11 cuotas** cuando el documento la declara; el comparativo muestra **Cuotas base: 11 cuotas** y la metodologia lo indica en el PDF.
- **Rol único en carga:** por archivo solo se asigna **Rol** (Básico / Equilibrado / Pro / Póliza actual); no hay columna Tier separada. Para cotizaciones, el rol define la etiqueta comercial visible en el PDF (`offer_tier_overrides`).
- **Ganador unico:** un control tipo **radio** permite marcar exactamente una cotizacion recomendada (borde verde en el PDF).
- **RC en exceso:** `rc_exceso` se extrae, compara, edita y renderiza como una fila separada de la RC base. Solo existe si el documento declara explicitamente una capa adicional que entra a cubrir despues de agotarse la RC base; no se infiere desde LUC ni desde usos genericos de la palabra "exceso".
- **Equivalencias de deducible:** la cabecera mantiene referencias para `0`, `3`, `5` y `10 UF`, pero los montos CLP se calculan dinamicamente con la UF canonica de cada corrida.

## Objetivos de exito

- reducir el tiempo de armado por caso;
- bajar al minimo el uso de tokens;
- aumentar consistencia del PDF final;
- facilitar correcciones manuales sin rehacer todo el documento;
- dejar la herramienta lista para entregar al cliente en Railway.

## No objetivos del MVP

- automatizar WhatsApp;
- integrar directamente con plataformas de aseguradoras;
- soportar muchos clientes desde el dia uno;
- resolver todos los tipos de PDF desde el primer sprint.

## Usuario principal

Usuario principal:

- corredor o asistente operativo del corredor.

Necesidades del usuario:

- cargar rapidamente documentos;
- obtener un PDF presentable;
- intervenir manualmente si algo salio mal;
- descargar y enviar el archivo final.

## Flujo actual

1. Llega un referido.
2. El corredor habla por WhatsApp con el prospecto.
3. El corredor cotiza en plataformas de aseguradoras.
4. Descarga varios PDFs.
5. Sube cotizaciones y, cuando existe, tambien consulta la poliza actual para construir comparacion.
6. Itera hasta acercarse al formato deseado.
7. Corrige manualmente.
8. Envía el PDF final por WhatsApp.

## Flujo futuro deseado

1. Login en la herramienta.
2. Crear nueva propuesta.
3. Subir cotizaciones (`Básico`, `Equilibrado`, `Pro` y, en modo sin poliza, una cuarta alternativa).
4. Subir `poliza actual` si existe.
5. Asignar rol por archivo (Básico / Equilibrado / Pro; póliza actual opcional).
6. Marcar cuál es el recomendado (radio entre cotizaciones; una sola).
7. Procesar documentos.
8. Ver el PDF generado en una nueva vista.
9. Editar campos o textos manualmente (sin selector de Tier por oferta).
10. Descargar PDF final.

## Entradas reales del sistema

El flujo real del negocio trabaja con hasta cinco PDFs:

- `cotizacion inicial`;
- `cotizacion media`;
- `cotizacion pro`;
- `poliza actual`;
- `PDF comparativo final esperado` como referencia visual/editorial.

Importante:

- para operar el producto, los 4 primeros son de trabajo;
- el quinto PDF no es un insumo obligatorio en produccion, pero si es una referencia clave para construir y evolucionar el template final.

La poliza actual **es recomendable** cuando existe seguro vigente, porque define el deducible base, el ahorro vs hoy y las etiquetas MEJORA/IGUAL/PEOR. Desde la plantilla **Refcar** (2026) tambien es **opcional**: sin poliza el sistema genera un comparativo solo entre cotizaciones, con 3 o 4 ofertas y `current_policy: null` en el analisis (ver `especificacion-formato-comparativo.md` secciones 4.1 y 9).

## Hipotesis de solucion

La herramienta debe separar el problema en tres capas:

### Capa 1. Extraccion literal

Convertir cada PDF de entrada a una estructura JSON de extraccion con:

- campos literales;
- evidencia;
- tablas;
- estado de extraccion.

### Capa 2. Analisis y normalizacion

Tomar poliza actual + cotizaciones, o solo cotizaciones, y producir un JSON analizado del caso con:

- comparacion a igual deducible;
- CLP normalizado con una UF comun;
- juicio de mejora / igual / peor;
- extras destacados;
- recomendacion;
- textos editoriales controlados.

### Capa 3. Presentacion

Generar el PDF final desde un template fijo en codigo consumiendo un JSON final listo para render.

Esta separacion reduce dependencia de prompts largos, mejora la consistencia y desacopla parsing, reglas de negocio y rendering.

## Requerimientos funcionales

### Requerimientos MVP

- login;
- login Refcar de un usuario administrado por variables de entorno;
- pantalla de carga de cotizaciones (minimo 3) y poliza actual opcional, mas modo dedicado de 4 cotizaciones sin poliza;
- asignación de **rol** por PDF (Básico / Equilibrado / Pro / Póliza actual);
- selector de **una** cotizacion ganadora (radio);
- procesamiento del set completo;
- preview del resultado;
- editor manual;
- descarga del PDF;
- persistencia basica de archivos, resultados y metricas internas;
- historial visible reducido a id de corrida, fecha y segundos.

### Requerimientos posteriores

- historial comercial de propuestas;
- versionado de template;
- scoring de confianza;
- comparacion entre estrategias de parsing;
- auth formal multiusuario;
- integracion con WhatsApp.

## Requerimientos no funcionales

- bajo costo operativo;
- alta consistencia visual;
- trazabilidad de cada corrida;
- modularidad por aseguradora;
- facilidad para agregar nuevas reglas y templates;
- posibilidad de usar distintos agentes/modelos segun el caso.

## Restriccion economica clave

El negocio se cobrara como mensualidad fija al cliente final, mientras el costo de hosting y tokens lo absorbe quien provee la herramienta. Por eso:

- no conviene que la solucion dependa de prompts largos en cada corrida;
- el PDF final no debe generarse con LLM de punta a punta;
- los agentes deben entrar solo donde aportan diferencial claro.

Supuesto operativo inicial para el primer cliente:

- volumen esperado: aproximadamente **100 corridas por mes**;
- costo observado historico de referencia: aproximadamente **USD 0,02 por corrida**, pero debe recalibrarse con nuevas corridas porque el historial anterior omitía la llamada final de analisis;
- saldo inicial previsto en OpenRouter: **USD 20**, con revision periodica manual de creditos;
- no se requiere imponer un limite de uso dentro de la aplicacion en la primera entrega, pero se conserva el historial de costo por corrida para detectar desvios;
- en la futura version desplegada, `OPENROUTER_API_KEY` debe vivir exclusivamente como variable de entorno del backend y nunca enviarse al navegador.

## Decisiones de arquitectura recomendadas

### Decision 1

El formato final del PDF debe definirse en codigo.

### Decision 2

El sistema debe trabajar con tres schemas JSON separados:

- `extraction.schema.json`: salida literal por PDF;
- `analysis.schema.json`: caso completo ya interpretado;
- `final-render.schema.json`: payload final para el generador de PDF.

### Decision 3

Cada aseguradora deberia tener un parser o mapping propio si sus PDFs son distintos.

### Decision 4

El uso de IA debe ser escalonado:

- primero reglas;
- despues modelo pequeno;
- por ultimo modelo mas potente solo si hace falta.

### Decision 5

Toda correccion manual importante deberia registrarse para retroalimentar reglas futuras.

## Arquitectura logica

### Frontend

- login;
- dashboard de nuevas propuestas;
- upload de PDFs;
- seleccion de recomendado;
- vista de preview/edicion;
- descarga.

### Backend

- autenticacion;
- recepcion y almacenamiento local de archivos;
- parser documental;
- pipeline `extraction -> analysis -> final-render`;
- generador de PDF;
- registro de ejecuciones;
- modulo de evaluacion de estrategias.

### Datos

- usuarios;
- propuestas;
- documentos subidos;
- JSON extraido;
- PDF final generado;
- historial de ediciones;
- metricas de corrida.

## Pipeline propuesto

1. Upload de cotizaciones.
2. Upload de poliza actual si existe.
3. Deteccion de proveedor o tipo documental por archivo.
4. Extraccion de texto/tablas.
5. Construccion de `extraction.json` por PDF.
6. Parsing por reglas.
7. Fallback con IA si faltan campos o hay ambiguedad.
8. Construccion de `analysis.json` del caso completo.
9. Construccion de `final-render.json`.
10. Render a PDF.
11. Preview editable.
12. Descarga.

## Schemas definidos del proyecto

Ya existen tres schemas reales en la carpeta `schemas/`:

- `schemas/extraction.schema.json`
- `schemas/analysis.schema.json`
- `schemas/final-render.schema.json`

Rol de cada uno:

- `extraction`: una salida por PDF, con campos literales, evidencia y tablas;
- `analysis`: interpretacion del caso completo con reglas de negocio, recomendacion y comparativos;
- `final-render`: payload final del template para el PDF.

## Schema canonico inicial sugerido

Cada plan deberia poder mapearse a una estructura similar a:

```json
{
  "plan_key": "inicial | medio | pro",
  "aseguradora": "",
  "nombre_plan": "",
  "prima": {
    "monto": 0,
    "moneda": "CLP",
    "periodicidad": "mensual"
  },
  "deducible": "",
  "coberturas": [],
  "asistencias": [],
  "restricciones": [],
  "vigencia": "",
  "beneficios_destacados": [],
  "observaciones": [],
  "source_file_name": "",
  "source_confidence": 0
}
```

Y la propuesta final:

```json
{
  "customer_name": "",
  "vehicle_data": {},
  "plans": [],
  "recommended_plan_key": "medio",
  "recommendation_reason": "",
  "advisor_notes": "",
  "generated_at": ""
}
```

## Agentes y modelos

Los agentes no deben ser el centro del producto; deben ser herramientas de apoyo dentro de una arquitectura mas robusta.

### Casos donde si usar agentes/modelos

- inferir campos cuando el PDF es desordenado;
- resumir diferencias entre planes;
- proponer una recomendacion redactada;
- detectar datos faltantes;
- ayudar a clasificar el tipo de documento.
- analizar fragmentos o parrafos concretos del PDF para poblar campos interpretativos del `analysis.json`.

### Casos donde no usar agentes/modelos

- maquetar el PDF final;
- decidir toda la estructura del documento;
- rehacer desde cero un caso que ya tiene schema definido;
- tareas repetitivas que codigo puede resolver.

### Estrategia de experimentacion

Mantener varias estrategias comparables:

- `solo_codigo`;
- `codigo_mas_modelo_liviano`;
- `codigo_mas_modelo_potente`;
- `agente_especializado_por_documento`.

Para cada corrida medir:

- costo;
- latencia;
- campos correctos;
- necesidad de correccion manual;
- calidad del PDF final.

## Dataset necesario

Para que el proyecto avance bien se necesita un set inicial real de:

- PDF barato;
- PDF medio;
- PDF caro;
- poliza actual;
- PDF final esperado.

Idealmente varios sets adicionales para testear robustez.

Tambien conviene documentar:

- aseguradora;
- fecha;
- si el PDF tiene texto seleccionable;
- si es siempre el mismo layout;
- que campos son indispensables.

## Riesgos del proyecto

### Riesgo 1

Los PDFs de las aseguradoras pueden cambiar de formato.

### Riesgo 2

Algunos PDFs pueden venir como imagen o con tablas dificiles de parsear.

### Riesgo 3

El corredor puede querer cambios frecuentes al diseño final.

### Riesgo 4

La recomendacion comercial puede tener criterios subjetivos.

## Mitigaciones

- versionar parsers por aseguradora;
- desacoplar parsing de rendering;
- versionar template del PDF final;
- permitir edicion manual antes de descargar;
- guardar feedback para mejorar reglas.

## Stack sugerido para el MVP local

### Opcion base

- frontend local web con `Next.js` o `React`;
- backend en `Node.js`;
- `SQLite` para datos locales;
- almacenamiento local de archivos;
- generacion PDF via HTML/CSS + `Playwright`.

### Opcion si los PDFs son complejos

- frontend en `Next.js`;
- backend principal en Node;
- microservicio o modulo Python para parsing documental.

La segunda opcion puede ser mejor para trabajar con tablas, OCR y extraccion avanzada.

## Estructura tecnica sugerida

```text
/app
  /frontend
  /backend
  /shared
  /storage
  /samples
  /templates
  /parsers
  /evaluations
```

## Roadmap resumido

### Etapa 1

Definir y estabilizar schemas + recibir ejemplos reales + replicar el PDF final en codigo.

### Etapa 2

Construir el flujo local completo con upload, parse, render, preview y descarga.

### Etapa 3

Agregar evaluacion de modelos/agentes y fallback inteligente.

### Etapa 4

Endurecer la herramienta y prepararla para version web.

## Estado actual de implementacion (junio 2026)

La version entregable corre en `app/`, puede usarse localmente y esta preparada para Railway con Docker:

- **Interfaz:** Streamlit (`app/web_app.py`), flujo directo (upload → editor → PDF). En carga: columnas **Archivo | Rol** y **radio** para ganador (sin Tier duplicado).
- **Login Refcar:** pantalla visual de acceso con logo corporativo. Usuario por `REFCAR_LOGIN_USER` (default `felipe_carmona`) y clave por `REFCAR_LOGIN_PASSWORD`. La sesion usa estado de Streamlit y un token firmado en URL para resistir reconexiones del runtime.
- **PDF:** plantilla HTML/CSS Refcar (`app/templates/comparativo.html`) + WeasyPrint (`app/src/pdf_generator.py`).
- **IA:** OpenRouter para extraccion y analisis; el render del PDF es 100% codigo (sin tokens). La app usa un unico modelo estándar: `google/gemini-3.1-flash-lite`.
- **Despliegue:** Railway desde GitHub con `Dockerfile` en la raiz y `railway.json`. Secrets como `OPENROUTER_API_KEY` y credenciales de login viven en variables de entorno del servicio.
- **Costo por corrida:** antes del pipeline, `OpenRouterClient.fetch_model_prices()` consulta `/models`; las metricas internas estiman el costo y lo guardan en el JSON de corrida. La tabla visible al cliente no muestra tokens ni costo.
- **Respuestas JSON robustas:** cuando el modelo lo soporta, el cliente usa `response_format: {"type": "json_object"}` y exige un endpoint compatible. Para `analysis`, toma el limite de salida publicado por OpenRouter hasta **65.536 tokens**; si recibe `finish_reason = "length"` o JSON incompleto, reintenta con mas margen disponible. Los reintentos pagados se suman en las metricas.
- **Auditoria de metricas:** el historial persiste la llamada final de analisis ademas de las extracciones y registra metricas internas. La tabla web visible muestra solo id de corrida, fecha y segundos.
- **Resiliencia de corrida:** al pulsar **Iniciar Extraccion Documental** aparece estado inmediato para evitar dobles clics por impaciencia. Si ya existen extracciones y falla el analisis, la app permite reintentar analisis sin volver a pagar toda la extraccion.
- **Registro de renders:** mostrar o descargar un PDF existente no guarda otra corrida. Solo el clic explicito en **Generar PDF** renderiza y registra una nueva version.
- **UF:** cada corrida consulta `mindicador.cl` automáticamente con reintentos y cache local. En la barra lateral existe **Ingresar UF manualmente** como respaldo visible si el servicio externo falla.
- **Modelo:** no hay selector de modelo en la interfaz de cliente; `DEFAULT_PRIMARY_MODEL` concentra el ID vigente.
- **Lanzador macOS:** doble clic en `app/Ejecutar Herramienta Seguros.command` → abre `http://localhost:8501`. Antes de iniciar, libera el puerto 8501 si quedo una instancia anterior colgada.
- **Regeneracion:** durante una sesion abierta, el usuario puede editar campos y generar nuevos PDFs sin cerrar la terminal ni reiniciar Streamlit. Si hubo cambios de codigo y la vista no se refresca automaticamente, basta con recargar el navegador; reiniciar el lanzador queda como ultimo recurso.
- **Git:** repositorio en la raiz conectado a GitHub/Railway; rama estable `main`. Claves, `.env`, corridas locales y PDFs de trabajo quedan excluidos via `.gitignore`.

### PDF comparativo Refcar (ultima iteracion visual, julio 2026)

Alineado a la plantilla de referencia del cliente (`PLANTILLA_BASE_Detalle_Comparativo_Refcar.pdf`):

- **Correccion vigente:** `Tu seguro hoy` separa deducible y prima mensual para evitar que `10 UF` se lea como `UF/mes`.
- **Tipografia mas grande** y **layout denso** (menos espacio vacio entre filas y bloques).
- **Layout PDF estable:** columnas y coberturas renderizadas como tablas HTML (WeasyPrint); zona «En simple» fijada al borde inferior de cada columna para mantener alineadas sus lineas superiores; footer separado al cierre de la pagina.
- **Colores de columna por posicion de subida** (izquierda a derecha):
  - con poliza vigente: gris (tu seguro hoy) → azul → celeste → naranja;
  - sin poliza: azul → celeste → naranja → café cuando hay cuarta cotización.
- Las etiquetas comerciales (`+ OPCIÓN PREMIUM`, `★ MEJOR OPERACIONAL`, etc.) derivan del **rol** asignado en Streamlit (Básico / Equilibrado / Pro); el borde verde marca solo la **recomendada**.
- La barra de metadatos del PDF muestra UF, **Cuotas base: 11 cuotas** y fecha; **no** incluye nombre de ejecutivo/a comercial.
- La franja explicativa del deducible muestra equivalencias para `0`, `3`, `5` y `10 UF`; sus valores CLP se calculan en cada render con la UF de referencia, no son montos fijos.
- En la columna **Tu seguro hoy**, la tabla separa deducible y prima: `Deducible` muestra `Mismo de hoy · X UF`, `UF/mes` muestra solo la prima mensual en UF y `CLP/mes` muestra solo la prima mensual en pesos. No se debe poner el deducible en `UF/mes`.
- La lista de coberturas incluye **RC en Exceso** en todas las columnas. Se muestra como capa adicional independiente de RC emergente, daño moral y lucro cesante.
- El pie editable (`broker_name`, `broker_website`) forma parte del contrato de analisis y se refleja realmente en el PDF.
- El orden de columnas respeta el orden en que se suben las cotizaciones (la recomendada no salta al frente).

Detalle tecnico completo en `especificacion-formato-comparativo.md` (seccion 9).

### Correcciones de comparativo entre 4 cotizaciones (julio 2026)

Tres correcciones deterministicas, sin costo adicional de tokens, enfocadas en el modo de comparacion entre 3-4 cotizaciones nuevas:

- **Deducible homologado entre columnas:** nuevo modulo `app/src/deductible_pricing.py` parsea de forma deterministica (regex sobre las tablas markdown ya extraidas, sin depender del nombre de la aseguradora) la grilla de precios por deducible de cada cotizacion. En la pantalla de carga, un selector **Deducible de comparacion** (2.1) muestra **todas** las opciones de deducible encontradas en **cualquiera** de las cotizaciones subidas (union, no interseccion), indicando entre parentesis cuando una opcion no esta disponible en todas; tras el analisis, `enforce_common_deductible` fuerza esa misma comparacion en las columnas y corrige el precio si el modelo lo desalineo (bug detectado en tablas grandes tipo grilla, por ejemplo HDI). Si una cotizacion no tiene una tabla reconocible para ese deducible, se deja el valor del modelo y se registra un aviso visible en el editor. En el PDF final cada columna muestra **una sola fila** de deducible/prima (la de comparacion), no una grilla de alternativas, para que el cliente compare de forma simple.
- **Etiquetas de columna por rol:** `_map_tier_to_category_and_badge` en `pdf_generator.py` unifica los badges a `OPCIÓN ECONÓMICA` / `OPCIÓN EQUILIBRADA` / `OPCIÓN PREMIUM` segun el rol asignado (Básico / Equilibrado / Pro), reemplazando las etiquetas previas inconsistentes (`MEJOR OPERACIONAL`, `OPCIÓN INTERMEDIA`, etc.).
- **Asistencia por rol:** la fila `Asistencia` de cada columna ya no muestra el texto literal extraido del PDF (`Full`, `Full Premium`); muestra `Básica` / `Equilibrada` / `Premium` segun el rol de esa columna, manteniendo el color MEJORA/IGUAL/PEOR cuando hay poliza actual.
- **Captura de precio reforzada:** `extraction_domain_instructions.md` y `prompts.py` (extraccion y analisis) agregan una regla explicita de verificacion columna-por-columna para tablas grandes donde el deducible va en el encabezado y la prima en filas separadas por modalidad de pago, ademas de la correccion deterministica anterior que ya no depende de que el LLM acierte esa alineacion.
- **Nombres de producto largos:** `.col-product` ya no trunca con elipsis; el texto puede envolver a 2 lineas y el tamano de fuente se reduce dinamicamente (`_product_name_font_size` en `pdf_generator.py`) segun el largo del nombre.
- **"11 cuotas" duplicado:** `_build_deductible_payment_label` ahora tambien detecta cuando el campo `payment_method` (mal extraido por el modelo) repite el texto de cuotas, y lo omite para evitar la duplicacion.

Estas correcciones no agregan reglas por nombre de aseguradora: detectan patrones estructurales de tabla (fila compacta vs. grilla) y usan un *fallback* seguro al valor del modelo cuando no reconocen el formato.

## Criterios de aceptacion del MVP

El MVP se considera exitoso si:

- permite subir cotizaciones con poliza actual opcional, o usar el modo dedicado de cuatro cotizaciones sin poliza;
- genera un PDF final visualmente consistente;
- requiere menos correcciones que el flujo actual;
- usa tokens solo en extraccion/analisis y nunca para renderizar el PDF;
- deja editar y descargar sin romper el formato.

## Preguntas abiertas

- que campos exactos deben aparecer siempre en futuras versiones del PDF final;
- si hay una o varias plantillas de salida;
- si la recomendacion debe ser manual, automatica o mixta;
- si se requerira auth formal multiusuario o si basta el login interno de Refcar;
- cuanta variacion existe entre aseguradoras;
- si los PDFs tienen texto seleccionable o necesitan OCR.

## Regla operativa para los proximos pasos

Antes de escribir parsers definitivos o integrar agentes, conseguir al menos un set real de:

- cotizacion barata;
- cotizacion media;
- cotizacion cara;
- poliza actual;
- PDF final esperado.

Con ese material se define el contrato de datos real y se construye el primer flujo productivo.
