import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="jeevia-test-")
os.environ.setdefault("JEEVIA_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["JEEVIA_STORAGE_DIR"] = f"{_tmp}/uploads"
os.environ["JEEVIA_LOG_LEVEL"] = "WARNING"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"
DEVICE = "dev_kiosk_manikpur_1"  # seeded, bound to PHC Manikpur


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, phone: str) -> dict:
    ch = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    r = client.post(f"{API}/auth/otp/verify", json={"challenge_id": ch["challenge_id"], "code": ch["dev_code"]}).json()
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
def patient(client):
    return login(client, "9876543210")


@pytest.fixture(scope="session")
def employer(client):
    return login(client, "9000000005")
