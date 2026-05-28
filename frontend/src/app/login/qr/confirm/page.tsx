"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Ban,
  CheckCircle2,
  Clock3,
  Loader2,
  LogIn,
  MonitorSmartphone,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import type { QrLoginRequestDetailResult, QrLoginRequestStatus } from "@/types/api";

type ConfirmState =
  | "loading"
  | "ready"
  | "approving"
  | "denying"
  | "approved"
  | "denied"
  | "expired"
  | "claimed"
  | "unauthorized"
  | "error";

const closedStateText: Record<Extract<ConfirmState, "approved" | "denied" | "expired" | "claimed">, string> = {
  approved: "Запрос подтвержден. Новое устройство завершает вход.",
  denied: "Запрос входа отменен.",
  expired: "QR-код устарел.",
  claimed: "Этот QR-код уже был использован.",
};

function getClosedStateText(status: QrLoginRequestStatus): string {
  if (status === "approved" || status === "denied" || status === "expired" || status === "claimed") {
    return closedStateText[status];
  }
  return "Запрос обработан.";
}

function getConfirmStateFromStatus(status: QrLoginRequestStatus): ConfirmState {
  return status === "pending" ? "ready" : status;
}

export default function QrLoginConfirmPage() {
  const { user, loading } = useUser();
  const [scanToken, setScanToken] = useState("");
  const [state, setState] = useState<ConfirmState>("loading");
  const [message, setMessage] = useState("");
  const [requestDetails, setRequestDetails] =
    useState<QrLoginRequestDetailResult | null>(null);

  const currentUserName = useMemo(() => {
    if (!user) return "";
    return [user.last_name, user.first_name, user.patronymic]
      .filter(Boolean)
      .join(" ") || user.email;
  }, [user]);

  const loadRequest = useCallback(async (token: string) => {
    setState("loading");
    setMessage("");

    try {
      const details = await apiClient.getQrLoginRequest(token);
      setRequestDetails(details);

      if (details.status === "pending") {
        setState("ready");
        return;
      }

      setState(details.status);
      setMessage(getClosedStateText(details.status));
    } catch (error) {
      console.error("Ошибка загрузки QR-запроса:", error);
      setState("error");
      setMessage("QR-запрос не найден или уже недоступен.");
    }
  }, []);

  const loadInitialRequest = useCallback(async () => {
    const token = new URLSearchParams(window.location.search).get("token")?.trim();
    if (!token) {
      setState("error");
      setMessage("В ссылке нет QR-токена.");
      return;
    }

    setScanToken(token);

    if (!user) {
      setState("unauthorized");
      setMessage("Откройте эту ссылку на устройстве, где уже выполнен вход.");
      return;
    }

    await loadRequest(token);
  }, [loadRequest, user]);

  useEffect(() => {
    if (loading) return;

    const timerId = window.setTimeout(() => {
      void loadInitialRequest();
    }, 0);

    return () => window.clearTimeout(timerId);
  }, [loadInitialRequest, loading]);

  const handleApprove = async () => {
    if (!scanToken || state !== "ready") return;
    setState("approving");
    setMessage("");

    try {
      const result = await apiClient.approveQrLoginRequest(scanToken);
      setState(getConfirmStateFromStatus(result.status));
      setMessage(getClosedStateText(result.status));
    } catch (error) {
      console.error("Ошибка подтверждения QR-входа:", error);
      setState("error");
      setMessage("Не удалось подтвердить вход. Запрос мог устареть.");
    }
  };

  const handleDeny = async () => {
    if (!scanToken || state !== "ready") return;
    setState("denying");
    setMessage("");

    try {
      const result = await apiClient.denyQrLoginRequest(scanToken);
      setState(getConfirmStateFromStatus(result.status));
      setMessage(getClosedStateText(result.status));
    } catch (error) {
      console.error("Ошибка отмены QR-входа:", error);
      setState("error");
      setMessage("Не удалось отменить вход. Запрос мог устареть.");
    }
  };

  const expiresAt = requestDetails
    ? new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(requestDetails.expires_at))
    : "";

  const isBusy = state === "loading" || state === "approving" || state === "denying";
  const statusIcon =
    state === "approved" ? (
      <CheckCircle2 className="app-accent-text" size={28} />
    ) : state === "denied" || state === "expired" || state === "claimed" || state === "error" ? (
      <XCircle className="text-[var(--danger-foreground)]" size={28} />
    ) : isBusy ? (
      <Loader2 className="app-accent-text animate-spin" size={28} />
    ) : (
      <ShieldCheck className="app-accent-text" size={28} />
    );

  return (
    <div className="app-shell min-h-screen text-[var(--foreground)]">
      <div className="mx-auto flex min-h-screen max-w-xl items-center justify-center px-6 py-12">
        <div className="app-surface-elevated w-full rounded-[2rem] p-8 sm:p-10">
          <div className="app-badge app-badge-accent mb-6 flex h-14 w-14 items-center justify-center rounded-2xl">
            {statusIcon}
          </div>

          <h1 className="text-3xl font-semibold tracking-tight">
            Подтверждение входа
          </h1>
          <p className="app-text-muted mt-3 text-sm">
            Проверьте устройство и аккаунт перед подтверждением.
          </p>

          {requestDetails ? (
            <div className="app-surface-muted mt-6 space-y-4 rounded-2xl p-5">
              <div className="flex gap-3">
                <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                  <MonitorSmartphone size={20} />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[var(--foreground)]">
                    {requestDetails.device_name}
                  </p>
                  <p className="app-text-muted mt-1 text-xs">
                    {requestDetails.ip_address ? `IP: ${requestDetails.ip_address}` : "IP не определен"}
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                  <Clock3 size={20} />
                </span>
                <div>
                  <p className="text-sm font-semibold text-[var(--foreground)]">
                    Действует до {expiresAt}
                  </p>
                  <p className="app-text-muted mt-1 text-xs">
                    Статус: {requestDetails.status}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {user ? (
            <div className="app-surface-muted mt-4 rounded-2xl p-5">
              <p className="app-text-muted text-xs">Вход будет подтвержден аккаунтом</p>
              <p className="mt-1 text-sm font-semibold text-[var(--foreground)]">
                {currentUserName}
              </p>
              <p className="app-text-muted mt-1 text-xs">{user.email}</p>
            </div>
          ) : null}

          {message ? (
            <div
              className={`mt-5 rounded-xl p-3 text-sm ${
                state === "approved" ? "app-feedback-success" : "app-feedback-danger"
              }`}
            >
              {message}
            </div>
          ) : null}

          {state === "unauthorized" ? (
            <Link
              href="/login"
              className="app-action-primary mt-6 inline-flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold"
            >
              Войти на этом устройстве
            </Link>
          ) : null}

          {state === "ready" || state === "approving" || state === "denying" ? (
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => void handleApprove()}
                disabled={isBusy}
                className="app-action-primary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {state === "approving" ? <Loader2 className="animate-spin" size={16} /> : <LogIn size={16} />}
                Войти
              </button>
              <button
                type="button"
                onClick={() => void handleDeny()}
                disabled={isBusy}
                className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {state === "denying" ? <Loader2 className="animate-spin" size={16} /> : <Ban size={16} />}
                Отменить
              </button>
            </div>
          ) : null}

          <Link
            href="/"
            className="app-action-secondary mt-6 inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold"
          >
            <ArrowLeft size={16} />
            Назад
          </Link>
        </div>
      </div>
    </div>
  );
}
