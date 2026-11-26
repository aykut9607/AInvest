import os

import pytest
from fastapi.testclient import TestClient

# tests never read the developer's .env or touch portfolio_db: a placeholder URL is enough to build the settings,
# and every test that needs the database replaces the engine
os.environ.setdefault("PORTFOLIO_DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/never_used")

from main import app  # noqa: E402  (imported after the environment is set)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
