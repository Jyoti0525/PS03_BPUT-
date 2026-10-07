"""Synthetic Indian lab reports for measuring OCR (EVALUATION.md, "OCR field accuracy"). Nothing here is a real person's
report: names, labs and values are drawn at random from a fixed seed, so the same set is rebuilt anywhere.

Each report is a printed table in the usual Indian layout (test, result, unit, biological reference interval) with a
header (lab, patient, age/sex, dates). It is saved once per capture type, so the types are compared on the same
content:
* scan        — flat, straight, 150 dpi;
* photo       — a phone photo: tilted, perspective, uneven light, slight blur, sensor noise, JPEG;
* poor_photo  — the same, worse: more blur and tilt, dim light. The quality gate should ask for a retake on many;
* photocopy   — thresholded black and white with speckle, a little thickened;
* thermal     — a narrow slip in a monospaced font, faded grey print (glucometer / small-lab printers).

Usage: python backend/scripts/make_ocr_set.py [out_dir=models/eval/ocr_synth] [n_reports=40] [seed=20261006] [b2]
The development set (tuning) uses the default seed; the held-out set in EVALUATION.md uses seed 777, never tuned on.
Writes <type>/<id>.jpg|png and truth.json ({id: {rows: [...], patient_name, date}}).
"""

import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS = "C:/Windows/Fonts"
SERIF, SANS = ["times.ttf", "georgia.ttf", "cambria.ttc"], ["arial.ttf", "calibri.ttf", "tahoma.ttf", "verdana.ttf", "segoeui.ttf", "ARIALN.TTF", "trebuc.ttf"]
MONO = ["cour.ttf", "consola.ttf", "lucon.ttf"]

FIRST = "Asha Ritu Sunita Pooja Lakshmi Meena Kavita Priya Anjali Rekha Ramesh Suresh Manoj Rajesh Sanjay Amit Bikash Pradeep Debasis Sibani Mamata Sasmita Gopal Arjun Farida Imran Salma Joseph Mary Harpreet".split()
LAST = "Devi Kumari Sahoo Mohanty Das Nayak Patra Behera Swain Mishra Sharma Verma Singh Yadav Patel Reddy Rao Iyer Nair Khan Ansari Gill Thomas Hembram Murmu".split()
LABS = ["Sanjeevani Diagnostics", "Shree Pathology Lab", "Arogya Clinical Laboratory", "Kalinga Diagnostic Centre", "Jeevan Path Lab",
        "City Care Diagnostics", "Utkal Pathology", "Lifeline Laboratory", "Swasthya Diagnostics", "Nirmal Path Lab"]

# test key, printed names, value maker(rng) -> (printed value, value as the parser should report it per µL etc.), unit
# choices, printed reference choices ((lo, hi) in the printed unit; None side = open).
def _f(lo, hi, nd):
    return lambda r: (lambda v: (f"{v:.{nd}f}", round(v, nd)))(r.uniform(lo, hi))


def _indian(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *parts, tail]) if head else ",".join([*parts, tail])


def _count(lo, hi, step):
    def make(r):
        v = int(round(r.uniform(lo, hi) / step) * step)
        return (_indian(v) if r.random() < 0.6 else str(v)), v
    return make


def _platelets(r):
    v = int(round(r.uniform(40000, 520000) / 1000) * 1000)
    style = r.choice(["indian", "plain", "lakh"])
    if style == "lakh":
        return f"{v / 100000:.2f}", v, "lakhs/cumm", ("1.50", "4.50")
    return (_indian(v) if style == "indian" else str(v)), v, "/cumm", ("1,50,000", "4,50,000")


