# src/agent_dev/refiner.py
"""
Refinamiento iterativo del plan junto al usuario.
"""
import json
from typing import Optional
import ollama

from src.agent_dev.analyzer import (
    analizar_brief, seleccionar_stack, generar_estructura, _extraer_json,
)
from src.agent_dev.web_search import buscar, debe_buscar


MODELO_REFINER = "qwen2.5:7b"


PROMPT_ANALIZAR_CONVERSACION = """Eres un arquitecto de software senior conversando con un cliente para definir un proyecto.

CONVERSACIÓN HASTA AHORA:
{conversacion}

BRIEF INICIAL DEL USUARIO:
{brief}

PLAN ACTUAL (si ya existe):
{plan_actual}

INFORMACIÓN DE BÚSQUEDA WEB (si aplica):
{info_web}

Tu tarea:
1. Analiza si tienes suficiente información para generar un plan sólido
2. Si FALTA info crítica, genera 2-3 preguntas específicas y breves para el usuario
3. Si tienes suficiente, indica que estás listo y resume el plan

Devuelve un JSON con:
{{
    "listo": true o false,
    "preguntas": ["pregunta 1", "pregunta 2"],
    "resumen": "resumen corto del plan propuesto",
    "cambios_sugeridos": "qué cambiarías del plan actual"
}}

REGLAS:
- Si listo=true, "preguntas" debe ser []
- Si listo=false, "resumen" puede estar vacío
- Pregunta SOLO lo crítico, no sobre detalles menores
- Máximo 3 preguntas por turno

Responde ÚNICAMENTE con el JSON.
"""


def _formatear_conversacion(historial: list) -> str:
    """Formatea el historial de conversación para el prompt."""
    lineas = []
    for msg in historial[-10:]:
        rol = "Usuario" if msg.get("role") == "user" else "NIAH"
        contenido = msg.get("content", "")
        lineas.append(f"{rol}: {contenido}")
    return "\n".join(lineas) if lineas else "(sin conversación previa)"


def refinar_plan(
    brief: str,
    historial: list,
    plan_actual: Optional[dict] = None,
) -> dict:
    """
    Refina el plan conversacionalmente.
    Devuelve dict con: listo, preguntas, resumen, info_web_usada.
    """
    ultimo_mensaje = historial[-1]["content"] if historial else brief
    info_web = ""
    busqueda_realizada = None

    if debe_buscar(ultimo_mensaje):
        query = ultimo_mensaje[:200]
        info_web = buscar(query, max_resultados=3)
        busqueda_realizada = query

    prompt = PROMPT_ANALIZAR_CONVERSACION.format(
        conversacion=_formatear_conversacion(historial),
        brief=brief,
        plan_actual=(
            json.dumps(plan_actual, ensure_ascii=False, indent=2)[:1500]
            if plan_actual else "(aún no hay plan)"
        ),
        info_web=info_web or "(sin búsqueda web)",
    )

    respuesta = ollama.chat(
        model=MODELO_REFINER,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
        format="json",
    )

    datos = _extraer_json(respuesta["message"]["content"]) or {}

    return {
        "listo": bool(datos.get("listo", False)),
        "preguntas": datos.get("preguntas", []) or [],
        "resumen": datos.get("resumen", "") or "",
        "cambios_sugeridos": datos.get("cambios_sugeridos", "") or "",
        "info_web_usada": busqueda_realizada,
    }


def generar_plan_actualizado(brief: str, historial: list) -> dict:
    """
    Regenera el plan completo basándose en toda la conversación.
    """
    conversacion = _formatear_conversacion(historial)
    brief_enriquecido = (
        f"{brief}\n\n--- ACLARACIONES DEL USUARIO ---\n{conversacion}"
    )

    analisis = analizar_brief(brief_enriquecido)
    stack = seleccionar_stack(analisis)
    estructura = generar_estructura(analisis, stack)

    advertencias = []
    if analisis.complejidad == "alta":
        advertencias.append("Proyecto de alta complejidad.")
    if not estructura.comandos_tests:
        advertencias.append("El plan no incluye comandos de tests.")

    return {
        "analisis": analisis.model_dump(),
        "stack": stack.model_dump(),
        "estructura": estructura.model_dump(),
        "tiempo_estimado_min": max(
            3, len(estructura.archivos) // 3 + len(estructura.comandos_setup) * 2
        ),
        "advertencias": advertencias,
    }
