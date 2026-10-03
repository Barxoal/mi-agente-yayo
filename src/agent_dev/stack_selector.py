# src/agent_dev/stack_selector.py
"""
Matriz de decisión de stack tecnológico.
El agente usa esta info como contexto para elegir el stack óptimo.
"""

MATRIZ_STACKS = """
MATRIZ DE DECISIÓN DE STACK TECNOLÓGICO
========================================

Landing page simple / portafolio:
  → HTML + CSS + JS vanilla
  → Razón: sin dependencias, deploy en cualquier lado, carga instantánea

Web interactiva / dashboard:
  → React + Vite + TypeScript
  → Razón: componentes, HMR, tipado, ecosistema enorme
  → Estilos: CSS Modules (simple) o Tailwind (rápido)

Dashboard con gráficos:
  → React + Vite + Recharts
  → Razón: gráficos listos, responsivos, fáciles

App móvil simple (que funcione en celular):
  → React + Vite + PWA (manifest + service worker)
  → Razón: una sola base de código, instalable, offline

App móvil nativa (acceso a cámara, GPS, etc.):
  → React Native + Expo
  → Razón: código compartido iOS+Android, acceso a hardware

API REST simple:
  → FastAPI (Python 3.12)
  → Razón: rápido de escribir, docs automáticas en /docs, tipado con Pydantic

API con IA / ML:
  → FastAPI + Python + Ollama o scikit-learn
  → Razón: ecosistema ML completo

API de alto tráfico / tiempo real:
  → Node.js + Fastify + Socket.io
  → Razón: event loop, WebSockets nativos

Fullstack moderno:
  → React + Vite (frontend) + FastAPI (backend)
  → Razón: lo mejor de ambos: UI moderna + backend Python robusto
  → Alternativa: Next.js (si todo es JavaScript)

CLI / scripts de automatización:
  → Python 3.12 + argparse o Typer
  → Razón: directo, sin setup, librerías infinitas

Scraping web:
  → Python + BeautifulSoup + httpx
  → Razón: estándar de facto

Procesamiento de datos / análisis:
  → Python + Pandas + matplotlib o Jupyter
  → Razón: librerías científicas líderes

Juego 2D simple:
  → HTML5 Canvas + JavaScript vanilla
  → Razón: sin instalación, corre en navegador

Juego 3D:
  → Three.js (navegador) o Godot (nativo)
  → Razón: potencia gráfica

Chatbot con IA local:
  → Python + FastAPI + Ollama
  → Razón: privacidad total, corre en tu PC

REGLAS DE DECISIÓN
==================

1. Si el usuario pide "simple" o "rápido" → elige el stack más minimalista
2. Si el usuario pide "escalable" o "producción" → elige stack maduro
3. Si no menciona preferencias → prioriza stack con mejor ecosistema y menor complejidad
4. Si el proyecto es solo para uso personal → SQLite, no PostgreSQL
5. Si el proyecto necesita tiempo real → WebSockets (Socket.io o FastAPI WebSockets)
6. Si el usuario ya tiene experiencia con un stack → respétala (pero sugiere mejoras)
7. Preferir siempre librerías activas (último commit < 6 meses)
"""


def obtener_matriz() -> str:
    """Devuelve la matriz como texto para pasar al modelo."""
    return MATRIZ_STACKS
