from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from banking_core.app.api.dependencies import get_db_session
from banking_core.app.main import app


class HealthySession:
    def execute(self, statement: object) -> None:
        return None


class BrokenSession:
    def execute(self, statement: object) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("offline"))


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health() -> None:
    app.dependency_overrides[get_db_session] = lambda: HealthySession()
    try:
        response = TestClient(app).get("/health/db")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_reports_unavailable() -> None:
    app.dependency_overrides[get_db_session] = lambda: BrokenSession()
    try:
        response = TestClient(app).get("/health/db")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"code": "HTTP_ERROR", "message": "database unavailable"}


def test_trace_id_is_propagated() -> None:
    trace_id = "00000000-0000-0000-0000-000000000123"
    response = TestClient(app).get("/health", headers={"X-Trace-Id": trace_id})
    assert response.headers["X-Trace-Id"] == trace_id
