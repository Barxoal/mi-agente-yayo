# src/agent_dev/tester.py
"""
Orquestador de la Fase C: compilación + tests + corrección automática.
"""
from pathlib import Path
from typing import Optional

from src.agent_dev.executor import ejecutar_comando, detectar_timeout
from src.agent_dev.fixer import corregir_archivo
from src.agent_dev.schemas import PlanCompleto


MAX_REINTENTOS_FIX = 3


def _contexto_proyecto(raiz: Path, plan: PlanCompleto) -> str:
    """Genera contexto breve del proyecto para el fixer."""
    return (
        f"Proyecto: {plan.estructura.nombre_proyecto}\n"
        f"Stack: frontend={plan.stack.frontend or 'ninguno'}, "
        f"backend={plan.stack.backend or 'ninguno'}, "
        f"db={plan.stack.base_datos or 'ninguna'}\n"
        f"Archivos: {', '.join(a.ruta for a in plan.estructura.archivos[:15])}"
    )


def _detectar_archivo_de_error(comando: str, error: str, raiz: Path) -> Optional[Path]:
    """
    Detecta qué archivo causó el error.
    Estrategia:
    1. Buscar patrones clásicos (File "...", ruta.py:N)
    2. Comandos conocidos → archivos específicos (pip install → requirements.txt)
    3. Buscar nombres de archivos del proyecto mencionados en el error
    """
    import re

    # 1. Patrones de traza clásicos
    patrones = [
        r'File "([^"]+\.py)"',
        r"([\w/._-]+\.py):\d+",
        r"([\w/._-]+\.tsx?):\d+",
        r"([\w/._-]+\.jsx?):\d+",
        r"([\w/._-]+\.rs):\d+",
        r"([\w/._-]+\.go):\d+",
    ]
    for patron in patrones:
        match = re.search(patron, error)
        if match:
            ruta_rel = match.group(1)
            if ruta_rel.startswith("/"):
                try:
                    ruta_rel = str(Path(ruta_rel).relative_to(raiz))
                except ValueError:
                    pass
            candidato = raiz / ruta_rel
            if candidato.exists() and candidato.is_file():
                return candidato

    # 2. Comandos conocidos → archivos específicos
    comando_low = comando.lower()
    if "pip install" in comando_low or "pip3 install" in comando_low:
        req = raiz / "requirements.txt"
        if req.exists():
            return req
    if "npm install" in comando_low or "yarn install" in comando_low:
        pkg = raiz / "package.json"
        if pkg.exists():
            return pkg
    if "pytest" in comando_low or "npm test" in comando_low:
        # Buscar el primer archivo de tests que exista
        for patron_test in ["tests/test_*.py", "test_*.py", "tests/*.test.ts", "tests/*.test.js"]:
            for f in raiz.glob(patron_test):
                if f.is_file():
                    return f

    # 3. Buscar nombres de archivos conocidos del proyecto en el error
    for archivo in raiz.rglob("*"):
        if not archivo.is_file():
            continue
        if archivo.name in error and archivo.name != "":
            return archivo

    return None


