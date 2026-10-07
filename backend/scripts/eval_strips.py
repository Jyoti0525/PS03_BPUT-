"""Synthetic medicine-strip pictures (I1 image set) and how well they are read (B1 image understanding).

Each picture is the back of a blister strip, drawn here: foil colour, the generic name and strength printed several
times at an angle, "Tablets IP", batch, MFG and EXP dates, MRP and a manufacturer line. Generic names only (from the
PMBJP list the app uses); no real brand or company is drawn. One medicine per strip, five ways to see it:

* clean — the strip flat, as a scan;
* photo — a phone photo: tilt, perspective, uneven light, slight blur, noise (as make_ocr_set.py);
* glare — the photo with a bright reflection across the foil;
* blurred — out of focus;
* torn — only part of the strip (the left 45-60 %), as when the patient brings a cut piece.

For each picture: is it labelled a medicine strip, is the medicine found, is the strength read, and is any other
medicine reported (a false medicine). Pictures go to an output folder that is not committed.

Usage: python backend/scripts/eval_strips.py <image_dir> [n_per_variant=8] [seed=1008] [out=docs/evaluation/strips.json]
"""

import io
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_ocr_set import _photo  # noqa: E402

FONTS = "C:/Windows/Fonts"
SANS = ["arial.ttf", "arialbd.ttf", "calibri.ttf", "calibrib.ttf", "verdana.ttf", "tahoma.ttf"]
MEDS = [("Paracetamol", "500 mg"), ("Amlodipine", "5 mg"), ("Metformin", "500 mg"), ("Atorvastatin", "10 mg"), ("Telmisartan", "40 mg"),
        ("Losartan", "50 mg"), ("Cetirizine", "10 mg"), ("Pantoprazole", "40 mg"), ("Omeprazole", "20 mg"), ("Azithromycin", "500 mg"),
        ("Glimepiride", "2 mg"), ("Metoprolol", "25 mg"), ("Ibuprofen", "400 mg"), ("Diclofenac", "50 mg"), ("Salbutamol", "4 mg"),
        ("Levocetirizine", "5 mg"), ("Montelukast", "10 mg"), ("Ondansetron", "4 mg"), ("Doxycycline", "100 mg"), ("Ciprofloxacin", "500 mg")]
FOIL = [(196, 198, 202), (205, 190, 150), (170, 190, 205), (200, 175, 180), (185, 200, 180)]
INK = [(20, 40, 120), (130, 20, 30), (20, 90, 40), (30, 30, 30)]
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
VARIANTS = ("clean", "photo", "glare", "blurred", "torn")


def font(name: str, size: int):
    return ImageFont.truetype(f"{FONTS}/{name}", size)


