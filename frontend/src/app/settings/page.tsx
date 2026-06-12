"use client";

import Image from "next/image";
import dynamic from "next/dynamic";
import {
  ArrowDown,
  ArrowUp,
  Bell,
  Check,
  Copy,
  Clock3,
  Download,
  Eye,
  EyeOff,
  KeyRound,
  LogOut,
  Mail,
  Monitor,
  Moon,
  QrCode,
  Save,
  Smartphone,
  Sun,
  UserRound,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { usePwa } from "@/contexts/PwaContext";
import { useMobileNavPlacement } from "@/contexts/MobileNavPlacementContext";
import {
  formatSessionDateTime,
  getSessionDeviceKind,
  getSessionDeviceName,
  type NotificationPreferences,
  useSettingsPage,
} from "@/hooks/useSettingsPage";
import { getVerbName } from "@/lib/verbTranslations";

const themeIcons = {
  Sun,
  Moon,
  Monitor,
} as const;

const AvatarCropper = dynamic(() => import("@/components/AvatarCropper"), {
  ssr: false,
});

const mobileNavCards = [
  {
    value: "top",
    title: "Сверху",
    description: "Мобильная панель навигации закреплена в верхней части экрана.",
    Icon: ArrowUp,
  },
  {
    value: "bottom",
    title: "Снизу",
    description: "Панель закреплена снизу, как в современных мобильных интерфейсах.",
    Icon: ArrowDown,
  },
] as const;

function getSessionDeviceIcon(deviceName?: string | null) {
  return getSessionDeviceKind(deviceName) === "mobile" ? Smartphone : Monitor;
}

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="relative inline-flex shrink-0 cursor-pointer items-center">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
        className="peer sr-only"
      />
      <div className="h-6 w-11 shrink-0 rounded-full bg-[var(--surface-tertiary)] transition after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow-sm after:transition-all after:content-[''] peer-checked:bg-[var(--accent-primary)] peer-checked:after:translate-x-full peer-disabled:cursor-not-allowed peer-disabled:opacity-50" />
    </label>
  );
}

