# NIAH — Neural Intelligent Assistant Hub

Asistente de IA **100% local** tipo Cursor/Replit. Corre en Ubuntu con Ollama.
Permite chatear, subir archivos (RAG), crear proyectos con IA desde un brief,
ejecutarlos/editarlos y exportar respuestas a múltiples formatos.

---

## Requisitos del sistema

| Componente | Versión mínima |
|------------|----------------|
| Ubuntu     | 24.04          |
| Python     | 3.12           |
| Node.js    | 22.x           |
| Ollama     | última estable |

### Modelos Ollama necesarios

    ollama pull phi3:mini              # chat general
    ollama pull granite-code:3b        # código simple
    ollama pull qwen2.5-coder:7b       # código complejo
    ollama pull qwen2.5:7b             # análisis / planeación
    ollama pull nomic-embed-text       # embeddings RAG

### Dependencias del sistema (para exportar/abrir archivos)

    sudo apt install -y libreoffice-impress

---

## Instalación

    cd ~/mi-agente-llama
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

    cd frontend
    npm install
    cd ..

### Variables de entorno (.env)

    NIAH_USER=barxoal
    NIAH_PASSWORD=changeme123
    SECRET_KEY=<cadena-aleatoria-larga>
    GITHUB_TOKEN=<token-opcional>

---

## Arranque

Backend (Terminal 1):

    cd ~/mi-agente-llama
    source venv/bin/activate
    uvicorn src.api:app --host 0.0.0.0 --port 8000

Frontend (Terminal 2):

    cd ~/mi-agente-llama/frontend
    npm run dev

Abrir: http://localhost:5173

Usuarios por defecto:
- admin → barxoal / changeme123
- demo  → prueba  / prueba

Al arrancar el backend verás en consola "✅ Dependencias de exportación OK"
o un aviso con lo que falte.


---

## Funcionalidades

1. RAG — sube PDF/TXT/MD/CSV/JSON/XLSX/DOCX/código; NIAH los lee y responde.
2. Exportar chats completos a Markdown.
3. Resaltado de sintaxis (Prism oneDark) en bloques de código.
4. Auth JWT multi-usuario + responsive móvil/tablet.
5. Crear proyectos con IA desde un brief:
   - Chat iterativo de refinamiento (con búsqueda web opcional vía ddgs)
   - Fase A: análisis + stack + estructura
   - Fase B: generación híbrida (granite-code / qwen-coder según complejidad)
   - Fase C: compilar + tests + autocorrección con IA (hasta 3 intentos)
6. Ejecutar / compilar / testear proyectos generados (SSE en vivo).
7. Editor inteligente con análisis de impacto, backup y revert.
8. Archivos subidos colapsables, con ver/eliminar/añadir.
9. Exportar respuestas a MD / PDF / DOCX / XLSX / HTML / TXT / JSON / PPTX.

---

## Requisitos para exportar / abrir

NIAH genera todos los formatos desde Python. Para abrirlos necesitas:

| Formato | App recomendada                          |
|---------|------------------------------------------|
| PPTX    | LibreOffice Impress / PowerPoint / WPS   |
| DOCX    | LibreOffice Writer / Word                |
| XLSX    | LibreOffice Calc / Excel                 |
| PDF     | cualquier visor (evince, okular, chrome) |

### Ubuntu 24.04 — troubleshooting PPTX

Si los .pptx no abren, verifica que libreoffice-impress esté instalado:

    dpkg -l | grep libreoffice-impress
    sudo apt install -y libreoffice-impress

Nota: en Ubuntu 24.04 el paquete libreoffice-impress puede NO venir por
defecto aunque ya tengas libreoffice-common, -writer, -calc, etc. Sin él,
LibreOffice rechaza cualquier .pptx (incluso los válidos) con
"Error: source file could not be loaded".

---

## Estructura del proyecto

    ~/mi-agente-llama/
    ├── src/
    │   ├── api.py                    # todos los endpoints
    │   ├── config.py                 # NIAH_PROMPT, MODEL_NAME
    │   ├── auth.py                   # JWT + users SQLite
    │   ├── core/
    │   │   ├── niah.py               # chat/stream con contexto
    │   │   ├── history.py            # proyectos, chats, mensajes
    │   │   ├── router.py             # elige modelo por mensaje
    │   │   └── builder.py            # estructura de proyectos manuales
    │   ├── rag/
    │   │   ├── indexer.py
    │   │   └── retriever.py
    │   └── agent_dev/
    │       ├── analyzer.py           # Fase A
    │       ├── coder.py              # Fase B
    │       ├── tester.py             # Fase C
    │       ├── fixer.py
    │       ├── executor.py
    │       ├── file_writer.py
    │       ├── job_manager.py
    │       ├── process_manager.py
    │       ├── editor.py
    │       ├── refiner.py
    │       ├── web_search.py
    │       ├── schemas.py
    │       └── stack_selector.py
    ├── frontend/
    │   └── src/
    │       ├── App.tsx
    │       ├── App.css
    │       ├── MessageContent.tsx
    │       ├── Login.tsx
    │       ├── AgentCreator.tsx
    │       ├── GenerationProgress.tsx
    │       ├── ProjectPanel.tsx
    │       ├── RunModal.tsx
    │       ├── EditPlan.tsx
    │       ├── AnalizandoEdit.tsx
    │       └── UploadedFiles.tsx
    ├── generated_projects/           # proyectos creados por IA
    ├── rag_docs/                     # archivos subidos
    ├── rag_chroma/                   # ChromaDB persistente
    ├── niah_history.db               # SQLite
    ├── requirements.txt
    └── .env

---

## Tests

    pytest tests/ -v

---

## Roadmap

- [x] RAG multi-formato
- [x] Auth JWT multi-usuario
- [x] Crear proyectos con IA (fases A/B/C)
- [x] Ejecutar / compilar / testear proyectos
- [x] Editor inteligente con análisis de impacto
- [x] Exportar respuestas a MD/PDF/DOCX/XLSX/HTML/TXT/JSON/PPTX
- [ ] Subida automática de proyectos a GitHub
- [ ] Backup automático de la DB (systemd timer)
- [ ] Notificaciones al terminar jobs largos
- [ ] Multi-sesión de chats en paralelo
- [ ] Despliegue público con Cloudflare Tunnel


