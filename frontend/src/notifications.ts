// frontend/src/notifications.ts
/**
 * Utilidad para notificaciones del navegador.
 * Usa la Web Notification API (estándar, sin dependencias).
 */

const STORAGE_KEY = "niah_notif_enabled";

export function notificacionesSoportadas(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function permisoActual(): NotificationPermission | "no-soportado" {
  if (!notificacionesSoportadas()) return "no-soportado";
  return Notification.permission;
}

export function notificacionesActivas(): boolean {
  if (!notificacionesSoportadas()) return false;
  if (Notification.permission !== "granted") return false;
  return localStorage.getItem(STORAGE_KEY) === "1";
}

export async function pedirPermiso(): Promise<boolean> {
  if (!notificacionesSoportadas()) return false;
  if (Notification.permission === "granted") {
    localStorage.setItem(STORAGE_KEY, "1");
    return true;
  }
  if (Notification.permission === "denied") return false;
  const permiso = await Notification.requestPermission();
  if (permiso === "granted") {
    localStorage.setItem(STORAGE_KEY, "1");
    return true;
  }
  return false;
}

export function desactivarNotificaciones(): void {
  localStorage.setItem(STORAGE_KEY, "0");
}

export function activarNotificaciones(): void {
  localStorage.setItem(STORAGE_KEY, "1");
}

interface NotifOptions {
  titulo: string;
  cuerpo: string;
  tag?: string;
  urlDestino?: string;
}

export function notificar({ titulo, cuerpo, tag, urlDestino }: NotifOptions): void {
  if (!notificacionesActivas()) return;
  if (Notification.permission !== "granted") return;

  // Solo notificar si la pestaña no está visible (evita spam cuando el usuario está mirando)
  if (document.visibilityState === "visible") return;

  try {
    const n = new Notification(titulo, {
      body: cuerpo,
      tag,
      icon: "/favicon.ico",
      badge: "/favicon.ico",
      requireInteraction: false,
    });

    if (urlDestino) {
      n.onclick = () => {
        window.focus();
        if (urlDestino) window.location.href = urlDestino;
        n.close();
      };
    } else {
      n.onclick = () => {
        window.focus();
        n.close();
      };
    }

    // Auto-cerrar a los 10s
    setTimeout(() => n.close(), 10000);
  } catch {
    /* silent */
  }
}
