# tests/test_api.py
import uuid
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["agente"] == "NIAH"


def test_crear_proyecto_y_chat():
    """Crea un proyecto y verifica que devuelve project_id y chat_id."""
    nombre = f"test-{uuid.uuid4().hex[:6]}"
    response = client.post("/projects", json={"nombre": nombre, "tipo": "python"})
    assert response.status_code == 200
    data = response.json()
    assert "project_id" in data
    assert "chat_id" in data


def test_chat_general():
    """Crea un proyecto y le envía un mensaje."""
    nombre = f"test-{uuid.uuid4().hex[:6]}"
    r = client.post("/projects", json={"nombre": nombre, "tipo": "python"})
    data = r.json()
    chat_id = data["chat_id"]

    response = client.post(
        "/chat", json={"mensaje": "Di 'hola'.", "chat_id": chat_id}
    )
    assert response.status_code == 200
    assert len(response.json()["respuesta"]) > 0


def test_listar_proyectos():
    response = client.get("/projects")
    assert response.status_code == 200
    assert "proyectos" in response.json()
