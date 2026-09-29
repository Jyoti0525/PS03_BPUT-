"""Email one-time codes (optional second channel next to SMS).

* none  — email sign-in is switched off (default).
* mock  — the code is returned to the client (local development and tests only).
* brevo — Brevo transactional email API (https://api.brevo.com/v3/smtp/email). The API key lives only
          in the server environment (JEEVIA_BREVO_API_KEY); the sender must be verified in Brevo.
"""

import logging

import httpx
from fastapi import HTTPException

from .config import get_settings

log = logging.getLogger("jeevia.mail")
BREVO = "https://api.brevo.com/v3/smtp/email"

from html import escape

# Copy for each purpose, in the interface languages. {code} / {min} are filled in.
COPY = {
    "en": {
        "subject": {"signin": "Your Jeevia sign-in code: {code}", "register": "Verify your email for Jeevia: {code}", "add": "Confirm your email for Jeevia: {code}"},
        "lead": {
            "signin": "Use the code below to sign in to Jeevia.",
            "register": "Use the code below to verify your email and finish creating your Jeevia account.",
            "add": "Use the code below to add this email to your Jeevia account.",
        },
        "hi": "Hi {name},", "hi_anon": "Hello,", "valid": "This code is valid for {min} minutes.",
        "expires": "This code expires in <b>{min} minutes</b>. Do not share it with anyone — Jeevia staff will never ask for it.",
        "ignore": "If you didn't request this code, you can safely ignore this email.",
        "tagline": "Triage support for India's health facilities", "footer": "Triage support only · not a diagnosis",
    },
    "hi": {
        "subject": {"signin": "आपका Jeevia साइन-इन कोड: {code}", "register": "Jeevia के लिए अपनी ईमेल सत्यापित करें: {code}", "add": "Jeevia के लिए अपनी ईमेल की पुष्टि करें: {code}"},
        "lead": {
            "signin": "Jeevia में साइन इन करने के लिए नीचे दिया कोड डालें।",
            "register": "अपनी ईमेल सत्यापित कर Jeevia खाता बनाने के लिए नीचे दिया कोड डालें।",
            "add": "इस ईमेल को अपने Jeevia खाते में जोड़ने के लिए नीचे दिया कोड डालें।",
        },
        "hi": "नमस्ते {name},", "hi_anon": "नमस्ते,", "valid": "यह कोड {min} मिनट तक मान्य है।",
        "expires": "यह कोड <b>{min} मिनट</b> में समाप्त हो जाएगा। इसे किसी के साथ साझा न करें — Jeevia स्टाफ़ कभी यह कोड नहीं माँगेगा।",
        "ignore": "अगर आपने यह कोड नहीं माँगा था, तो इस ईमेल को अनदेखा करें।",
        "tagline": "भारत के स्वास्थ्य केंद्रों के लिए ट्राइएज सहायता", "footer": "केवल ट्राइएज सहायता · निदान नहीं",
    },
    "or": {
        "subject": {"signin": "ଆପଣଙ୍କ Jeevia ସାଇନ୍-ଇନ୍ କୋଡ୍: {code}", "register": "Jeevia ପାଇଁ ଆପଣଙ୍କ ଇମେଲ ଯାଞ୍ଚ କରନ୍ତୁ: {code}", "add": "Jeevia ପାଇଁ ଆପଣଙ୍କ ଇମେଲ ନିଶ୍ଚିତ କରନ୍ତୁ: {code}"},
        "lead": {
            "signin": "Jeevia ରେ ସାଇନ୍ ଇନ୍ କରିବାକୁ ତଳ କୋଡ୍ ବ୍ୟବହାର କରନ୍ତୁ।",
            "register": "ଇମେଲ ଯାଞ୍ଚ କରି Jeevia ଖାତା ତିଆରି ସମ୍ପୂର୍ଣ୍ଣ କରିବାକୁ ତଳ କୋଡ୍ ବ୍ୟବହାର କରନ୍ତୁ।",
            "add": "ଏହି ଇମେଲକୁ ଆପଣଙ୍କ Jeevia ଖାତାରେ ଯୋଡ଼ିବାକୁ ତଳ କୋଡ୍ ବ୍ୟବହାର କରନ୍ତୁ।",
        },
        "hi": "ନମସ୍କାର {name},", "hi_anon": "ନମସ୍କାର,", "valid": "ଏହି କୋଡ୍ {min} ମିନିଟ୍ ପର୍ଯ୍ୟନ୍ତ ବୈଧ।",
        "expires": "ଏହି କୋଡ୍ <b>{min} ମିନିଟ୍</b> ରେ ମିଆଦ ପୂରିବ। କାହା ସହ ବାଣ୍ଟନ୍ତୁ ନାହିଁ — Jeevia କର୍ମଚାରୀ କେବେ ଏହା ମାଗିବେ ନାହିଁ।",
        "ignore": "ଯଦି ଆପଣ ଏହି କୋଡ୍ ମାଗି ନାହାନ୍ତି, ଏହି ଇମେଲକୁ ଅଣଦେଖା କରନ୍ତୁ।",
        "tagline": "ଭାରତର ସ୍ୱାସ୍ଥ୍ୟ କେନ୍ଦ୍ର ପାଇଁ ଟ୍ରାଏଜ୍ ସହାୟତା", "footer": "କେବଳ ଟ୍ରାଏଜ୍ ସହାୟତା · ରୋଗ ନିର୍ଣ୍ଣୟ ନୁହେଁ",
    },
}