SPECS = {
    "glucose_fasting": (["Fasting Blood Sugar", "Blood Sugar (Fasting)", "FBS", "Glucose Fasting"], _f(62, 260, 0), ["mg/dL", "mg/dl"], [(70, 100), (70, 110)]),
    "glucose_pp": (["Post Prandial Blood Sugar", "PPBS", "Blood Sugar PP"], _f(80, 340, 0), ["mg/dL", "mg/dl"], [(70, 140), (None, 140)]),
    "glucose_random": (["Random Blood Sugar", "RBS"], _f(70, 380, 0), ["mg/dL"], [(70, 140), (None, 140)]),
    "hba1c": (["HbA1c", "Glycated Haemoglobin (HbA1c)", "Glycosylated Hemoglobin"], _f(4.4, 12.5, 1), ["%"], [(4.0, 5.6), (None, 5.7)]),
    "haemoglobin": (["Haemoglobin", "Hemoglobin", "Hb"], _f(6.5, 16.8, 1), ["g/dL", "gm/dL"], [(12.0, 15.0), (13.0, 17.0), (11.5, 16.0)]),
    "pcv": (["PCV", "Packed Cell Volume", "Haematocrit"], _f(22, 52, 1), ["%"], [(36, 46), (40, 50)]),
    "wbc": (["Total WBC Count", "Total Leucocyte Count", "TLC"], _count(2500, 21000, 100), ["/cumm", "cells/cumm", "/µL"], [(4000, 11000), ("4,000", "11,000")]),
    "platelets": (["Platelet Count", "Platelets"], None, None, None),
    "creatinine": (["Serum Creatinine", "Creatinine"], _f(0.5, 4.8, 2), ["mg/dL"], [(0.6, 1.3), (0.5, 1.1), (0.7, 1.4)]),
    "urea": (["Blood Urea", "Serum Urea"], _f(12, 140, 0), ["mg/dL"], [(15, 45), (17, 43)]),
    "potassium": (["Serum Potassium", "Potassium (K+)"], _f(2.9, 6.8, 1), ["mmol/L", "mEq/L"], [(3.5, 5.1), (3.5, 5.0)]),
    "sodium": (["Serum Sodium", "Sodium (Na+)"], _f(124, 152, 0), ["mmol/L", "mEq/L"], [(135, 145), (136, 145)]),
    "cholesterol": (["Total Cholesterol", "Serum Cholesterol"], _f(120, 320, 0), ["mg/dL"], [(None, 200), (125, 200)]),
    "triglycerides": (["Triglycerides"], _f(60, 480, 0), ["mg/dL"], [(None, 150), (35, 150)]),
    "hdl": (["HDL Cholesterol"], _f(24, 78, 0), ["mg/dL"], [(40, 60)]),
    "ldl": (["LDL Cholesterol"], _f(50, 220, 0), ["mg/dL"], [(None, 100), (None, 130)]),
    "bilirubin": (["Total Bilirubin", "Serum Bilirubin (Total)"], _f(0.2, 6.5, 1), ["mg/dL"], [(0.2, 1.2), (0.3, 1.0)]),
    "alt": (["SGPT (ALT)", "SGPT"], _f(8, 260, 0), ["U/L", "IU/L"], [(7, 56), (None, 40)]),
    "ast": (["SGOT (AST)", "SGOT"], _f(10, 240, 0), ["U/L", "IU/L"], [(10, 40), (None, 40)]),
    "tsh": (["TSH", "Thyroid Stimulating Hormone"], _f(0.05, 14.0, 2), ["µIU/mL", "uIU/mL"], [(0.4, 4.0), (0.35, 5.5)]),
}
QUAL = {"malaria": (["Malaria Antigen (RDT)", "Malaria Parasite"], ["Negative", "Positive"]),
        "dengue_ns1": (["Dengue NS1 Antigen"], ["Negative", "Positive"]),
        "urine_albumin": (["Urine Albumin"], ["Nil", "Trace", "1+", "2+", "3+"])}
