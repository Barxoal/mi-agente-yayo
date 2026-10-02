# Mi Agente IA Local

Agente de IA que corre 100% localmente usando Ollama y phi3:mini.

## Requisitos
- Python 3.12+
- Ollama instalado y corriendo
- Modelo: ollama pull phi3:mini

## Instalación
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Uso
python -m src.agent

## Tests
pytest tests/ -v
