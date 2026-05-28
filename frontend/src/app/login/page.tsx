"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import {
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  QrCode,
  RefreshCw,
  UserRound,
} from "lucide-react";

import { AuthLegalNotice } from "@/components/auth/AuthLegalNotice";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import type { QrLoginRequestStatus } from "@/types/api";

type LoginMode = "password" | "qr";

type QrLoginViewState =
  | "idle"
  | "creating"
  | "pending"
  | "approved"
  | "denied"
  | "expired"
  | "claimed"
  | "error";

export default function Login() {
  const router = useRouter();
  const { refreshUser } = useUser();
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qrCompletedRef = useRef(false);
  const [mode, setMode] = useState<LoginMode>("password");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [qrState, setQrState] = useState<QrLoginViewState>("idle");
  const [qrError, setQrError] = useState("");
  const [qrRequest, setQrRequest] = useState<{
    clientSecret: string;
    qrDataUrl: string;
    expiresAt: string;
    deviceName: string;
    ipAddress?: string | null;
  } | null>(null);

  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const startQrLogin = useCallback(async () => {
    clearPollTimer();
    qrCompletedRef.current = false;
    const previousClientSecret = qrRequest?.clientSecret;
    setQrRequest(null);
    setQrError("");
    setQrState("creating");

    try {
      if (previousClientSecret) {
        await apiClient.cancelQrLoginRequest(previousClientSecret).catch((err) => {
          console.warn("Не удалось отменить предыдущий QR-запрос:", err);
        });
      }

      const request = await apiClient.createQrLoginRequest();
      const scanUrl = `${window.location.origin}/login/qr/confirm?token=${encodeURIComponent(request.scan_token)}`;
      const qrDataUrl = await QRCode.toDataURL(scanUrl, {
        errorCorrectionLevel: "M",
        margin: 1,
        width: 240,
        color: {
          dark: "#111827",
          light: "#ffffff",
        },
      });

      setQrRequest({
        clientSecret: request.client_secret,
        qrDataUrl,
        expiresAt: request.expires_at,
        deviceName: request.device_name,
        ipAddress: request.ip_address,
      });
      setQrState("pending");
    } catch (err) {
      console.error("Ошибка создания QR-входа:", err);
      setQrError("Не удалось создать QR-код для входа");
      setQrState("error");
    }
  }, [clearPollTimer, qrRequest?.clientSecret]);

  const handleQrStatus = useCallback(
    async (status: QrLoginRequestStatus) => {
      clearPollTimer();
      setQrState(status);
      if (status === "approved") {
        qrCompletedRef.current = true;
        setQrError("");
        await refreshUser().catch((err) => {
          console.warn("Не удалось обновить пользователя после QR-входа:", err);
        });
        window.location.replace("/");
        return;
      }
      if (status === "claimed" && apiClient.getToken()) {
        qrCompletedRef.current = true;
        window.location.replace("/");
        return;
      }
      if (status === "denied") {
        qrCompletedRef.current = true;
        setQrError("Вход по QR отменен на авторизованном устройстве");
      } else if (status === "expired") {
        qrCompletedRef.current = true;
        setQrError("QR-код устарел");
      } else if (status === "claimed") {
        qrCompletedRef.current = true;
        setQrError("Этот QR-код уже был использован");
      }
    },
    [clearPollTimer, refreshUser],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const credentials = login.includes("@")
        ? { email: login, password }
        : { phone: login, password };

      await apiClient.login(credentials);
      await refreshUser();
      router.push("/");
    } catch (err) {
      console.error("Ошибка авторизации:", err);
      setError("Неверный логин или пароль");
    } finally {
      setLoading(false);
    }
  };

  const handleCancelQrLogin = async () => {
    clearPollTimer();
    qrCompletedRef.current = true;
    const clientSecret = qrRequest?.clientSecret;
    setMode("password");
    setQrRequest(null);
    setQrState("idle");
    setQrError("");
    if (!clientSecret) return;

    try {
      await apiClient.cancelQrLoginRequest(clientSecret);
    } catch (err) {
      console.warn("Не удалось отменить QR-запрос:", err);
    }
  };

  useEffect(() => {
    if (mode === "qr" && !qrRequest && qrState === "idle") {
      void startQrLogin();
    }
  }, [mode, qrRequest, qrState, startQrLogin]);

  useEffect(() => {
    if (mode !== "qr" || qrState !== "pending" || !qrRequest) return;

    let cancelled = false;

    const poll = async () => {
      if (qrCompletedRef.current) return;

      try {
        const response = await apiClient.pollQrLoginRequest(qrRequest.clientSecret);
        if (cancelled || qrCompletedRef.current) return;
        if (response.status === "pending") {
          pollTimerRef.current = setTimeout(poll, 1800);
          return;
        }
        qrCompletedRef.current = true;
        await handleQrStatus(response.status);
      } catch (err) {
        if (cancelled || qrCompletedRef.current) return;
        console.error("Ошибка проверки QR-входа:", err);
        setQrError("Не удалось проверить статус QR-входа");
        setQrState("error");
      }
    };

    pollTimerRef.current = setTimeout(poll, 900);

    return () => {
      cancelled = true;
      clearPollTimer();
    };
  }, [clearPollTimer, handleQrStatus, mode, qrRequest, qrState]);

  const qrExpiresAt = qrRequest
    ? new Intl.DateTimeFormat("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(qrRequest.expiresAt))
    : "";

  return (
    <div className="app-shell min-h-screen text-[var(--foreground)]">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6 py-12 sm:px-10">
        <div className="app-surface-elevated w-full max-w-xl rounded-[2rem] p-8 sm:p-10">
          <h1 className="mb-2 text-3xl font-semibold tracking-tight text-[var(--foreground)] sm:text-4xl">
            Войти в аккаунт
          </h1>
          <p className="app-text-muted mb-8 text-sm">
            Используйте телефон или почту, чтобы продолжить.
          </p>

          {error ? (
            <div className="app-feedback-danger mb-4 rounded-xl p-3 text-sm">
              {error}
            </div>
          ) : null}

          <div className="app-surface-muted mb-6 grid grid-cols-2 gap-2 rounded-xl p-1">
            <button
              type="button"
              onClick={() => void handleCancelQrLogin()}
              className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                mode === "password" ? "app-action-primary" : "text-[var(--muted-foreground)]"
              }`}
            >
              <KeyRound size={16} />
              Пароль
            </button>
            <button
              type="button"
              onClick={() => setMode("qr")}
              className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                mode === "qr" ? "app-action-primary" : "text-[var(--muted-foreground)]"
              }`}
            >
              <QrCode size={16} />
              QR-код
            </button>
          </div>

          {mode === "password" ? (
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="app-field-label" htmlFor="login">
                  Телефон или почта
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
                    <UserRound size={18} />
                  </span>
                  <input
                    id="login"
                    name="login"
                    type="text"
                    autoComplete="username"
                    value={login}
                    onChange={(e) => setLogin(e.target.value)}
                    required
                    className="app-input w-full rounded-lg py-3 pl-11 pr-4 text-sm"
                    placeholder="example@mail.com"
                  />
                </div>
              </div>

              <div>
                <label className="app-field-label" htmlFor="password">
                  Пароль
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
                    <KeyRound size={18} />
                  </span>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="app-input w-full rounded-lg py-3 pl-11 pr-12 text-sm"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="app-icon-button absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
                    aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div className="flex justify-end text-sm">
                <Link href="/forgot-password" className="app-link-accent text-sm font-medium">
                  Забыли пароль?
                </Link>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="app-action-primary flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Вход..." : "Войти"}
              </button>

              <Link
                href="/register"
                className="app-action-secondary flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold"
              >
                Создать аккаунт
              </Link>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="app-surface-muted flex min-h-[280px] flex-col items-center justify-center rounded-2xl p-5 text-center">
                {qrState === "creating" ? (
                  <Loader2 className="app-accent-text animate-spin" size={32} />
                ) : qrRequest ? (
                  <>
                    <div className="rounded-2xl bg-white p-3">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={qrRequest.qrDataUrl}
                        alt="QR для входа"
                        className="h-48 w-48"
                      />
                    </div>
                    <p className="app-text-muted mt-4 text-sm">
                      {qrState === "pending"
                        ? "Ожидаем подтверждение на авторизованном устройстве"
                        : qrError || "QR-вход недоступен"}
                    </p>
                    <div className="mt-3 flex flex-wrap justify-center gap-2">
                      <span className="app-badge px-2.5 py-1 text-xs font-medium">
                        {qrRequest.deviceName}
                      </span>
                      {qrRequest.ipAddress ? (
                        <span className="app-badge px-2.5 py-1 text-xs font-medium">
                          IP: {qrRequest.ipAddress}
                        </span>
                      ) : null}
                      <span className="app-badge px-2.5 py-1 text-xs font-medium">
                        До {qrExpiresAt}
                      </span>
                    </div>
                  </>
                ) : (
                  <p className="app-text-muted text-sm">
                    {qrError || "QR-код не создан"}
                  </p>
                )}
              </div>

              {qrError ? (
                <div className="app-feedback-danger rounded-xl p-3 text-sm">
                  {qrError}
                </div>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => void startQrLogin()}
                  disabled={qrState === "creating"}
                  className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold disabled:opacity-50"
                >
                  <RefreshCw size={16} />
                  Обновить QR
                </button>
                <button
                  type="button"
                  onClick={() => void handleCancelQrLogin()}
                  className="app-action-secondary inline-flex items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold"
                >
                  Отмена
                </button>
              </div>
            </div>
          )}

          <AuthLegalNotice />
        </div>
      </div>
    </div>
  );
}
