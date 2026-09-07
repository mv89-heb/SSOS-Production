"use client";

import { useEffect } from "react";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

export default function ReminderPushRegistration() {
  useEffect(() => {
    let cancelled = false;

    async function register() {
      if (cancelled || typeof window === "undefined") return;
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;
      if (!API_URL) return;

      try {
        const publicKeyResponse = await fetch(`${API_URL}/api/push/public-key`, { credentials: "include" });
        if (!publicKeyResponse.ok) return;
        const { public_key: publicKey } = await publicKeyResponse.json();
        if (!publicKey) return;

        const permission = Notification.permission === "default"
          ? await Notification.requestPermission()
          : Notification.permission;
        if (permission !== "granted") return;

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
      }
    }

    void register();
    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
