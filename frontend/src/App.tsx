import { useState } from "react";
import axios from "axios";
import "./App.css";

const API_URL = "http://localhost:8000";

interface Message {
  role: "user" | "assistant";
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        mensaje: input,
      });
      const assistantMessage: Message = {
        role: "assistant",
        content: response.data.respuesta,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: no se pudo conectar con el servidor." },
      ]);
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

  return (
    <div className="app">
      <header>
        <h1>Mi Agente IA Local</h1>
        <span className="badge">phi3:mini · 100% local</span>
      </header>

      <main className="chat">
        {messages.length === 0 && (
          <p className="empty">Escribe un mensaje para empezar...</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <strong>{msg.role === "user" ? "Tú" : "Agente"}:</strong>
            <p>{msg.content}</p>
          </div>
        ))}
        {loading && <div className="message assistant">Pensando...</div>}
      </main>

      <footer>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Escribe tu mensaje..."
          rows={2}
        />
        <button onClick={sendMessage} disabled={loading}>
          {loading ? "..." : "Enviar"}
        </button>
      </footer>
    </div>
  );
}

export default App;
