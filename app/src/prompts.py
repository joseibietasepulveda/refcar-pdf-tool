from __future__ import annotations

import json
from pathlib import Path

from .config import SCHEMAS_DIR


def _load_schema_compact(name: str) -> str:
    schema_path = SCHEMAS_DIR / name
    schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
    return json.dumps(schema_obj, ensure_ascii=False, separators=(",", ":"))


_PROMPTS_DIR = Path(__file__).resolve().parent


def _load_domain_extraction_rules() -> str:
    path = _PROMPTS_DIR / "extraction_domain_instructions.md"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


EXTRACTION_DOMAIN_RULES = _load_domain_extraction_rules()


EXTRACTION_SCHEMA = _load_schema_compact("extraction.schema.json")
ANALYSIS_SCHEMA = _load_schema_compact("analysis.schema.json")


def build_extraction_prompt(pdf_text: str, file_name: str, document_type: str, document_role: str) -> list[dict]:
    """Build the messages for extracting structured data from a single PDF."""
    system_parts = [
        "Eres un extractor de datos de documentos de seguros automotrices chilenos. "
        "Tu trabajo es leer el texto derivado de un PDF y devolver un JSON que cumpla exactamente "
        "el schema oficial adjunto.",
        "Responde SOLO con el JSON válido, sin texto adicional ni markdown ni fences.",
    ]
    if EXTRACTION_DOMAIN_RULES:
        system_parts.append("Instrucciones de negocio y calidad obligatorias:\n\n" + EXTRACTION_DOMAIN_RULES)
    system = "\n\n".join(system_parts)

    user = (
        f"## JSON Schema oficial del documento extraído (debes cumplirlo tal cual)\n\n"
        f"```json\n{EXTRACTION_SCHEMA}\n```\n\n"
        f"## Metadatos de este archivo\n\n"
        f"- Archivo: {file_name}\n"
        f"- document_type debe ser exactamente: {document_type!r}\n"
        f"- document_role debe ser exactamente: {document_role!r}\n\n"
        f"## Contenido del documento (texto OCR/plano)\n\n"
        f"{pdf_text}\n\n"
        f"## Tareas obligatorias\n\n"
        f"- Construye un único objeto JSON válido contra el schema.\n"
        f'- Usa `document_id = "{file_name}"`, `source_file = "{file_name}"` '
        f"(puedes reutilizar el nombre de archivo como id estable).\n"
        f"- Completa `source_metadata`: al menos file_name y mime_type `application/pdf`, "
        f"si puedes inferir page_count desde el marcador --- Página N --- .\n"
        f"- Rellena `fields`: identidad (`identity`), vehículo (`vehicle`), opciones económicas "
        f"(`pricing_options`), coberturas (`coverages`/asistencias/extras donde aplique).\n"
        f"- Extrae `fields.vehicle.vehicle_plate` con especial cuidado: busca cerca de etiquetas como "
        f"\"Patente\", \"Placa patente\", \"Placa\", \"PPU\", \"Dominio\" o \"Matrícula\". "
        f"No confundas patente con RUT, número de póliza, número de cotización, chasis, motor, teléfono ni código interno. "
        f"Normaliza la patente chilena sin espacios, puntos ni guiones y en mayúsculas (por ejemplo `ABCD12` o `AB1234`). "
        f"Si el documento no declara una patente clara, deja el campo vacío o como no encontrado; no la inventes.\n"
        f"- Pon advertencias coherentes en `extraction_status` (warnings, missing_fields si aplica).\n\n"
        f"## ⚠️ CHECKLIST DE COBERTURAS OBLIGATORIAS (fields.coverages[])\n\n"
        f"Debes buscar en TODAS las páginas del documento (tablas, cláusulas, condiciones particulares, letra chica) "
        f"y extraer CADA uno de estos 12 campos como un `coverageItem` en `fields.coverages[]` con el `key` exacto:\n\n"
        f"1. `rc_emergente` — RC Daño Emergente. Buscar: \"Daño Emergente\", \"SUBSECCIÓN DAÑO EMERGENTE\". Si es LUC (límite único combinado), pon el monto total.\n"
        f"2. `rc_moral` — RC Daño Moral. Buscar: \"Daño Moral\", \"SUBSECCIÓN DAÑO MORAL\". Si es LUC, pon el monto total.\n"
        f"3. `rc_lucro_cesante` — RC Lucro Cesante. Buscar: \"Lucro Cesante\", \"SUBSECCIÓN LUCRO CESANTE\". Si es LUC, pon el monto total.\n"
        f"4. `rc_exceso` — RC adicional en exceso de RC base. Buscar SOLO en contexto explícito de RC: \"R. CIVIL EN EXCESO DE R. CIVIL BASE\", \"RC EN EXCESO DE RC BASE\", \"RESPONSABILIDAD CIVIL EN EXCESO\". Extrae únicamente el monto adicional, no base+exceso. No lo infieras desde LUC ni desde usos irrelevantes de \"exceso\" (SOAP/Isapre/Fonasa, kilómetros, carga, deducibles u otros).\n"
        f"5. `auto_reemplazo` — Auto de Reemplazo. Buscar: \"Auto de Reemplazo\", \"Servicio de Movilidad\", \"AUTO REEMPLAZO ILIMITADO\". Valor: días o \"Ilimitado\".\n"
        f"6. `copago_reemplazo` — Copago Auto Reemplazo. Buscar: \"copago\" cerca de auto reemplazo. Si no menciona copago, pon \"Sin copago\".\n"
        f"7. `taller` — Tipo de Taller. Buscar: \"Taller\", \"CLÁUSULA DE TALLER\", \"Exclusividad de Taller\". Incluir restricciones de antigüedad.\n"
        f"8. `reposicion_a_nuevo` — Reposición a Nuevo. Buscar: \"Reposición a nuevo\", \"Indemnización 0 Km\", \"0 km\". Valor: meses.\n"
        f"9. `perdida_total` — Umbral Pérdida Total. Buscar: \"Pérdida Total\", \"costo de reparación supere\". Valor: porcentaje o \"Valor Comercial\".\n"
        f"10. `asistencia` — Asistencia al Vehículo. Buscar: \"Asistencia al Vehículo\", \"Asistencia VM\", \"ASISTENCIA\". Incluir nivel (Básica/Premium/Full) y monto UF.\n"
        f"11. `asiento_pasajeros` — Asiento de Pasajeros. Buscar: \"Asiento de Pasajero\", \"Plan A\", \"Plan B\", \"Plan C\". Extraer todos los planes con montos.\n"
        f"12. `defensa_penal` — Defensa Penal. Buscar: \"Defensa Penal\", \"Constitución de Fianza\". Valor: monto en UF.\n\n"
        f"Para CADA uno: si lo encuentras en el documento, pon `present: true` con el valor. "
        f"Si genuinamente NO existe en ninguna parte del documento, pon `present: false`.\n\n"
        f"### Prima mensual para pólizas con solo prima anual\n"
        f"Si el documento solo tiene prima anual (ej: UF 12.04) y cuotas (ej: 12), calcula:\n"
        f"  `monthly_premium_uf = annual_premium_uf / installments` (ej: 12.04 / 12 = 1.003)\n"
        f"El resultado es un decimal PEQUEÑO (típicamente entre 0.5 y 2.0 UF). Marca `source_value_type: \"computed\"`.\n\n"
        f"### Modalidad de 11 cuotas (obligatorio en cotizaciones)\n"
        f"Si `document_type` es `quote`, **busca en el PDF** la opción de pago en **11 cuotas** (tablas de primas, "
        f"texto explícito \"11 cuotas\", etc.). Si existe, úsala como fila principal de `pricing_options` y refleja "
        f"`installments`/cuotas coherentes con esa modalidad. Si no existe 11 cuotas, documenta en `extraction_status` "
        f"qué modalidad usaste y por qué."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_analysis_prompt(
    extractions: list[dict],
    recommended_tier: str = "",
    uf_clp: float | None = None,
    uf_date: str | None = None,
    case_mode: str = "current_policy_plus_quotes",
    recommended_position: int | None = None,
) -> list[dict]:
    """Build the messages for analyzing the complete case from extraction JSONs."""
    quote_count = sum(1 for ext in extractions if ext.get("document_type") != "current_policy")
    has_current_policy = any(ext.get("document_type") == "current_policy" for ext in extractions)
    quote_only_mode = case_mode == "quotes_only_4" or not has_current_policy
    case_description = (
        "4 cotizaciones sin póliza actual"
        if quote_only_mode
        else "1 póliza actual opcional + cotizaciones"
    )
    system = (
        "Eres un analista experto de seguros automotrices chilenos que produce documentos comparativos comerciales. "
        f"Recibirás los datos extraídos de un caso de {case_description} "
        "y debes producir un JSON de análisis comparativo que cumpla exactamente con el schema adjunto.\n\n"
        "REGLAS FUNDAMENTALES:\n"
        "- Compara siempre al mismo deducible que la póliza actual si existe; si no existe, usa un deducible comparable entre propuestas.\n"
        "- Si existe póliza actual, calcula ahorros mensuales en CLP respecto a ella (positivo = ahorro, negativo = sobrecosto).\n"
        "- Si existe póliza actual, clasifica coberturas como MEJORA, IGUAL, PEOR o MIXTO respecto a la actual.\n"
        "- Si NO existe póliza actual, deja `current_policy: null`, genera 3 o 4 ofertas según los documentos recibidos y compara las propuestas entre sí.\n"
        "- En modo sin póliza, usa labels relativos al set: MEJORA para fortalezas claras frente al grupo, PEOR para debilidades claras, IGUAL para paridad y MIXTO para tradeoffs.\n"
        "- Responde SOLO con el JSON válido, sin texto adicional ni markdown ni fences.\n"
        "- Todos los campos derivedField DEBEN tener la estructura {\"value\": ..., \"confidence\": N, \"method\": \"...\"}."
    )

    extractions_text = json.dumps(extractions, ensure_ascii=False, separators=(",", ":"))

    recommendation_note = ""
    if recommended_tier:
        recommendation_note = (
            f"\n**Recomendación del corredor:** El corredor marcó como recomendado el documento con "
            f"document_role = \"{recommended_tier}\""
            + (f" y position = {recommended_position}" if recommended_position else "")
            + ". Usa esta preferencia exacta para `recommended_offer_id`."
        )

    uf_block = ""
    if uf_clp is not None and uf_date:
        uf_block = (
            "\n## UF de referencia OBLIGATORIA (no uses otro valor ni el de los PDFs si difiere)\n\n"
            f"- `context.uf_value_used` = **{uf_clp}** (pesos chilenos por 1 UF).\n"
            f"- `context.uf_reference_date` = **{uf_date}** (fecha ISO YYYY-MM-DD).\n"
            "- Recalcula `monthly_premium_clp` y los de `deductible_options[]` como entero: "
            "`round(prima_mensual_UF × uf_value_used)`. "
            "Si existe póliza actual, recalcula `monthly_savings_vs_current_clp` como diferencia respecto a ella. "
            "Si no existe póliza actual, usa 0 en `monthly_savings_vs_current_clp` y explica diferencias relativas en `editorial_summary`.\n"
        )

    user = (
        f"## Schema esperado\n\n"
        f"```json\n{ANALYSIS_SCHEMA}\n```\n\n"
        f"## Documentos extraídos ({len(extractions)} JSONs; {quote_count} cotizaciones)\n\n"
        f"```json\n{extractions_text}\n```\n\n"
        f"{uf_block}"
        f"## Instrucciones detalladas\n\n"
        f"1. Identifica si existe póliza actual (`document_type: \"current_policy\"`). Si no existe, `current_policy` debe ser null.\n"
        f"2. Normaliza a una UF común: si arriba hay un bloque «UF de referencia OBLIGATORIA», usa esos números tal cual; "
        f"si no, elige la UF que aparezca en los documentos (la más reciente o la de la póliza actual).\n"
        f"3. Si hay póliza actual, compara cada cotización contra la póliza actual AL MISMO deducible. "
        f"Si no hay póliza actual, compara las cotizaciones entre sí: identifica la más barata, la más completa, "
        f"la mejor equilibrada y las principales fortalezas/debilidades relativas.\n"
        f"4. Genera un `case_id` único basado en nombre del asegurado y fecha.\n"
        f"{recommendation_note}\n\n"
        f"## CAMPOS OBLIGATORIOS que debes completar con cuidado\n\n"
        f"### Patente del vehículo (`insured.plate`)\n"
        f"- Revisa los `fields.vehicle.vehicle_plate` de las extracciones en el orden recibido.\n"
        f"- Si una extracción ya trae una patente chilena clara y confiable, úsala como `insured.plate` "
        f"y NO sigas buscando ni reemplazándola con datos de otros PDFs.\n"
        f"- Normalízala en mayúsculas, sin espacios, puntos ni guiones (ej: `ABCD12` o `AB1234`).\n"
        f"- No confundas patente con RUT, número de póliza, número de cotización, número de propuesta, chasis, motor, teléfono ni código interno.\n"
        f"- Si otros PDFs traen patente vacía, distinta o ambigua, conserva la primera patente clara ya encontrada salvo que haya evidencia explícita de que era un error.\n\n"
        f"### current_policy (si es null, déjalo como null en el JSON raíz; si existe, completa sus campos)\n"
        f"- `insurer`: nombre real de la aseguradora (BCI, HDI, Zurich, FID, etc.), NO \"Desconocida\".\n"
        f"- `product_name`: nombre del producto/plan.\n"
        f"- Las siguientes coberturas detalladas, cada una con un objeto de tipo `comparisonResult` (que tiene un derivedField `summary` y un string `label`): \n"
        f"  - **Responsabilidad Civil (RC)**:\n"
        f"    - `rc`: Responsabilidad Civil general o combinada (ej: \"UF 1.500 total\" o \"Límite único combinado\").\n"
        f"    - `rc_emergente`: Daños emergentes de la RC base (ej: \"UF 2.000\" o \"UF 1.000\"). Nunca mezcles aquí el monto adicional en exceso.\n"
        f"    - `rc_moral`: Daño moral (ej: \"UF 2.000\" o \"UF 1.000\").\n"
        f"    - `rc_lucro_cesante`: Lucro cesante (ej: \"UF 2.000\" o \"UF 1.000\").\n"
        f"    - `rc_exceso`: capa adicional de RC que opera solo después de agotar la RC base (ej: \"UF 3.000 adicionales\" o \"No incluye\"). No sumes este monto a las subsecciones base.\n"
        f"  - **Auto de Reemplazo**:\n"
        f"    - `auto_replacement`: Días incluidos (ej: \"45 días\", \"30 días\", \"No incluye\").\n"
        f"    - `copago_reemplazo`: Valor diario de copago (ej: \"$4.000/día\", \"Sin copago\", \"—\").\n"
        f"  - **Taller**:\n"
        f"    - `workshop`: Tipo de taller y antigüedad (ej: \"Taller Marca sin restricción de antigüedad\", \"≤3 años / Multimarca +3\", \"Multimarca preferente\").\n"
        f"  - **Reposición y Pérdida Total**:\n"
        f"    - `reposicion_a_nuevo`: Si incluye reposición del vehículo a nuevo (ej: \"Sí (≤730 días)\", \"No incluye\").\n"
        f"    - `perdida_total`: Umbral de pérdida total (ej: \"65% VC\", \"75% VC\", \"No declarado\").\n"
        f"  - **Asistencia**:\n"
        f"    - `assistance`: Nivel de asistencia (ej: \"Intermedia\", \"Premium\", \"Ilimitada\").\n"
        f"  - **Adicionales**:\n"
        f"    - `asiento_pasajeros`: Cobertura por asiento de pasajeros (ej: \"Plan A+B+C · UF 250\", \"UF 100\", \"No incluye\").\n"
        f"    - `defensa_penal`: Tope de defensa penal (ej: \"UF 300\", \"UF 200\", \"UF 100\").\n"
        f"  Para la póliza actual, pon \"IGUAL\" como `label` de comparación por defecto en todas estas coberturas.\n\n"
        f"### offers[] — para CADA cotización ({quote_count} en este caso)\n"
        f"- `commercial_tier`: debe ser **coherente con el `document_role` de la extracción** de esa cotización "
        f"(el corredor ya asignó el rol por archivo). Mapeo obligatorio: `initial_option` → \"ESTÁNDAR\", "
        f"`middle_option` → \"INTERMEDIA\", `pro_option` → \"PREMIUM\". No inventes otra clasificación.\n"
        f"- Rellena todas las coberturas detalladas enumeradas arriba (`rc`, `rc_emergente`, `rc_moral`, `rc_lucro_cesante`, `rc_exceso`, `auto_replacement`, `copago_reemplazo`, `workshop`, `reposicion_a_nuevo`, `perdida_total`, `assistance`, `asiento_pasajeros`, `defensa_penal`) exactamente con la misma estructura y un juicio comercial riguroso para la `label` (\"MEJORA\", \"IGUAL\", \"PEOR\", \"MIXTO\"). Si hay póliza actual, compara contra la póliza. Si no hay póliza actual, compara contra el resto de propuestas del set.\n"
        f"- `deductible_options`: OBLIGATORIO para la oferta recomendada. Lista TODAS las opciones de deducible "
        f"que aparezcan en la cotización con su prima mensual en UF y CLP. Marca `is_same_as_current: true` para "
        f"el que coincida con el deducible actual, y `is_proposed: true` para el que el corredor propondría "
        f"(típicamente un deducible más bajo que sea más conveniente que el seguro actual).\n"
        f"- `extra_highlights`: lista de extras destacados como derivedField.\n"
        f"- `editorial_summary`: derivedField con un párrafo corto (2-3 oraciones) que sintetice la tesis comercial "
        f"de esta oferta. Debe ser específico, NO genérico. **El tono debe variar según el tier comercial:**\n"
        f"  - **BÁSICO/ESTÁNDAR**: enfocarse en ahorro y economía. Si hay póliza, destacar cuánto se ahorra vs. hoy; si no hay póliza, indicar si es la más barata o una de las más convenientes del grupo.\n"
        f"  - **EQUILIBRADO/INTERMEDIA**: enfocarse en equilibrio precio-cobertura. Si no hay póliza, explica por qué es mejor equilibrio frente al resto.\n"
        f"  - **PRO/PREMIUM**: enfocarse en cobertura completa y extras premium. Si no hay póliza, explica si es la más completa y qué justifica su precio.\n"
        f"  Ejemplos:\n"
        f"  - BÁSICO: \"Zurich es la alternativa más económica del set: mejora RC y extiende el auto de reemplazo "
        f"a 90 días, todo con un ahorro de $4.200/mes respecto a tu seguro actual.\"\n"
        f"  - EQUILIBRADO: \"HDI MAX es el mejor equilibrio del set: mejora todos los puntos clave pagando menos "
        f"que hoy. Por el mismo presupuesto actual podrías incluso bajar el deducible a 3 UF.\"\n"
        f"  - PRO: \"FID Premium es la opción más completa: RC de 5.000 UF, auto de reemplazo ilimitado, taller "
        f"de marca sin restricción y asistencia en viaje USD 15.000 para toda la familia.\"\n\n"
        f"### Modo sin póliza actual\n"
        f"Si `current_policy` es null:\n"
        f"- No inventes datos de póliza actual.\n"
        f"- `offers` debe contener todas las cotizaciones recibidas, hasta 4.\n"
        f"- `monthly_savings_vs_current_clp` debe ser 0 porque no existe baseline mensual.\n"
        f"- `editorial_summary` debe comparar contra el set: \"la más barata\", \"la más completa\", \"mejor equilibrio\", \"más cara pero con mejores coberturas\", etc.\n"
        f"- `headline_insight` y `reason_summary` deben justificar la recomendación entre propuestas, no contra un seguro vigente.\n\n"
        f"### Modalidad de 11 cuotas (todas las cotizaciones)\n"
        f"Para **cada** oferta en `offers[]` que provenga de una cotización, el `installments` y las primas mensuales "
        f"mostradas deben corresponder a la **modalidad de 11 cuotas** si consta en el JSON extraído de ese PDF. "
        f"Búscala en `pricing_options` y en campos de cuotas del documento. Si en la extracción no hay 11 cuotas, "
        f"usa la mejor evidencia disponible sin contradecir el JSON extraído y deja constancia razonable en el análisis "
        f"(p. ej. advertencia breve) si la modalidad difiere del estándar de 11 cuotas.\n\n"
        f"### Reglas específicas por aseguradora\n"
        f"- **HDI**: muchas tablas listan explícitamente **11 cuotas**; priorízala como arriba. "
        f"También puede declarar `R. CIVIL (...) EN EXCESO DE R. CIVIL BASE`: mapea esa fila a `rc_exceso` y conserva solo su monto adicional.\n\n"
        f"### ⚠️ REGLA CRÍTICA: Mapeo de coberturas desde la extracción\n"
        f"Las extracciones contienen `fields.coverages[]` y `fields.extra_features[]` con items que tienen un `key` estandarizado. "
        f"Debes mapear DIRECTAMENTE estos keys a los campos del análisis:\n"
        f"- key `rc_emergente` → campo `rc_emergente` del análisis\n"
        f"- key `rc_moral` → campo `rc_moral`\n"
        f"- key `rc_lucro_cesante` → campo `rc_lucro_cesante`\n"
        f"- key `rc_exceso` → campo `rc_exceso`\n"
        f"- key `auto_reemplazo` → campo `auto_replacement`\n"
        f"- key `copago_reemplazo` → campo `copago_reemplazo`\n"
        f"- key `taller` → campo `workshop`\n"
        f"- key `reposicion_a_nuevo` → campo `reposicion_a_nuevo`\n"
        f"- key `perdida_total` → campo `perdida_total`\n"
        f"- key `asistencia` → campo `assistance`\n"
        f"- key `asiento_pasajeros` → campo `asiento_pasajeros`\n"
        f"- key `defensa_penal` → campo `defensa_penal`\n\n"
        f"**NO pongas \"No especificado\" si la extracción tiene el dato.** Revisa `coverages[]` Y `extra_features[]` de cada extracción. "
        f"Si un key aparece con `present: true`, DEBES usar su `raw_value` (o `raw_label` si no hay raw_value).\n\n"
        f"### Regla de RC con Límite Único Combinado (LUC)\n"
        f"Si la extracción indica que la RC es un \"Límite Único y Combinado\", los campos rc_emergente, rc_moral y rc_lucro_cesante "
        f"deben mostrar el monto total seguido de \"(LUC)\". Ejemplo: si el LUC es de 1.500 UF, pon:\n"
        f"- rc_emergente: \"1.500 UF (LUC)\"\n"
        f"- rc_moral: \"1.500 UF (LUC)\"\n"
        f"- rc_lucro_cesante: \"1.500 UF (LUC)\"\n"
        f"NO pongas \"Incluido en LUC\" ni \"--\" — siempre incluye el monto numérico.\n"
        f"Un LUC por sí solo NO implica `rc_exceso`: si no existe una capa adicional explícita, usa `rc_exceso.summary.value = \"No incluye\"`.\n\n"
        f"### Regla de RC en exceso de RC base\n"
        f"`rc_exceso` representa una capa adicional que entra a cubrir solo después de agotarse la RC base. "
        f"Debe permanecer separada de `rc`, `rc_emergente`, `rc_moral` y `rc_lucro_cesante`.\n"
        f"- Si la extracción declara RC base UF 2.000 y `rc_exceso` UF 3.000, muestra `rc_exceso.summary.value = \"UF 3.000 adicionales\"`; no muestres UF 5.000 y no alteres los montos base.\n"
        f"- Si la extracción trae `rc_exceso.present = false`, usa `rc_exceso.summary.value = \"No incluye\"`.\n"
        f"- Si ambas pólizas no incluyen RC en exceso, clasifica `IGUAL`. Si una oferta agrega una capa explícita frente a una póliza actual sin ella, clasifica `MEJORA`. Si reduce o elimina una capa existente, clasifica `PEOR`.\n"
        f"- No conviertas menciones de SOAP, salud, kilómetros adicionales, carga o deducibles en `rc_exceso`.\n\n"
        f"### Regla de prima mensual\n"
        f"Si la póliza actual solo tiene prima anual (ej: `annual_premium_uf: 12.04`) y cuotas (ej: 12), "
        f"calcula `monthly_premium_uf = annual_premium_uf / installments`. "
        f"El resultado es un decimal pequeño (ej: 12.04/12 = 1.003 UF), NO 1003. "
        f"Verifica que `monthly_premium_uf` esté entre 0.3 y 5.0 UF para vehículos particulares.\n\n"
        f"### recommendation\n"
        f"- `headline_insight`: frase comercial específica mencionando el producto recomendado y su ventaja "
        f"principal con números concretos. Si hay póliza actual, puedes hablar de ahorro o mejora vs. hoy. "
        f"Si no hay póliza actual, habla de posición relativa en el set: más barata, más completa o mejor equilibrio. NO uses frases genéricas.\n"
        f"- `reason_summary`: resumen corto del motivo de la recomendación.\n"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
