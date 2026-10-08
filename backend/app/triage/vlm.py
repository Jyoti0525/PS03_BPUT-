"""Second document-type label from a small vision-language model (Qwen3-VL-4B-Instruct, Apache-2.0, on llama.cpp).

The deterministic label (images.doc_type, from the OCR text) decides what the app does with a picture. This model only
looks at the picture and names its type from the same list; when the two differ, the reviewer is told to look. It
never changes the label, never reads values and never sees the patient's name (only the image is sent, to a server on
the same machine). Off unless JEEVIA_VLM_URL points at a llama-server started by scripts/start_vlm.sh.
"""

import base64
import io
import json
import re
import urllib.error
import urllib.request

from app.config import get_settings
from app.triage.images import DOC_TYPES

PROMPT = (
    "Look at this picture from a patient at an Indian clinic. Which ONE of these is it?\n"
    "lab_report: printed lab test results with values and reference ranges\n"
    "prescription: a doctor's prescription, printed or handwritten\n"
    "medicine_strip: a medicine blister strip, bottle or box\n"
    "discharge_summary: a hospital discharge summary\n"
    "maternal_card: a mother and child protection card\n"
    "other_document: any other paper or card with text\n"
    "non_document: not a document (a wound, a rash, a person, a room)\n"
    "Answer with the label only."
)


def enabled() -> bool:
    return bool(get_settings().vlm_url)


def parse(text: str) -> str | None:
    """The first known label in the reply; None when there is none (the reply is then ignored, not guessed)."""
    t = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).lower()
    found = [(t.find(k), k) for k in DOC_TYPES if k in t]
    return min(found)[1] if found else None


SIDE = 768  # long side in pixels: enough to tell a report from a strip, and a page costs seconds, not minutes, on CPU


def _small(image: bytes) -> tuple[bytes, str] | None:
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(image)).convert("RGB")
    except Exception:
        return None
    im.thumbnail((SIDE, SIDE))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def label(image: bytes, content_type: str = "image/jpeg") -> dict | None:
    """{'type', 'label', 'engine'} or None when the server is off, unreachable or unclear."""
    s = get_settings()
    if not s.vlm_url or not content_type.startswith("image/"):
        return None
    small = _small(image)
    if small is None:
        return None
    url = f"data:{small[1]};base64,{base64.b64encode(small[0]).decode()}"
    body = {"model": s.vlm_model_name, "temperature": 0, "max_tokens": 12,
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": PROMPT}]}]}
    req = urllib.request.Request(s.vlm_url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=s.vlm_timeout_s) as r:  # nosec B310: http(s) URL checked in config
            reply = json.loads(r.read())["choices"][0]["message"]["content"]
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError):
        return None
    kind = parse(reply)
    return {"type": kind, "label": DOC_TYPES[kind], "engine": s.vlm_model_name} if kind else None


def compare(rule_label: dict, image: bytes, content_type: str) -> tuple[dict | None, str | None]:
    """The model's label and, when it differs from the rule label, a warning for the reviewer."""
    got = label(image, content_type)
    if not got or got["type"] == rule_label.get("type"):
        return got, None
    return got, f'The image model sees this as "{got["label"]}", the text reading as "{rule_label.get("label")}" — check the picture'
