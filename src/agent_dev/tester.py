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
                    # Ruta del sistema (/usr/lib/...) → ignorar este match
                    continue
            candidato = raiz / ruta_rel
            if candidato.exists() and candidato.is_file():
                # Verificar que esté DENTRO del proyecto (defensa extra)
                try:
                    candidato.resolve().relative_to(raiz.resolve())
                except ValueError:
                    continue
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


# ═══════════════════════════════════════════════════════════
# Auto-fix para proyectos ya generados (sin PlanCompleto)
# ═══════════════════════════════════════════════════════════

def _contexto_proyecto_simple(raiz: Path) -> str:
    """Contexto del proyecto sin necesidad de PlanCompleto."""
    archivos = [str(f.relative_to(raiz)) for f in raiz.rglob("*") if f.is_file() and ".bak" not in str(f)]
    return (
        f"Proyecto: {raiz.name}\n"
        f"Archivos ({len(archivos)}): {', '.join(archivos[:20])}"
    )


# ═══════════════════════════════════════════════════════════
# Detección de stack y limpieza de archivos incoherentes
# ═══════════════════════════════════════════════════════════

WEB_LIBS = {"react", "vue", "svelte", "next", "nuxt", "vite",
            "angular", "solid-js", "@angular/core", "preact"}


def _es_proyecto_node_claro(raiz: Path) -> bool:
    """Es Node claro si tiene package.json con libs web y no hay código Python real."""
    import json as _j
    pkg = raiz / "package.json"
    if not pkg.exists():
        return False
    try:
        data = _j.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return False
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    tiene_web_lib = bool(set(deps) & WEB_LIBS)
    if not tiene_web_lib:
        return False
    # ¿Hay Python real? main.py / app.py / src/*.py con imports
    py_real = (
        (raiz / "main.py").exists()
        or (raiz / "app.py").exists()
        or (raiz / "src" / "main.py").exists()
    )
    return not py_real


def _parece_basura_requirements(contenido: str) -> bool:
    """Un requirements.txt es basura si tiene frases, no paquetes."""
    lineas = [l.strip() for l in contenido.splitlines() if l.strip() and not l.startswith("#")]
    if not lineas:
        return True
    for linea in lineas:
        # Un paquete válido no tiene espacios ni palabras en español
        if " " in linea and not linea.startswith("-") and not linea.startswith("git+"):
            return True
        if any(p in linea.lower() for p in [" se ", " para ", " con ", " archivo", " siguiente", " necesit"]):
            return True
    return False


async def _limpiar_archivos_incoherentes(raiz: Path, emitir_evento) -> list:
    """
    Mueve a .bak los archivos que no corresponden al stack detectado.
    Devuelve lista de rutas movidas.
    """
    if not _es_proyecto_node_claro(raiz):
        return []

    movidos = []

    # requirements.txt basura en proyecto Node
    req = raiz / "requirements.txt"
    if req.exists():
        try:
            contenido = req.read_text(encoding="utf-8", errors="replace")
            if _parece_basura_requirements(contenido):
                bak = req.with_suffix(req.suffix + ".bak")
                if not bak.exists():
                    req.rename(bak)
                else:
                    req.unlink()
                movidos.append("requirements.txt")
        except Exception:
            pass

    # tests Python en proyecto Node
    tests_dir = raiz / "tests"
    if tests_dir.exists():
        for py in list(tests_dir.glob("test_*.py")):
            bak = py.with_suffix(py.suffix + ".bak")
            try:
                if not bak.exists():
                    py.rename(bak)
                else:
                    py.unlink()
                movidos.append(str(py.relative_to(raiz)))
            except Exception:
                pass

    # test_*.py en raíz
    for py in list(raiz.glob("test_*.py")):
        bak = py.with_suffix(py.suffix + ".bak")
        try:
            if not bak.exists():
                py.rename(bak)
            else:
                py.unlink()
            movidos.append(str(py.relative_to(raiz)))
        except Exception:
            pass

    if movidos:
        await emitir_evento({
            "tipo": "limpieza",
            "archivos": movidos,
            "mensaje": f"Movidos a .bak (no corresponden al stack): {', '.join(movidos)}",
        })

    return movidos


def _detectar_comandos_test(raiz: Path) -> list:
    """
    Detecta comandos de test según el stack REAL del proyecto.
    - Node claro (package.json con react/vue/vite) → solo npm
    - Python claro → pip + pytest
    - Mixto (backend/ + frontend/) → ambos
    """
    import json as _j
    cmds = []

    # Detección de stack
    es_node = _es_proyecto_node_claro(raiz)
    tiene_backend_py = (raiz / "backend" / "main.py").exists() or (raiz / "backend" / "app.py").exists()
    tiene_requirements = (raiz / "requirements.txt").exists()
    tiene_tests_py = bool(
        ((raiz / "tests").exists() and list((raiz / "tests").glob("test_*.py")))
        or list(raiz.glob("test_*.py"))
    )

    tiene_script_test_node = False
    if (raiz / "package.json").exists():
        try:
            data = _j.loads((raiz / "package.json").read_text(encoding="utf-8"))
            tiene_script_test_node = "test" in (data.get("scripts") or {})
        except Exception:
            pass

    # CASO A: Node claro → ignorar TODO lo Python
    if es_node:
        cmds.append("npm install")
        if tiene_script_test_node:
            cmds.append("npm test")
        return cmds

    # CASO B: backend Python + frontend Node
    if tiene_backend_py and (raiz / "frontend" / "package.json").exists():
        cmds.append("pip install -r requirements.txt")
        if (raiz / "tests").exists():
            cmds.append("python -m pytest tests/ -v")
        cmds.append("cd frontend && npm install")
        if tiene_script_test_node:
            cmds.append("cd frontend && npm test")
        return cmds

    # CASO C: Python claro
    if tiene_tests_py or tiene_backend_py:
        if tiene_requirements:
            cmds.append("pip install -r requirements.txt")
        if (raiz / "tests").exists():
            cmds.append("python -m pytest tests/ -v")
        elif (raiz / "backend").exists() and (raiz / "backend" / "tests").exists():
            cmds.append("cd backend && python -m pytest tests/ -v")
        return cmds

    # CASO D: Node sin script test (raro)
    if (raiz / "package.json").exists():
        cmds.append("npm install")
        if tiene_script_test_node:
            cmds.append("npm test")
        return cmds

    return cmds


