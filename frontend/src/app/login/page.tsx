"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";

export default function Login() {
  const router = useRouter();
  const { refreshUser } = useUser();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Определяем email это или телефон
      const credentials = login.includes("@")
        ? { email: login, password }
        : { phone: login, password };

      await apiClient.login(credentials);

      // Обновляем данные пользователя в контексте
      await refreshUser();

      // Перенаправляем на главную
      router.push("/");
    } catch (err: any) {
      console.error("Ошибка авторизации:", err);
      setError("Неверный логин или пароль");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white text-gray-900">
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-12 sm:px-10">
        <div className="mx-auto w-full max-w-xl rounded-2xl bg-white p-8 shadow-xl ring-1 ring-gray-100">
          <h1 className="mb-2 text-3xl font-semibold tracking-tight text-gray-900 sm:text-4xl">
            Войти в аккаунт
          </h1>
          <p className="mb-8 text-sm text-gray-600">
            Используйте телефон или почту, чтобы продолжить.
          </p>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="login">
                Телефон или почта
              </label>
              <input
                id="login"
                name="login"
                type="text"
                autoComplete="username"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="example@mail.com"
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="password">
                Пароль
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="••••••••"
              />
            </div>
            <div className="flex items-center justify-between text-sm text-gray-600">
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                />
                Запомнить меня
              </label>
              <a className="font-medium text-sky-600 transition hover:text-sky-700" href="#">
                Забыли пароль?
              </a>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center rounded-lg bg-sky-400 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Вход..." : "Войти"}
            </button>
            <Link
              href="/register"
              className="flex w-full items-center justify-center rounded-lg border border-gray-200 px-4 py-3 text-sm font-semibold text-sky-700 transition hover:border-sky-200 hover:bg-sky-50 focus:outline-none focus:ring-2 focus:ring-sky-100"
            >
              Создать аккаунт
            </Link>
          </form>
          <p className="mt-6 text-center text-xs text-gray-500">
            Продолжая, вы соглашаетесь с условиями использования и подтверждаете ознакомление с политикой конфиденциальности.
          </p>
        </div>
      </div>
    </div>
  );
}
