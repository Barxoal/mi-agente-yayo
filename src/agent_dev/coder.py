# src/agent_dev/coder.py
"""
Fase B: generación de código archivo por archivo.
Estrategia híbrida: granite-code:3b para simples, qwen2.5-coder:7b para complejos.
"""
import re
import time
from typing import Optional
import ollama

from src.agent_dev.schemas import PlanCompleto


MODELO_RAPIDO = "granite-code:3b"
MODELO_POTENTE = "qwen2.5-coder:7b"

ARCHIVOS_SIMPLES = (
    ".gitignore",
    "README.md",
    ".env.example",
    "requirements.txt",
    "package.json",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "pyproject.toml",
    "setup.py",
    "Makefile",
    ".editorconfig",
    "LICENSE",
)

EXT_SIMPLES = (".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")


def elegir_modelo(ruta: str) -> str:
    """Elige el modelo según el tipo de archivo."""
    nombre = ruta.split("/")[-1]
    if nombre in ARCHIVOS_SIMPLES:
        return MODELO_RAPIDO
    if ruta.endswith(EXT_SIMPLES):
        return MODELO_RAPIDO
    return MODELO_POTENTE


def _limpiar_markdown(texto: str) -> str:
    """Limpia bloques de markdown si el modelo los incluyó."""
    patron = re.compile(r"^```[a-zA-Z0-9_+-]*\s*\n", re.MULTILINE)
    texto = patron.sub("", texto)
    texto = re.sub(r"\n```\s*$", "", texto)
    texto = texto.strip()
    if texto.startswith("```") and texto.endswith("```"):
        texto = texto[3:-3].strip()
    return texto


def _reglas_especificas(ruta: str) -> str:
    """Devuelve reglas especiales según el tipo de archivo."""
    nombre_lower = ruta.lower()

    if nombre_lower.endswith("requirements.txt"):
        return """
REGLAS ESPECÍFICAS PARA requirements.txt:
- SOLO paquetes Python, uno por línea
- Formato: nombre_paquete>=version (ej: fastapi>=0.115.0)
- NADA de comentarios explicativos largos ni texto descriptivo
- Ejemplo válido:
pytest>=8.0.0
requests>=2.31.0
fastapi>=0.115.0
"""

    if nombre_lower.endswith("package.json"):
        return """
REGLAS ESPECÍFICAS PARA package.json:
- JSON válido estricto, sin comentarios
- Debe tener: name, version, scripts, dependencies
- Ejemplo válido:
{
  "name": "mi-app",
  "version": "1.0.0",
  "scripts": {"dev": "vite", "build": "vite build", "test": "vitest"},
  "dependencies": {"react": "^18.3.0"},
  "devDependencies": {"vite": "^5.0.0", "vitest": "^1.0.0"}
}
"""

    if nombre_lower.endswith(".gitignore"):
        return """
REGLAS ESPECÍFICAS PARA .gitignore:
- Solo patrones de archivos a ignorar, uno por línea
- Sin comentarios largos
- Sin texto descriptivo
- Ejemplo:
node_modules/
__pycache__/
*.pyc
.env
venv/
"""

    if nombre_lower.endswith("readme.md"):
        return """
REGLAS ESPECÍFICAS PARA README.md:
- Markdown válido
- Secciones: título, descripción, instalación, uso, tests
- Sin explicaciones internas del modelo
- Sin frases como "Aquí tienes el README"
"""

    return ""


def _construir_prompt(
    plan: PlanCompleto,
    ruta: str,
    descripcion: str,
    archivos_previos: dict,
) -> str:
    """Construye el prompt específico para este archivo."""
    nombre = plan.estructura.nombre_proyecto
    stack = plan.stack
    analisis = plan.analisis

    otros = [a.ruta for a in plan.estructura.archivos if a.ruta != ruta]
    otros_str = "\n".join(f"  - {o}" for o in otros[:20])

    contexto_previo = ""
    relevantes = [r for r in archivos_previos if r != ruta][:3]
    for r_prev in relevantes:
        contenido = archivos_previos[r_prev]
        if len(contenido) > 500:
            contenido = contenido[:500] + "\n... (truncado)"
        contexto_previo += f"\n--- {r_prev} ---\n{contenido}\n"

    reglas_extra = _reglas_especificas(ruta)

    prompt = f"""Eres un desarrollador senior. Genera el contenido del archivo "{ruta}" para el proyecto "{nombre}".

CONTEXTO DEL PROYECTO:
- Objetivo: {analisis.objetivo}
- Stack: frontend={stack.frontend or "ninguno"}, backend={stack.backend or "ninguno"}, db={stack.base_datos or "ninguna"}
- Estilos: {stack.estilos or "ninguno"}

DESCRIPCIÓN DEL ARCHIVO:
{descripcion}

{reglas_extra}

OTROS ARCHIVOS DEL PROYECTO:
{otros_str}

CONTEXTO DE ARCHIVOS YA GENERADOS:
{contexto_previo or "(ninguno aún)"}

REGLAS ESTRICTAS:
1. Devuelve ÚNICAMENTE el contenido del archivo, sin explicaciones previas ni posteriores
2. NO uses bloques de markdown (```). Solo el contenido crudo.
3. NO incluyas frases como "Aquí tienes el archivo" o "Este es el contenido"
4. El código debe estar completo, funcional, listo para ejecutar
5. Sigue las mejores prácticas del stack elegido

CONTENIDO DEL ARCHIVO {ruta}:
"""
    return prompt


def generar_archivo(
    plan: PlanCompleto,
    ruta: str,
    descripcion: str,
    archivos_previos: dict,
) -> dict:
    """
    Genera el contenido de un archivo.
    Devuelve dict con: ruta, contenido, modelo, bytes, tiempo, exito, error.
    """
    modelo = elegir_modelo(ruta)
    inicio = time.time()

    try:
        prompt = _construir_prompt(plan, ruta, descripcion, archivos_previos)
        respuesta = ollama.chat(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 2048},
        )
        contenido = respuesta["message"]["content"]
        contenido = _limpiar_markdown(contenido)

        if not contenido.strip():
            raise ValueError("El modelo devolvió contenido vacío")

        tiempo = round(time.time() - inicio, 2)
        return {
            "ruta": ruta,
            "contenido": contenido,
            "modelo": modelo,
            "bytes": len(contenido.encode("utf-8")),
            "tiempo": tiempo,
            "exito": True,
            "error": None,
        }
    except Exception as e:
        tiempo = round(time.time() - inicio, 2)
        return {
            "ruta": ruta,
            "contenido": "",
            "modelo": modelo,
            "bytes": 0,
            "tiempo": tiempo,
            "exito": False,
            "error": str(e),
        }
