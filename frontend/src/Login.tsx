import { useState } from "react";
import { LogIn, Sparkles } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Props {
  onLogin: (token: string) => void;
}

export default function Login({ onLogin }: Props) {
  const [usuario, setUsuario] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usuario, password }),
      });
      if (!r.ok) {
        setError("Usuario o contraseña incorrectos");
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

  const entrarComoPrueba = () => {
    setUsuario("prueba");
    setPassword("prueba");
  };

  return (
    <div className="login-screen">
      <form className="login-box" onSubmit={enviar}>
        <div className="login-title">
          <Sparkles size={28} />
          <h1>NIAH</h1>
        </div>
        <p className="login-subtitle">Neural Intelligent Assistant Hub</p>

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

        {error && <p className="login-error">{error}</p>}

        <button type="submit" disabled={loading} className="login-btn">
          <LogIn size={14} />
          <span>{loading ? "Entrando..." : "Entrar"}</span>
        </button>

        <button
          type="button"
          className="login-demo"
          onClick={entrarComoPrueba}
          disabled={loading}
        >
          Probar como invitado (prueba / prueba)
        </button>
      </form>
    </div>
  );
}
