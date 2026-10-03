# src/agent_dev/coder.py
"""
Fase B: generación de código archivo por archivo.
Usa estrategia híbrida: granite-code:3b para simples, qwen2.5-coder:7b para complejos.
"""
import re
import time
from typing import Optional
import ollama

from src.agent_dev.schemas import PlanCompleto


MODELO_RAPIDO = "granite-code:3b"
MODELO_POTENTE = "qwen2.5-coder:7b"

# Archivos que se generan con el modelo rápido
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

# Extensiones que se generan con el modelo rápido
EXT_SIMPLES = (".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")


def elegir_modelo(ruta: str) -> str:
    """Elige el modelo según el tipo de archivo."""
    nombre = ruta.split("/")[-1]
    if nombre in ARCHIVOS_SIMPLES:
        return MODELO_RAPIDO
    if ruta.endswith(EXT_SIMPLES):
        return MODELO_RAPIDO
    # Archivos de código fuente → modelo potente
    return MODELO_POTENTE


def _limpiar_markdown(texto: str) -> str:
    """Limpia bloques de markdown si el modelo los incluyó."""
    # Quitar ```lenguaje ... ```
    patron = re.compile(r"^```[a-zA-Z0-9_+-]*\s*\n", re.MULTILINE)
    texto = patron.sub("", texto)
    texto = re.sub(r"\n```\s*$", "", texto)
    # Quitar bloques de código inline al inicio/fin
    texto = texto.strip()
    if texto.startswith("```") and texto.endswith("```"):
        texto = texto[3:-3].strip()
    return texto


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

    # Lista de archivos del proyecto
    otros = [a.ruta for a in plan.estructura.archivos if a.ruta != ruta]
    otros_str = "\n".join(f"  - {o}" for o in otros[:20])

    # Contexto de archivos ya generados (solo los más relevantes)
    contexto_previo = ""
    relevantes = [r for r in archivos_previos if r != ruta][:3]
    for r_prev in relevantes:
        contenido = archivos_previos[r_prev]
        # Limitar a 500 caracteres por archivo
        if len(contenido) > 500:
            contenido = contenido[:500] + "\n... (truncado)"
        contexto_previo += f"\n--- {r_prev} ---\n{contenido}\n"

    prompt = f"""Eres un desarrollador senior. Genera el contenido del archivo "{ruta}" para el proyecto "{nombre}".

CONTEXTO DEL PROYECTO:
- Objetivo: {analisis.objetivo}
- Stack: frontend={stack.frontend or "ninguno"}, backend={stack.backend or "ninguno"}, db={stack.base_datos or "ninguna"}
- Estilos: {stack.estilos or "ninguno"}

DESCRIPCIÓN DEL ARCHIVO:
{descripcion}

OTROS ARCHIVOS DEL PROYECTO:
{otros_str}

CONTEXTO DE ARCHIVOS YA GENERADOS:
{contexto_previo or "(ninguno aún)"}

REGLAS ESTRICTAS:
1. Devuelve ÚNICAMENTE el contenido del archivo, sin explicaciones
2. NO uses bloques de markdown (```). Solo el contenido crudo.
3. El código debe estar completo, funcional, listo para producción
4. Usa comentarios claros donde sea necesario
5. Sigue las mejores prácticas del stack elegido
6. Si es un archivo de configuración, incluye valores sensatos por defecto

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
