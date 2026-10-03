# src/agent_dev/analyzer.py
import json
from typing import Optional
import ollama

from src.agent_dev.schemas import (
    AnalisisBrief, StackRecomendado, EstructuraProyecto, PlanCompleto,
)
from src.agent_dev.stack_selector import obtener_matriz


MODELO_ANALISIS = "qwen2.5:7b"


def _limpiar_claves(d):
    if not isinstance(d, dict):
        return d
    limpio = {}
    for k, v in d.items():
        nueva_k = str(k).strip().strip('"').strip("'").strip()
        if isinstance(v, dict):
            v = _limpiar_claves(v)
        elif isinstance(v, list):
            v = [_limpiar_claves(i) if isinstance(i, dict) else i for i in v]
        limpio[nueva_k] = v
    return limpio


def _extraer_json(texto):
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        return None
    try:
        datos = json.loads(texto[inicio : fin + 1])
        return _limpiar_claves(datos)
    except json.JSONDecodeError:
        return None


def _limpiar_nombre(texto):
    """Convierte un texto en un nombre de proyecto válido (kebab-case)."""
    texto = texto.lower().strip()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    permitidos = "abcdefghijklmnopqrstuvwxyz0123456789- "
    limpio = "".join(c if c in permitidos else "-" for c in texto)
    limpio = limpio.replace(" ", "-")
    while "--" in limpio:
        limpio = limpio.replace("--", "-")
    limpio = limpio.strip("-")

    partes = [p for p in limpio.split("-") if p]
    stop = {
        "una", "un", "el", "la", "los", "las", "de", "del", "para",
        "con", "y", "o", "en", "que", "es", "por", "al", "se",
    }
    significativas = [p for p in partes if p not in stop and len(p) > 2]
    if significativas:
        partes = significativas

    nombre = "-".join(partes[:5])
    if len(nombre) > 50:
        recortado = nombre[:50]
        if "-" in recortado:
            recortado = recortado.rsplit("-", 1)[0]
        nombre = recortado.rstrip("-")
    return nombre or "proyecto"


PROMPT_ANALISIS = """Eres un arquitecto de software senior. Analiza el brief del usuario y devuelve un JSON con:

- objetivo: string (1-2 frases)
- tipo_proyecto: string ("web", "api", "fullstack", "script", "cli", "movil", "otro")
- funcionalidades: array de strings (3-8 features clave)
- usuarios_objetivo: string
- requiere_persistencia: bool
- requiere_auth: bool
- complejidad: string ("baja", "media", "alta")
- notas_adicionales: string

Responde UNICAMENTE con el JSON.

Brief del usuario:
\"\"\"
{brief}
\"\"\"
"""


def analizar_brief(brief):
    prompt = PROMPT_ANALISIS.format(brief=brief)
    respuesta = ollama.chat(
        model=MODELO_ANALISIS,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
        format="json",
    )
    contenido = respuesta["message"]["content"]
    datos = _extraer_json(contenido)

    if not datos:
        return AnalisisBrief(
            objetivo=brief[:200],
            tipo_proyecto="web",
            funcionalidades=["Por definir"],
            complejidad="media",
            notas_adicionales="El modelo no devolvio JSON, usando defaults",
        )

    return AnalisisBrief(**{
        k: v for k, v in datos.items()
        if k in AnalisisBrief.model_fields
    })


PROMPT_STACK = """Eres un arquitecto de software senior. Dado el analisis del proyecto, elige el STACK TECNOLOGICO OPTIMO.

{matriz}

ANALISIS DEL PROYECTO:
- Objetivo: {objetivo}
- Tipo: {tipo_proyecto}
- Funcionalidades: {funcionalidades}
- Persistencia: {persistencia}
- Auth: {auth}
- Complejidad: {complejidad}

Devuelve un JSON con:
- frontend: string o null
- backend: string o null
- base_datos: string o null
- estilos: string o null
- testing: string o null
- extras: array de strings
- justificacion: string
- alternativas_descartadas: array de strings

Responde UNICAMENTE con el JSON.
"""


