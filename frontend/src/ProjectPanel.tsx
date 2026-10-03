import { useState, useEffect } from "react";
import {
  FolderOpen,
  Play,
  Hammer,
  TestTube,
  Download,
  FileCode,
  RefreshCw,
  Wand2,
  ChevronRight,
  X,
  Loader2,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Archivo {
  ruta: string;
  bytes: number;
}

interface Props {
  token: string;
  nombreProyecto: string;
  onResultado: (mensaje: string) => void;
}

export default function ProjectPanel({
  token,
  nombreProyecto,
  onResultado,
}: Props) {
  const [info, setInfo] = useState<any>(null);
  const [cargando, setCargando] = useState(true);
  const [accionEnCurso, setAccionEnCurso] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [archivoAbierto, setArchivoAbierto] = useState<string | null>(null);
  const [contenidoArchivo, setContenidoArchivo] = useState("");

  useEffect(() => {
    cargarInfo();
  }, [nombreProyecto]);

  const cargarInfo = async () => {
    setCargando(true);
    try {
      const r = await fetch(`${API_URL}/agent/projects/${nombreProyecto}/info`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        setInfo(await r.json());
      } else {
        setError("No se pudo cargar la información del proyecto");
      }
    } catch {
      setError("Error de conexión");
    } finally {
      setCargando(false);
    }
  };

  const ejecutarAccion = async (accion: string) => {
    setAccionEnCurso(accion);
    setError("");

    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/action`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ accion }),
        }
      );

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || `Error ejecutando ${accion}`);
        setAccionEnCurso(null);
        return;
      }

      const data = await r.json();

      // Caso especial: "run" devuelve comandos
      if (accion === "run" && data.comandos) {
        let mensaje = "📋 **Comandos para ejecutar en tu terminal:**\n\n";
        data.comandos.forEach((cmd: string, i: number) => {
          mensaje += `${i + 1}. \`${cmd}\`\n\n`;
        });
        mensaje += `_${data.nota || ""}_`;
        onResultado(mensaje);
        setAccionEnCurso(null);
        return;
      }

      // Construir mensaje de resultado
      if (data.mensaje) {
        onResultado(`ℹ️ ${data.mensaje}`);
        setAccionEnCurso(null);
        return;
      }

      let mensaje = `## ${iconoAccion(accion)} ${tituloAccion(accion)}\n\n`;

      if (data.resultados && data.resultados.length > 0) {
        data.resultados.forEach((res: any) => {
          const emoji = res.exito ? "✅" : "❌";
          mensaje += `${emoji} **\`${res.comando}\`** (${res.tiempo}s)\n`;

          if (!res.exito) {
            // Extraer solo las últimas líneas del error
            const lineas = (res.stderr || res.stdout || res.error || "")
              .split("\n")
              .filter((l: string) => l.trim())
              .slice(-10);
            mensaje += "\n```\n" + lineas.join("\n") + "\n```\n\n";
          }
        });
      }

      mensaje += `\n**Resultado:** ${data.exitos} / ${data.total} exitosos`;

      onResultado(mensaje);
    } catch (e) {
      setError("Error de conexión");
    } finally {
      setAccionEnCurso(null);
    }
  };

  const corregirArchivo = async (archivo: string, error: string) => {
    setAccionEnCurso(`fix-${archivo}`);
    setError("");

    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/fix`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ archivo, error }),
        }
      );

      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "No se pudo corregir el archivo");
        setAccionEnCurso(null);
        return;
      }

      const data = await r.json();
      onResultado(
        `🔧 **Corregido:** \`${data.archivo}\`\n\n` +
          `- Bytes anteriores: ${data.bytes_anteriores}\n` +
          `- Bytes nuevos: ${data.bytes_nuevos}\n` +
          `- Modelo: ${data.modelo}\n\n` +
          `_Vuelve a intentar la acción para verificar_`
      );
    } catch {
      setError("Error de conexión");
    } finally {
      setAccionEnCurso(null);
    }
  };

  const abrirArchivo = async (ruta: string) => {
    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/file?ruta=${encodeURIComponent(
          ruta
        )}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.ok) {
        const data = await r.json();
        setContenidoArchivo(data.contenido);
        setArchivoAbierto(ruta);
      }
    } catch {}
  };

  const abrirCarpeta = async () => {
    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/open`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (r.ok) {
        onResultado(`📂 Carpeta abierta en el explorador: \`${info?.ruta}\``);
      } else {
        const data = await r.json().catch(() => ({}));
        setError(data.detail || "No se pudo abrir la carpeta");
      }
    } catch {
      setError("Error de conexión");
    }
  };

  if (cargando) {
    return (
      <div className="project-panel loading">
        <Loader2 size={24} className="spin" />
        <p>Cargando información del proyecto...</p>
      </div>
    );
  }

  if (!info) {
    return (
      <div className="project-panel error">
        <p>No se pudo cargar el proyecto</p>
      </div>
    );
  }

  return (
    <div className="project-panel">
      <div className="project-header">
        <div className="project-header-icon">
          <Wand2 size={28} />
        </div>
        <div className="project-header-info">
          <h2>{info.nombre}</h2>
          <p>
            {info.total_archivos} archivos ·{" "}
            {(info.total_bytes / 1024).toFixed(1)} KB
          </p>
        </div>
      </div>

      <div className="project-ruta">
        <FolderOpen size={14} />
        <code>{info.ruta}</code>
        <button className="btn-icon" onClick={abrirCarpeta} title="Abrir carpeta">
          <FolderOpen size={14} />
        </button>
      </div>

      <div className="project-acciones">
        <button
          className="proj-btn"
          onClick={() => ejecutarAccion("compile")}
          disabled={accionEnCurso !== null}
        >
          {accionEnCurso === "compile" ? (
            <Loader2 size={14} className="spin" />
          ) : (
            <Hammer size={14} />
          )}
          <span>Compilar</span>
        </button>
        <button
          className="proj-btn"
          onClick={() => ejecutarAccion("setup")}
          disabled={accionEnCurso !== null}
        >
          {accionEnCurso === "setup" ? (
            <Loader2 size={14} className="spin" />
          ) : (
            <Download size={14} />
          )}
          <span>Instalar</span>
        </button>
        <button
          className="proj-btn"
          onClick={() => ejecutarAccion("test")}
          disabled={accionEnCurso !== null}
        >
          {accionEnCurso === "test" ? (
            <Loader2 size={14} className="spin" />
          ) : (
            <TestTube size={14} />
          )}
          <span>Probar</span>
        </button>
        <button
          className="proj-btn primary"
          onClick={() => ejecutarAccion("run")}
          disabled={accionEnCurso !== null}
        >
          <Play size={14} />
          <span>Ejecutar</span>
        </button>
      </div>

      {error && (
        <div className="project-error">
          <X size={14} />
          <span>{error}</span>
        </div>
      )}

      <div className="project-archivos">
        <h3>
          <FileCode size={14} /> Archivos del proyecto
        </h3>
        {info.archivos.map((a: Archivo) => (
          <div
            key={a.ruta}
            className="project-archivo-item"
            onClick={() => abrirArchivo(a.ruta)}
          >
            <ChevronRight size={12} />
            <code>{a.ruta}</code>
            <span className="project-archivo-bytes">
              {(a.bytes / 1024).toFixed(1)} KB
            </span>
          </div>
        ))}
      </div>

      {archivoAbierto && (
        <div className="modal-overlay" onClick={() => setArchivoAbierto(null)}>
          <div
            className="modal modal-wide"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-title">
              <FileCode size={18} />
              <h3>{archivoAbierto}</h3>
              <button
                className="modal-close"
                onClick={() => setArchivoAbierto(null)}
              >
                <X size={16} />
              </button>
            </div>
            <pre className="archivo-contenido">{contenidoArchivo}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function iconoAccion(accion: string): string {
  if (accion === "compile") return "🔨";
  if (accion === "setup") return "📦";
  if (accion === "test") return "🧪";
  if (accion === "run") return "🚀";
  return "⚙️";
}

function tituloAccion(accion: string): string {
  if (accion === "compile") return "Compilación";
  if (accion === "setup") return "Instalación de dependencias";
  if (accion === "test") return "Tests";
  if (accion === "run") return "Comandos para ejecutar";
  return accion;
}