PANELS = [
    ("HAEMATOLOGY", ["haemoglobin", "pcv", "wbc", "platelets"]),
    ("BIOCHEMISTRY", ["glucose_fasting", "glucose_pp", "hba1c", "creatinine", "urea"]),
    ("BIOCHEMISTRY", ["glucose_random", "potassium", "sodium", "creatinine", "urea"]),
    ("LIPID PROFILE", ["cholesterol", "triglycerides", "hdl", "ldl"]),
    ("LIVER FUNCTION TEST", ["bilirubin", "alt", "ast"]),
    ("THYROID PROFILE", ["tsh"]),
    ("SEROLOGY", ["malaria", "dengue_ns1"]),
    ("URINE ROUTINE", ["urine_albumin"]),
]


def _fmt_ref(lo, hi) -> str:
    def s(x):  # 12.0 stays "12.0" as labs print it; 70 stays "70"
        return x if isinstance(x, str) else f"{x:.1f}" if isinstance(x, float) and x == int(x) else f"{x:g}"
    return f"< {s(hi)}" if lo is None else f"{s(lo)} - {s(hi)}"


def _num(s) -> float:
    return float(str(s).replace(",", ""))


def report(rng: random.Random, i: int) -> dict:
    name = f"{rng.choice(['Mr.', 'Mrs.', 'Ms.', ''])} {rng.choice(FIRST)} {rng.choice(LAST)}".strip()
    day, month = rng.randint(1, 28), rng.choice([7, 8, 9, 10])
    sections, used = [], set()
    for title, keys in rng.sample(PANELS, rng.randint(2, 3)):
        rows = []
        for k in keys:
            if k in used:  # two biochemistry panels share creatinine and urea; a report prints each test once
                continue
            used.add(k)
            if k in QUAL:
                names, vals = QUAL[k]
                v = rng.choice(vals)
                rows.append({"test_key": k, "printed": rng.choice(names), "value": v, "value_num": None, "unit": "",
                             "ref": "Nil" if k == "urine_albumin" else "Negative", "lo": None, "hi": None, "out": v not in ("Negative", "Nil")})
                continue
            if k == "platelets":
                printed_v, num, unit, (lo, hi) = _platelets(rng)
                ref = f"{lo} - {hi}"
                lo_n, hi_n = (_num(lo) * 100000, _num(hi) * 100000) if unit.startswith("lakh") else (_num(lo), _num(hi))
            else:
                names, make, units, refs = SPECS[k]
                printed_v, num = make(rng)
                unit = rng.choice(units)
                lo, hi = rng.choice(refs)
                ref = _fmt_ref(lo, hi)
                lo_n, hi_n = (None if lo is None else _num(lo)), _num(hi)
            printed = rng.choice(["Platelet Count", "Platelets"]) if k == "platelets" else rng.choice(SPECS[k][0])
            rows.append({"test_key": k, "printed": printed, "value": printed_v, "value_num": num, "unit": unit, "ref": ref,
                         "lo": lo_n, "hi": hi_n, "out": (lo_n is not None and num < lo_n) or num > hi_n})
        sections.append((title, rows))
    return {"id": f"r{i:03d}", "lab": rng.choice(LABS), "patient_name": name, "age": rng.randint(18, 78), "sex": rng.choice("MF"),
            "date": f"2026-{month:02d}-{day:02d}", "date_printed": f"{day:02d}/{month:02d}/2026", "sections": sections,
            "font": rng.choice(SANS + SERIF)}


# ---------------------------------------------------------------- B2 set (argument "b2"): panels whose values must add up
# Values are drawn as an analyser holds them (unrounded) and each is rounded only where it is printed, so the set carries
# the rounding a real report does. 60 % of labs print their own H / L marks; about one report in five prints glucose,
# creatinine or HbA1c in SI units. The default set (no "b2") is unchanged: same seed, same images.

