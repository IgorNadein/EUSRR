"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { ArrowLeft, Eye, EyeOff, KeyRound, LockKeyhole } from "lucide-react";

import { AuthLegalNotice } from "@/components/auth/AuthLegalNotice";
import { apiClient } from "@/lib/api";

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid") ?? "";
  const token = searchParams.get("token") ?? "";
  const hasResetParams = Boolean(uid && token);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const submitDisabled = useMemo(
    () => loading || !newPassword || !confirmPassword || !hasResetParams,
    [confirmPassword, hasResetParams, loading, newPassword],
  );

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await apiClient.confirmPasswordReset({
        uid,
        token,
        new_password: newPassword,
        new_password_confirm: confirmPassword,
      });
      setSuccess(true);
      setTimeout(() => router.push("/login"), 1200);
    } catch (requestError) {
      console.error("Password reset confirmation failed", requestError);
      setError("Ссылка недействительна, устарела или пароль не прошел проверку.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell min-h-screen text-[var(--foreground)]">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-6 py-12 sm:px-10">
        <div className="app-surface-elevated w-full max-w-xl rounded-[2rem] p-8 sm:p-10">
          <div className="app-badge app-badge-accent mb-6 flex h-14 w-14 items-center justify-center rounded-2xl">
            <LockKeyhole size={26} />
          </div>

          <h1 className="text-3xl font-semibold tracking-tight">Новый пароль</h1>
          <p className="app-text-muted mt-3 text-sm leading-6">
            Установите новый пароль для входа в аккаунт.
          </p>

          {!hasResetParams ? (
            <div className="app-feedback-danger mt-6 rounded-xl p-4 text-sm">
              В ссылке отсутствуют параметры восстановления. Запросите новую ссылку со страницы входа.
            </div>
          ) : null}

          {success ? (
            <div className="app-surface-muted mt-6 rounded-2xl p-5">
              <div className="flex items-start gap-3">
                <span className="app-badge app-badge-accent flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                  <KeyRound size={18} />
                </span>
                <div>
                  <p className="text-sm font-semibold">Пароль обновлен</p>
                  <p className="app-text-muted mt-1 text-sm leading-6">
                    Можно входить с новым паролем. Сейчас вернем вас на страницу входа.
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
                <label className="app-field-label" htmlFor="new-password">
                  Новый пароль
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
                    <KeyRound size={18} />
                  </span>
                  <input
                    id="new-password"
                    type={showNewPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="app-input w-full rounded-lg py-3 pl-11 pr-12 text-sm"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword((prev) => !prev)}
                    className="app-icon-button absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
                    aria-label={showNewPassword ? "Скрыть пароль" : "Показать пароль"}
                  >
                    {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="app-field-label" htmlFor="confirm-password">
                  Подтвердите пароль
                </label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
                    <KeyRound size={18} />
                  </span>
                  <input
                    id="confirm-password"
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="app-input w-full rounded-lg py-3 pl-11 pr-12 text-sm"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    className="app-icon-button absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
                    aria-label={showConfirmPassword ? "Скрыть пароль" : "Показать пароль"}
                  >
                    {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitDisabled}
                className="app-action-primary flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Сохранение..." : "Сохранить пароль"}
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  );
}
