import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(BASE_DIR, "config", "ai_settings.json")
ALLOWED_PROCUREMENT_MODELS = ["qwen3.5:4b", "qwen3.5:2b", "qwen3.5:0.8b"]
DEFAULT_SETTINGS = {
    "enabled": True,
    "provider": os.getenv("AI_PROVIDER", "ollama"),
    "procurement_model": os.getenv("PROCUREMENT_AI_MODEL", "qwen3.5:4b"),
    "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    "base_url": os.getenv("AI_API_BASE_URL", ""),
    "chat_completions_url": os.getenv("AI_API_CHAT_COMPLETIONS_URL", ""),
    "responses_url": os.getenv("AI_API_RESPONSES_URL", ""),
    "model": os.getenv("AI_API_MODEL", ""),
    "api_key": os.getenv("AI_API_KEY", ""),
    "updated_at": "",
}


def _normalize_provider(value):
    text = str(value or "").strip().lower()
    if text in {"api", "openai", "compatible"}:
        return "api"
    return "ollama"


def _normalize_model(value):
    text = str(value or "").strip()
    return text if text in ALLOWED_PROCUREMENT_MODELS else "qwen3.5:4b"


def _normalize_ollama_base_url(value):
    text = str(value or "").strip().rstrip("/")
    if not text:
        return "http://127.0.0.1:11434"
    if not (text.startswith("http://") or text.startswith("https://")):
        text = f"http://{text}"
    return text.rstrip("/")


def _normalize_optional_url(value):
    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    if not (text.startswith("http://") or text.startswith("https://")):
        text = f"https://{text}"
    return text.rstrip("/")


def load_ai_settings():
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            data = {}

    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["provider"] = _normalize_provider(merged.get("provider"))
    merged["procurement_model"] = _normalize_model(merged.get("procurement_model"))
    merged["ollama_base_url"] = _normalize_ollama_base_url(merged.get("ollama_base_url"))
    merged["base_url"] = _normalize_optional_url(merged.get("base_url"))
    merged["chat_completions_url"] = _normalize_optional_url(merged.get("chat_completions_url"))
    merged["responses_url"] = _normalize_optional_url(merged.get("responses_url"))
    merged["model"] = str(merged.get("model") or "").strip()
    merged["api_key"] = str(merged.get("api_key") or "").strip()
    return merged


def save_ai_settings(data):
    current = load_ai_settings()
    if isinstance(data, dict) and "enabled" in data:
        current["enabled"] = bool(data.get("enabled"))
    if isinstance(data, dict) and "provider" in data:
        current["provider"] = _normalize_provider(data.get("provider"))
    if isinstance(data, dict) and "procurement_model" in data:
        current["procurement_model"] = _normalize_model(data.get("procurement_model"))
    if isinstance(data, dict) and "ollama_base_url" in data:
        current["ollama_base_url"] = _normalize_ollama_base_url(data.get("ollama_base_url"))
    if isinstance(data, dict) and "base_url" in data:
        current["base_url"] = _normalize_optional_url(data.get("base_url"))
    if isinstance(data, dict) and "chat_completions_url" in data:
        current["chat_completions_url"] = _normalize_optional_url(data.get("chat_completions_url"))
    if isinstance(data, dict) and "responses_url" in data:
        current["responses_url"] = _normalize_optional_url(data.get("responses_url"))
    if isinstance(data, dict) and "model" in data:
        current["model"] = str(data.get("model") or "").strip()
    if isinstance(data, dict) and "api_key" in data:
        current["api_key"] = str(data.get("api_key") or "").strip()
    current["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current