DIFF = ("neutrophils", "lymphocytes", "monocytes", "eosinophils", "basophils")
DIFF_NAMES = {"neutrophils": ["Neutrophils", "Polymorphs"], "lymphocytes": ["Lymphocytes"], "monocytes": ["Monocytes"],
              "eosinophils": ["Eosinophils"], "basophils": ["Basophils"]}
DIFF_REFS = {"neutrophils": (40, 80), "lymphocytes": (20, 40), "monocytes": (2, 10), "eosinophils": (1, 6), "basophils": (0, 2)}
ABS_REFS = {"neutrophils": (2000, 7000), "lymphocytes": (1000, 3000), "monocytes": (200, 1000), "eosinophils": (20, 500), "basophils": (0, 100)}


def _r(k, names, value: str, unit: str, lo, hi, rng, conv=None) -> dict:
    """A printed row; `conv` takes a printed number to the unit the parser reports (x1000 for 10^3/µL, mmol/L to mg/dL)."""
    conv = conv or (lambda x: x)
    num = conv(_num(value))
    lo_n = None if lo is None else conv(_num(lo))
    hi_n = None if hi is None else conv(_num(hi))
    return {"test_key": k, "printed": rng.choice(names) if isinstance(names, list) else names, "value": value, "value_num": num, "unit": unit,
            "ref": _fmt_ref(lo, hi), "lo": lo_n, "hi": hi_n, "out": (lo_n is not None and num < lo_n) or (hi_n is not None and num > hi_n)}


def _cbc(rng, sex) -> list[dict]:
    hb, mchc = rng.uniform(6.5, 16.8), rng.uniform(29.5, 35.0)
    pcv = hb / mchc * 100
    mcv = rng.uniform(62, 112)
    rbc = pcv / mcv * 10
    mch = hb / rbc * 10
    wbc = int(round(rng.uniform(2500, 21000) / 100) * 100)
    f = [rng.uniform(35, 85), rng.uniform(10, 50), rng.uniform(2, 11), rng.uniform(0.5, 12), rng.uniform(0, 1.5)]
    f = [x / sum(f) * 100 for x in f]
    if rng.random() < 0.6:  # a counted differential: whole cells per hundred, adding to exactly 100
        pct = [round(x) for x in f]
        pct[0] += 100 - sum(pct)
        f, pct_s = pct, [str(p) for p in pct]
    else:  # a 5-part analyser: one decimal, adding to 100 give or take rounding
        pct_s = [f"{x:.1f}" for x in f]
    male = sex == "M"
    rows = [
        _r("haemoglobin", ["Haemoglobin", "Hemoglobin (Hb)"], f"{hb:.1f}", rng.choice(["g/dL", "gm/dL"]), *((13.0, 17.0) if male else (12.0, 15.0)), rng),
        _r("pcv", ["PCV", "Packed Cell Volume", "Haematocrit"], f"{pcv:.1f}", "%", *((40, 50) if male else (36, 46)), rng),
        _r("rbc", ["RBC Count", "Total RBC Count", "Red Blood Cell Count"], f"{rbc:.2f}", rng.choice(["mill/cumm", "million/µL", "x10^6/µL"]),
           *(("4.5", "5.5") if male else ("3.8", "4.8")), rng),
        _r("mcv", ["MCV", "Mean Corpuscular Volume"], f"{mcv:.1f}", "fL", 83, 101, rng),
        _r("mch", "MCH", f"{mch:.1f}", "pg", 27, 32, rng),
        _r("mchc", "MCHC", f"{mchc:.1f}", "g/dL", 31.5, 34.5, rng),
        _r("wbc", ["Total WBC Count", "Total Leucocyte Count", "TLC"], _indian(wbc) if rng.random() < 0.5 else str(wbc), rng.choice(["/cumm", "cells/cumm"]),
           4000, 11000, rng),
    ]
    rows += [_r(c, DIFF_NAMES[c], s, "%", *DIFF_REFS[c], rng) for c, s in zip(DIFF, pct_s)]
    k3 = rng.random() < 0.4  # absolute counts printed in thousands per µL
    for c, frac in zip(DIFF, f):
        a, (lo, hi) = frac * wbc / 100, ABS_REFS[c]
        name = c[:-1].capitalize()
        names = [f"Absolute {name} Count", f"{name}s (Absolute)"] + (["Absolute Eosinophil Count (AEC)"] if c == "eosinophils" else [])
        if k3:
            rows.append(_r(f"abs_{c}", names, f"{a / 1000:.2f}", "x10^3/µL", f"{lo / 1000:.2f}", f"{hi / 1000:.2f}", rng, conv=lambda x: x * 1000))
        else:
            rows.append(_r(f"abs_{c}", names, str(int(round(a))), rng.choice(["/cumm", "cells/µL"]), lo, hi, rng))
    printed_v, num, unit, (lo, hi) = _platelets(rng)
    scale = 100000 if unit.startswith("lakh") else 1
    rows.append({**_r("platelets", ["Platelet Count", "Platelets"], printed_v, unit, lo, hi, rng, conv=lambda x: x * scale), "value_num": num})
    return rows


