# src/core/router.py
import re
from src.config import MODEL_GENERAL, MODEL_CODE, MODEL_ANALYSIS


# Palabras clave que sugieren código
CODE_KEYWORDS = [
    "código", "codigo", "programa", "función", "funcion", "script",
    "python", "javascript", "typescript", "java", "c++", "rust", "go",
    "html", "css", "react", "sql", "bash", "shell",
    "error", "bug", "debug", "compilar", "algoritmo",
    "clase", "objeto", "variable", "loop", "bucle", "api",
    "```", "def ", "function ", "class ", "import ", "const ",
]

# Palabras clave que sugieren análisis complejo
ANALYSIS_KEYWORDS = [
    "analiza", "análisis", "explica detalladamente", "compara",
    "razona", "por qué", "porque", "causas", "consecuencias",
    "estrategia", "plan", "diseña", "arquitectura",
    "matemáticas", "cálculo", "ecuación", "demuestra",
]


def elegir_modelo(mensaje: str) -> str:
    """Decide qué modelo usar según el contenido del mensaje."""
    texto = mensaje.lower()

    # Si contiene bloques de código o palabras clave de código
    if any(kw in texto for kw in CODE_KEYWORDS):
        return MODEL_CODE

    # Si pide análisis profundo
    if any(kw in texto for kw in ANALYSIS_KEYWORDS) or len(mensaje) > 500:
        return MODEL_ANALYSIS

    # Por defecto: conversación general
    return MODEL_GENERAL
