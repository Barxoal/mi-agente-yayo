# src/auth.py
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

load_dotenv()

DB_PATH = Path("niah_history.db")
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-min-32-chars")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

security = HTTPBearer()


# ===== BASE DE DATOS DE USUARIOS =====

def init_users_table():
    """Crea la tabla de usuarios y migra los del .env si no existen."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Migrar usuarios del .env si la tabla está vacía
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        admin_user = os.getenv("NIAH_USER", "admin")
        admin_pass = os.getenv("NIAH_PASSWORD", "admin")
        test_user = os.getenv("NIAH_TEST_USER", "prueba")
        test_pass = os.getenv("NIAH_TEST_PASSWORD", "prueba")

        for user, pwd, role in [
            (admin_user, admin_pass, "admin"),
            (test_user, test_pass, "user"),
        ]:
            hash_pwd = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
            c.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (user, hash_pwd, role),
            )
        conn.commit()

    conn.close()


def crear_usuario(username: str, password: str, role: str = "user") -> bool:
    """Crea un nuevo usuario. Devuelve False si ya existe."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        hash_pwd = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_pwd, role),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verificar_credenciales(usuario: str, password: str) -> bool:
    """Valida usuario y contraseña contra la DB."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (usuario,))
    row = c.fetchone()
    conn.close()

    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row[0].encode())


def obtener_rol(usuario: str) -> str:
    """Devuelve el rol del usuario."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (usuario,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "user"


def listar_usuarios():
    """Devuelve todos los usuarios (sin hash)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, role, created_at FROM users ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "username": r[1], "role": r[2], "created_at": r[3]}
        for r in rows
    ]


def eliminar_usuario(username: str) -> bool:
    """Elimina un usuario (excepto el admin principal)."""
    if username == os.getenv("NIAH_USER", "admin"):
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    afectados = c.rowcount
    conn.commit()
    conn.close()
    return afectados > 0


# ===== JWT =====

def crear_token(usuario: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": usuario, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario: Optional[str] = payload.get("sub")
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )
        return usuario
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