def _lft(rng) -> list[dict]:
    tp = rng.uniform(5.2, 8.6)
    alb = rng.uniform(2.2, min(5.2, tp - 1.5))
    glob = tp - alb
    bt = rng.uniform(0.3, 6.5)
    bd = bt * rng.uniform(0.08, 0.6)
    nd = rng.choice([1, 2])
    out = [
        _r("bilirubin", ["Total Bilirubin", "Bilirubin (Total)"], f"{bt:.{nd}f}", "mg/dL", 0.2, 1.2, rng),
        _r("bilirubin_direct", ["Direct Bilirubin", "Bilirubin (Direct)"], f"{bd:.{nd}f}", "mg/dL", 0.0, 0.3, rng),
        _r("bilirubin_indirect", ["Indirect Bilirubin", "Bilirubin (Indirect)"], f"{bt - bd:.{nd}f}", "mg/dL", 0.2, 0.8, rng),
    ]
    for k in ("alt", "ast"):
        names, make, units, refs = SPECS[k]
        v, _ = make(rng)
        out.append(_r(k, names, v, rng.choice(units), *rng.choice(refs), rng))
    out += [
        _r("total_protein", ["Total Protein", "Serum Total Protein"], f"{tp:.1f}", "g/dL", 6.0, 8.3, rng),
        _r("albumin", ["Albumin", "Serum Albumin"], f"{alb:.1f}", "g/dL", 3.5, 5.2, rng),
        _r("globulin", "Globulin", f"{glob:.1f}", "g/dL", 2.0, 3.5, rng),
        _r("ag_ratio", ["A/G Ratio", "Albumin/Globulin Ratio"], f"{alb / glob:.2f}", "", 1.0, 2.2, rng),
    ]
    return out


def _lipid(rng) -> list[dict]:
    tg, hdl, ldl = rng.uniform(60, 380), rng.uniform(26, 75), rng.uniform(55, 210)
    vldl = tg / 5
    tc = hdl + ldl + vldl
    nd = rng.choice([1, 2])
    return [
        _r("cholesterol", ["Total Cholesterol", "Serum Cholesterol"], f"{tc:.0f}", "mg/dL", None, 200, rng),
        _r("triglycerides", "Triglycerides", f"{tg:.0f}", "mg/dL", None, 150, rng),
        _r("hdl", "HDL Cholesterol", f"{hdl:.0f}", "mg/dL", 40, 60, rng),
        _r("ldl", ["LDL Cholesterol", "LDL Cholesterol (Calculated)"], f"{ldl:.0f}", "mg/dL", None, 100, rng),
        _r("vldl", ["VLDL Cholesterol", "VLDL"], f"{vldl:.{rng.choice([0, 1])}f}", "mg/dL", None, 30, rng),
        _r("non_hdl", "Non-HDL Cholesterol", f"{tc - hdl:.0f}", "mg/dL", None, 130, rng),
        _r("tc_hdl_ratio", ["Total Cholesterol/HDL Ratio", "Chol/HDL Ratio"], f"{tc / hdl:.{nd}f}", "", None, 4.5, rng),
        _r("ldl_hdl_ratio", "LDL/HDL Ratio", f"{ldl / hdl:.{nd}f}", "", None, 3.0, rng),
    ]


