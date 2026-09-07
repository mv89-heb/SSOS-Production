"use client";

import { useEffect, useState } from "react";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

export default function ReminderPushRegistration() {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      setPermission("unsupported");
      return;
    }
    setPermission(Notification.permission);

    if (Notification.permission === "granted") {
      void subscribe(false);
    }
  }, []);

  async function subscribe(requestPermission: boolean) {
    if (busy || !API_URL || typeof window === "undefined") return;
    setBusy(true);
    try {
      if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) return;

      const nextPermission = requestPermission
        ? await Notification.requestPermission()
        : Notification.permission;
      setPermission(nextPermission);
      if (nextPermission !== "granted") return;

      const publicKeyResponse = await fetch(`${API_URL}/api/push/public-key`, { credentials: "include" });
      if (!publicKeyResponse.ok) return;
      const { public_key: publicKey } = await publicKeyResponse.json();
      if (!publicKey) return;

      const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
      }

      await fetch(`${API_URL}/api/push/subscribe`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(subscription.toJSON()),
      });
    } catch {
      // Push is an enhancement; never block the application if a device/browser rejects it.
    } finally {
      setBusy(false);
    }
  }

  if (permission === "unsupported" || permission === "granted") return null;

  return (
    <button
      type="button"
      onClick={() => void subscribe(true)}
      disabled={busy}
      className="fixed bottom-4 left-4 z-50 rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-slate-800 disabled:opacity-60"
      aria-label="הפעל התראות תזכורות בנייד"
    >
      {busy ? "מפעיל התראות…" : permission === "denied" ? "אפשר התראות בהגדרות" : "🔔 הפעל התראות תזכורות בנייד"}
    </button>
  );
}
