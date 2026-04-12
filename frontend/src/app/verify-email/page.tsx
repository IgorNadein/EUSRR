'use client';

import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Check, Mail, RotateCw } from 'lucide-react';

export default function VerifyEmail() {
  return (
    <Suspense fallback={<VerifyEmailFallback />}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailFallback() {
  return (
    <div className="app-shell flex min-h-screen items-center justify-center px-6">
      <div className="app-surface-elevated w-full max-w-md rounded-[2rem] p-8 text-center">
        <div className="mx-auto mb-4 h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
        <p className="app-text-muted text-sm">Загрузка...</p>
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code: code.trim() }),
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
        headers: { 'Content-Type': 'application/json' },
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
      setCode('');
    } catch (err) {
      setError('Не удалось отправить код');
      console.error('Resend error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="app-shell flex min-h-screen items-center justify-center px-6">
        <div className="app-surface-elevated w-full max-w-md rounded-[2rem] p-8 text-center">
          <div className="app-badge app-badge-accent mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full">
            <Check size={30} />
          </div>
          <h1 className="mb-2 text-2xl font-semibold text-[var(--foreground)]">Email подтвержден</h1>
          <p className="app-text-muted mb-6 text-sm">
            Ваш аккаунт активирован. Перенаправляем на страницу входа...
          </p>
          <Link
            href="/login"
            className="app-action-primary inline-flex items-center justify-center rounded-lg px-6 py-3 text-sm font-semibold"
          >
            Войти в аккаунт
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell flex min-h-screen items-center justify-center px-6">
      <div className="app-surface-elevated w-full max-w-md rounded-[2rem] p-8">
        <div className="mb-8 text-center">
          <div className="app-badge app-badge-accent mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full">
            <Mail size={30} />
          </div>
          <h1 className="mb-2 text-2xl font-semibold text-[var(--foreground)]">Подтвердите email</h1>
          <p className="app-text-muted text-sm">
            Мы отправили код подтверждения на <br />
            <span className="font-medium text-[var(--foreground)]">{email}</span>
          </p>
        </div>

        {error ? (
          <div className="app-feedback-danger mb-6 rounded-xl p-4 text-sm">{error}</div>
        ) : null}

        {resendSuccess ? (
          <div className="app-feedback-success mb-6 rounded-xl p-4 text-sm">
            Новый код отправлен на {email}
          </div>
        ) : null}

        <form onSubmit={handleVerify} className="space-y-6">
          <div>
            <label className="app-field-label" htmlFor="code">
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
              className="app-input w-full rounded-lg px-4 py-3 text-center text-lg font-semibold tracking-[0.35em]"
              autoComplete="one-time-code"
            />
            <p className="app-text-muted mt-2 text-xs">Введите 6-значный код из письма</p>
          </div>

          <button
            type="submit"
            disabled={isLoading || code.length !== 6}
            className="app-action-primary w-full rounded-lg px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? 'Проверяем...' : 'Подтвердить email'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={handleResend}
            disabled={isLoading}
            className="app-link-accent inline-flex items-center gap-2 text-sm font-medium disabled:opacity-50"
          >
            <RotateCw size={16} />
            Отправить повторно
          </button>
        </div>

        <div className="mt-6 text-center">
          <Link href="/login" className="app-text-muted text-sm transition hover:text-[var(--foreground)]">
            ← Вернуться к входу
          </Link>
        </div>
      </div>
    </div>
  );
}