def _kft(rng) -> list[dict]:
    urea = rng.uniform(12, 140)
    out = [_r("urea", ["Blood Urea", "Serum Urea"], f"{urea:.0f}", "mg/dL", 15, 45, rng),
           _r("bun", ["Blood Urea Nitrogen (BUN)", "BUN"], f"{urea / 2.14:.1f}", "mg/dL", 7, 20, rng)]
    cr = rng.uniform(0.5, 4.8)
    if rng.random() < 0.2:
        out.append(_r("creatinine", ["Serum Creatinine", "Creatinine"], f"{cr * 88.42:.0f}", "µmol/L", 62, 106, rng, conv=lambda x: x / 88.42))
    else:
        out.append(_r("creatinine", ["Serum Creatinine", "Creatinine"], f"{cr:.2f}", "mg/dL", 0.6, 1.3, rng))
    for k in ("potassium", "sodium"):
        names, make, units, refs = SPECS[k]
        v, _ = make(rng)
        out.append(_r(k, names, v, rng.choice(units), *rng.choice(refs), rng))
    return out


def _diabetes(rng) -> list[dict]:
    g = rng.uniform(62, 260)
    if rng.random() < 0.2:
        out = [_r("glucose_fasting", ["Fasting Blood Sugar", "Glucose Fasting"], f"{g / 18.016:.1f}", "mmol/L", "3.9", "5.6", rng, conv=lambda x: x * 18.016)]
    else:
        out = [_r("glucose_fasting", ["Fasting Blood Sugar", "Glucose Fasting"], f"{g:.0f}", "mg/dL", 70, 100, rng)]
    names, make, units, refs = SPECS["glucose_pp"]
    v, _ = make(rng)
    out.append(_r("glucose_pp", names, v, "mg/dL", *rng.choice(refs), rng))
    a1c = rng.uniform(4.4, 12.5)
    if rng.random() < 0.2:  # IFCC units
        out.append(_r("hba1c", ["HbA1c", "Glycated Haemoglobin (HbA1c)"], f"{(a1c - 2.15) * 10.929:.0f}", "mmol/mol", 20, 38, rng,
                      conv=lambda x: x / 10.929 + 2.15))
    else:
        out.append(_r("hba1c", ["HbA1c", "Glycated Haemoglobin (HbA1c)"], f"{a1c:.1f}", "%", 4.0, 5.6, rng))
    return out


B2_PANELS = [("HAEMATOLOGY", _cbc), ("LIVER FUNCTION TEST", _lft), ("LIPID PROFILE", _lipid), ("KIDNEY FUNCTION TEST", _kft), ("DIABETES PROFILE", _diabetes)]


def report_b2(rng: random.Random, i: int) -> dict:
    r = report(rng, i)  # header fields (name, lab, date, font) as in the default set
    flags = rng.random() < 0.6
    sections = []
    for title, make in rng.sample(B2_PANELS, 2):
        rows = make(rng, r["sex"]) if make is _cbc else make(rng)
        for row in rows:
            row["flag"] = ("H" if row["hi"] is not None and row["value_num"] > row["hi"] else "L") if flags and row["out"] else ""
        sections.append((title, rows))
    return {**r, "sections": sections, "flags": flags, "step": 40}


def _font(name: str, size: int):
    return ImageFont.truetype(f"{FONTS}/{name}", size)


