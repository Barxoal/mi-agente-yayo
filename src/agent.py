# src/agent.py
import ollama
from src.config import MODEL_NAME, SYSTEM_PROMPT


def chat(mensaje: str) -> str:
    """Envía un mensaje al modelo configurado y devuelve la respuesta."""
    respuesta = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensaje},
        ],
    )
    return respuesta["message"]["content"]


if __name__ == "__main__":
    print(f"Usando modelo: {MODEL_NAME}")
    respuesta = chat("Di 'hola' en español y preséntate brevemente.")
    print(f"\nRespuesta: {respuesta}")
