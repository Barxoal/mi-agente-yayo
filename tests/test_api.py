# tests/test_api.py
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


def test_root():
    """Verifica que la API responde."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health():
    """Verifica el endpoint de salud."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_chat_endpoint():
    """Verifica que el endpoint /chat devuelve una respuesta."""
    response = client.post("/chat", json={"mensaje": "Di 'hola' en una palabra."})
    assert response.status_code == 200
    data = response.json()
    assert "respuesta" in data
    assert len(data["respuesta"]) > 0
    assert data["modelo"] == "phi3:mini"
