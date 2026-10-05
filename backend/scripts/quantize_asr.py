"""Make an 8-bit copy of IndicConformer for machines with 16 GB RAM or less.

The fp32 encoder holds ~2.4 GB of weights. Dynamic int8 quantisation of its MatMul weights (ONNX Runtime)
shrinks it ~4x; activations stay float. The copy is written to models/indic-conformer-600m-int8 with the
same layout, so the app loads it by name (JEEVIA_ASR_MODEL). Accuracy is re-measured with eval_asr.py —
see docs/EVALUATION.md before switching.

    python backend/scripts/quantize_asr.py
"""

import shutil
from pathlib import Path

from onnxruntime.quantization import QuantType, quantize_dynamic

root = Path(__file__).resolve().parents[2] / "models"
src = root / "indic-conformer-600m-multilingual"
dst = root / "indic-conformer-600m-int8"
QUANTISE = ["encoder", "ctc_decoder"]  # the large graphs; the small RNNT pieces are copied as-is


def main() -> None:
    (dst / "assets").mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)  # config, README, model_onnx.py loader
    for f in (src / "assets").iterdir():
        if f.suffix in (".json", ".ts") or (f.suffix == ".onnx" and f.stem not in QUANTISE):
            shutil.copy2(f, dst / "assets" / f.name)
    for name in QUANTISE:
        print(f"- quantising {name}", flush=True)
        quantize_dynamic(
            model_input=src / "assets" / f"{name}.onnx",
            model_output=dst / "assets" / f"{name}.onnx",
            op_types_to_quantize=["MatMul"],
            weight_type=QuantType.QInt8,
            per_channel=True,
            use_external_data_format=True,  # one protobuf would exceed memory while serialising
        )
    size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file()) / 2**30
    print(f"done: {dst} ({size:.2f} GB)")


if __name__ == "__main__":
    main()
