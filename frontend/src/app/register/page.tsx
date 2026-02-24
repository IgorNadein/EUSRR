import Link from "next/link";

export default function Register() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white text-gray-900">
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-12 sm:px-10">
        <div className="mx-auto w-full max-w-xl rounded-2xl bg-white p-8 shadow-xl ring-1 ring-gray-100">
          <h1 className="mb-2 text-3xl font-semibold tracking-tight text-gray-900 sm:text-4xl">
            Регистрация
          </h1>
          <p className="mb-8 text-sm text-gray-600">
            Создайте новый аккаунт, указав имя и контактные данные.
          </p>

          <form className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="firstName">
                  Имя
                </label>
                <input
                  id="firstName"
                  name="firstName"
                  type="text"
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  placeholder="Иван"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="lastName">
                  Фамилия
                </label>
                <input
                  id="lastName"
                  name="lastName"
                  type="text"
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  placeholder="Иванов"
                />
              </div>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="login">
                Телефон или почта
              </label>
              <input
                id="login"
                name="login"
                type="text"
                autoComplete="username"
                className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="example@mail.com"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="password">
                  Пароль
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="confirmPassword">
                  Повторите пароль
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  placeholder="••••••••"
                />
              </div>
            </div>
            <label className="flex items-center gap-3 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              />
              Я согласен с условиями использования
            </label>

            <button
              type="submit"
              className="flex w-full items-center justify-center rounded-lg bg-sky-400 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
            >
              Создать аккаунт
            </button>
            <Link
              href="/login"
              className="flex w-full items-center justify-center rounded-lg border border-gray-200 px-4 py-3 text-sm font-semibold text-sky-700 transition hover:border-sky-200 hover:bg-sky-50 focus:outline-none focus:ring-2 focus:ring-sky-100"
            >
              Уже есть аккаунт? Войти
            </Link>
          </form>
          <p className="mt-6 text-center text-xs text-gray-500">
            Регистрируясь, вы принимаете условия использования и подтверждаете ознакомление с политикой конфиденциальности.
          </p>
        </div>
      </div>
    </div>
  );
}