def draw_strip(rng: random.Random, med: tuple[str, str]) -> Image.Image:
    name, strength = med
    W, H = 1100, 560
    im = Image.new("RGB", (W, H), rng.choice(FOIL))
    a = np.array(im).astype(np.float32)  # brushed foil: fine streaks
    a += np.random.default_rng(rng.randint(0, 2**31)).normal(0, 6, (H, 1, 1))
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    ink = rng.choice(INK)
    f = rng.choice(SANS)
    # the printed pattern repeats per pocket, slightly rotated
    tile = Image.new("RGBA", (520, 230), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.text((10, 10), f"{name} Tablets IP", font=font(f, 34), fill=ink)
    d.text((10, 58), f"{name} IP {strength}", font=font(f, 26), fill=ink)
    d.text((10, 98), "Store below 30°C. Protect from light.", font=font(f, 18), fill=ink)
    d.text((10, 128), "Schedule H Prescription Drug", font=font(f, 18), fill=ink)
    ang = rng.uniform(-8, 8)
    t = tile.rotate(ang, expand=True, resample=Image.BICUBIC)
    for x, y in ((20, 20), (560, 20), (20, 290), (560, 290)):
        im.paste(t, (x, y), t)
    d = ImageDraw.Draw(im)
    y0, m0 = 2025 + rng.randint(0, 1), rng.randrange(12)
    small = font(f, 20)
    d.text((40, H - 50), f"B.No. {rng.choice('ABCDEFGHK')}{rng.randint(10000, 99999)}   MFG.{MONTHS[m0]}.{y0}   EXP.{MONTHS[(m0 + 23) % 12]}.{y0 + 2}",
           font=small, fill=ink)
    d.text((620, H - 50), f"M.R.P. Rs.{rng.randint(12, 140)}.{rng.choice(['00', '50'])} for 10 tablets", font=small, fill=ink)
    d.text((40, H - 80), "Mfd. by: Sample Pharma Labs, Plot 4, Industrial Area (synthetic)", font=font(f, 16), fill=ink)
    return im


def glare(rgb: np.ndarray, rng: random.Random) -> np.ndarray:
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
    ang = rng.uniform(0, np.pi)
    u = (xx - cx) * np.cos(ang) + (yy - cy) * np.sin(ang)
    v = -(xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang)
    spot = np.exp(-(u / (0.35 * w)) ** 2 - (v / (0.07 * h)) ** 2)
    return np.clip(rgb.astype(np.float32) + 230 * spot[..., None], 0, 255).astype(np.uint8)


def variant(im: Image.Image, kind: str, rng: random.Random) -> Image.Image:
    rgb = np.array(im)
    if kind == "clean":
        return im
    if kind == "torn":
        w = rgb.shape[1]
        return Image.fromarray(rgb[:, : int(w * rng.uniform(0.45, 0.6))])
    if kind == "blurred":
        return Image.fromarray(cv2.GaussianBlur(rgb, (0, 0), rng.uniform(1.8, 2.6)))
    chans = [_photo(rgb[..., c], random.Random(s), False) for c, s in zip(range(3), [rng.randint(0, 2**31)] * 3)]
    photo = np.dstack(chans)
    return Image.fromarray(glare(photo, rng) if kind == "glare" else photo)


def main(image_dir: str, n: int = 8, seed: int = 1008, out: str = "docs/evaluation/strips.json") -> None:
    from app.triage.extraction import extract_document

    rng = random.Random(seed)
    folder = Path(image_dir)
    folder.mkdir(parents=True, exist_ok=True)
    rows, tally = [], {}
    for kind in VARIANTS:
        t = tally.setdefault(kind, {"n": 0, "labelled_strip": 0, "medicine_found": 0, "strength_right": 0, "false_medicines": 0})
        for i in range(n):
            med = MEDS[(VARIANTS.index(kind) * n + i) % len(MEDS)]
            pic = variant(draw_strip(rng, med), kind, rng)
            path = folder / f"{kind}_{i:02d}.jpg"
            pic.save(path, quality=88)
            buf = io.BytesIO()
            pic.save(buf, "JPEG", quality=88)
            ex = extract_document(buf.getvalue(), "image/jpeg")
            meds = ex["medicines"]
            hit = next((m for m in meds if med[0].lower() in m["name"].lower()), None)
            strength = (hit or {}).get("strength") or ""
            ok_strength = bool(hit) and strength.replace(" ", "").lower() == med[1].replace(" ", "").lower()
            others = [m["name"] for m in meds if m is not hit]
            t["n"] += 1
            t["labelled_strip"] += ex["doc_type"]["type"] == "medicine_strip"
            t["medicine_found"] += bool(hit)
            t["strength_right"] += ok_strength
            t["false_medicines"] += len(others)
            rows.append({"file": path.name, "variant": kind, "truth": f"{med[0]} {med[1]}", "doc_type": ex["doc_type"]["type"],
                         "found": [f"{m['name']} {m.get('strength') or ''}".strip() for m in meds], "strength_right": ok_strength,
                         "quality": ex["quality"].get("issues", [])})
            print(f"{kind:8s} {med[0]:15s} {ex['doc_type']['type']:15s} {rows[-1]['found']}", flush=True)
    total = {k: sum(t[k] for t in tally.values()) for k in ("n", "labelled_strip", "medicine_found", "strength_right", "false_medicines")}
    res = {"seed": seed, "per_variant": n, "by_variant": tally, "all": total, "pictures": rows}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"by_variant": tally, "all": total}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], int(a[1]) if len(a) > 1 else 8, int(a[2]) if len(a) > 2 else 1008, a[3] if len(a) > 3 else "docs/evaluation/strips.json")
