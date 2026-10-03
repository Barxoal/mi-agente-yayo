# src/agent_dev/fixer.py
"""Corrección automática de errores con el modelo."""
import re
from pathlib import Path
import ollama


MODELO_FIXER = "qwen2.5-coder:7b"


def _extraer_codigo(texto: str) -> str:
    """Extrae el código limpio de la respuesta del modelo."""
    texto = texto.strip()
    # Quitar bloques ```lenguaje ... ```
    match = re.search(r"```[a-zA-Z0-9_+-]*\s*\n(.*?)```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Quitar ``` sueltos
    texto = re.sub(r"^```[a-zA-Z0-9_+-]*\s*\n", "", texto)
    texto = re.sub(r"\n```\s*$", "", texto)
    return texto.strip()


def corregir_archivo(
    ruta: Path,
    contenido_actual: str,
    error: str,
    contexto_proyecto: str = "",
) -> dict:
    """
    Pide al modelo que corrija un archivo basándose en el error.
    Devuelve dict con: contenido_nuevo, modelo, exito, error.
    """
    prompt = f"""Eres un desarrollador senior experto en debugging. Un archivo de tu proyecto falló al compilar o testear.

ARCHIVO CON ERROR: {ruta.name}

CONTENIDO ACTUAL DEL ARCHIVO:
\"\"\"
{contenido_actual[:4000]}
\"\"\"

ERROR OBTENIDO:
\"\"\"
{error[:1500]}
\"\"\"

CONTEXTO DEL PROYECTO:
{contexto_proyecto[:800] or "(sin contexto adicional)"}

TAREA:
Corrige el archivo para que solucione el error. Devuelve ÚNICAMENTE el contenido completo del archivo corregido, sin markdown, sin explicaciones.

REGLAS:
1. Mantén el propósito original del archivo
2. Corrige SOLO lo necesario para resolver el error
3. El código debe seguir las mejores prácticas
4. Si el error es por una dependencia faltante, agrega la lógica para manejar el caso

CONTENIDO CORREGIDO:
"""

    try:
        respuesta = ollama.chat(
            model=MODELO_FIXER,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2, "num_predict": 3000},
        )
        contenido = _extraer_codigo(respuesta["message"]["content"])

        if not contenido.strip():
            return {
                "contenido_nuevo": None,
                "modelo": MODELO_FIXER,
                "exito": False,
                "error": "El modelo devolvió contenido vacío",
            }

        return {
            "contenido_nuevo": contenido,
            "modelo": MODELO_FIXER,
            "exito": True,
            "error": None,
        }

    except Exception as e:
        return {
            "contenido_nuevo": None,
            "modelo": MODELO_FIXER,
            "exito": False,
            "error": str(e),
        }
