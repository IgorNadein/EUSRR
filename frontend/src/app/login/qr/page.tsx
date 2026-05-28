"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Loader2, QrCode } from "lucide-react";

import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";

type QrLoginState = "loading" | "success" | "error";

export default function QrLoginPage() {
  const { refreshUser } = useUser();
  const startedRef = useRef(false);
  const [state, setState] = useState<QrLoginState>("loading");
  const [message, setMessage] = useState("Проверяем одноразовую ссылку...");

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    async function exchangeToken() {
      const token = new URLSearchParams(window.location.search).get("token")?.trim();
      if (!token) {
        setState("error");
        setMessage("В ссылке нет QR-токена.");
        return;
      }

      try {
        await apiClient.loginWithQrToken(token);
        setState("success");
        setMessage("Вход выполнен.");
        await refreshUser().catch((error) => {
          console.warn("Не удалось обновить пользователя после QR-входа:", error);
        });
        window.location.replace("/");
      } catch (error) {
        console.error("QR login failed", error);
        apiClient.clearToken();
        setState("error");
        setMessage("QR-ссылка недействительна, устарела или уже использована.");
      }
    }

    void exchangeToken();
  }, [refreshUser]);

  return (
    <div className="app-shell min-h-screen text-[var(--foreground)]">
      <div className="mx-auto flex min-h-screen max-w-xl items-center justify-center px-6 py-12">
        <div className="app-surface-elevated w-full rounded-[2rem] p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl app-surface-muted">
            {state === "loading" ? (
              <Loader2 className="animate-spin app-accent-text" size={26} />
            ) : (
              <QrCode className="app-accent-text" size={26} />
            )}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Вход по QR
          </h1>
          <p className="app-text-muted mt-3 text-sm">{message}</p>

          {state === "error" ? (
            <Link
              href="/login"
              className="app-action-primary mt-6 inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold"
            >
              Войти с паролем
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}
