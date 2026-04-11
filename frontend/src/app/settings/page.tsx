"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";

import { AppShell, PageHeader } from "@/components/AppShell";
import { useTheme } from "@/contexts/ThemeContext";
import type { ThemePreference } from "@/lib/theme";

const themeCards: Array<{
  value: ThemePreference;
  title: string;
  description: string;
  icon: typeof Sun;
}> = [
  {
    value: "light",
    title: "Светлая",
    description: "Светлые поверхности и нейтральный фон.",
    icon: Sun,
  },
  {
    value: "dark",
    title: "Темная",
    description: "Темные поверхности, ручное включение без браузерной подкраски.",
    icon: Moon,
  },
  {
    value: "auto",
    title: "Авто",
    description: "Следует системной теме устройства и браузера.",
    icon: Monitor,
  },
];

export default function SettingsPage() {
  const { theme, resolvedTheme, setTheme } = useTheme();

  return (
    <AppShell>
      <PageHeader
        title="Настройки"
        subtitle="Управление темой текущего фронта. Переключение работает через собственный runtime приложения, без зависимости от browser force-dark."
        eyebrow="Оформление"
        badge={`Активно: ${resolvedTheme === "dark" ? "Темная" : "Светлая"}`}
      />

      <section className="app-surface space-y-6 rounded-2xl p-5">
        <div>
          <h2 className="text-base font-semibold text-[var(--foreground)]">Тема интерфейса</h2>
          <p className="app-text-muted mt-1 text-sm">
            Режим сохраняется в браузере как <code>localStorage.theme</code> со значениями <code>light</code>, <code>dark</code> или <code>auto</code>.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {themeCards.map(({ value, title, description, icon: Icon }) => {
            const active = theme === value;

            return (
              <button
                key={value}
                type="button"
                onClick={() => setTheme(value)}
                className={`rounded-2xl p-4 text-left transition ${
                  active
                    ? "app-selected"
                    : "app-surface-muted hover:bg-[var(--surface-tertiary)]"
                }`}
              >
                <div className="mb-4 flex items-start justify-between gap-3">
                  <span
                    className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${
                      active ? "app-action-primary text-white" : "bg-[var(--surface-elevated)] text-[var(--muted-foreground)]"
                    }`}
                  >
                    <Icon size={20} />
                  </span>
                  <span
                    className={`app-badge inline-flex h-6 min-w-6 justify-center px-2 text-xs font-semibold ${
                      active ? "app-badge-accent" : ""
                    }`}
                  >
                    {active ? <Check size={14} /> : value}
                  </span>
                </div>

                <p className="text-sm font-semibold text-[var(--foreground)]">{title}</p>
                <p className="app-text-muted mt-1 text-sm">{description}</p>
              </button>
            );
          })}
        </div>

        <div className="app-surface-muted rounded-2xl p-4">
          <p className="text-sm font-medium text-[var(--foreground)]">Текущее состояние</p>
          <p className="app-text-muted mt-1 text-sm">
            Предпочтение: <strong className="text-[var(--foreground)]">{theme}</strong>. Примененная тема:{" "}
            <strong className="text-[var(--foreground)]">{resolvedTheme}</strong>.
          </p>
        </div>
      </section>
    </AppShell>
  );
}