def draw_a4(r: dict, rng: random.Random) -> Image.Image:
    W, H = 1240, 1754
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    f, fb = _font(r["font"], 24), _font(r["font"], 34)
    d.text((W // 2, 70), r["lab"].upper(), font=fb, fill=0, anchor="mm")
    d.text((W // 2, 112), "NABL style report · Plot 12, Main Road · Ph 0674-2xxxxxx", font=_font(r["font"], 18), fill=60, anchor="mm")
    d.line((60, 140, W - 60, 140), fill=0, width=2)
    d.text((70, 165), f"Patient Name : {r['patient_name']}", font=f, fill=0)
    d.text((760, 165), f"Age/Sex : {r['age']} Y / {r['sex']}", font=f, fill=0)
    d.text((70, 205), "Ref. By : Dr. Self", font=f, fill=0)
    d.text((760, 205), f"Date : {r['date_printed']}", font=f, fill=0)
    d.line((60, 245, W - 60, 245), fill=0, width=1)
    cols = (70, 560, 790, 960) if rng.random() < 0.5 else (70, 520, 740, 930)
    y = 270
    for c, h in zip(cols, ["Test Name", "Result", "Unit", "Biological Ref. Interval"]):
        d.text((c, y), h, font=_font(r["font"], 22), fill=0)
    y += 50
    for title, rows in r["sections"]:
        d.text((W // 2, y), title, font=_font(r["font"], 24), fill=0, anchor="mt")
        y += 48
        for row in rows:
            d.text((cols[0], y), row["printed"], font=f, fill=0)
            d.text((cols[1], y), row["value"], font=f, fill=0)
            if row.get("flag"):
                d.text((cols[1] + 140, y), row["flag"], font=f, fill=0)
            d.text((cols[2], y), row["unit"], font=f, fill=0)
            d.text((cols[3], y), row["ref"], font=f, fill=0)
            y += r.get("step", 46)
        y += 20
    d.text((W // 2, y + 30), "*** End of Report ***", font=_font(r["font"], 20), fill=0, anchor="mm")
    d.text((W - 300, H - 150), "Pathologist", font=f, fill=0)
    return im


def draw_thermal(r: dict, rng: random.Random) -> Image.Image:
    rows = [row for _, s in r["sections"] for row in s]
    W, H = 640, 330 + 44 * len(rows) + 120
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    f = _font(rng.choice(MONO), 21)
    d.text((W // 2, 40), r["lab"], font=f, fill=0, anchor="mm")
    d.text((20, 90), f"Name: {r['patient_name']}", font=f, fill=0)
    d.text((20, 130), f"Age/Sex: {r['age']}/{r['sex']}  Date: {r['date_printed']}", font=f, fill=0)
    d.text((20, 175), "-" * 46, font=f, fill=0)
    y = 215
    for row in rows:
        d.text((20, y), row["printed"][:22], font=f, fill=0)
        d.text((330, y), " ".join(x for x in (row["value"], row.get("flag", ""), row["unit"]) if x), font=f, fill=0)
        y += 22
        d.text((330, y), f"({row['ref']})", font=_font("cour.ttf", 17), fill=0)
        y += 22
    d.text((20, y + 20), "-" * 46, font=f, fill=0)
    # fading: thermal print greys out unevenly
    a = np.array(im).astype(np.float32)
    fade = np.linspace(rng.uniform(0.0, 0.25), rng.uniform(0.3, 0.55), W)[None, :]
    a = 255 - (255 - a) * (1 - fade)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _photo(gray: np.ndarray, rng: random.Random, poor: bool) -> np.ndarray:
    h, w = gray.shape
    pad = 80
    bg = np.full((h + 2 * pad, w + 2 * pad), rng.randint(40, 110), np.uint8)
    bg[pad:pad + h, pad:pad + w] = gray
    j = 0.05 if poor else 0.03
    src = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    dst = src + np.float32([[rng.uniform(-j, j) * w, rng.uniform(-j, j) * h] for _ in range(4)])
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(bg, M, (bg.shape[1], bg.shape[0]), borderValue=int(bg[0, 0]))
    ang = rng.uniform(-6, 6) if poor else rng.uniform(-2.5, 2.5)
    R = cv2.getRotationMatrix2D((out.shape[1] / 2, out.shape[0] / 2), ang, 1.0)
    out = cv2.warpAffine(out, R, (out.shape[1], out.shape[0]), borderValue=int(bg[0, 0]))
    # uneven light: a gradient from one corner, dimmer overall for a poor photo
    yy, xx = np.mgrid[0:out.shape[0], 0:out.shape[1]].astype(np.float32)
    g = (xx / out.shape[1] * rng.uniform(-1, 1) + yy / out.shape[0] * rng.uniform(-1, 1))
    light = (0.55 if poor else 0.85) + (0.25 if poor else 0.15) * (g - g.min()) / (np.ptp(g) + 1e-6)
    out = out.astype(np.float32) * light
    out = cv2.GaussianBlur(out, (0, 0), rng.uniform(1.4, 2.2) if poor else rng.uniform(0.5, 1.0))
    out += np.random.default_rng(rng.randint(0, 2**31)).normal(0, 9 if poor else 5, out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    scale = (rng.uniform(0.7, 0.85) if poor else rng.uniform(0.85, 1.0))
    return cv2.resize(out, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def _photocopy(gray: np.ndarray, rng: random.Random) -> np.ndarray:
    a = cv2.GaussianBlur(gray, (0, 0), 0.7)
    a = np.where(a < rng.randint(150, 190), 0, 255).astype(np.uint8)
    a = cv2.erode(a, np.ones((2, 2), np.uint8), iterations=1)  # strokes thicken
    n = np.random.default_rng(rng.randint(0, 2**31)).random(a.shape)
    a[n < 0.0015] = 0  # toner speckle
    return a


def main(out_dir: Path, n: int, seed: int = 20261006, b2: bool = False) -> None:
    rng = random.Random(seed)
    truth = {}
    for t in ("scan", "photo", "poor_photo", "photocopy", "thermal"):
        (out_dir / t).mkdir(parents=True, exist_ok=True)
    for i in range(n):
        r = report_b2(rng, i) if b2 else report(rng, i)
        a4 = draw_a4(r, rng)
        a4 = a4.rotate(rng.uniform(-0.4, 0.4), fillcolor=255, resample=Image.BICUBIC)
        g = np.array(a4)
        cv2.imwrite(str(out_dir / "scan" / f"{r['id']}.png"), g)
        cv2.imwrite(str(out_dir / "photo" / f"{r['id']}.jpg"), _photo(g, rng, False), [cv2.IMWRITE_JPEG_QUALITY, rng.randint(70, 88)])
        cv2.imwrite(str(out_dir / "poor_photo" / f"{r['id']}.jpg"), _photo(g, rng, True), [cv2.IMWRITE_JPEG_QUALITY, rng.randint(50, 65)])
        cv2.imwrite(str(out_dir / "photocopy" / f"{r['id']}.png"), _photocopy(g, rng))
        th = np.array(draw_thermal(r, rng))
        cv2.imwrite(str(out_dir / "thermal" / f"{r['id']}.jpg"), _photo(th, rng, False), [cv2.IMWRITE_JPEG_QUALITY, 85])
        truth[r["id"]] = {"patient_name": r["patient_name"], "date": r["date"], "font": r["font"],
                          "rows": [row for _, s in r["sections"] for row in s]}
    (out_dir / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{n} reports x 5 capture types -> {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "models/eval/ocr_synth"), int(sys.argv[2]) if len(sys.argv) > 2 else 40,
         int(sys.argv[3]) if len(sys.argv) > 3 else 20261006, len(sys.argv) > 4 and sys.argv[4] == "b2")
