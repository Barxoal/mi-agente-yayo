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
  Upload,
  ExternalLink,
  Check,
  Copy,
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
  onRunRequest?: () => void;
  onTestFixRequest?: () => void;
  onHide?: () => void;
}

export default function ProjectPanel({
  token,
  nombreProyecto,
  onResultado,
  onRunRequest,
  onTestFixRequest,
  onHide,
}: Props) {
  const [info, setInfo] = useState<any>(null);
  const [cargando, setCargando] = useState(true);
  const [accionEnCurso, setAccionEnCurso] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [archivoAbierto, setArchivoAbierto] = useState<string | null>(null);
  const [contenidoArchivo, setContenidoArchivo] = useState("");

  // GitHub
  const [showGithubModal, setShowGithubModal] = useState(false);
  const [githubNombreRepo, setGithubNombreRepo] = useState("");
  const [githubDescripcion, setGithubDescripcion] = useState("");
  const [githubPrivado, setGithubPrivado] = useState(true);
  const [githubSubiendo, setGithubSubiendo] = useState(false);
  const [githubResultado, setGithubResultado] = useState<any>(null);
  const [githubError, setGithubError] = useState("");
  const [githubCopiado, setGithubCopiado] = useState(false);

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

  const subirAGithub = async () => {
    setGithubSubiendo(true);
    setGithubError("");
    setGithubResultado(null);

    try {
      const r = await fetch(
        `${API_URL}/agent/projects/${nombreProyecto}/github`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            nombre_repo: githubNombreRepo || nombreProyecto,
            descripcion: githubDescripcion,
            privado: githubPrivado,
          }),
        }
      );

      const data = await r.json().catch(() => ({}));

      if (!r.ok) {
        setGithubError(data.detail || "Error subiendo a GitHub");
        setGithubSubiendo(false);
        return;
      }

      setGithubResultado(data);
      onResultado(
        `## ✅ Subido a GitHub\n\n` +
          `**Repo:** [${data.nombre}](${data.repo_url})\n` +
          `**Privado:** ${data.privado ? "Sí" : "No"}\n` +
          `**${data.creado ? "Repo nuevo creado" : "Repo existente actualizado"}**`
      );
    } catch {
      setGithubError("Error de conexión");
    } finally {
      setGithubSubiendo(false);
    }
  };

  const copiarUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setGithubCopiado(true);
      setTimeout(() => setGithubCopiado(false), 2000);
    } catch {
      /* silent */
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
        {onHide && (
          <button
            className="project-hide-btn"
            onClick={onHide}
            title="Ocultar panel (vuelve a abrirlo con 'Panel' en la barra superior)"
          >
            <X size={16} />
          </button>
        )}
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
          onClick={() =>
            onTestFixRequest ? onTestFixRequest() : ejecutarAccion("test")
          }
          disabled={accionEnCurso !== null}
          title="Ejecuta tests y los corrige automáticamente con IA (hasta 3 intentos)"
        >
          {accionEnCurso === "test" ? (
            <Loader2 size={14} className="spin" />
          ) : (
            <TestTube size={14} />
          )}
          <span>Probar + Fix</span>
        </button>
        <button
          className="proj-btn primary"
          onClick={() =>
            onRunRequest ? onRunRequest() : ejecutarAccion("run")
          }
          disabled={accionEnCurso !== null}
        >
          <Play size={14} />
          <span>Ejecutar</span>
        </button>
        <button
          className="proj-btn"
          onClick={() => {
            setShowGithubModal(true);
            setGithubError("");
            setGithubResultado(null);
            setGithubNombreRepo(nombreProyecto);
            setGithubDescripcion(`Proyecto generado por NIAH: ${nombreProyecto}`);
            setGithubPrivado(true);
          }}
          disabled={accionEnCurso !== null}
          title="Subir proyecto a GitHub"
        >
          <Upload size={14} />
          <span>Subir a GitHub</span>
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

      {showGithubModal && (
        <div
          className="modal-overlay"
          onClick={() => !githubSubiendo && setShowGithubModal(false)}
        >
          <div
            className="modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 500 }}
          >
            <div className="modal-title">
              <Upload size={18} />
              <h3>Subir a GitHub</h3>
              <button
                className="modal-close"
                onClick={() => !githubSubiendo && setShowGithubModal(false)}
              >
                <X size={16} />
              </button>
            </div>

            {githubResultado ? (
              <div style={{ padding: "20px 0" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    marginBottom: 16,
                    color: "#34C759",
                  }}
                >
                  <Check size={20} />
                  <strong>
                    {githubResultado.creado
                      ? "Repositorio creado"
                      : "Repositorio actualizado"}
                  </strong>
                </div>

                <p style={{ marginBottom: 8, color: "#6E6E73" }}>
                  URL del repositorio:
                </p>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    background: "#F5F5F7",
                    padding: "10px 12px",
                    borderRadius: 8,
                    marginBottom: 16,
                  }}
                >
                  <code style={{ flex: 1, fontSize: 12, wordBreak: "break-all" }}>
                    {githubResultado.repo_url}
                  </code>
                  <button
                    className="btn-icon"
                    onClick={() => copiarUrl(githubResultado.repo_url)}
                    title="Copiar URL"
                  >
                    {githubCopiado ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>

                <a
                  href={githubResultado.repo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    color: "#0A84FF",
                    textDecoration: "none",
                    fontSize: 14,
                  }}
                >
                  <ExternalLink size={14} />
                  Abrir en GitHub
                </a>
              </div>
            ) : (
              <>
                <div style={{ marginBottom: 16 }}>
                  <label
                    style={{
                      display: "block",
                      marginBottom: 6,
                      fontSize: 13,
                      color: "#6E6E73",
                    }}
                  >
                    Nombre del repositorio
                  </label>
                  <input
                    type="text"
                    value={githubNombreRepo}
                    onChange={(e) => setGithubNombreRepo(e.target.value)}
                    disabled={githubSubiendo}
                    placeholder="mi-proyecto"
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: 8,
                      border: "1px solid #D2D2D7",
                      fontSize: 14,
                      fontFamily: "inherit",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ marginBottom: 16 }}>
                  <label
                    style={{
                      display: "block",
                      marginBottom: 6,
                      fontSize: 13,
                      color: "#6E6E73",
                    }}
                  >
                    Descripción (opcional)
                  </label>
                  <textarea
                    value={githubDescripcion}
                    onChange={(e) => setGithubDescripcion(e.target.value)}
                    disabled={githubSubiendo}
                    rows={3}
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: 8,
                      border: "1px solid #D2D2D7",
                      fontSize: 14,
                      fontFamily: "inherit",
                      resize: "vertical",
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ marginBottom: 20 }}>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 14,
                      cursor: githubSubiendo ? "not-allowed" : "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={githubPrivado}
                      onChange={(e) => setGithubPrivado(e.target.checked)}
                      disabled={githubSubiendo}
                    />
                    <span>Repositorio privado</span>
                  </label>
                </div>

                {githubError && (
                  <div
                    style={{
                      padding: "10px 12px",
                      background: "#FFEBE9",
                      color: "#C0392B",
                      borderRadius: 8,
                      fontSize: 13,
                      marginBottom: 16,
                    }}
                  >
                    {githubError}
                  </div>
                )}

                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setShowGithubModal(false)}
                    disabled={githubSubiendo}
                    style={{
                      padding: "10px 20px",
                      borderRadius: 8,
                      border: "1px solid #D2D2D7",
                      background: "white",
                      cursor: githubSubiendo ? "not-allowed" : "pointer",
                      fontSize: 14,
                      fontFamily: "inherit",
                    }}
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={subirAGithub}
                    disabled={githubSubiendo || !githubNombreRepo.trim()}
                    style={{
                      padding: "10px 20px",
                      borderRadius: 8,
                      border: "none",
                      background: githubSubiendo ? "#8FBFFF" : "#0A84FF",
                      color: "white",
                      cursor: githubSubiendo ? "not-allowed" : "pointer",
                      fontSize: 14,
                      fontFamily: "inherit",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    {githubSubiendo ? (
                      <>
                        <Loader2 size={14} className="spin" />
                        Subiendo...
                      </>
                    ) : (
                      <>
                        <Upload size={14} />
                        Subir
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
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
