'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';

export default function VerifyEmail() {
  return (
    <Suspense fallback={<VerifyEmailFallback />}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailFallback() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white flex items-center justify-center px-6">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center ring-1 ring-gray-100">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-sky-600"></div>
        <p className="mt-3 text-sm text-gray-500">Загрузка...</p>
      </div>
    </div>
  );
}

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get('email');
  
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);

  useEffect(() => {
    if (!email) {
      router.push('/register');
    }
  }, [email, router]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/auth/verify-email/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          code: code.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.error === 'expired') {
          setError('Код истёк. Запросите новый код.');
        } else if (data.error === 'invalid_code') {
          setError('Неверный код подтверждения');
        } else if (data.error === 'user_not_found') {
          setError('Пользователь не найден');
        } else {
          setError('Ошибка подтверждения');
        }
        return;
      }

      setSuccess(true);

      // Редирект на страницу входа через 2 секунды
      setTimeout(() => {
        router.push('/login?verified=true');
      }, 2000);

    } catch (err) {
      setError('Не удалось подключиться к серверу');
      console.error('Verification error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    setIsLoading(true);
    setError(null);
    setResendSuccess(false);

    try {
      const response = await fetch('/api/v1/auth/resend-email/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.error === 'already_verified') {
          setError('Email уже подтвержден');
        } else if (data.error === 'user_not_found') {
          setError('Пользователь не найден');
        } else {
          setError('Ошибка отправки кода');
        }
        return;
      }

      setResendSuccess(true);
      setCode(''); // Очистить поле кода

    } catch (err) {
      setError('Не удалось отправить код');
      console.error('Resend error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white flex items-center justify-center px-6">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center ring-1 ring-gray-100">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <svg className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="mb-2 text-2xl font-semibold text-gray-900">
            Email подтвержден!
          </h1>
          <p className="text-gray-600 mb-6">
            Ваш аккаунт активирован. Перенаправляем на страницу входа...
          </p>
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-lg bg-sky-500 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-300"
          >
            Войти в аккаунт
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white flex items-center justify-center px-6">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 ring-1 ring-gray-100">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-sky-100">
            <svg className="h-8 w-8 text-sky-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="mb-2 text-2xl font-semibold text-gray-900">
            Подтвердите email
          </h1>
          <p className="text-sm text-gray-600">
            Мы отправили код подтверждения на <br />
            <span className="font-medium text-gray-900">{email}</span>
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-800">
            {error}
          </div>
        )}

        {resendSuccess && (
          <div className="mb-6 rounded-lg bg-green-50 border border-green-200 p-4 text-sm text-green-800">
            Новый код отправлен на {email}
          </div>
        )}

        <form onSubmit={handleVerify} className="space-y-6">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="code">
              Код подтверждения
            </label>
            <input
              id="code"
              type="text"
              required
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-center text-lg font-semibold tracking-widest text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              autoComplete="one-time-code"
            />
            <p className="mt-2 text-xs text-gray-500">
              Введите 6-значный код из письма
            </p>
          </div>

          <button
            type="submit"
            disabled={isLoading || code.length !== 6}
            className="w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Проверяем...
              </span>
            ) : (
              'Подтвердить email'
            )}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600">
            Не получили код?{' '}
            <button
              type="button"
              onClick={handleResend}
              disabled={isLoading}
              className="font-medium text-sky-600 hover:text-sky-700 transition disabled:opacity-50"
            >
              Отправить повторно
            </button>
          </p>
        </div>

        <div className="mt-6 text-center">
          <Link
            href="/login"
            className="text-sm text-gray-600 hover:text-gray-900 transition"
          >
            ← Вернуться к входу
          </Link>
        </div>
      </div>
    </div>
  );
}
