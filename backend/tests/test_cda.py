"""HL7 CDA R2 export is schema-valid (skipped unless HL7's CDA-core-2.0 schema is in models/reference/cdaxsd)."""

from pathlib import Path

import pytest

from app.exports import to_cda

XSD = Path(__file__).resolve().parents[2] / "models" / "reference" / "cdaxsd" / "infrastructure" / "cda" / "CDA.xsd"


def _enc(note=True, reviewed=None):
    v = {"id": "v1", "label": "SpO2", "value": "91", "unit": "%", "needs_check": True, "status": "low", "source": {"engine": "kiosk"}}
    return {"id": "enc_1", "created_at": "2026-10-08T06:00:00", "data_origin": "SYNTHETIC", "chief_complaint": "Chest pain <2 h> & sweating",
            "patient": {"id": "p1", "code": "JV-0001", "name": "Test Patient", "age": 56, "sex": "M", "language": "or"},
            "urgency": "red", "urgency_source": "rules", "override": None, "reviewed_by": reviewed, "reviewed_at": "2026-10-08T06:10:00",
            "note": {"summary": "56 M chest pain", "flags": [{"severity": "critical", "label": "Red", "code": "ATP"}], "vitals": [v], "labs": [],
                     "missing_info": ["Pulse"], "rules_fired": [{"rule_id": "ATP-1", "protocol": "ATP", "description": "Chest pain", "urgency": "red"}]} if note else None}


@pytest.mark.skipif(not XSD.exists(), reason="HL7 CDA schema not downloaded (see docs/FEATURES.md)")
@pytest.mark.parametrize("enc", [_enc(), _enc(reviewed="Dr A"), _enc(note=False)])
def test_cda_is_schema_valid(enc):
    from lxml import etree

    schema = etree.XMLSchema(etree.parse(str(XSD)))
    assert schema.validate(etree.fromstring(to_cda(enc, {"id": "fac1", "name": "PHC Demo"}))), schema.error_log
