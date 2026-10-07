import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="jeevia-test-")
os.environ.setdefault("JEEVIA_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["JEEVIA_STORAGE_DIR"] = f"{_tmp}/uploads"
os.environ["JEEVIA_LOG_LEVEL"] = "WARNING"
os.environ["JEEVIA_SEED_SCENARIOS"] = "false"  # test_zz_scenarios.py adds them after the other tests
os.environ["JEEVIA_DIRECTORY_AUTOLOAD"] = "false"  # tests load their own small directory fixture
os.environ["JEEVIA_OTP_PER_IP_HOUR"] = "100000"  # the whole test session shares one client address
os.environ["JEEVIA_RATE_LIMIT"] = "false"  # same reason; test_security.py switches the limits on
os.environ["JEEVIA_MODELS_DIR"] = f"{_tmp}/no-models"  # API tests run without AI models; test_language.py loads the real ones
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402

# Never the developer's backend/.env: tests must not spend Sarvam credits, place Twilio calls or send SMS
Settings.model_config["env_file"] = None
for _k in [k for k in os.environ if k.startswith(("SARVAM_", "JEEVIA_SARVAM_", "JEEVIA_TWILIO_", "JEEVIA_VONAGE_", "JEEVIA_TELEPHONY_", "JEEVIA_PUBLIC_BASE_URL"))]:
    del os.environ[_k]

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"
DEVICE = "dev_kiosk_manikpur_1"  # seeded, bound to PHC Manikpur
SAMPLE_PIN = "4826"  # sample accounts' PIN (JEEVIA_DEMO_PIN)
GOOD_PIN = "7391"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, phone: str) -> dict:
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    r = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
    if r["status"] == "pin_required":  # staff and employers: second factor
        r = client.post(f"{API}/auth/pin/verify", json={"pin_token": r["pin_token"], "pin": SAMPLE_PIN}).json()
    else:
        assert r["status"] == "authenticated", r
    return {"Authorization": f"Bearer {r['tokens']['access_token']}"}


@pytest.fixture(scope="session")
def doctor(client):
    return login(client, "9000000001")


@pytest.fixture(scope="session")
def nurse(client):
    return login(client, "9000000002")


@pytest.fixture(scope="session")
def supervisor(client):
    return login(client, "9000000004")


@pytest.fixture(scope="session")
def employer(client):
    return login(client, "9000000005")
