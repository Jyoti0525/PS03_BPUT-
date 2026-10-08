"""Second document-type label from the image model: off by default, never changes the label, warns on a difference."""

import io
import json

from PIL import Image

import pytest

from app.triage import vlm


class _Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def server(monkeypatch):
    sent = {}

    def answer(text):
        def fake(req, timeout):
            sent["body"] = json.loads(req.data)
            return _Reply(json.dumps({"choices": [{"message": {"content": text}}]}).encode())

        monkeypatch.setattr(vlm.urllib.request, "urlopen", fake)
        monkeypatch.setattr(vlm.get_settings(), "vlm_url", "http://127.0.0.1:8032")
        return sent

    return answer


def _jpeg(w=2000, h=1500):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "JPEG")
    return buf.getvalue()


def test_off_by_default():
    assert not vlm.enabled() and vlm.label(b"x") is None


@pytest.mark.parametrize("reply,want", [("medicine_strip", "medicine_strip"), ("Lab_report.", "lab_report"), ("<think>hm</think>prescription", "prescription"),
                                        ("I am not sure", None), ("non_document", "non_document")])
def test_parse(reply, want):
    assert vlm.parse(reply) == want


def test_same_label_no_warning(server):
    sent = server("lab_report")
    got, warn = vlm.compare({"type": "lab_report", "label": "Lab report"}, _jpeg(), "image/jpeg")
    assert got["type"] == "lab_report" and warn is None
    content = sent["body"]["messages"][0]["content"]
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")  # only the picture is sent, no name
    import base64

    small = Image.open(io.BytesIO(base64.b64decode(content[0]["image_url"]["url"].split(",", 1)[1])))
    assert max(small.size) == vlm.SIDE


def test_different_label_warns_but_does_not_change(server):
    server("prescription")
    rule = {"type": "medicine_strip", "label": "Medicine strip or pack"}
    got, warn = vlm.compare(rule, _jpeg(), "image/jpeg")
    assert got["type"] == "prescription" and "check the picture" in warn and rule["type"] == "medicine_strip"


def test_unclear_or_unreachable_is_ignored(server, monkeypatch):
    server("a cat")
    assert vlm.compare({"type": "lab_report"}, _jpeg(), "image/png") == (None, None)

    def down(req, timeout):
        raise OSError("refused")

    monkeypatch.setattr(vlm.urllib.request, "urlopen", down)
    assert vlm.label(_jpeg()) is None and vlm.label(b"not an image") is None
    assert vlm.label(b"%PDF", "application/pdf") is None
