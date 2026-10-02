# tests/test_agent.py
from src.agent import chat


def test_agente_responde():
    """Verifica que el agente devuelve una respuesta no vacía."""
    respuesta = chat("Di 'hola' en una palabra.")
    assert respuesta is not None
    assert len(respuesta) > 0
    print(f"\nRespuesta del modelo: {respuesta}")


def test_agente_responde_espanol():
    """Verifica que responde en español."""
    respuesta = chat("¿Cuál es la capital de Francia? Responde en español.")
    assert "parís" in respuesta.lower() or "paris" in respuesta.lower()
