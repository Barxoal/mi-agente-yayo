# tests/test_niah.py
from src.core import niah
from src.core.router import elegir_modelo
from src.core.history import init_db, crear_proyecto, crear_chat


def test_router_detecta_codigo():
    modelo = elegir_modelo("Escríbeme una función en Python")
    assert modelo == "granite-code:3b"


def test_router_detecta_analisis():
    modelo = elegir_modelo("Analiza detalladamente las causas de la inflación")
    assert modelo == "qwen2.5:7b"


def test_router_default_general():
    modelo = elegir_modelo("¿Cómo estás?")
    assert modelo == "phi3:mini"


def test_niah_responde():
    init_db()
    # Crear proyecto y chat temporales para el test
    crear_proyecto("test-proj", "test-proyecto", "python")
    crear_chat("test-chat", "test-proj", "test")
    resultado = niah.chat("Di 'hola' en una palabra.", "test-chat")
    assert resultado["respuesta"]
    assert resultado["modelo"]