async def ejecutar_tests_con_fix(raiz: Path, emitir_evento) -> dict:
    """
    Ejecuta los tests del proyecto con auto-fix. No requiere PlanCompleto.
    Primero limpia archivos incoherentes con el stack detectado.
    """
    # Limpiar archivos basura antes de testear
    await emitir_evento({"tipo": "info", "mensaje": "Detectando stack y limpiando archivos incoherentes..."})
    movidos = await _limpiar_archivos_incoherentes(raiz, emitir_evento)
    if movidos:
        await emitir_evento({
            "tipo": "info",
            "mensaje": f"Archivos movidos a .bak: {', '.join(movidos)}",
        })

    comandos = _detectar_comandos_test(raiz)
    if not comandos:
        await emitir_evento({"tipo": "info", "mensaje": "No se detectaron comandos de test"})
        return {"total": 0, "exitos": 0, "correcciones": []}

    await emitir_evento({"tipo": "inicio", "comandos": comandos})

    correcciones_totales = []
    exitos = 0
    resultados = []

    for i, comando in enumerate(comandos, start=1):
        await emitir_evento({"tipo": "comando_inicio", "i": i, "total": len(comandos), "comando": comando})

        intentos = 0
        comando_exitoso = False

        while intentos < MAX_REINTENTOS_FIX:
            intentos += 1
            await emitir_evento({
                "tipo": "intento",
                "i": i,
                "intento": intentos,
                "max": MAX_REINTENTOS_FIX,
            })

            timeout = detectar_timeout(comando)
            resultado = await ejecutar_comando(comando, raiz, timeout=timeout)

            if resultado["exito"]:
                await emitir_evento({
                    "tipo": "comando_ok",
                    "i": i,
                    "intento": intentos,
                    "stdout": (resultado.get("stdout") or "")[-800:],
                    "tiempo": resultado["tiempo"],
                })
                comando_exitoso = True
                exitos += 1
                resultados.append({"comando": comando, "exito": True, "intentos": intentos})
                break

            error = (
                resultado.get("error")
                or resultado.get("stderr")
                or resultado.get("stdout")
                or "Error desconocido"
            )
            await emitir_evento({
                "tipo": "comando_error",
                "i": i,
                "intento": intentos,
                "error": error[:1000],
            })

            if intentos >= MAX_REINTENTOS_FIX:
                resultados.append({"comando": comando, "exito": False, "intentos": intentos, "error": error[:300]})
                break

            # Detectar archivo con error
            archivo_error = _detectar_archivo_de_error(comando, error, raiz)
            if not archivo_error:
                await emitir_evento({
                    "tipo": "fix_sin_archivo",
                    "mensaje": "No se pudo identificar el archivo con error",
                })
                resultados.append({"comando": comando, "exito": False, "intentos": intentos, "error": error[:300]})
                break

            rel = str(archivo_error.relative_to(raiz))
            await emitir_evento({"tipo": "fix_inicio", "archivo": rel, "intento": intentos})

            contenido_actual = archivo_error.read_text(encoding="utf-8", errors="replace")

            import asyncio
            fix = await asyncio.to_thread(
                corregir_archivo,
                archivo_error,
                contenido_actual,
                error,
                _contexto_proyecto_simple(raiz),
            )

            if not fix["exito"]:
                await emitir_evento({
                    "tipo": "fix_fallo",
                    "archivo": rel,
                    "error": fix["error"],
                })
                resultados.append({"comando": comando, "exito": False, "intentos": intentos, "error": fix["error"]})
                break

            # Backup del original
            bak = archivo_error.with_suffix(archivo_error.suffix + ".bak")
            if not bak.exists():
                bak.write_text(contenido_actual, encoding="utf-8")

            archivo_error.write_text(fix["contenido_nuevo"], encoding="utf-8")
            correcciones_totales.append({
                "archivo": rel,
                "intento": intentos,
                "comando": comando,
            })

            await emitir_evento({
                "tipo": "fix_aplicado",
                "archivo": rel,
                "intento": intentos,
                "modelo": fix["modelo"],
            })

        if not comando_exitoso and intentos >= MAX_REINTENTOS_FIX:
            pass  # ya se agregó a resultados

    await emitir_evento({
        "tipo": "fin",
        "exitos": exitos,
        "total": len(comandos),
        "correcciones": len(correcciones_totales),
    })

    return {
        "total": len(comandos),
        "exitos": exitos,
        "correcciones": correcciones_totales,
        "resultados": resultados,
    }