function NotificationChannelIcon({
  active,
  children,
}: {
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
        active ? "app-badge app-badge-accent" : "app-badge"
      }`}
    >
      {children}
    </span>
  );
}

function SectionCard({
  id,
  title,
  description,
  action,
  children,
}: {
  id: string;
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="app-surface scroll-mt-24 rounded-2xl p-5">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="app-card-caption">{title}</h2>
          <p className="app-text-muted mt-1 text-sm">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const { mobileNavPlacement, setMobileNavPlacement } = useMobileNavPlacement();
  const { canInstall, install, isInstalled, isRegistrationReady } = usePwa();
  const {
    activeVerbCount,
    avatarCropperImage,
    avatarInputRef,
    changingPassword,
    contactsDirty,
    contactsForm,
    currentSession,
    fullName,
    isSubscribed,
    isSupported,
    loading,
    notificationDirty,
    otherSessions,
    passwordForm,
    permission,
    preferences,
    preferencesLoading,
    profileDirty,
    profileForm,
    pushLoading,
    qrLogin,
    qrLoginLoading,
    resolvedTheme,
    savingContacts,
    savingPreferences,
    savingProfile,
    sessionActionKey,
    sessionsLoading,
    sessionsUnavailable,
    showPasswordFields,
    summaryAvatar,
    theme,
    unreadVerbCount,
    user,
    verbTypes,
    handleAvatarChange,
    handleAvatarCropCancel,
    handleAvatarCropComplete,
    handleChangePassword,
    handleDndToggle,
    handleLogoutOthers,
    handleCreateQrLogin,
    handlePushToggle,
    handleSessionLogout,
    logout,
    saveContacts,
    savePreferences,
    saveProfile,
    setContactsForm,
    setPasswordForm,
    setPreferences,
    setProfileForm,
    setShowPasswordFields,
    setTheme,
    settingsInitials,
    settingsThemeCards,
  } = useSettingsPage();

  if (loading || !user) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка настроек...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <>
      <AppShell>
        <div className="space-y-6">
        {/* <PageHeader
          title="Настройки"
          subtitle="Единая точка для темы, профиля, контактов и правил доставки уведомлений."
        /> */}

        <div className="space-y-6">
            <SectionCard
              id="account"
              title="Профиль"
              description="Основные данные сотрудника, фото и краткая сводка по аккаунту."
              action={
                <button
                  type="button"
                  onClick={() => void saveProfile()}
                  disabled={!profileDirty || savingProfile}
                  className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                  <Save size={16} />
                  {savingProfile ? "Сохраняем..." : "Сохранить профиль"}
                </button>
              }
            >
              {/* <div className="mb-6 grid gap-3 md:grid-cols-3">
                <div className="app-surface-muted rounded-2xl p-4">
                  <p className="app-text-muted text-xs uppercase tracking-[0.16em]">Статус</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="app-badge app-badge-accent px-2.5 py-1 text-xs font-medium">
                      {user.is_active ? "Активный сотрудник" : "Неактивный профиль"}
                    </span>
                    <span className="app-badge px-2.5 py-1 text-xs font-medium">
                      {user.departments?.length || 0} отделов
                    </span>
                  </div>
                </div>
                <div className="app-surface-muted rounded-2xl p-4">
                  <p className="app-text-muted text-xs uppercase tracking-[0.16em]">Навыки</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--foreground)]">{user.skills?.length || 0}</p>
                </div>
                <div className="app-surface-muted rounded-2xl p-4">
                  <p className="app-text-muted text-xs uppercase tracking-[0.16em]">Непрочитано</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--foreground)]">{unreadVerbCount}</p>
                </div>
              </div> */}

              <div className="grid gap-6 lg:grid-cols-[220px,minmax(0,1fr)]">
                <div className="space-y-3">
                  <div className="relative mx-auto h-40 w-40 overflow-hidden rounded-[2rem] app-surface-muted">
                    {summaryAvatar ? (
                      <Image src={summaryAvatar} alt={fullName} fill className="object-cover" unoptimized />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center bg-[var(--accent-primary)] text-4xl font-semibold text-white">
                        {settingsInitials(user.first_name, user.last_name)}
                      </div>
                    )}
                  </div>

                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => handleAvatarChange(event.target.files?.[0] || null)}
                  />

                  <button
                    type="button"
                    onClick={() => avatarInputRef.current?.click()}
                    className="app-action-secondary w-full rounded-lg px-4 py-2 text-sm font-medium"
                  >
                    Выбрать фото
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="app-surface-muted rounded-2xl p-4 md:col-span-2">
                    <p className="text-sm font-semibold text-[var(--foreground)]">{fullName}</p>
                    <p className="app-text-muted mt-1 text-sm">{user.email || "Почта не указана"}</p>
                  </div>
                  <label className="block">
                    <span className="app-text-muted mb-2 block text-sm">Имя</span>
                    <input
                      value={profileForm.first_name}
                      onChange={(event) => setProfileForm((prev) => ({ ...prev, first_name: event.target.value }))}
                      className="app-input w-full rounded-lg px-4 py-3 text-sm"
                    />
                  </label>
                  <label className="block">
                    <span className="app-text-muted mb-2 block text-sm">Фамилия</span>
                    <input
                      value={profileForm.last_name}
                      onChange={(event) => setProfileForm((prev) => ({ ...prev, last_name: event.target.value }))}
                      className="app-input w-full rounded-lg px-4 py-3 text-sm"
                    />
                  </label>
                  <label className="block">
                    <span className="app-text-muted mb-2 block text-sm">Отчество</span>
                    <input
                      value={profileForm.patronymic}
                      onChange={(event) => setProfileForm((prev) => ({ ...prev, patronymic: event.target.value }))}
                      className="app-input w-full rounded-lg px-4 py-3 text-sm"
                    />
                  </label>
                  <label className="block">
                    <span className="app-text-muted mb-2 block text-sm">Дата рождения</span>
                    <input
                      type="date"
                      value={profileForm.birth_date}
                      onChange={(event) => setProfileForm((prev) => ({ ...prev, birth_date: event.target.value }))}
                      className="app-input w-full rounded-lg px-4 py-3 text-sm"
                    />
                  </label>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              id="appearance"
              title="Оформление"
              description="Тема текущего фронта и примененный visual mode."
            >
              <div className="grid gap-3 md:grid-cols-3">
                {settingsThemeCards.map(({ value, title, description, iconName }) => {
                  const active = theme === value;
                  const Icon = themeIcons[iconName];

                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setTheme(value)}
                      className={`rounded-2xl p-4 text-left transition ${
                        active ? "app-selected" : "app-surface-muted hover:bg-[var(--surface-tertiary)]"
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
                        <span className={`app-badge inline-flex h-6 min-w-6 justify-center px-2 text-xs font-semibold ${active ? "app-badge-accent" : ""}`}>
                          {active ? <Check size={14} /> : value}
                        </span>
                      </div>

                      <p className="text-sm font-semibold text-[var(--foreground)]">{title}</p>
                      <p className="app-text-muted mt-1 text-sm">{description}</p>
                    </button>
                  );
                })}
              </div>

              <div className="app-surface-muted mt-4 rounded-2xl p-4">
                <p className="text-sm font-medium text-[var(--foreground)]">Текущее состояние</p>
                <p className="app-text-muted mt-1 text-sm">
                  Предпочтение: <strong className="text-[var(--foreground)]">{theme}</strong>. Примененная тема:{" "}
                  <strong className="text-[var(--foreground)]">{resolvedTheme}</strong>.
                </p>
              </div>

              <div className="app-surface-muted mt-4 rounded-2xl p-4">
                <div className="mb-4">
                  <p className="text-sm font-medium text-[var(--foreground)]">Положение мобильной панели</p>
                  <p className="app-text-muted mt-1 text-sm">
                    Настраивает расположение мобильной панели навигации на этом устройстве.
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  {mobileNavCards.map(({ value, title, description, Icon }) => {
                    const active = mobileNavPlacement === value;

                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setMobileNavPlacement(value)}
                        className={`rounded-2xl p-4 text-left transition ${
                          active ? "app-selected" : "app-surface hover:bg-[var(--surface-tertiary)]"
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
                          <span className={`app-badge inline-flex h-6 min-w-6 justify-center px-2 text-xs font-semibold ${active ? "app-badge-accent" : ""}`}>
                            {active ? <Check size={14} /> : value}
                          </span>
                        </div>

                        <p className="text-sm font-semibold text-[var(--foreground)]">{title}</p>
                        <p className="app-text-muted mt-1 text-sm">{description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </SectionCard>

            <SectionCard
              id="app"
              title="Приложение"
              description="Установка приложения на устройство и базовый PWA-статус."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <div className="app-surface-muted rounded-2xl p-4">
                  <div className="flex items-start gap-3">
                    <span
                      className={`app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                        isInstalled ? "app-badge-accent" : ""
                      }`}
                    >
                      <Download size={18} />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--foreground)]">Статус установки</p>
                      <p className="app-text-muted mt-1 text-sm">
                        {isInstalled
                          ? "Приложение уже установлено на это устройство."
                          : canInstall
                            ? "Приложение можно установить через системный prompt браузера."
                            : "Установка через браузер сейчас недоступна."}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="app-surface-muted rounded-2xl p-4">
                  <div className="flex items-start gap-3">
                    <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                      <Smartphone size={18} />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--foreground)]">PWA-компоненты</p>
                      <p className="app-text-muted mt-1 text-sm">
                        Service Worker: {isRegistrationReady ? "зарегистрирован" : "не зарегистрирован"}.
                      </p>
                      <div className="mt-3">
                        <button
                          type="button"
                          onClick={() => void install()}
                          disabled={!canInstall}
                          className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                        >
                          <Download size={16} />
                          {isInstalled ? "Установлено" : "Установить приложение"}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              id="contacts"
              title="Контакты"
              description="Контакты, которые видят коллеги и которые используются для уведомлений."
              action={
                <button
                  type="button"
                  onClick={() => void saveContacts()}
                  disabled={!contactsDirty || savingContacts}
                  className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                  <Save size={16} />
                  {savingContacts ? "Сохраняем..." : "Сохранить контакты"}
                </button>
              }
            >
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="app-text-muted mb-2 block text-sm">Email</span>
                  <input
                    value={contactsForm.email}
                    onChange={(event) => setContactsForm((prev) => ({ ...prev, email: event.target.value }))}
                    className="app-input w-full rounded-lg px-4 py-3 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="app-text-muted mb-2 block text-sm">Телефон</span>
                  <input
                    value={contactsForm.phone_number}
                    onChange={(event) => setContactsForm((prev) => ({ ...prev, phone_number: event.target.value }))}
                    className="app-input w-full rounded-lg px-4 py-3 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="app-text-muted mb-2 block text-sm">Telegram</span>
                  <input
                    value={contactsForm.telegram}
                    onChange={(event) => setContactsForm((prev) => ({ ...prev, telegram: event.target.value }))}
                    className="app-input w-full rounded-lg px-4 py-3 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="app-text-muted mb-2 block text-sm">WhatsApp</span>
                  <input
                    value={contactsForm.whatsapp}
                    onChange={(event) => setContactsForm((prev) => ({ ...prev, whatsapp: event.target.value }))}
                    className="app-input w-full rounded-lg px-4 py-3 text-sm"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="app-text-muted mb-2 block text-sm">WeChat</span>
                  <input
                    value={contactsForm.wechat}
                    onChange={(event) => setContactsForm((prev) => ({ ...prev, wechat: event.target.value }))}
                    className="app-input w-full rounded-lg px-4 py-3 text-sm"
                  />
                </label>
              </div>
            </SectionCard>

            <SectionCard
              id="notifications"
              title="Уведомления"
              description="Каналы доставки, режим тишины и отключение отдельных типов событий."
              action={
                <button
                  type="button"
                  onClick={() => void savePreferences()}
                  disabled={!notificationDirty || savingPreferences || preferencesLoading}
                  className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                >
                  <Save size={16} />
                  {savingPreferences ? "Сохраняем..." : "Сохранить настройки"}
                </button>
              }
            >
              {preferencesLoading ? (
                <div className="app-surface-muted rounded-2xl p-5">
                  <p className="app-text-muted text-sm">Загрузка настроек уведомлений...</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="app-surface-muted rounded-2xl p-5">
                    <div className="space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex min-w-0 items-start gap-3">
                          <NotificationChannelIcon active={preferences.web_enabled}>
                            <Bell size={18} />
                          </NotificationChannelIcon>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[var(--foreground)]">Веб-уведомления</p>
                            <p className="app-text-muted mt-1 text-sm">
                              Колокольчик, popup и центр уведомлений внутри приложения.
                            </p>
                          </div>
                        </div>
                        <Toggle
                          checked={preferences.web_enabled}
                          onChange={(checked) => setPreferences((prev) => ({ ...prev, web_enabled: checked }))}
                        />
                      </div>

                      <div className="app-divider border-t" />

                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex min-w-0 items-start gap-3">
                            <NotificationChannelIcon active={preferences.email_enabled}>
                              <Mail size={18} />
                            </NotificationChannelIcon>
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-[var(--foreground)]">Email-уведомления</p>
                              <p className="app-text-muted mt-1 text-sm">
                                Письма и дайджесты на рабочую почту.
                              </p>
                            </div>
                          </div>
                          <Toggle
                            checked={preferences.email_enabled}
                            onChange={(checked) => setPreferences((prev) => ({ ...prev, email_enabled: checked }))}
                          />
                        </div>

                        {preferences.email_enabled && (
                          <div className="pl-[3.25rem]">
                            <label className="block">
                              <span className="app-text-muted mb-2 block text-sm">Частота отправки</span>
                              <select
                                value={preferences.email_frequency}
                                onChange={(event) =>
                                  setPreferences((prev) => ({
                                    ...prev,
                                    email_frequency: event.target.value as NotificationPreferences["email_frequency"],
                                  }))
                                }
                                className="app-select w-full rounded-lg px-4 py-3 text-sm md:max-w-sm"
                              >
                                <option value="instant">Мгновенно</option>
                                <option value="daily">Ежедневно</option>
                                <option value="weekly">Еженедельно</option>
                                <option value="never">Никогда</option>
                              </select>
                            </label>
                          </div>
                        )}
                      </div>

                      <div className="app-divider border-t" />

                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex min-w-0 items-start gap-3">
                            <NotificationChannelIcon active={preferences.push_enabled}>
                              <Smartphone size={18} />
                            </NotificationChannelIcon>
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-[var(--foreground)]">Push-уведомления</p>
                              <p className="app-text-muted mt-1 text-sm">
                                Системные уведомления на устройстве и в браузере.
                              </p>
                            </div>
                          </div>
                          <Toggle
                            checked={preferences.push_enabled}
                            onChange={(checked) => void handlePushToggle(checked)}
                            disabled={!isSupported || pushLoading}
                          />
                        </div>

                        {!isSupported && (
                          <div className="app-surface rounded-xl p-3 pl-[3.25rem]">
                            <p className="app-text-muted text-sm">Ваш браузер не поддерживает push-уведомления.</p>
                          </div>
                        )}

                        {isSupported && permission === "denied" && (
                          <div className="app-feedback-danger rounded-xl p-3 pl-[3.25rem] text-sm">
                            Уведомления запрещены в браузере. Измените разрешение в настройках браузера.
                          </div>
                        )}

                        {isSupported && permission === "granted" && preferences.push_enabled && (
                          <div className="app-selected rounded-xl p-3 pl-[3.25rem]">
                            <p className="app-accent-text text-sm font-medium">
                              Push-уведомления активны {isSubscribed ? "и подписка подтверждена" : ""}.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="app-surface-muted rounded-2xl p-5">
                    <div className="mb-4 flex items-start justify-between gap-4">
                      <div className="flex min-w-0 items-start gap-3">
                        <NotificationChannelIcon active={preferences.dnd_enabled}>
                          <Clock3 size={18} />
                        </NotificationChannelIcon>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[var(--foreground)]">Режим тишины</p>
                          <p className="app-text-muted mt-1 text-sm">
                            В этот период push и email отключаются, web-уведомления приходят без звука.
                          </p>
                        </div>
                      </div>
                      <Toggle
                        checked={preferences.dnd_enabled}
                        onChange={(checked) => handleDndToggle(checked)}
                      />
                    </div>

                    {preferences.dnd_enabled && (
                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="block">
                          <span className="app-text-muted mb-2 block text-sm">Начало</span>
                          <input
                            type="time"
                            value={preferences.dnd_start_time || "00:00"}
                            onChange={(event) =>
                              setPreferences((prev) => ({ ...prev, dnd_start_time: event.target.value || null }))
                            }
                            className="app-input w-full rounded-lg px-4 py-3 text-sm"
                          />
                        </label>
                        <label className="block">
                          <span className="app-text-muted mb-2 block text-sm">Конец</span>
                          <input
                            type="time"
                            value={preferences.dnd_end_time || "23:59"}
                            onChange={(event) =>
                              setPreferences((prev) => ({ ...prev, dnd_end_time: event.target.value || null }))
                            }
                            className="app-input w-full rounded-lg px-4 py-3 text-sm"
                          />
                        </label>
                      </div>
                    )}
                  </div>

                  <div className="app-surface-muted rounded-2xl p-4">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[var(--foreground)]">Типы событий</p>
                        <p className="app-text-muted mt-1 text-sm">
                          Активно: <strong className="text-[var(--foreground)]">{activeVerbCount}</strong> из{" "}
                          <strong className="text-[var(--foreground)]">{verbTypes.length}</strong>.
                        </p>
                      </div>
                      <span className="app-badge app-badge-accent px-2.5 py-1 text-xs font-medium">
                        {unreadVerbCount} непрочитанных
                      </span>
                    </div>

                    <div className="grid gap-2">
                      {verbTypes.map((verbType) => {
                        const enabled = !preferences.disabled_verbs.includes(verbType.verb);
                        return (
                          <label
                            key={verbType.verb}
                            className={`grid w-full max-w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3 overflow-hidden rounded-xl px-3 py-3 transition sm:px-4 ${
                              enabled ? "app-surface" : "app-surface-muted opacity-80"
                            }`}
                          >
                            <div className="min-w-0 flex-1">
                              <p className="app-text-wrap whitespace-normal text-sm font-medium leading-snug text-[var(--foreground)]">
                                {getVerbName(verbType.verb) || verbType.name}
                              </p>
                              <p className="app-text-muted app-text-wrap mt-1 text-xs leading-snug">
                                Всего: {verbType.total} · Непрочитано: {verbType.unread}
                              </p>
                            </div>
                            <Toggle
                              checked={enabled}
                              onChange={(checked) =>
                                setPreferences((prev) => ({
                                  ...prev,
                                  disabled_verbs: checked
                                    ? prev.disabled_verbs.filter((item) => item !== verbType.verb)
                                    : [...prev.disabled_verbs, verbType.verb],
                                }))
                              }
                            />
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </SectionCard>

            <SectionCard
              id="access"
              title="Доступ"
              description="Пароль, текущее устройство, остальные активные сессии и действия по безопасности аккаунта."
            >
              <div className="space-y-4">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr),minmax(280px,0.8fr)]">
                  <div className="app-surface-muted rounded-2xl p-4">
                    <div className="flex items-start gap-3">
                      <span className="app-badge app-badge-accent flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                        <UserRound size={18} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[var(--foreground)]">Текущий аккаунт</p>
                        <p className="app-text-muted mt-1 text-sm">{user.email}</p>
                        <p className="app-text-muted mt-1 text-xs">
                          {fullName}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="app-surface-muted rounded-2xl p-4">
                    <div className="flex items-start gap-3">
                      <span
                        className={`app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                          isSupported && isSubscribed ? "app-badge-accent" : ""
                        }`}
                      >
                        <Smartphone size={18} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[var(--foreground)]">Push-статус</p>
                        <p className="app-text-muted mt-1 text-sm">
                          {isSupported ? (isSubscribed ? "Подписка активна" : "Подписка не активна") : "Не поддерживается"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="app-surface-muted rounded-2xl p-4">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                        <QrCode size={18} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[var(--foreground)]">Вход по QR</p>
                        <p className="app-text-muted mt-1 text-sm">
                          Одноразовая ссылка для авторизации нового устройства.
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleCreateQrLogin()}
                      disabled={qrLoginLoading}
                      className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                    >
                      <QrCode size={16} />
                      {qrLoginLoading ? "Создаем..." : qrLogin ? "Обновить QR" : "Создать QR"}
                    </button>
                  </div>

                  {qrLogin ? (
                    <div className="mt-4 grid gap-4 md:grid-cols-[auto,minmax(0,1fr)]">
                      <div className="w-fit rounded-2xl bg-white p-3">
                        <Image
                          src={qrLogin.qrDataUrl}
                          alt="QR для входа"
                          width={176}
                          height={176}
                          unoptimized
                        />
                      </div>
                      <div className="min-w-0">
                        <p className="app-text-muted text-sm">
                          Действует до {formatSessionDateTime(qrLogin.expiresAt)}.
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => void navigator.clipboard?.writeText(qrLogin.loginUrl)}
                            className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
                          >
                            <Copy size={16} />
                            Скопировать ссылку
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="app-surface-muted rounded-2xl p-4">
                  <div className="mb-4 flex items-start gap-3">
                    <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                      <KeyRound size={18} />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--foreground)]">Смена пароля</p>
                      <p className="app-text-muted mt-1 text-sm">
                        Обновляет пароль для входа в аккаунт{user.is_ldap_managed ? " и LDAP-профиль" : ""}.
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <label className="block">
                      <span className="app-text-muted mb-2 block text-sm">Текущий пароль</span>
                      <div className="relative">
                        <input
                          type={showPasswordFields.current ? "text" : "password"}
                          autoComplete="current-password"
                          value={passwordForm.current_password}
                          onChange={(event) =>
                            setPasswordForm((prev) => ({
                              ...prev,
                              current_password: event.target.value,
                            }))
                          }
                          className="app-input w-full rounded-lg px-4 py-3 pr-12 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setShowPasswordFields((prev) => ({
                              ...prev,
                              current: !prev.current,
                            }))
                          }
                          className="app-icon-button absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
                          aria-label={showPasswordFields.current ? "Скрыть пароль" : "Показать пароль"}
                        >
                          {showPasswordFields.current ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </label>
                    <label className="block">
                      <span className="app-text-muted mb-2 block text-sm">Новый пароль</span>
                      <div className="relative">
                        <input
                          type={showPasswordFields.next ? "text" : "password"}
                          autoComplete="new-password"
                          value={passwordForm.new_password}
                          onChange={(event) =>
                            setPasswordForm((prev) => ({
                              ...prev,
                              new_password: event.target.value,
                            }))
                          }
                          className="app-input w-full rounded-lg px-4 py-3 pr-12 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setShowPasswordFields((prev) => ({
                              ...prev,
                              next: !prev.next,
                            }))
                          }
                          className="app-icon-button absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
                          aria-label={showPasswordFields.next ? "Скрыть пароль" : "Показать пароль"}
                        >
                          {showPasswordFields.next ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </label>
                    <label className="block">
                      <span className="app-text-muted mb-2 block text-sm">Подтверждение</span>
                      <div className="relative">
                        <input
                          type={showPasswordFields.confirm ? "text" : "password"}
                          autoComplete="new-password"
                          value={passwordForm.new_password_confirm}
                          onChange={(event) =>
                            setPasswordForm((prev) => ({
                              ...prev,
                              new_password_confirm: event.target.value,
                            }))
                          }
                          className="app-input w-full rounded-lg px-4 py-3 pr-12 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setShowPasswordFields((prev) => ({
                              ...prev,
                              confirm: !prev.confirm,
                            }))
                          }
                          className="app-icon-button absolute right-3 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
                          aria-label={showPasswordFields.confirm ? "Скрыть пароль" : "Показать пароль"}
                        >
                          {showPasswordFields.confirm ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                    </label>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <p className="app-text-muted text-sm">
                      После смены пароля текущая сессия сохранится, остальные устройства можно завершить ниже.
                    </p>
                    <button
                      type="button"
                      onClick={() => void handleChangePassword()}
                      disabled={
                        changingPassword ||
                        !passwordForm.current_password ||
                        !passwordForm.new_password ||
                        !passwordForm.new_password_confirm
                      }
                      className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                    >
                      <KeyRound size={16} />
                      {changingPassword ? "Сохраняем..." : "Сменить пароль"}
                    </button>
                  </div>
                </div>

                {sessionsLoading ? (
                  <div className="app-surface-muted rounded-2xl p-5">
                    <p className="app-text-muted text-sm">Загрузка активных сессий...</p>
                  </div>
                ) : sessionsUnavailable ? (
                  <div className="app-surface-muted rounded-2xl p-5">
                    <p className="text-sm font-semibold text-[var(--foreground)]">Управление сессиями недоступно</p>
                    <p className="app-text-muted mt-2 text-sm">
                      Запущенный backend-процесс еще не знает про новые auth endpoints.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="app-surface-muted rounded-2xl p-4">
                      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-[var(--foreground)]">Это устройство</p>
                          <p className="app-text-muted mt-1 text-sm">
                            Текущая сессия, которая держит вас в приложении сейчас.
                          </p>
                        </div>
                        {currentSession ? (
                          <span className="app-badge app-badge-accent px-2.5 py-1 text-xs font-medium">
                            Активна
                          </span>
                        ) : null}
                      </div>

                      {currentSession ? (
                        <div className="app-surface rounded-2xl p-4">
                          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                            <div className="flex min-w-0 items-start gap-3">
                              <span className="app-badge app-badge-accent flex h-11 w-11 shrink-0 items-center justify-center rounded-xl">
                                {(() => {
                                  const Icon = getSessionDeviceIcon(currentSession.device_name);
                                  return <Icon size={20} />;
                                })()}
                              </span>
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-[var(--foreground)]">
                                  {getSessionDeviceName(currentSession)}
                                </p>
                                <p className="app-text-muted mt-1 text-sm">
                                  IP: {currentSession.ip_address || "не определен"}
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  <span className="app-badge px-2.5 py-1 text-xs font-medium">
                                    Последняя активность: {formatSessionDateTime(currentSession.last_seen_at)}
                                  </span>
                                  <span className="app-badge px-2.5 py-1 text-xs font-medium">
                                    Создана: {formatSessionDateTime(currentSession.created_at)}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={() => void handleSessionLogout(currentSession)}
                              disabled={sessionActionKey === `delete:${currentSession.session_id}`}
                              className="app-action-danger inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                            >
                              <LogOut size={16} />
                              {sessionActionKey === `delete:${currentSession.session_id}` ? "Выходим..." : "Завершить"}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="app-surface rounded-2xl p-4">
                          <p className="app-text-muted text-sm">
                            Сервер не вернул текущую сессию, но локальный выход все еще доступен.
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="app-surface-muted rounded-2xl p-4">
                      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-[var(--foreground)]">Другие устройства</p>
                          <p className="app-text-muted mt-1 text-sm">
                            Сессии, которые сейчас активны на других устройствах и в других браузерах.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => void handleLogoutOthers()}
                          disabled={otherSessions.length === 0 || sessionActionKey === "logout-others"}
                          className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                        >
                          <LogOut size={16} />
                          {sessionActionKey === "logout-others" ? "Завершаем..." : "Завершить все"}
                        </button>
                      </div>

                      {otherSessions.length === 0 ? (
                        <div className="app-surface rounded-2xl p-4">
                          <p className="app-text-muted text-sm">
                            Кроме текущего устройства активных сессий нет.
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {otherSessions.map((session) => {
                            const Icon = getSessionDeviceIcon(session.device_name);
                            const busy = sessionActionKey === `delete:${session.session_id}`;

                            return (
                              <div
                                key={session.session_id}
                                className="app-surface rounded-2xl p-4"
                              >
                                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                  <div className="flex min-w-0 items-start gap-3">
                                    <span className="app-badge flex h-11 w-11 shrink-0 items-center justify-center rounded-xl">
                                      <Icon size={20} />
                                    </span>
                                    <div className="min-w-0">
                                      <p className="text-sm font-semibold text-[var(--foreground)]">
                                        {getSessionDeviceName(session)}
                                      </p>
                                      <p className="app-text-muted mt-1 text-sm">
                                        IP: {session.ip_address || "не определен"}
                                      </p>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        <span className="app-badge px-2.5 py-1 text-xs font-medium">
                                          Последняя активность: {formatSessionDateTime(session.last_seen_at)}
                                        </span>
                                        <span className="app-badge px-2.5 py-1 text-xs font-medium">
                                          Создана: {formatSessionDateTime(session.created_at)}
                                        </span>
                                      </div>
                                    </div>
                                  </div>

                                  <button
                                    type="button"
                                    onClick={() => void handleSessionLogout(session)}
                                    disabled={busy}
                                    className="app-action-danger inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
                                  >
                                    <LogOut size={16} />
                                    {busy ? "Завершаем..." : "Завершить"}
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => {
                    if (currentSession) {
                      void handleSessionLogout(currentSession);
                      return;
                    }
                    logout();
                  }}
                  className="app-feedback-danger inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
                >
                  <LogOut size={16} />
                  Выйти из аккаунта
                </button>
              </div>
            </SectionCard>
        </div>
        </div>
      </AppShell>

      {avatarCropperImage ? (
        <AvatarCropper
          initialImage={avatarCropperImage}
          onCropComplete={handleAvatarCropComplete}
          onCancel={handleAvatarCropCancel}
        />
      ) : null}
    </>
  );
}
