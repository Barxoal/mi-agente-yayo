# src/agent_dev/web_search.py
"""
Búsqueda web para el agente (DuckDuckGo via ddgs, sin API key).
"""
from typing import Optional


def buscar(query: str, max_resultados: int = 3) -> str:
    """
    Busca en DuckDuckGo y devuelve los resultados formateados.
    Si falla, devuelve string vacío.
    """
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            resultados = list(ddgs.text(query, max_results=max_resultados))

        if not resultados:
            return ""

        lineas = [f"Resultados de búsqueda para: '{query}'\n"]
        for i, r in enumerate(resultados, 1):
            titulo = r.get("title", "")
            cuerpo = r.get("body", "")
            url = r.get("href", "")
            lineas.append(f"{i}. {titulo}")
            lineas.append(f"   {cuerpo}")
            lineas.append(f"   Fuente: {url}\n")

        return "\n".join(lineas)
    except Exception as e:
        return f"(Error en búsqueda web: {e})"


def debe_buscar(mensaje: str) -> bool:
    """
    Detecta si el mensaje del usuario pide explícitamente buscar en internet
    o si hace referencia a info reciente que requiere búsqueda.
    """
    texto = mensaje.lower()
    gatillos = [
        "busca", "buscar", "investiga", "investigar",
        "en internet", "en la web", "en google",
        "información actual", "ultima version", "última versión",
        "mejor práctica", "mejores prácticas",
        "recomienda", "compara", "compara con",
    ]
    return any(g in texto for g in gatillos)
