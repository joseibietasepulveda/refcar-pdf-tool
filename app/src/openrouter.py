import json
import os
import time
import httpx
from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from .metrics import CallMetrics


DEFAULT_ANALYSIS_MAX_TOKENS = 16384
PREFERRED_ANALYSIS_MAX_TOKENS = 65536
DEFAULT_MAX_ATTEMPTS = 3
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_BACKOFF_SECONDS = (8, 18, 35, 55)


class OpenRouterClient:
    """Wrapper over OpenRouter API with built-in metrics tracking."""

    def __init__(self, model: str):
        self.model = model
        self._prices: dict[str, dict] = {}
        self._supported_parameters: dict[str, set[str]] = {}
        self._max_completion_tokens: dict[str, int] = {}
        self._client = httpx.Client(
            base_url=OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv(
                    "OPENROUTER_HTTP_REFERER",
                    "http://localhost",
                ),
                "X-OpenRouter-Title": os.getenv(
                    "OPENROUTER_APP_TITLE",
                    "Herramienta Seguros PDF",
                ),
            },
            timeout=180.0,
        )

    def fetch_model_prices(self):
        """Fetch pricing info from OpenRouter for cost calculation."""
        try:
            resp = self._client.get("/models")
            resp.raise_for_status()
            data = resp.json()
            for m in data.get("data", []):
                mid = m.get("id", "")
                pricing = m.get("pricing", {})
                self._prices[mid] = {
                    "prompt": float(pricing.get("prompt", "0")),
                    "completion": float(pricing.get("completion", "0")),
                }
                self._supported_parameters[mid] = set(m.get("supported_parameters", []))
                max_tokens = m.get("top_provider", {}).get("max_completion_tokens")
                if isinstance(max_tokens, int) and max_tokens > 0:
                    self._max_completion_tokens[mid] = max_tokens
        except Exception:
            pass

    def _calculate_cost(self, tokens_in: int, tokens_out: int) -> float:
        prices = self._prices.get(self.model, {})
        if not prices:
            return 0.0
        cost_in = tokens_in * prices.get("prompt", 0)
        cost_out = tokens_out * prices.get("completion", 0)
        return cost_in + cost_out

    def _calculate_response_cost(self, usage: dict, tokens_in: int, tokens_out: int) -> float:
        """Prefer OpenRouter's billed cost when available, then fall back to catalog prices."""
        try:
            if usage.get("cost") is not None:
                return float(usage["cost"])
        except (TypeError, ValueError):
            pass
        return self._calculate_cost(tokens_in, tokens_out)

    def _analysis_max_tokens(self) -> int:
        """Use each model's advertised output ceiling, capped to a practical maximum."""
        model_limit = self._max_completion_tokens.get(self.model)
        if model_limit:
            return min(model_limit, PREFERRED_ANALYSIS_MAX_TOKENS)
        return DEFAULT_ANALYSIS_MAX_TOKENS

    @staticmethod
    def _error_text(error_detail) -> str:
        if isinstance(error_detail, str):
            return error_detail
        try:
            return json.dumps(error_detail, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(error_detail)

    @classmethod
    def _is_embedded_rate_limit(cls, error_detail) -> bool:
        text = cls._error_text(error_detail).lower()
        return "rate_limit_exceeded" in text or '"code": 429' in text or "'code': 429" in text

    @staticmethod
    def _is_rate_limit_text(text: str) -> bool:
        lowered = text.lower()
        return "rate_limit_exceeded" in lowered or "rate limit" in lowered or "code': 429" in lowered or '"code": 429' in lowered

    @staticmethod
    def _rate_limit_message(step_name: str) -> str:
        return (
            f"OpenRouter alcanzó un límite temporal de uso en el paso '{step_name}'. "
            "Las extracciones ya quedaron guardadas; espera 1-2 minutos y presiona "
            "**Reintentar análisis**. Si vuelve a pasar seguido, normalmente es límite temporal "
            "del proveedor/modelo, no un problema de los PDFs."
        )

    @staticmethod
    def _retry_wait_seconds(attempt: int, *, rate_limited: bool) -> int:
        if rate_limited:
            idx = min(max(attempt - 1, 0), len(RATE_LIMIT_BACKOFF_SECONDS) - 1)
            return RATE_LIMIT_BACKOFF_SECONDS[idx]
        return 2 * attempt

    def _next_analysis_max_tokens(self, current: int) -> int | None:
        """Increase a conservative fallback ceiling if the catalog request was unavailable."""
        model_limit = self._max_completion_tokens.get(self.model, PREFERRED_ANALYSIS_MAX_TOKENS)
        ceiling = min(model_limit, PREFERRED_ANALYSIS_MAX_TOKENS)
        next_limit = min(current * 2, ceiling)
        return next_limit if next_limit > current else None

    @staticmethod
    def _is_valid_json_content(content: str) -> bool:
        """Return whether model content contains one complete JSON value."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if len(lines) < 3 or lines[-1].strip() != "```":
                return False
            cleaned = "\n".join(lines[1:-1])
        try:
            json.loads(cleaned)
            return True
        except (TypeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _parse_response_json(resp: httpx.Response, step_name: str) -> dict:
        """Parse OpenRouter JSON body; raise RuntimeError with context if invalid."""
        raw = (resp.text or "").strip()
        if not raw:
            raise RuntimeError(
                f"OpenRouter devolvió respuesta vacía en paso '{step_name}' "
                f"(HTTP {resp.status_code}). Suele ser timeout o corte de red; intenta de nuevo."
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            preview = raw[:500].replace("\n", " ")
            raise RuntimeError(
                f"OpenRouter devolvió un cuerpo que no es JSON en paso '{step_name}' "
                f"(HTTP {resp.status_code}): {exc}. Inicio de respuesta: {preview!r}"
            ) from exc

    def chat(self, messages: list[dict], step_name: str = "unknown") -> tuple[str, CallMetrics]:
        """Send a JSON chat completion request and return complete content plus billed metrics."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if "response_format" in self._supported_parameters.get(self.model, set()):
            payload["response_format"] = {"type": "json_object"}
            payload["provider"] = {"require_parameters": True}
        if step_name == "analysis":
            payload["max_tokens"] = self._analysis_max_tokens()

        last_error: Exception | None = None
        total_tokens_in = 0
        total_tokens_out = 0
        total_reasoning_tokens = 0
        total_cost = 0.0
        total_elapsed = 0.0
        resolved_model = ""

        max_attempts = RATE_LIMIT_MAX_ATTEMPTS

        for attempt in range(1, max_attempts + 1):
            start = time.perf_counter()
            try:
                resp = self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                last_error = RuntimeError(
                    f"Timeout de OpenRouter en paso '{step_name}' (intento {attempt}/{max_attempts}). "
                    "El análisis puede tardar; vuelve a intentar."
                )
                if attempt < DEFAULT_MAX_ATTEMPTS:
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise last_error from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    f"Error de red con OpenRouter en paso '{step_name}': {exc}"
                ) from exc

            elapsed = time.perf_counter() - start

            if resp.status_code != 200:
                try:
                    error_body = self._parse_response_json(resp, step_name)
                    err = error_body.get("error")
                    if isinstance(err, dict):
                        error_msg = err.get("message") or json.dumps(err)[:800]
                    else:
                        error_msg = str(err) if err else resp.text[:800]
                except RuntimeError:
                    error_msg = (resp.text or "")[:800]
                if resp.status_code == 429 or self._is_rate_limit_text(error_msg):
                    last_error = RuntimeError(self._rate_limit_message(step_name))
                    if attempt < max_attempts:
                        time.sleep(self._retry_wait_seconds(attempt, rate_limited=True))
                        continue
                    raise last_error
                last_error = RuntimeError(
                    f"OpenRouter error ({resp.status_code}) en paso '{step_name}': {error_msg}"
                )
                if resp.status_code in (502, 503, 504) and attempt < DEFAULT_MAX_ATTEMPTS:
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise last_error

            try:
                data = self._parse_response_json(resp, step_name)
            except RuntimeError as exc:
                last_error = exc
                if attempt < DEFAULT_MAX_ATTEMPTS:
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise

            usage = data.get("usage", {})
            tokens_in = int(usage.get("prompt_tokens", 0) or 0)
            tokens_out = int(usage.get("completion_tokens", 0) or 0)
            reasoning_tokens = int(
                usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0) or 0
            )
            cost = self._calculate_response_cost(usage, tokens_in, tokens_out)
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out
            total_reasoning_tokens += reasoning_tokens
            total_cost += cost
            total_elapsed += elapsed
            resolved_model = str(data.get("model") or resolved_model or self.model)

            content = ""
            choices = data.get("choices", [])
            if not choices:
                last_error = RuntimeError(
                    f"OpenRouter no devolvió alternativas en paso '{step_name}' "
                    f"(intento {attempt}/{max_attempts})."
                )
                if attempt < DEFAULT_MAX_ATTEMPTS:
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise last_error

            choice = choices[0]
            content = choice.get("message", {}).get("content", "") or ""
            finish_reason = choice.get("finish_reason")
            native_finish_reason = choice.get("native_finish_reason")

            if finish_reason == "length":
                current_limit = int(payload.get("max_tokens", 0) or 0)
                next_limit = (
                    self._next_analysis_max_tokens(current_limit)
                    if step_name == "analysis" and current_limit
                    else None
                )
                last_error = RuntimeError(
                    f"OpenRouter cortó la respuesta por límite de salida en paso '{step_name}' "
                    f"(finish_reason='length', límite={current_limit or 'del proveedor'}, "
                    f"modelo={self.model!r})."
                )
                if attempt < DEFAULT_MAX_ATTEMPTS and next_limit:
                    payload["max_tokens"] = next_limit
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise last_error

            if finish_reason == "error" or choice.get("error"):
                error_detail = choice.get("error") or native_finish_reason or "sin detalle"
                if self._is_embedded_rate_limit(error_detail):
                    last_error = RuntimeError(self._rate_limit_message(step_name))
                    if attempt < max_attempts:
                        time.sleep(self._retry_wait_seconds(attempt, rate_limited=True))
                        continue
                    raise last_error
                last_error = RuntimeError(
                    f"OpenRouter devolvió un error dentro de la respuesta en paso '{step_name}': "
                    f"{self._error_text(error_detail)}"
                )
                if attempt < DEFAULT_MAX_ATTEMPTS:
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise last_error

            if not isinstance(content, str) or not self._is_valid_json_content(content):
                current_limit = int(payload.get("max_tokens", 0) or 0)
                next_limit = (
                    self._next_analysis_max_tokens(current_limit)
                    if step_name == "analysis" and current_limit
                    else None
                )
                last_error = RuntimeError(
                    f"OpenRouter devolvió JSON incompleto o inválido en paso '{step_name}' "
                    f"(intento {attempt}/{max_attempts}, finish_reason={finish_reason!r}, "
                    f"native_finish_reason={native_finish_reason!r})."
                )
                if attempt < DEFAULT_MAX_ATTEMPTS:
                    if next_limit:
                        payload["max_tokens"] = next_limit
                    time.sleep(self._retry_wait_seconds(attempt, rate_limited=False))
                    continue
                raise last_error

            metrics = CallMetrics(
                step=step_name,
                model=self.model,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                cost_usd=total_cost,
                time_seconds=total_elapsed,
                attempts=attempt,
                finish_reason=finish_reason or "",
                reasoning_tokens=total_reasoning_tokens,
                resolved_model=resolved_model,
            )

            return content, metrics

        if last_error:
            if self._is_rate_limit_text(str(last_error)):
                raise RuntimeError(self._rate_limit_message(step_name)) from last_error
            raise last_error
        raise RuntimeError(f"OpenRouter falló en paso '{step_name}' sin detalle.")

    def close(self):
        self._client.close()