async def ejecutar_comando_con_fix(
    comando: str,
    raiz: Path,
    plan: PlanCompleto,
    autorizaciones_sesion: set,
    emitir_evento,
) -> dict:
    """
    Ejecuta un comando. Si falla, intenta corregir hasta MAX_REINTENTOS_FIX veces.
    """
    correcciones = []
    intentos = 0

    while intentos < MAX_REINTENTOS_FIX:
        intentos += 1

        await emitir_evento({
            "tipo": "comando",
            "comando": comando,
            "estado": "ejecutando",
            "intento": intentos,
            "max_intentos": MAX_REINTENTOS_FIX,
        })

        timeout = detectar_timeout(comando)
        resultado = await ejecutar_comando(
            comando, raiz, timeout=timeout,
            autorizaciones_sesion=autorizaciones_sesion,
        )

        # Si requiere autorización, emitir evento y detener
        if resultado.get("requiere_auth"):
            await emitir_evento({
                "tipo": "autorizacion_requerida",
                "comando": comando,
                "razon": resultado.get("razon_auth", "Comando no permitido"),
            })
            return {
                "comando": comando,
                "exito": False,
                "intentos": intentos,
                "tiempo_total": resultado["tiempo"],
                "correcciones": correcciones,
                "requiere_auth": True,
                "razon_auth": resultado.get("razon_auth", ""),
            }

        if resultado["exito"]:
            await emitir_evento({
                "tipo": "comando",
                "comando": comando,
                "estado": "ok",
                "intento": intentos,
                "tiempo": resultado["tiempo"],
                "stdout": resultado["stdout"][-500:],
            })
            return {
                "comando": comando,
                "exito": True,
                "intentos": intentos,
                "tiempo_total": resultado["tiempo"],
                "correcciones": correcciones,
                "stdout": resultado["stdout"],
            }

        # Falló: intentar corregir
        error = (
            resultado.get("error")
            or resultado.get("stderr")
            or resultado.get("stdout")
            or "Error desconocido"
        )

        await emitir_evento({
            "tipo": "comando",
            "comando": comando,
            "estado": "error",
            "intento": intentos,
            "error": error[:800],
        })

        if intentos >= MAX_REINTENTOS_FIX:
            break

        # Detectar archivo con error
        archivo_error = _detectar_archivo_de_error(comando, error, raiz)
        if not archivo_error:
            await emitir_evento({
                "tipo": "fix",
                "estado": "sin_archivo",
                "mensaje": "No se pudo identificar el archivo con error, deteniendo",
            })
            break

        # Leer contenido actual
        contenido_actual = archivo_error.read_text(encoding="utf-8", errors="replace")

        await emitir_evento({
            "tipo": "fix",
            "estado": "corrigiendo",
            "archivo": str(archivo_error.relative_to(raiz)),
            "intento": intentos,
            "error": error[:300],
        })

        # Corregir
        import asyncio
        fix = await asyncio.to_thread(
            corregir_archivo,
            archivo_error,
            contenido_actual,
            error,
            _contexto_proyecto(raiz, plan),
        )

        if not fix["exito"]:
            await emitir_evento({
                "tipo": "fix",
                "estado": "fallo",
                "archivo": str(archivo_error.relative_to(raiz)),
                "error": fix["error"],
            })
            break

        # Escribir corrección
        archivo_error.write_text(fix["contenido_nuevo"], encoding="utf-8")
        correcciones.append({
            "archivo": str(archivo_error.relative_to(raiz)),
            "intento": intentos,
        })

        await emitir_evento({
            "tipo": "fix",
            "estado": "aplicado",
            "archivo": str(archivo_error.relative_to(raiz)),
            "bytes_nuevos": len(fix["contenido_nuevo"]),
        })

    return {
        "comando": comando,
        "exito": False,
        "intentos": intentos,
        "tiempo_total": 0,
        "correcciones": correcciones,
        "error_final": "Se agotaron los reintentos",
    }


async def validar_proyecto(
    plan: PlanCompleto,
    raiz: Path,
    autorizaciones_sesion: set,
    emitir_evento,
) -> dict:
    """
    Ejecuta todos los comandos del plan (setup, build, tests) en orden.
    """
    comandos_totales = (
        plan.estructura.comandos_setup
        + plan.estructura.comandos_compilacion
        + plan.estructura.comandos_tests
    )

    if not comandos_totales:
        await emitir_evento({
            "tipo": "validacion",
            "estado": "sin_comandos",
            "mensaje": "El plan no tiene comandos de validación",
        })
        return {
            "total": 0,
            "exitos": 0,
            "fallos": 0,
            "requiere_auth": False,
            "resultados": [],
        }

    resultados = []
    exitos = 0
    fallos = 0
    requiere_auth = False

    for i, comando in enumerate(comandos_totales, start=1):
        await emitir_evento({
            "tipo": "progreso",
            "i": i,
            "total": len(comandos_totales),
            "comando": comando,
        })

        resultado = await ejecutar_comando_con_fix(
            comando, raiz, plan, autorizaciones_sesion, emitir_evento
        )
        resultados.append(resultado)

        if resultado["exito"]:
            exitos += 1
        elif resultado.get("requiere_auth"):
            requiere_auth = True
            fallos += 1
            break
        else:
            fallos += 1

    return {
        "total": len(comandos_totales),
        "exitos": exitos,
        "fallos": fallos,
        "requiere_auth": requiere_auth,
        "resultados": resultados,
    }
