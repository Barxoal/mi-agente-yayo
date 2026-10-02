# src/core/history.py
import sqlite3
from pathlib import Path

DB_PATH = Path("niah_history.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            titulo TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id)
        )
    """)
    conn.commit()
    conn.close()


# ===== PROYECTOS =====

def crear_proyecto(project_id: str, user_id: str, nombre: str, tipo: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO projects (id, user_id, nombre, tipo) VALUES (?, ?, ?, ?)",
        (project_id, user_id, nombre, tipo),
    )
    conn.commit()
    conn.close()


def listar_proyectos(user_id: str):
    """Lista solo los proyectos del usuario."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, nombre, tipo, created_at FROM projects WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "nombre": r[1], "tipo": r[2], "created_at": r[3]}
        for r in rows
    ]


def verificar_propietario(project_id: str, user_id: str) -> bool:
    """Verifica que el proyecto pertenece al usuario."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return row is not None


def eliminar_proyecto(project_id: str, user_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Verificar propietario
    c.execute("SELECT user_id FROM projects WHERE id = ?", (project_id,))
    row = c.fetchone()
    if not row or row[0] != user_id:
        conn.close()
        return False
    c.execute(
        "DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE project_id = ?)",
        (project_id,),
    )
    c.execute("DELETE FROM chats WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()
    return True


# ===== CHATS =====

def crear_chat(chat_id: str, project_id: str, titulo: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO chats (id, project_id, titulo) VALUES (?, ?, ?)",
        (chat_id, project_id, titulo),
    )
    conn.commit()
    conn.close()


def listar_chats(project_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, titulo, created_at FROM chats WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "titulo": r[1], "created_at": r[2]} for r in rows]


def verificar_chat_propietario(chat_id: str, user_id: str) -> bool:
    """Verifica que el chat pertenece a un proyecto del usuario."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT 1 FROM chats
        JOIN projects ON chats.project_id = projects.id
        WHERE chats.id = ? AND projects.user_id = ?
    """, (chat_id, user_id))
    row = c.fetchone()
    conn.close()
    return row is not None


def eliminar_chat(chat_id: str, user_id: str):
    if not verificar_chat_propietario(chat_id, user_id):
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return True


# ===== MENSAJES =====

def guardar_mensaje(chat_id: str, role: str, content: str, model: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (chat_id, role, content, model) VALUES (?, ?, ?, ?)",
        (chat_id, role, content, model),
    )
    conn.commit()
    conn.close()


def obtener_historial(chat_id: str, limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT role, content, model, timestamp FROM messages WHERE chat_id = ? ORDER BY id ASC LIMIT ?",
        (chat_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"role": r[0], "content": r[1], "model": r[2], "timestamp": r[3]}
        for r in rows
    ]


def limpiar_historial(chat_id: str, user_id: str):
    if not verificar_chat_propietario(chat_id, user_id):
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return True
