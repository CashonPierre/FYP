# STL
import json
import logging
from typing import Any

# External
from openai import OpenAI
from pydantic import ValidationError

# Custom
from app_common.enums import ExceptionEnum
from app_common.exceptions import AppError
from configs import settings
from .schemas import BuildGraphResponse, BuiltGraph
from .system_prompt import SYSTEM_PROMPT


logger = logging.getLogger(__name__)

# Cap the self-correction loop. 1 retry is plenty — if the second attempt
# still fails, the user's prompt is likely ambiguous and we should surface
# the error rather than burn more credit.
_MAX_RETRIES = 1


class LLMConfigError(AppError):
  """OPENROUTER_API_KEY missing — the feature is disabled."""

  status_code: int = 503
  error_code: ExceptionEnum = ExceptionEnum.APP_ERROR


class LLMGraphError(AppError):
  """The LLM returned output that didn't validate as a runnable graph."""

  status_code: int = 422
  error_code: ExceptionEnum = ExceptionEnum.APP_ERROR


def _client() -> OpenAI:
  if not settings.openrouter_api_key:
    raise LLMConfigError(
      message="AI graph builder is not configured on this server."
    )
  return OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
  )


def _extract_json(text: str) -> dict[str, Any]:
  """Strip fenced code blocks and parse. Some models wrap JSON in ```json."""
  stripped = text.strip()
  if stripped.startswith("```"):
    stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
    if stripped.endswith("```"):
      stripped = stripped.rsplit("```", 1)[0]
    stripped = stripped.strip()
    if stripped.lower().startswith("json\n"):
      stripped = stripped[5:]
  return json.loads(stripped)


def _parse_and_validate(
  text: str,
) -> tuple[BuiltGraph, str]:
  """Parse the LLM response. Raises LLMGraphError on malformed JSON
  or schema-invalid graphs."""
  if not text:
    raise LLMGraphError(message="LLM returned an empty response.")

  try:
    raw = _extract_json(text)
  except json.JSONDecodeError as exc:
    logger.warning("LLM output was not valid JSON: %s", text[:500])
    raise LLMGraphError(
      message=f"LLM did not return valid JSON: {exc}"
    ) from exc

  graph_data = raw.get("graph", raw) if isinstance(raw, dict) else raw
  notes = raw.get("notes", "") if isinstance(raw, dict) else ""

  try:
    graph = BuiltGraph.model_validate(graph_data)
  except ValidationError as exc:
    logger.warning("LLM graph failed validation: %s", exc.errors())
    raise LLMGraphError(
      message="LLM produced an invalid graph. "
      f"Validation errors: {exc.errors()[:5]}"
    ) from exc

  return graph, str(notes)


def build_graph_from_prompt(prompt: str) -> BuildGraphResponse:
  """Translate a natural-language strategy idea into a validated graph.

  If the LLM's first attempt fails validation, we feed the error back
  into the same conversation and ask for a correction. Capped at one
  retry so cost stays bounded."""
  client = _client()
  messages: list[dict[str, str]] = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": prompt},
  ]

  last_error: LLMGraphError | None = None
  for attempt in range(_MAX_RETRIES + 1):
    try:
      completion = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=messages,
        temperature=0.2,
        response_format={"type": "json_object"},
      )
    except Exception as exc:
      logger.exception("OpenRouter call failed")
      raise LLMGraphError(
        message=f"LLM request failed: {exc}"
      ) from exc

    text = (completion.choices[0].message.content or "").strip()

    try:
      graph, notes = _parse_and_validate(text)
      return BuildGraphResponse(graph=graph, notes=notes)
    except LLMGraphError as exc:
      last_error = exc
      if attempt >= _MAX_RETRIES:
        break
      logger.info(
        "LLM graph invalid on attempt %d — retrying with error context",
        attempt + 1,
      )
      messages.append({"role": "assistant", "content": text})
      messages.append({
        "role": "user",
        "content": (
          "Your previous response failed validation:\n"
          f"{exc.message}\n\n"
          "Return a corrected JSON object. Fix only the issues listed; "
          "keep the rest of the graph the same. Output JSON only, no prose."
        ),
      })

  assert last_error is not None
  raise last_error
