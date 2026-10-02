# src/auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Usuarios válidos (usuario -> password)
USUARIOS = {
    os.getenv("NIAH_USER", "admin"): os.getenv("NIAH_PASSWORD", "admin"),
    os.getenv("NIAH_TEST_USER", "prueba"): os.getenv("NIAH_TEST_PASSWORD", "prueba"),
}

security = HTTPBearer()


def crear_token(usuario: str) -> str:
    """Genera un JWT firmado con expiración."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": usuario, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_credenciales(usuario: str, password: str) -> bool:
    """Valida usuario y contraseña contra el diccionario de usuarios."""
    return USUARIOS.get(usuario) == password


def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Dependency para proteger endpoints. Devuelve el usuario o lanza 401."""
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