def seleccionar_stack(analisis):
    prompt = PROMPT_STACK.format(
        matriz=obtener_matriz(),
        objetivo=analisis.objetivo,
        tipo_proyecto=analisis.tipo_proyecto,
        funcionalidades=", ".join(analisis.funcionalidades),
        persistencia="si" if analisis.requiere_persistencia else "no",
        auth="si" if analisis.requiere_auth else "no",
        complejidad=analisis.complejidad,
    )
    respuesta = ollama.chat(
        model=MODELO_ANALISIS,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
        format="json",
    )
    contenido = respuesta["message"]["content"]
    datos = _extraer_json(contenido)

    if not datos:
        return StackRecomendado(
            frontend="React + Vite + TypeScript",
            backend="FastAPI (Python 3.12)",
            base_datos="SQLite" if analisis.requiere_persistencia else None,
            justificacion="Stack por defecto (fallback)",
        )

    return StackRecomendado(**{
        k: v for k, v in datos.items()
        if k in StackRecomendado.model_fields
    })


PROMPT_ESTRUCTURA = """Eres un arquitecto de software senior. Genera la ESTRUCTURA DE CARPETAS Y ARCHIVOS del proyecto.

STACK ELEGIDO:
- Frontend: {frontend}
- Backend: {backend}
- Base de datos: {base_datos}
- Estilos: {estilos}
- Testing: {testing}
- Extras: {extras}

OBJETIVO: {objetivo}
FUNCIONALIDADES: {funcionalidades}
NOMBRE SUGERIDO: {nombre}

Devuelve un JSON con:
- nombre_proyecto: string (kebab-case)
- descripcion_repo: string (max 100 chars)
- carpetas: array de strings
- archivos: array de objetos con claves "ruta" y "descripcion"
- comandos_setup: array de strings (instalacion de dependencias)
- comandos_compilacion: array de strings (build, lint, typecheck)
- comandos_tests: array de strings (ejecucion de tests)

REGLAS OBLIGATORIAS SOBRE TESTS:
1. SIEMPRE incluye al menos un archivo de tests reales:
   - Python: tests/test_*.py (con pytest)
   - JavaScript/TypeScript: src/**/*.test.ts o tests/*.test.js (con vitest o jest)
2. SIEMPRE incluye el comando de tests en 'comandos_tests':
   - Python: ["python -m pytest tests/ -v"]
   - Node: ["npm test"]
3. SIEMPRE incluye el comando de instalacion en 'comandos_setup':
   - Python: ["pip install -r requirements.txt"]
   - Node: ["npm install"]
4. SIEMPRE incluye un comando de compilacion/validacion si aplica:
   - Python: ["python -m py_compile src/*.py"]
   - TypeScript: ["npm run build"]
5. SIEMPRE incluye requirements.txt (Python) o package.json (Node)

REGLAS GENERALES:
- Sé realista: 8-20 archivos máximo
- Incluye siempre: README.md, .gitignore
- Los tests deben cubrir al menos 2 funciones/comportamientos clave

IMPORTANTE: cada objeto de 'archivos' DEBE tener las claves exactas "ruta" y "descripcion".

Responde UNICAMENTE con el JSON.
"""


def _normalizar_archivos(archivos_raw):
    if isinstance(archivos_raw, dict):
        archivos_raw = [archivos_raw]
    if not isinstance(archivos_raw, list):
        archivos_raw = []

    archivos_norm = []
    for item in archivos_raw:
        if isinstance(item, str):
            s = item.strip()
            if not s or s.startswith('"'):
                continue
            archivos_norm.append({"ruta": s, "descripcion": "Archivo del proyecto"})
        elif isinstance(item, dict):
            ruta = (
                item.get("ruta")
                or item.get("path")
                or item.get("file")
                or item.get("nombre")
                or ""
            )
            desc = (
                item.get("descripcion")
                or item.get("description")
                or item.get("desc")
                or "Archivo del proyecto"
            )
            ruta = str(ruta).strip().strip('"').strip("'")
            if ruta and ruta not in ("archivos", "files"):
                archivos_norm.append({
                    "ruta": ruta,
                    "descripcion": str(desc).strip() or "Archivo del proyecto",
                })
    return archivos_norm


