import json
import os


DEFAULT_APP_VERSION = "1.3.0"


def resolve_backend_app_version(root_dir):
    manual_version = os.environ.get("BACKEND_APP_VERSION", "").strip()
    if manual_version:
        return manual_version, "env"

    package_json_path = os.path.join(root_dir, "homes-frontend", "package.json")
    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)
        version = str(package_json.get("version", "")).strip()
        if version:
            return version, package_json_path
    except Exception:
        pass

    return DEFAULT_APP_VERSION, "default"
