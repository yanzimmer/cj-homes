# 该文件负责封装阿里云身份证 OCR 调用与结果字段解析。
import io
import json
import re

from alibabacloud_ocr_api20210707.client import Client as OcrClient
from alibabacloud_ocr_api20210707 import models as ocr_models
from alibabacloud_tea_openapi import models as open_api_models

from ocr_settings import get_ocr_runtime_config


def aliyun_ocr_is_configured():
    runtime = get_ocr_runtime_config()
    return bool(runtime["access_key_id"] and runtime["access_key_secret"])


def _build_ocr_client():
    runtime = get_ocr_runtime_config()
    access_key_id = runtime["access_key_id"]
    access_key_secret = runtime["access_key_secret"]
    if not access_key_id or not access_key_secret:
        raise ValueError("阿里云 OCR 未配置，请填写 ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=runtime["endpoint"],
        read_timeout=10000,
        connect_timeout=5000,
    )
    return OcrClient(config)


def _normalize_birth_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(re.findall(r"\d+", text))
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return ""


def _safe_quality_int(value):
    try:
        return int(float(value))
    except Exception:
        return None


def _load_response_data(payload):
    if payload is None:
        return {}
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {}
    if isinstance(payload, dict):
        return payload
    return {}


def parse_cn_id_card_ocr_result(data):
    parsed = _load_response_data(data)
    root_data = parsed.get("data", {}) or {}
    face = root_data.get("face", {}) or root_data.get("faceResult", {}) or {}
    face_data = face.get("data", {}) or {}
    if not face_data and isinstance(root_data, dict):
        face_data = root_data.get("faceData", {}) or {}
    if not face_data and isinstance(root_data, dict):
        face_data = {
            "name": root_data.get("name"),
            "sex": root_data.get("sex"),
            "ethnicity": root_data.get("ethnicity"),
            "birthDate": root_data.get("birthDate"),
            "idNumber": root_data.get("idNumber"),
            "address": root_data.get("address"),
        }
    warning = face.get("warning", {}) or {}
    fields = {
        "name": str(face_data.get("name") or "").strip(),
        "gender": str(face_data.get("sex") or "").strip(),
        "nation": str(face_data.get("ethnicity") or "").strip(),
        "birth_date": _normalize_birth_date(face_data.get("birthDate")),
        "id_card": str(face_data.get("idNumber") or "").strip(),
        "address": str(face_data.get("address") or "").strip(),
    }
    quality = {
        "completeness_score": _safe_quality_int(warning.get("completenessScore")),
        "quality_score": _safe_quality_int(warning.get("qualityScore")),
        "is_copy": _safe_quality_int(warning.get("isCopy")),
        "is_reshoot": _safe_quality_int(warning.get("isReshoot")),
        "tamper_score": _safe_quality_int(warning.get("tamperScore")),
    }
    hints = []
    if quality["is_copy"] == 1:
        hints.append("检测到图片可能是复印件。")
    if quality["is_reshoot"] == 1:
        hints.append("检测到图片可能是翻拍件。")
    if quality["completeness_score"] is not None and quality["completeness_score"] < 80:
        hints.append("身份证边缘可能不完整，请尽量完整拍摄。")
    if quality["quality_score"] is not None and quality["quality_score"] < 70:
        hints.append("图片清晰度一般，建议重新拍摄。")
    return {
        "fields": fields,
        "quality": quality,
        "hints": hints,
        "raw": parsed,
    }


def recognize_cn_id_card(image_bytes):
    client = _build_ocr_client()
    request = ocr_models.RecognizeIdcardRequest(
        body=io.BytesIO(image_bytes),
        output_quality_info=True,
        output_figure=False,
    )
    response = client.recognize_idcard(request)
    if int(response.status_code or 0) >= 400:
        raise RuntimeError(f"阿里云 OCR 调用失败，HTTP {response.status_code}")
    body = response.body
    code = str(body.code or "").strip().upper()
    message = str(body.message or "").strip()
    if code and code not in ("200", "OK"):
        raise RuntimeError(message or f"阿里云 OCR 识别失败：{code}")
    if body.data in (None, "", {}):
        raise RuntimeError(message or "阿里云 OCR 未返回识别结果")
    result = parse_cn_id_card_ocr_result(body.data)
    if not result["fields"]["id_card"] and not result["fields"]["name"]:
        raise ValueError("未识别到身份证正面信息，请上传身份证人像面（正面）")
    return result
