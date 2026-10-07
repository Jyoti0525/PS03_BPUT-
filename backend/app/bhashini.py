"""Bhashini (MeitY ULCA, online, India-hosted): translation, used when the offline IndicTrans2 cannot run (the stub
profile, the hosted link, or a model not downloaded).

Two steps, as the ULCA pipeline API asks: get the pipeline's service id and inference key, then call it. Plain REST over
httpx. Unset keys = not used. What is sent: the text to translate only, never a name (patient text is scrubbed before
translation, app/privacy.py).
"""

import logging
from functools import lru_cache

import httpx

from .config import get_settings

log = logging.getLogger("jeevia.bhashini")
CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
PIPELINE_ID = "64392f96daac500b55c543cd"  # MeitY's public pipeline
ENGINE = "Bhashini (online)"
LANGS = {"en", "hi", "or", "bn", "ta", "te", "gu", "kn", "ml", "mr", "pa", "as", "ur", "ne", "kok", "ks", "sd", "sa", "sat", "mni", "brx", "mai", "doi"}


class BhashiniUnavailable(Exception):
    """No keys, a language not covered, or the service could not be reached."""


def enabled() -> bool:
    s = get_settings()
    return bool(s.bhashini_user_id and s.bhashini_api_key)


def _post(url: str, headers: dict, body: dict) -> dict:
    try:
        r = httpx.post(url, headers=headers, json=body, timeout=get_settings().sarvam_timeout_s)
    except httpx.HTTPError as e:
        raise BhashiniUnavailable("Could not reach Bhashini") from e
    if r.status_code >= 400:
        log.warning("bhashini error", extra={"status": r.status_code})
        raise BhashiniUnavailable(f"Bhashini error {r.status_code}")
    return r.json()


@lru_cache(maxsize=64)
def _service(src: str, tgt: str) -> tuple[str, str, str, str]:
    s = get_settings()
    cfg = _post(CONFIG_URL, {"userID": s.bhashini_user_id, "ulcaApiKey": s.bhashini_api_key},
                {"pipelineTasks": [{"taskType": "translation", "config": {"language": {"sourceLanguage": src, "targetLanguage": tgt}}}],
                 "pipelineRequestConfig": {"pipelineId": PIPELINE_ID}})
    try:
        ep = cfg["pipelineInferenceAPIEndPoint"]
        sid = cfg["pipelineResponseConfig"][0]["config"][0]["serviceId"]
        return ep["callbackUrl"], ep["inferenceApiKey"]["name"], ep["inferenceApiKey"]["value"], sid
    except (KeyError, IndexError, TypeError) as e:
        raise BhashiniUnavailable(f"No Bhashini translation for {src} → {tgt}") from e


def translate(texts: list[str], src: str, tgt: str) -> dict:
    if not enabled():
        raise BhashiniUnavailable("Bhashini is not configured")
    if src not in LANGS or tgt not in LANGS:
        raise BhashiniUnavailable(f"No Bhashini translation for {src} → {tgt}")
    url, key_name, key, sid = _service(src, tgt)
    out = _post(url, {key_name: key}, {
        "pipelineTasks": [{"taskType": "translation", "config": {"language": {"sourceLanguage": src, "targetLanguage": tgt}, "serviceId": sid}}],
        "inputData": {"input": [{"source": t} for t in texts]}})
    try:
        return {"texts": [o["target"] for o in out["pipelineResponse"][0]["output"]], "engine": ENGINE}
    except (KeyError, IndexError, TypeError) as e:
        raise BhashiniUnavailable("Unexpected Bhashini reply") from e
