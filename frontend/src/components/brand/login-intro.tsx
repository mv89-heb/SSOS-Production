"use client";

import { useEffect, useState } from "react";
import SsosLogo from "@/components/brand/ssos-logo";

export default function LoginIntro() {
  // Render the splash immediately (including the server render) so the login
  // form can never flash before it. It is intentionally shown on every visit.
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timeout = window.setTimeout(() => setVisible(false), 7000);
    return () => window.clearTimeout(timeout);
  }, []);

  if (!visible) return null;

  return (
    <div
      className="ssos-intro fixed inset-0 z-[100] flex min-h-[100svh] items-center justify-center overflow-hidden px-6"
      role="status"
      aria-label="SSOS — סביבת עבודה חכמה לניהול רכש"
    >
      <div className="ssos-intro-grid absolute inset-0" aria-hidden="true" />
      <div className="ssos-intro-glow ssos-intro-glow-one" aria-hidden="true" />
      <div className="ssos-intro-glow ssos-intro-glow-two" aria-hidden="true" />
      <div className="ssos-intro-ring ssos-intro-ring-one" aria-hidden="true" />
      <div className="ssos-intro-ring ssos-intro-ring-two" aria-hidden="true" />
      <div className="ssos-intro-content relative z-10 flex flex-col items-center text-center">
        <div className="ssos-intro-logo">
          <SsosLogo size="lg" light />
        </div>
        <div className="ssos-intro-rule mt-8 h-px w-28" aria-hidden="true" />
        <p className="ssos-intro-title mt-6 text-xl font-extrabold tracking-wide text-white sm:text-2xl">
          כל שרשרת הרכש. בשליטה אחת.
        </p>
        <p className="ssos-intro-subtitle mt-3 text-xs font-semibold tracking-[0.2em] text-teal-100/70 sm:text-sm">
          SMART SUPPLIER ORDER SYSTEM
        </p>
      </div>
      <button
        type="button"
        onClick={() => setVisible(false)}
        className="absolute bottom-8 z-20 rounded-full border border-white/20 bg-white/5 px-4 py-2 text-xs font-semibold text-white/70 backdrop-blur transition hover:bg-white/10 hover:text-white"
        aria-label="דלג על פתיח המערכת"
      >
        דלג לפתיחת המערכת
      </button>
    </div>
  );
}
