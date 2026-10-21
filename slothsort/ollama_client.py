"""Thin wrapper over the local Ollama HTTP API."""
import base64
import json
import time

import httpx

from . import config


class OllamaError(RuntimeError):
    pass


def chat_json(prompt: str, schema: dict, images: list[bytes] | None = None,
              system: str | None = None, model: str | None = None) -> tuple[dict, dict]:
    """Run one chat turn constrained to `schema`. Returns (parsed_json, stats)."""
    model = model or config.MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    msg = {"role": "user", "content": prompt}
    if images:
        msg["images"] = [base64.b64encode(b).decode() for b in images]
    messages.append(msg)

    started = time.perf_counter()
    try:
        r = httpx.post(
            f"{config.OLLAMA_URL}/api/chat",
            timeout=config.OLLAMA_TIMEOUT,
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "format": schema,
                "keep_alive": "5m",  # free the memory when there is nothing to name
                "options": {"temperature": 0, "num_ctx": 4096},
            },
        )
    except httpx.HTTPError as e:
        raise OllamaError(f"Could not reach Ollama at {config.OLLAMA_URL}: {e}") from e
    if r.status_code != 200:
        raise OllamaError(f"Ollama returned {r.status_code}: {r.text[:300]}")

    body = r.json()
    content = body.get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise OllamaError(f"Model did not return valid JSON: {content[:300]}") from e

    stats = {
        "model": model,
        "seconds": round(time.perf_counter() - started, 1),
        "prompt_tokens": body.get("prompt_eval_count"),
        "output_tokens": body.get("eval_count"),
    }
    return parsed, stats


def list_models() -> list[str]:
    try:
        r = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except httpx.HTTPError:
        return []
