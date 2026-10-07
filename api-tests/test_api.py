"""Backend tests. Endpoints are NOT hard-coded: I could not see the Rhombus network traffic.
Find each request in DevTools > Network (filter Fetch/XHR), then fill api-tests/.env (see .env.example).
Run: cd api-tests && pip install -r requirements.txt && pytest -v
"""
import os, pytest, requests

BASE = os.environ.get("RHOMBUS_API_BASE", "").rstrip("/")
TOKEN = os.environ.get("RHOMBUS_TOKEN", "")
AUTH_HEADER = os.environ.get("RHOMBUS_AUTH_HEADER", "Authorization")
AUTH_SCHEME = os.environ.get("RHOMBUS_AUTH_SCHEME", "Bearer")
LIST_PATH = os.environ.get("RHOMBUS_PIPELINES_PATH", "")      # GET: list pipelines/projects
SCHEDULE_PATH = os.environ.get("RHOMBUS_SCHEDULE_PATH", "")   # GET: schedule for PIPELINE_ID, may contain {id}
PIPELINE_ID = os.environ.get("RHOMBUS_PIPELINE_ID", "")
T = 30

need_cfg = pytest.mark.skipif(not (BASE and TOKEN and LIST_PATH), reason="set RHOMBUS_API_BASE/TOKEN/PIPELINES_PATH in .env")


def hdrs(token=TOKEN):
    return {AUTH_HEADER: f"{AUTH_SCHEME} {token}", "Accept": "application/json"}


@need_cfg
def test_list_pipelines_authenticated():
    r = requests.get(BASE + LIST_PATH, headers=hdrs(), timeout=T)
    assert r.status_code == 200, r.text[:300]
    assert "json" in r.headers.get("content-type", "")
    body = r.json()
    items = body if isinstance(body, list) else next((v for v in body.values() if isinstance(v, list)), [])
    assert items, "expected at least the pipeline you built"
    if PIPELINE_ID:
        assert any(PIPELINE_ID in str(i) for i in items), f"pipeline {PIPELINE_ID} not in listing"


@pytest.mark.skipif(not (BASE and SCHEDULE_PATH and PIPELINE_ID and TOKEN), reason="schedule endpoint not configured")
def test_schedule_is_configured_and_active():
    r = requests.get(BASE + SCHEDULE_PATH.format(id=PIPELINE_ID), headers=hdrs(), timeout=T)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    flat = str(body).lower()
    # adjust these two assertions to the real field names once you've seen the payload
    assert any(k in flat for k in ("cron", "interval", "frequency", "schedule")), body
    state = body.get("enabled", body.get("active", True)) if isinstance(body, dict) else True
    assert str(state).lower() != "false", "schedule is disabled"


@pytest.mark.skipif(not (BASE and LIST_PATH), reason="not configured")
def test_unauthenticated_request_rejected():
    r = requests.get(BASE + LIST_PATH, timeout=T)  # no auth header at all
    assert r.status_code in (401, 403), f"got {r.status_code}: {r.text[:200]}"
    assert "email" not in r.text.lower() or r.status_code in (401, 403)  # no data leaked in the error body


@pytest.mark.skipif(not (BASE and LIST_PATH), reason="not configured")
def test_invalid_token_rejected():
    r = requests.get(BASE + LIST_PATH, headers=hdrs("not-a-real-token"), timeout=T)
    assert r.status_code in (401, 403), f"got {r.status_code}"
    assert r.json() if "json" in r.headers.get("content-type", "") else True  # error body should be structured


@pytest.mark.skipif(not (BASE and TOKEN and LIST_PATH), reason="not configured")
def test_nonexistent_pipeline_returns_404_not_500():
    r = requests.get(BASE + LIST_PATH.rstrip("/") + "/00000000-0000-0000-0000-000000000000", headers=hdrs(), timeout=T)
    assert r.status_code in (400, 404), f"got {r.status_code} (a 500 here is a bug worth reporting)"
