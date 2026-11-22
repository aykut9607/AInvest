from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from api.deps import current_user_id
from db.session import get_engine
from main import app
from schemas.envelope import Envelope


def test_health_answers(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "portfolio-service"


def test_db_check_reachable(client):
    # an in-memory SQLite engine stands in for portfolio_db: it answers SELECT 1
    app.dependency_overrides[get_engine] = lambda: create_engine("sqlite://")

    response = client.get("/health/db-check")

    assert response.status_code == 200
    assert response.json() == {"database": "reachable"}


def test_db_check_unreachable_is_503_and_does_not_crash(client):
    # nothing listens on port 1: the check must report it, not raise a 500
    app.dependency_overrides[get_engine] = lambda: create_engine("postgresql+psycopg://x:y@127.0.0.1:1/none?connect_timeout=1")

    response = client.get("/health/db-check")

    assert response.status_code == 503
    assert response.json() == {"database": "unreachable"}


def _app_with_user_endpoint() -> TestClient:
    probe = FastAPI()

    @probe.get("/me")
    def me(user_id: str = Depends(current_user_id)) -> dict:
        return {"userId": user_id}

    return TestClient(probe)


def test_user_id_comes_from_the_gateway_header():
    response = _app_with_user_endpoint().get("/me", headers={"X-User-Id": "u1"})

    assert response.json() == {"userId": "u1"}


def test_request_without_the_gateway_header_is_401():
    response = _app_with_user_endpoint().get("/me")

    assert response.status_code == 401


def test_envelope_has_the_same_shape_as_the_dotnet_services():
    assert Envelope[int].ok(5, "done").model_dump() == {"data": 5, "success": True, "message": "done"}
    assert Envelope[int].error("not found").model_dump() == {"data": None, "success": False, "message": "not found"}