def _normalizar_carpetas(carpetas_raw):
    if isinstance(carpetas_raw, dict):
        carpetas_raw = [carpetas_raw]
    if not isinstance(carpetas_raw, list):
        carpetas_raw = []

    carpetas_norm = []
    for item in carpetas_raw:
        if isinstance(item, str):
            carpetas_norm.append(item.strip())
        elif isinstance(item, dict):
            ruta = item.get("ruta") or item.get("path") or item.get("name") or ""
            if ruta:
                carpetas_norm.append(str(ruta).strip())
    return [c for c in carpetas_norm if c]


def _normalizar_comandos(comandos_raw):
    if isinstance(comandos_raw, dict):
        comandos_raw = [comandos_raw]
    if not isinstance(comandos_raw, list):
        comandos_raw = []

    comandos_norm = []
    for item in comandos_raw:
        if isinstance(item, str):
            comandos_norm.append(item.strip())
        elif isinstance(item, dict):
            cmd = item.get("cmd") or item.get("command") or item.get("comando") or ""
            if cmd:
                comandos_norm.append(str(cmd).strip())
    return [c for c in comandos_norm if c]


def _aplicar_defaults(archivos_norm, setup_norm, build_norm, test_norm, stack):
    """Fuerza comandos y archivos de tests según el stack."""
    stack_str = ((stack.frontend or "") + " " + (stack.backend or "")).lower()
    es_python = ("python" in stack_str) or ("fastapi" in stack_str) or ("django" in stack_str)
    es_node = any(
        x in stack_str for x in ("react", "vite", "node", "next", "vue", "svelte")
    )

    if es_python:
        if not any("pytest" in c for c in test_norm):
            test_norm.append("python -m pytest tests/ -v")
        if not any("pip install" in c for c in setup_norm):
            setup_norm.insert(0, "pip install -r requirements.txt")
        if not build_norm:
            build_norm.append("python -m py_compile src/*.py")

    if es_node:
        if not any("npm test" in c or "vitest" in c for c in test_norm):
            test_norm.append("npm test")
        if not any("npm install" in c or "yarn install" in c for c in setup_norm):
            setup_norm.insert(0, "npm install")
        if not any("build" in c for c in build_norm):
            build_norm.append("npm run build")

    tiene_test = any("test" in a["ruta"].lower() for a in archivos_norm)
    if not tiene_test:
        if es_python:
            archivos_norm.append({
                "ruta": "tests/test_basico.py",
                "descripcion": "Tests basicos con pytest",
            })
        elif es_node:
            archivos_norm.append({
                "ruta": "src/basico.test.ts",
                "descripcion": "Tests basicos con vitest",
            })

    return archivos_norm, setup_norm, build_norm, test_norm


