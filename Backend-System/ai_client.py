import base64
import json
import os
import urllib.error
import urllib.request

from local_ai_settings import load_ai_settings


AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "180"))
DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def get_active_ai_model(settings=None):
    current = settings or load_ai_settings()
    if current.get("provider") == "api":
        return str(current.get("model") or "").strip()
    return str(current.get("procurement_model") or "").strip()


def get_active_ai_provider(settings=None):
    current = settings or load_ai_settings()
    return str(current.get("provider") or "ollama").strip() or "ollama"


def _build_ollama_payload(model, prompt, images):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
        },
    }
    if images:
        payload["images"] = images
    return payload


def _detect_image_mime(base64_value):
    try:
        raw = base64.b64decode(base64_value, validate=False)
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            return "image/webp"
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
    except Exception:
        pass
    return "image/jpeg"


def _build_api_messages(prompt, images):
    content = [{"type": "text", "text": prompt}]
    for item in images or []:
        value = str(item or "").strip()
        if not value:
            continue
        if value.startswith("data:image/"):
            url = value
        else:
            url = f"data:{_detect_image_mime(value)};base64,{value}"
        content.append({
            "type": "image_url",
            "image_url": {
                "url": url,
            },
        })
    return [{"role": "user", "content": content}]


def _extract_api_text(data):
    choices = data.get("choices") or []
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text" and item.get("text"):
                        texts.append(str(item.get("text")))
                    elif item.get("type") == "output_text" and item.get("text"):
                        texts.append(str(item.get("text")))
            if texts:
                return "\n".join(texts)
    if data.get("output_text"):
        return str(data.get("output_text"))
    raise RuntimeError("API 未返回可解析的文本结果")


def _resolve_chat_completions_url(settings):
    direct = str(settings.get("chat_completions_url") or "").strip().rstrip("/")
    if direct:
        return direct
    base_url = str(settings.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/chat/completions"


def _call_ollama_generate(settings, prompt, images, model_fallback, timeout_seconds):
    model = settings.get("procurement_model") or model_fallback
    ollama_base_url = settings.get("ollama_base_url") or DEFAULT_OLLAMA_BASE_URL
    payload = _build_ollama_payload(model, prompt, images)
    req = urllib.request.Request(
        f"{ollama_base_url.rstrip('/')}/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama 连接失败: {e}") from e


def _call_openai_compatible_generate(settings, prompt, images, timeout_seconds):
    api_key = str(settings.get("api_key") or "").strip()
    model = str(settings.get("model") or "").strip()
    url = _resolve_chat_completions_url(settings)
    if not api_key:
        raise RuntimeError("API Key 未配置")
    if not model:
        raise RuntimeError("API 模型未配置")
    if not url:
        raise RuntimeError("API 地址未配置")

    payload = {
        "model": model,
        "messages": _build_api_messages(prompt, images),
        "temperature": 0,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return {
                "response": _extract_api_text(data),
                "provider": "api",
                "model": model,
                "raw": data,
            }
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"API 调用失败: {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"API 连接失败: {e}") from e


def call_configured_ai(prompt, images=None, *, ollama_model_fallback="", timeout_seconds=None):
    settings = load_ai_settings()
    timeout = int(timeout_seconds or AI_TIMEOUT_SECONDS)
    provider = get_active_ai_provider(settings)
    if provider == "api":
        return _call_openai_compatible_generate(settings, prompt, images or [], timeout)
    return _call_ollama_generate(settings, prompt, images or [], ollama_model_fallback, timeout)