def render(code: str, purpose: str = "signin", name: str | None = None, lang: str = "en", minutes: int = 5) -> tuple[str, str, str]:
    """Subject, HTML and plain text for a one-time-code email (Jeevia brand: coral → teal header, dark card)."""
    c = COPY.get(lang, COPY["en"])
    purpose = purpose if purpose in c["subject"] else "signin"
    subject = c["subject"][purpose].format(code=code)
    greet = c["hi"].format(name=escape(name)) if name else c["hi_anon"]
    lead = f"{c['lead'][purpose]} {c['valid'].format(min=minutes)}"
    digits = "&nbsp;".join(escape(ch) for ch in code)
    font = "'Segoe UI',Roboto,'Noto Sans','Noto Sans Devanagari','Noto Sans Oriya',Arial,sans-serif"
    html = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f4f5f8;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(subject)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f8;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;border-radius:18px;overflow:hidden;background:#12142a;font-family:{font};">
  <tr><td align="center" style="background:#ef8a8f;background-image:linear-gradient(120deg,#ec7f86 0%,#f29191 45%,#f7adad 100%);padding:34px 24px 30px;">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="width:40px;height:40px;border-radius:12px;background:#ffffff;text-align:center;vertical-align:middle;font-size:26px;font-weight:800;line-height:40px;color:#f29191;">+</td>
      <td style="padding-left:12px;font-size:30px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">Jeevia</td>
    </tr></table>
    <div style="margin-top:10px;font-size:15px;color:#ffffff;opacity:.95;">{escape(c['tagline'])}</div>
  </td></tr>
  <tr><td style="padding:34px 32px 8px;color:#e9eaf2;">
    <p style="margin:0 0 14px;font-size:17px;">{greet if not name else greet.replace(escape(name), f'<b style="color:#ffffff">{escape(name)}</b>')}</p>
    <p style="margin:0 0 26px;font-size:15px;line-height:1.6;color:#c6c8d6;">{lead}</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td align="center" style="border:2px solid #5fc7c9;border-radius:14px;background:#0e2a35;padding:22px 10px;">
        <span style="font-family:'SFMono-Regular',Menlo,Consolas,monospace;font-size:40px;font-weight:700;letter-spacing:10px;padding-left:10px;color:#8ee3e4;">{digits}</span>
      </td>
    </tr></table>
    <p style="margin:26px 0 30px;font-size:13px;line-height:1.6;color:#9a9cb0;text-align:center;">{c['expires'].format(min=minutes)}</p>
  </td></tr>
  <tr><td style="border-top:1px solid #262944;padding:18px 32px 24px;text-align:center;">
    <p style="margin:0 0 6px;font-size:12px;color:#8a8ca2;">{escape(c['ignore'])}</p>
    <p style="margin:0;font-size:11px;color:#62657c;">Jeevia · {escape(c['footer'])}</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""
    text = f"{greet}\n\n{c['lead'][purpose]}\n\n    {code}\n\n{c['valid'].format(min=minutes)}\n{c['ignore']}\n\nJeevia · {c['footer']}"
    return subject, html, text


def enabled() -> bool:
    s = get_settings()
    return s.email_provider == "mock" or (s.email_provider == "brevo" and bool(s.brevo_api_key and s.email_from))


def send_code(email: str, code: str, purpose: str = "signin", name: str | None = None, lang: str = "en") -> None:
    s = get_settings()
    if s.email_provider == "mock":
        log.info("mock email code issued")
        return
    if not enabled():
        raise HTTPException(503, "Email codes are not enabled on this server")
    subject, html, text = render(code, purpose, name, lang, max(1, s.otp_ttl_sec // 60))
    body = {
        "sender": {"name": s.email_from_name, "email": s.email_from},
        "to": [{"email": email}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
        "tags": ["jeevia-otp"],
    }
    try:
        r = httpx.post(BREVO, json=body, headers={"api-key": s.brevo_api_key or "", "accept": "application/json"}, timeout=15)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the email provider — try again")
    if r.status_code >= 400:
        log.warning("brevo send failed", extra={"status": r.status_code})
        raise HTTPException(502, "The email could not be sent — check the address or try again")