def generar_estructura(analisis, stack, nombre_sugerido=None):
    nombre = _limpiar_nombre(nombre_sugerido or analisis.objetivo[:40])
    prompt = PROMPT_ESTRUCTURA.format(
        frontend=stack.frontend or "ninguno",
        backend=stack.backend or "ninguno",
        base_datos=stack.base_datos or "ninguna",
        estilos=stack.estilos or "ninguno",
        testing=stack.testing or "ninguno",
        extras=", ".join(stack.extras) or "ninguno",
        objetivo=analisis.objetivo,
        funcionalidades=", ".join(analisis.funcionalidades),
        nombre=nombre,
    )
    respuesta = ollama.chat(
        model=MODELO_ANALISIS,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.4},
        format="json",
    )
    contenido = respuesta["message"]["content"]
    datos = _extraer_json(contenido)

    if not datos:
        return EstructuraProyecto(
            nombre_proyecto=nombre,
            descripcion_repo=analisis.objetivo[:100],
            carpetas=["src", "tests"],
            archivos=[
                {"ruta": "README.md", "descripcion": "Documentacion"},
                {"ruta": ".gitignore", "descripcion": "Archivos ignorados"},
                {"ruta": "requirements.txt", "descripcion": "Dependencias"},
                {"ruta": "src/main.py", "descripcion": "Punto de entrada"},
                {"ruta": "tests/test_basico.py", "descripcion": "Tests basicos"},
            ],
            comandos_setup=["pip install -r requirements.txt"],
            comandos_compilacion=["python -m py_compile src/*.py"],
            comandos_tests=["python -m pytest tests/ -v"],
        )

    if "nombre_proyecto" in datos:
        datos["nombre_proyecto"] = _limpiar_nombre(datos["nombre_proyecto"])

    archivos_norm = _normalizar_archivos(
        datos.get("archivos") or datos.get("files") or []
    )
    carpetas_norm = _normalizar_carpetas(
        datos.get("carpetas") or datos.get("folders") or []
    )
    setup_norm = _normalizar_comandos(
        datos.get("comandos_setup") or datos.get("setup_commands") or []
    )
    build_norm = _normalizar_comandos(
        datos.get("comandos_compilacion") or datos.get("build_commands") or []
    )
    test_norm = _normalizar_comandos(
        datos.get("comandos_tests") or datos.get("test_commands") or []
    )

    rutas_existentes = {a["ruta"] for a in archivos_norm}
    if "README.md" not in rutas_existentes:
        archivos_norm.insert(0, {
            "ruta": "README.md",
            "descripcion": "Documentacion del proyecto",
        })
    if ".gitignore" not in rutas_existentes:
        archivos_norm.insert(1, {
            "ruta": ".gitignore",
            "descripcion": "Archivos ignorados por Git",
        })

    if not archivos_norm:
        archivos_norm = [
            {"ruta": "README.md", "descripcion": "Documentacion"},
            {"ruta": ".gitignore", "descripcion": "Archivos ignorados"},
            {"ruta": "src/main.py", "descripcion": "Punto de entrada"},
        ]

    archivos_norm, setup_norm, build_norm, test_norm = _aplicar_defaults(
        archivos_norm, setup_norm, build_norm, test_norm, stack
    )

    tiene_test = any("test" in a["ruta"].lower() for a in archivos_norm)
    if tiene_test and "tests" not in carpetas_norm:
        carpetas_norm.append("tests")

    return EstructuraProyecto(
        nombre_proyecto=datos.get("nombre_proyecto", nombre),
        descripcion_repo=(
            datos.get("descripcion_repo") or analisis.objetivo[:100]
        ),
        carpetas=carpetas_norm,
        archivos=archivos_norm,
        comandos_setup=setup_norm,
        comandos_compilacion=build_norm,
        comandos_tests=test_norm,
    )


def generar_plan_completo(brief, nombre_sugerido=None):
    analisis = analizar_brief(brief)
    stack = seleccionar_stack(analisis)
    estructura = generar_estructura(analisis, stack, nombre_sugerido)

    advertencias = []
    if analisis.complejidad == "alta":
        advertencias.append("Proyecto de alta complejidad: la generacion puede tomar mas tiempo.")
    if not estructura.archivos:
        advertencias.append("El plan no incluye archivos, revisa el brief.")
    if estructura.nombre_proyecto in ("proyecto", "app", "test"):
        advertencias.append("El nombre del proyecto es generico, considera cambiarlo.")
    if not estructura.comandos_tests:
        advertencias.append("El plan no incluye comandos de tests.")

    tiempo = max(3, len(estructura.archivos) // 3 + len(estructura.comandos_setup) * 2)

    return PlanCompleto(
        analisis=analisis,
        stack=stack,
        estructura=estructura,
        tiempo_estimado_min=tiempo,
        advertencias=advertencias,
    )
