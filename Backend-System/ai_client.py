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


def _build_api_responses_input(prompt, images):
    content = [{"type": "input_text", "text": prompt}]
    for item in images or []:
        value = str(item or "").strip()
        if not value:
            continue
        if value.startswith("data:image/"):
            url = value
        else:
            url = f"data:{_detect_image_mime(value)};base64,{value}"
        content.append({
            "type": "input_image",
            "image_url": url,
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
    output = data.get("output") or []
    if isinstance(output, list):
        texts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text_value = content.get("text")
                if content.get("type") in {"output_text", "text"} and text_value:
                    texts.append(str(text_value))
        if texts:
            return "\n".join(texts)
    raise RuntimeError("API 未返回可解析的文本结果")


def _resolve_chat_completions_url(settings):
    direct = str(settings.get("chat_completions_url") or "").strip().rstrip("/")
    if direct:
        return direct
    base_url = str(settings.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/chat/completions"


def _resolve_responses_url(settings):
    direct = str(settings.get("responses_url") or "").strip().rstrip("/")
    if direct:
        return direct
    base_url = str(settings.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/responses"


def _build_multimodal_not_supported_error(settings, detail):
    model = str(settings.get("model") or "").strip() or "未配置模型"
    base_url = str(settings.get("base_url") or "").strip() or "未配置地址"
    message = (
        f"当前 API 模型或接口不支持图片输入。当前配置为 {model} @ {base_url}。"
        "如果需要图片识别，请切换到支持视觉的模型/接口，或改用本地 Ollama 视觉模型。"
    )
    detail_text = str(detail or "").strip()
    if detail_text:
        return f"{message} 原始错误: {detail_text}"
    return message


def _is_multimodal_not_supported_error(detail):
    text = str(detail or "")
    return (
        "unknown variant `image_url`" in text
        or "expected `text`" in text
        or "does not support images" in text.lower()
        or "image input is not supported" in text.lower()
    )


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
    has_images = bool(images)
    explicit_responses_url = str(settings.get("responses_url") or "").strip()
    base_url = str(settings.get("base_url") or "").strip().lower()
    use_responses_api = has_images and bool(
        explicit_responses_url
        or "api.openai.com" in base_url
    )
    url = _resolve_responses_url(settings) if use_responses_api else _resolve_chat_completions_url(settings)
    if not api_key:
        raise RuntimeError("API Key 未配置")
    if not model:
        raise RuntimeError("API 模型未配置")
    if not url:
        raise RuntimeError("API 地址未配置")

    if use_responses_api:
        payload = {
            "model": model,
            "input": _build_api_responses_input(prompt, images),
        }
    else:
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
        if has_images and _is_multimodal_not_supported_error(detail):
            raise RuntimeError(_build_multimodal_not_supported_error(settings, detail)) from e
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
