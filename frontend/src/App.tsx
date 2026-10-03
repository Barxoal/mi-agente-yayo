import { useState, useEffect, useRef } from "react";
import {
  FolderClosed,
  MessageSquare,
  Plus,
  Trash2,
  Mic,
  Square,
  Volume2,
  Send,
  Sparkles,
  Paperclip,
  FileText,
  X,
  Download,
  LogOut,
  Menu,
  Wand2,
} from "lucide-react";
import MessageContent from "./MessageContent";
import Login from "./Login";
import AgentCreator from "./AgentCreator";
import GenerationProgress from "./GenerationProgress";
import ProjectPanel from "./ProjectPanel";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface Proyecto {
  id: string;
  nombre: string;
  tipo: string;
  created_at: string;
  origen?: string;
}

interface Chat {
  id: string;
  titulo: string;
  created_at: string;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  model?: string;
}

interface Documento {
  nombre: string;
  size: number;
}

type SpeechRecognitionType = {
  new (): {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    start: () => void;
    stop: () => void;
    onresult: (event: {
      results: { [k: number]: { [k: number]: { transcript: string } } };
    }) => void;
    onerror: () => void;
    onend: () => void;
  };
};

function App() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("niah_token")
  );
  const [proyectos, setProyectos] = useState<Proyecto[]>([]);
  const [proyectoActivo, setProyectoActivo] = useState<Proyecto | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatActivo, setChatActivo] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [modalProyecto, setModalProyecto] = useState(false);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [nuevoTipo, setNuevoTipo] = useState("script");
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [modalDocs, setModalDocs] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [sidebarAbierto, setSidebarAbierto] = useState(false);
  const [modalAgent, setModalAgent] = useState(false);
  const [planGenerado, setPlanGenerado] = useState<any>(null);
  const [nombreGenerado, setNombreGenerado] = useState<string>("");
  const [generandoPlan, setGenerandoPlan] = useState<any>(null);
  const [historialPlan, setHistorialPlan] = useState<
    { role: string; content: string }[]
  >([]);
  const recognitionRef = useRef<ReturnType<SpeechRecognitionType> | null>(null);
  const chatRef = useRef<HTMLElement>(null);

  const apiFetch = async (url: string, options: RequestInit = {}) => {
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  };

  const handleLogin = (nuevoToken: string) => {
    localStorage.setItem("niah_token", nuevoToken);
    setToken(nuevoToken);
  };

  const handleLogout = () => {
    localStorage.removeItem("niah_token");
    setToken(null);
    setProyectos([]);
    setProyectoActivo(null);
    setChats([]);
    setChatActivo(null);
    setMessages([]);
  };

  useEffect(() => {
    if (token) cargarProyectos();
  }, [token]);

  useEffect(() => {
    if (proyectoActivo) {
      cargarChats(proyectoActivo.id);
      cargarDocumentos(proyectoActivo.id);
    } else {
      setChats([]);
      setChatActivo(null);
      setMessages([]);
      setDocumentos([]);
    }
  }, [proyectoActivo]);

  useEffect(() => {
    if (chatActivo) {
      cargarHistorial(chatActivo.id);
    } else {
      setMessages([]);
    }
  }, [chatActivo]);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  const cargarProyectos = async () => {
    const r = await apiFetch(`${API_URL}/projects`);
    if (r.status === 401) return handleLogout();
    const data = await r.json();
    setProyectos(data.proyectos || []);
  };

  const cargarChats = async (projectId: string) => {
    const r = await apiFetch(`${API_URL}/projects/${projectId}/chats`);
    const data = await r.json();
    const lista = data.chats || [];
    setChats(lista);
    if (lista.length > 0) {
      setChatActivo(lista[0]);
    } else {
      setChatActivo(null);
    }
  };

  const cargarHistorial = async (chatId: string) => {
    const r = await apiFetch(`${API_URL}/chats/${chatId}/history`);
    const data = await r.json();
    setMessages(
      (data.historial || []).map(
        (h: { role: string; content: string; model: string }) => ({
          role: h.role as "user" | "assistant" | "system",
          content: h.content,
          model: h.model,
        })
      )
    );
  };

  const cargarDocumentos = async (projectId: string) => {
    const r = await apiFetch(`${API_URL}/projects/${projectId}/documents`);
    const data = await r.json();
    setDocumentos(data.documentos || []);
  };

  const crearProyecto = async () => {
    if (!nuevoNombre.trim()) return;
    const r = await apiFetch(`${API_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre: nuevoNombre, tipo: nuevoTipo }),
    });
    const data = await r.json();
    setModalProyecto(false);
    setNuevoNombre("");
    await cargarProyectos();
    const nuevosProyectos = await (await apiFetch(`${API_URL}/projects`)).json();
    const proyectoNuevo = nuevosProyectos.proyectos.find(
      (p: Proyecto) => p.id === data.project_id
    );
    if (proyectoNuevo) setProyectoActivo(proyectoNuevo);
  };

  const eliminarProyecto = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("¿Eliminar este proyecto y todos sus chats?")) return;
    await apiFetch(`${API_URL}/projects/${id}`, { method: "DELETE" });
    if (proyectoActivo?.id === id) setProyectoActivo(null);
    await cargarProyectos();
  };

  const crearChat = async () => {
    if (!proyectoActivo) return;
    const titulo = prompt("Nombre del nuevo chat:", "Nuevo chat");
    if (!titulo) return;
    const r = await apiFetch(`${API_URL}/projects/${proyectoActivo.id}/chats`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo }),
    });
    const data = await r.json();
    await cargarChats(proyectoActivo.id);
    const nuevos = await (
      await apiFetch(`${API_URL}/projects/${proyectoActivo.id}/chats`)
    ).json();
    const chatNuevo = nuevos.chats.find((c: Chat) => c.id === data.chat_id);
    if (chatNuevo) setChatActivo(chatNuevo);
  };

  const eliminarChat = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("¿Eliminar este chat?")) return;
    await apiFetch(`${API_URL}/chats/${id}`, { method: "DELETE" });
    if (proyectoActivo) await cargarChats(proyectoActivo.id);
  };

  const subirDocumento = async (file: File) => {
    if (!proyectoActivo) return;
    setSubiendo(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const r = await apiFetch(
        `${API_URL}/projects/${proyectoActivo.id}/documents`,
        { method: "POST", body: formData }
      );
      if (r.ok) {
        await cargarDocumentos(proyectoActivo.id);
      } else {
        alert("Error al subir el archivo");
      }
    } catch {
      alert("Error de conexión");
    } finally {
      setSubiendo(false);
    }
  };

  const eliminarDocumento = async (nombre: string) => {
    if (!proyectoActivo) return;
    if (!confirm(`¿Eliminar "${nombre}"?`)) return;
    await apiFetch(
      `${API_URL}/projects/${proyectoActivo.id}/documents/${nombre}`,
      { method: "DELETE" }
    );
    await cargarDocumentos(proyectoActivo.id);
  };

  const exportarChat = () => {
    if (!chatActivo || !token) return;
    apiFetch(`${API_URL}/chats/${chatActivo.id}/export`)
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${chatActivo.titulo.replace(/\s+/g, "_")}.md`;
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  const speak = (text: string) => {
    if (!voiceEnabled || !("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "es-MX";
    u.rate = 1.0;
    window.speechSynthesis.speak(u);
  };

  const startListening = () => {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert("Tu navegador no soporta reconocimiento de voz. Usa Chrome o Edge.");
      return;
    }
    const recognition = new SR();
    recognition.lang = "es-MX";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event: any) => {
      setInput(event.results[0][0].transcript);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || loading || !chatActivo) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    const prompt = input;
    setInput("");
    setLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await apiFetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mensaje: prompt,
          chat_id: chatActivo.id,
          project_id: proyectoActivo?.id,
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No hay stream");

      let fullText = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        fullText += chunk;
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, content: fullText };
          return updated;
        });
      }
      speak(fullText);
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "Error: no se pudo conectar con el servidor.",
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const seleccionarProyecto = (p: Proyecto) => {
    setProyectoActivo(p);
    if (window.innerWidth <= 768) setSidebarAbierto(false);
  };

  const seleccionarChat = (c: Chat) => {
    setChatActivo(c);
    if (window.innerWidth <= 768) setSidebarAbierto(false);
  };

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  // Determinar si mostrar ProjectPanel (proyecto IA + chat vacío)
  const mostrarProjectPanel =
    proyectoActivo?.origen === "ia" &&
    chatActivo &&
    messages.length === 0;

  return (
    <div className="layout">
      {sidebarAbierto && (
        <div
          className="sidebar-overlay open"
          onClick={() => setSidebarAbierto(false)}
        />
      )}
      <aside className={`sidebar ${sidebarAbierto ? "open" : ""}`}>
        <div className="sidebar-header">
          <h2>Proyectos</h2>
          <div className="sidebar-header-btns">
            <button
              className="btn-add"
              onClick={() => setModalProyecto(true)}
              title="Crear manualmente"
            >
              <Plus size={14} />
              <span>Crear</span>
            </button>
            <button
              className="btn-ia"
              onClick={() => setModalAgent(true)}
              title="Crear con IA"
            >
              <Wand2 size={14} />
              <span>IA</span>
            </button>
          </div>
        </div>
        <div className="proyectos-lista">
          {proyectos.length === 0 && (
            <p className="empty-sidebar">
              Aún no tienes nada creado.
              <br />
              Clic en <strong>Crear</strong> o <strong>IA</strong> para empezar.
            </p>
          )}
          {proyectos.map((p) => (
            <div key={p.id}>
              <div
                className={`proyecto-item ${
                  proyectoActivo?.id === p.id ? "active" : ""
                }`}
                onClick={() => seleccionarProyecto(p)}
              >
                <span className="proyecto-nombre">
                  {p.origen === "ia" ? <Wand2 size={14} /> : <FolderClosed size={14} />}
                  {p.nombre}
                </span>
                <button
                  className="btn-del"
                  onClick={(e) => eliminarProyecto(p.id, e)}
                  title="Eliminar proyecto"
                >
                  <Trash2 size={13} />
                </button>
              </div>
              {proyectoActivo?.id === p.id && (
                <div className="chats-lista">
                  {chats.map((c) => (
                    <div
                      key={c.id}
                      className={`chat-item ${
                        chatActivo?.id === c.id ? "active" : ""
                      }`}
                      onClick={() => seleccionarChat(c)}
                    >
                      <span>
                        <MessageSquare size={13} />
                        {c.titulo}
                      </span>
                      <button
                        className="btn-del"
                        onClick={(e) => eliminarChat(c.id, e)}
                        title="Eliminar chat"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                  <button className="btn-new-chat" onClick={crearChat}>
                    <Plus size={12} />
                    <span>Nuevo chat</span>
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </aside>

      <main className="main">
        <header>
          <div className="header-left">
            <button
              className="btn-menu"
              onClick={() => setSidebarAbierto(!sidebarAbierto)}
              title="Menú"
            >
              <Menu size={16} />
            </button>
            <h1>NIAH</h1>
            <span className="subtitle">
              {proyectoActivo
                ? `${proyectoActivo.nombre} · ${
                    chatActivo?.titulo || "sin chat"
                  }`
                : "Neural Intelligent Assistant Hub"}
            </span>
          </div>
          <div className="header-right">
            {proyectoActivo && (
              <button
                className="btn-docs"
                onClick={() => setModalDocs(true)}
                title="Documentos del proyecto"
              >
                <Paperclip size={14} />
                <span>Archivos ({documentos.length})</span>
              </button>
            )}
            {chatActivo && messages.length > 0 && (
              <button
                className="btn-docs"
                onClick={exportarChat}
                title="Exportar chat a Markdown"
              >
                <Download size={14} />
                <span>Exportar</span>
              </button>
            )}
            <label className="voice-toggle">
              <input
                type="checkbox"
                checked={voiceEnabled}
                onChange={(e) => setVoiceEnabled(e.target.checked)}
              />
              <Volume2 size={14} />
              <span>Voz</span>
            </label>
            <button
              className="btn-logout"
              onClick={handleLogout}
              title="Cerrar sesión"
            >
              <LogOut size={14} />
            </button>
          </div>
        </header>

        <section className="chat" ref={chatRef}>
          {!proyectoActivo && (
            <div className="empty">
              <p>Bienvenido a NIAH</p>
              <p className="hint">
                Elige algo del panel izquierdo, o crea uno nuevo con el botón{" "}
                <strong>Crear</strong> o <strong>IA</strong>.
              </p>
            </div>
          )}
          {proyectoActivo && !chatActivo && (
            <div className="empty">
              <p>Este proyecto no tiene chats</p>
              <p className="hint">Crea uno nuevo con el botón de arriba.</p>
            </div>
          )}

          {/* Opción C: ProjectPanel si es IA y el chat está vacío */}
          {mostrarProjectPanel && token && proyectoActivo && chatActivo && (
            <ProjectPanel
              token={token}
              nombreProyecto={proyectoActivo.nombre}
              chatId={chatActivo.id}
              onResultado={async (mensaje) => {
                if (!chatActivo || !mensaje) return;
                try {
                  await apiFetch(`${API_URL}/agent/system-message`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      chat_id: chatActivo.id,
                      contenido: mensaje,
                    }),
                  });
                } catch {}
                await cargarHistorial(chatActivo.id);
              }}
            />
          )}
          {/* Chat vacío normal (no IA o ya tiene ProjectPanel) */}
          {proyectoActivo &&
            chatActivo &&
            messages.length === 0 &&
            !mostrarProjectPanel && (
              <div className="empty">
                <p>Chat vacío</p>
                <p className="hint">
                  Escribe tu primer mensaje o sube documentos al proyecto para
                  que NIAH los consulte.
                </p>
              </div>
            )}

          {messages.map((msg, i) => {
            if (msg.role === "system") {
              return (
                <div key={i} className="message-system">
                  <div className="message-system-header">
                    <Sparkles size={12} />
                    <span>Resultado del sistema</span>
                  </div>
                  <div className="message-body">
                    <MessageContent content={msg.content} />
                  </div>
                </div>
              );
            }
            return (
              <div key={i} className={`message ${msg.role}`}>
                <strong>{msg.role === "user" ? "Tú" : "NIAH"}:</strong>
                <div className="message-body">
                  <MessageContent content={msg.content} />
                </div>
              </div>
            );
          })}
        </section>

        <footer>
          <button
            className={`mic ${listening ? "listening" : ""}`}
            onClick={listening ? stopListening : startListening}
            disabled={!chatActivo}
            title={listening ? "Detener grabación" : "Hablar"}
          >
            {listening ? <Square size={16} /> : <Mic size={16} />}
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={
              chatActivo
                ? "Escribe tu mensaje..."
                : "Selecciona un chat primero"
            }
            rows={2}
            disabled={!chatActivo}
          />
          <button onClick={sendMessage} disabled={loading || !chatActivo}>
            <Send size={14} />
            <span>{loading ? "..." : "Enviar"}</span>
          </button>
        </footer>
      </main>

      {modalProyecto && (
        <div className="modal-overlay" onClick={() => setModalProyecto(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">
              <Sparkles size={20} />
              <h3>Crear algo nuevo</h3>
            </div>
            <p className="modal-hint">
              Ponle un nombre y elige qué quieres crear. NIAH armará las
              carpetas y archivos por ti.
            </p>

            <label className="modal-label">Nombre</label>
            <input
              type="text"
              placeholder="Ej: Mi primer proyecto, Tareas del trabajo, Ideas..."
              value={nuevoNombre}
              onChange={(e) => setNuevoNombre(e.target.value)}
              autoFocus
            />

            <label className="modal-label">Tipo</label>
            <select
              value={nuevoTipo}
              onChange={(e) => setNuevoTipo(e.target.value)}
            >
              <option value="script">
                Nota simple — Un solo archivo para tareas rápidas
              </option>
              <option value="python">
                Carpeta organizada — Varios archivos ordenados por secciones
              </option>
              <option value="api">
                Servidor de datos — Responde preguntas a otras aplicaciones
              </option>
              <option value="web">
                Página web completa — Con diseño visual y servidor
              </option>
            </select>

            <div className="modal-actions">
              <button onClick={() => setModalProyecto(false)}>Cancelar</button>
              <button className="primary" onClick={crearProyecto}>
                <Plus size={14} />
                <span>Crear</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {modalDocs && proyectoActivo && (
        <div className="modal-overlay" onClick={() => setModalDocs(false)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">
              <Paperclip size={20} />
              <h3>Documentos de {proyectoActivo.nombre}</h3>
            </div>
            <p className="modal-hint">
              Sube archivos PDF, TXT o Markdown. NIAH los leerá y usará su
              contenido para responder tus preguntas.
            </p>

            <label className="upload-zone">
              <input
                type="file"
                accept=".pdf,.txt,.md,.py,.js,.ts,.json"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) subirDocumento(file);
                }}
                disabled={subiendo}
                style={{ display: "none" }}
              />
              <Paperclip size={20} />
              <span>
                {subiendo
                  ? "Subiendo..."
                  : "Haz clic para seleccionar un archivo"}
              </span>
            </label>

            <div className="docs-lista">
              {documentos.length === 0 && (
                <p className="empty-sidebar">
                  Aún no hay documentos en este proyecto.
                </p>
              )}
              {documentos.map((d) => (
                <div key={d.nombre} className="doc-item">
                  <div className="doc-info">
                    <FileText size={14} />
                    <span className="doc-nombre">{d.nombre}</span>
                    <span className="doc-size">
                      {(d.size / 1024).toFixed(1)} KB
                    </span>
                  </div>
                  <button
                    className="btn-del"
                    onClick={() => eliminarDocumento(d.nombre)}
                    title="Eliminar documento"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>

            <div className="modal-actions">
              <button onClick={() => setModalDocs(false)}>
                <X size={14} />
                <span>Cerrar</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {modalAgent && token && (
        <AgentCreator
          token={token}
          onClose={() => setModalAgent(false)}
          onPlanReady={(plan, nombre, historial) => {
            setPlanGenerado(plan);
            setNombreGenerado(nombre);
            setHistorialPlan(historial);
            setGenerandoPlan(plan);
            setModalAgent(false);
          }}
        />
      )}

      {generandoPlan && token && (
        <GenerationProgress
          token={token}
          plan={generandoPlan}
          historial={historialPlan}
          nombreProyecto={nombreGenerado}
          onClose={() => {
            setGenerandoPlan(null);
            setHistorialPlan([]);
            cargarProyectos();
          }}
          onGenerated={() => {
            cargarProyectos();
          }}
        />
      )}
    </div>
  );
}

export default App;
