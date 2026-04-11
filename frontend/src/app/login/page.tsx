"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Eye, EyeOff, KeyRound, UserRound } from "lucide-react";

import { AuthLegalNotice } from "@/components/auth/AuthLegalNotice";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const { refreshUser } = useUser();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

          <AuthLegalNotice />
        </div>
      </div>
    </div>
  );
}
