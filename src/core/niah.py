# src/core/niah.py
import ollama
from src.config import NIAH_PROMPT
from src.core.router import elegir_modelo
from src.core.history import init_db, guardar_mensaje, obtener_historial


def _mensajes(mensaje: str, chat_id: str) -> list:
    historial = obtener_historial(chat_id, limit=20)
    mensajes = [{"role": "system", "content": NIAH_PROMPT}]
    for h in historial:
        mensajes.append({"role": h["role"], "content": h["content"]})
    mensajes.append({"role": "user", "content": mensaje})
    return mensajes


def chat(mensaje: str, chat_id: str) -> dict:
    init_db()
    modelo = elegir_modelo(mensaje)
    mensajes = _mensajes(mensaje, chat_id)

    guardar_mensaje(chat_id, "user", mensaje)
    respuesta = ollama.chat(model=modelo, messages=mensajes)
    contenido = respuesta["message"]["content"]
    guardar_mensaje(chat_id, "assistant", contenido, modelo)

    return {"respuesta": contenido, "modelo": modelo}


def stream(mensaje: str, chat_id: str):
    init_db()
    modelo = elegir_modelo(mensaje)
    mensajes = _mensajes(mensaje, chat_id)
    guardar_mensaje(chat_id, "user", mensaje)

    stream_resp = ollama.chat(model=modelo, messages=mensajes, stream=True)
    full = ""
    for chunk in stream_resp:
        token = chunk["message"]["content"]
        if token:
            full += token
            yield token

    guardar_mensaje(chat_id, "assistant", full, modelo)
