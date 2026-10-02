import { useState } from "react";
import { LogIn, Sparkles, UserPlus } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  onLogin: (token: string) => void;
}

export default function Login({ onLogin }: Props) {
  const [modo, setModo] = useState<"login" | "register">("login");
  const [usuario, setUsuario] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (modo === "register") {
      if (usuario.length < 3) {
        setError("El usuario debe tener al menos 3 caracteres");
        return;
      }
      if (password.length < 6) {
        setError("La contraseña debe tener al menos 6 caracteres");
        return;
      }
      if (password !== password2) {
        setError("Las contraseñas no coinciden");
        return;
      }
    }

    setLoading(true);
    const endpoint = modo === "login" ? "/auth/login" : "/auth/register";

    try {
      const r = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usuario, password }),
      });

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "Error al autenticar");
        setLoading(false);
        return;
      }

      const data = await r.json();
      onLogin(data.access_token);
    } catch {
      setError("Error de conexión con el servidor");
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="login-box" onSubmit={enviar}>
        <div className="login-title">
          <Sparkles size={28} />
          <h1>NIAH</h1>
        </div>
        <p className="login-subtitle">Neural Intelligent Assistant Hub</p>

        <div className="login-tabs">
          <button
            type="button"
            className={modo === "login" ? "active" : ""}
            onClick={() => { setModo("login"); setError(""); }}
          >
            Iniciar sesión
          </button>
          <button
            type="button"
            className={modo === "register" ? "active" : ""}
            onClick={() => { setModo("register"); setError(""); }}
          >
            Crear cuenta
          </button>
        </div>

        <label className="modal-label">Usuario</label>
        <input
          type="text"
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
          placeholder="Tu usuario"
          autoFocus
          required
        />

        <label className="modal-label">Contraseña</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Tu contraseña"
          required
        />

        {modo === "register" && (
          <>
            <label className="modal-label">Repite la contraseña</label>
            <input
              type="password"
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
              placeholder="Repite la contraseña"
              required
            />
          </>
        )}

        {error && <p className="login-error">{error}</p>}

        <button type="submit" disabled={loading} className="login-btn">
          {modo === "login" ? <LogIn size={14} /> : <UserPlus size={14} />}
          <span>
            {loading
              ? "Procesando..."
              : modo === "login"
              ? "Entrar"
              : "Crear cuenta"}
          </span>
        </button>
      </form>
    </div>
  );
}
