import { useState, useEffect } from "react";
import { Sparkles, Loader2, Check, Clock } from "lucide-react";

interface Props {
  instruccion: string;
}

const PASOS = [
  { id: 1, label: "Leyendo archivos del proyecto", duracion: 3 },
  { id: 2, label: "Analizando la instrucción", duracion: 5 },
  { id: 3, label: "Identificando archivos afectados", duracion: 15 },
  { id: 4, label: "Detectando dependencias y riesgos", duracion: 20 },
  { id: 5, label: "Evaluando alternativas", duracion: 15 },
  { id: 6, label: "Generando plan de cambios", duracion: 10 },
];

export default function AnalizandoEdit({ instruccion }: Props) {
  const [pasoActual, setPasoActual] = useState(0);
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    let paso = 0;
    let tiempoAcumulado = 0;
    const duraciones = PASOS.map((p) => p.duracion);

    const interval = setInterval(() => {
      setSegundos((s) => s + 1);
      tiempoAcumulado += 1;

      while (paso < PASOS.length - 1 && tiempoAcumulado >= duraciones[paso]) {
        tiempoAcumulado -= duraciones[paso];
        paso += 1;
        setPasoActual(paso);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="analizando-edit">
      <div className="analizando-header">
        <Loader2 size={16} className="spin" />
        <div>
          <strong>Analizando impacto del cambio</strong>
          <p className="analizando-instruccion">"{instruccion}"</p>
        </div>
        <div className="analizando-tiempo">
          <Clock size={12} />
          <span>{segundos}s</span>
        </div>
      </div>

      <div className="analizando-pasos">
        {PASOS.map((paso, i) => {
          const completado = i < pasoActual;
          const activo = i === pasoActual;
          return (
            <div
              key={paso.id}
              className={`analizando-paso ${completado ? "ok" : ""} ${
                activo ? "activo" : ""
              }`}
            >
              <div className="analizando-paso-icon">
                {completado ? (
                  <Check size={12} />
                ) : activo ? (
                  <Loader2 size={12} className="spin" />
                ) : (
                  <div className="analizando-paso-punto" />
                )}
              </div>
              <span>{paso.label}</span>
            </div>
          );
        })}
      </div>

      <div className="analizando-hint">
        <Sparkles size={11} />
        <span>
          Esto puede tardar 1-2 minutos. NIAH está usando el modelo
          qwen2.5:7b para razonar sobre tu proyecto.
        </span>
      </div>
    </div>
  );
}
