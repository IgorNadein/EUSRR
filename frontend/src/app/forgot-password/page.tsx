"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, KeyRound, Mail, UserRound } from "lucide-react";

import { AuthLegalNotice } from "@/components/auth/AuthLegalNotice";
import { apiClient } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [login, setLogin] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await apiClient.requestPasswordReset({ login });
      setSubmitted(true);
    } catch (requestError) {
      console.error("Password reset request failed", requestError);
      setError("Не удалось отправить письмо для восстановления. Попробуйте позже.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell min-h-screen text-[var(--foreground)]">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6 py-12 sm:px-10">
        <div className="app-surface-elevated w-full max-w-xl rounded-[2rem] p-8 sm:p-10">
          <div className="app-badge app-badge-accent mb-6 flex h-14 w-14 items-center justify-center rounded-2xl">
            <KeyRound size={26} />
          </div>

          <h1 className="text-3xl font-semibold tracking-tight">Восстановление доступа</h1>
          <p className="app-text-muted mt-3 text-sm leading-6">
            Укажите почту или телефон аккаунта. Если такой профиль существует, на привязанный email
            придет ссылка для сброса пароля.
          </p>

          {submitted ? (
            <div className="app-surface-muted mt-6 rounded-2xl p-5">
              <div className="flex items-start gap-3">
                <span className="app-badge app-badge-accent flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                  <Mail size={18} />
                </span>
                <div>
                  <p className="text-sm font-semibold">Письмо отправлено</p>
                  <p className="app-text-muted mt-1 text-sm leading-6">
                    Если аккаунт найден, ссылка уже отправлена на email, привязанный к профилю.
                    Проверьте входящие и папку со спамом.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
              {error ? (
                <div className="app-feedback-danger rounded-xl p-3 text-sm">
                  {error}
                </div>
              ) : null}

              <div>
                <label className="app-field-label" htmlFor="forgot-login">
                  Телефон или почта
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
                    <UserRound size={18} />
                  </span>
                  <input
                    id="forgot-login"
                    type="text"
                    autoComplete="username"
                    value={login}
                    onChange={(e) => setLogin(e.target.value)}
                    className="app-input w-full rounded-lg py-3 pl-11 pr-4 text-sm"
                    placeholder="example@mail.com или +7 999 123-45-67"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="app-action-primary flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Отправка..." : "Отправить ссылку"}
              </button>
            </form>
          )}

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/login"
              className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
            >
              <ArrowLeft size={16} />
              Вернуться ко входу
            </Link>
          </div>

          <AuthLegalNotice prefix="Продолжая использовать сервис, вы соглашаетесь с " />
        </div>
      </div>
    </div>
  );
}
