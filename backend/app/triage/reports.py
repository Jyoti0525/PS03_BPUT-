"""Synthetic lab slips rendered as SVG, with per-row bounding boxes for source traceability."""

from datetime import date
from html import escape

SAMPLE_REPORTS: dict[str, dict] = {
    "glucose": {
        "title": "Blood sugar & HbA1c slip",
        "lab": "Sunrise Diagnostics (Synthetic)",
        "rows": [
            {"test": "Fasting Blood Sugar", "value": "310", "unit": "mg/dL", "ref": "70–110", "status": "abnormal", "field": "glucose"},
            {"test": "HbA1c", "value": "9.8", "unit": "%", "ref": "< 7.0", "status": "abnormal"},
            {"test": "Serum Creatinine", "value": "1.38", "unit": "mg/dL", "ref": "0.6–1.2", "status": "borderline"},
            {"test": "eGFR", "value": "54", "unit": "mL/min", "ref": "> 60", "status": "borderline"},
        ],
    },
    "cbc": {
        "title": "Complete blood count",
        "lab": "District Lab Services (Synthetic)",
        "rows": [
            {"test": "Haemoglobin", "value": "9.4", "unit": "g/dL", "ref": "12.0–15.0", "status": "abnormal", "field": "hb"},
            {"test": "Total WBC", "value": "11,800", "unit": "/µL", "ref": "4,000–11,000", "status": "borderline"},
            {"test": "Platelets", "value": "96,000", "unit": "/µL", "ref": "1.5–4.5 lakh", "status": "abnormal"},
            {"test": "PCV", "value": "31", "unit": "%", "ref": "36–46", "status": "abnormal"},
        ],
    },
    "anc": {
        "title": "Mother & child protection card",
        "lab": "MCP Card — Sub-Centre Entry (Synthetic)",
        "handwritten": True,
        "rows": [
            {"test": "Blood Pressure", "value": "150/98", "unit": "mmHg", "ref": "< 140/90", "status": "abnormal", "field": "bp"},
            {"test": "Urine Albumin", "value": "2+", "unit": "", "ref": "Nil", "status": "abnormal"},
            {"test": "Haemoglobin", "value": "9.6", "unit": "g/dL", "ref": "≥ 11.0", "status": "abnormal", "field": "hb"},
            {"test": "Fundal Height", "value": "31", "unit": "cm", "ref": "~ weeks", "status": "normal"},
        ],
    },
    "lipid": {
        "title": "Lipid profile",
        "lab": "CityCare Pathology (Synthetic)",
        "rows": [
            {"test": "Total Cholesterol", "value": "238", "unit": "mg/dL", "ref": "< 200", "status": "abnormal"},
            {"test": "LDL", "value": "162", "unit": "mg/dL", "ref": "< 100", "status": "abnormal"},
            {"test": "HDL", "value": "38", "unit": "mg/dL", "ref": "> 40", "status": "borderline"},
            {"test": "Triglycerides", "value": "180", "unit": "mg/dL", "ref": "< 150", "status": "borderline"},
        ],
    },
}

W, ROW_H, TOP = 640, 34, 150


def render(key: str, patient: str) -> tuple[str, list[list[float]]]:
    s = SAMPLE_REPORTS[key]
    rows = s["rows"]
    h = TOP + len(rows) * ROW_H + 90
    font = "'Comic Sans MS','Segoe Print',cursive" if s.get("handwritten") else "Courier New, monospace"
    body = []
    for i, r in enumerate(rows):
        y = TOP + i * ROW_H
        body.append(
            f'<g font-family="{font}" font-size="15" fill="#1f2937">'
            f'<text x="32" y="{y + 22}">{escape(r["test"])}</text>'
            f'<text x="330" y="{y + 22}" font-weight="700">{escape(r["value"])} {escape(r["unit"])}</text>'
            f'<text x="480" y="{y + 22}" fill="#6b7280" font-size="13">{escape(r["ref"])}</text>'
            f'<line x1="24" y1="{y + ROW_H}" x2="{W - 24}" y2="{y + ROW_H}" stroke="#e5e7eb"/></g>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">'
        f'<rect width="{W}" height="{h}" fill="#fffdf7"/>'
        f'<rect x="8" y="8" width="{W - 16}" height="{h - 16}" fill="none" stroke="#d6d3d1"/>'
        f'<text x="32" y="48" font-family="Georgia,serif" font-size="22" font-weight="700" fill="#0f172a">{escape(s["lab"])}</text>'
        f'<text x="32" y="72" font-family="Arial" font-size="12" fill="#b91c1c">SYNTHETIC SAMPLE — NOT A REAL PATIENT RECORD</text>'
        f'<text x="32" y="104" font-family="Arial" font-size="14" fill="#334155">Patient: {escape(patient)}</text>'
        f'<text x="400" y="104" font-family="Arial" font-size="14" fill="#334155">Date: {date.today().strftime("%d/%m/%Y")}</text>'
        f'<g font-family="Arial" font-size="12" font-weight="700" fill="#475569"><text x="32" y="138">TEST</text>'
        f'<text x="330" y="138">RESULT</text><text x="480" y="138">REFERENCE</text></g>'
        + "".join(body)
        + f'<text x="32" y="{h - 36}" font-family="Arial" font-size="12" fill="#64748b">Authorised signatory · Jeevia demo data generator</text></svg>'
    )
    boxes = [[16 / W, (TOP + i * ROW_H - 2) / h, (W - 32) / W, (ROW_H + 4) / h] for i in range(len(rows))]
    return svg, boxes
