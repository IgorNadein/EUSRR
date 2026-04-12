"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  Check,
  Clock3,
  Eye,
  EyeOff,
  KeyRound,
  LogOut,
  Mail,
  Monitor,
  Moon,
  RefreshCw,
  Save,
  Smartphone,
  Sun,
  UserRound,
} from "lucide-react";
import { toast } from "sonner";

import { AppShell, PageHeader } from "@/components/AppShell";
import { useTheme } from "@/contexts/ThemeContext";
import { useUser } from "@/contexts/UserContext";
import { useWebPush } from "@/hooks/useWebPush";
import { apiClient } from "@/lib/api";
import type { ThemePreference } from "@/lib/theme";
import { resolveMediaUrl } from "@/lib/url";
import type { AuthSession, DirectoryLoginResult } from "@/types/api";
import { getVerbName } from "@/lib/verbTranslations";

type NotificationPreferences = {
  web_enabled: boolean;
  email_enabled: boolean;
  email_frequency: "instant" | "daily" | "weekly" | "never";
  push_enabled: boolean;
  dnd_enabled: boolean;
  dnd_start_time: string | null;
  dnd_end_time: string | null;
  disabled_verbs: string[];
};

type VerbType = {
  verb: string;
  name: string;
  total: number;
  unread: number;
};

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
    description: "Темные поверхности без browser force-dark.",
    icon: Moon,
  },
  {
    value: "auto",
    title: "Авто",
    description: "Следует системной теме устройства.",
    icon: Monitor,
  },
];

const defaultPreferences: NotificationPreferences = {
  web_enabled: true,
  email_enabled: false,
  email_frequency: "instant",
  push_enabled: false,
  dnd_enabled: false,
  dnd_start_time: null,
  dnd_end_time: null,
  disabled_verbs: [],
};

function preferencesSignature(value: NotificationPreferences | null) {
  if (!value) return "";
  return JSON.stringify({
    ...value,
    disabled_verbs: [...value.disabled_verbs].sort(),
    dnd_start_time: value.dnd_start_time || null,
    dnd_end_time: value.dnd_end_time || null,
  });
}

function initials(firstName?: string, lastName?: string) {
  return `${lastName?.[0] || ""}${firstName?.[0] || ""}`.trim() || "П";
}

function formatSessionDateTime(value?: string | null) {
  if (!value) return "—";

  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function getSessionDeviceIcon(deviceName?: string | null) {
  const normalized = (deviceName || "").toLowerCase();
  return /iphone|android|mobile|ipad|phone/.test(normalized) ? Smartphone : Monitor;
}

function getSessionDeviceName(session: AuthSession) {
  return session.device_name?.trim() || "Неизвестное устройство";
}

function isApiNotFoundError(error: unknown) {
  return error instanceof Error && error.message.includes("API Error: 404");
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
    <label className="relative inline-flex cursor-pointer items-center">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
        className="peer sr-only"
      />
      <div className="h-6 w-11 rounded-full bg-[var(--surface-tertiary)] transition after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow-sm after:transition-all after:content-[''] peer-checked:bg-[var(--accent-primary)] peer-checked:after:translate-x-full peer-disabled:cursor-not-allowed peer-disabled:opacity-50" />
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
          <h2 className="text-base font-semibold text-[var(--foreground)]">{title}</h2>
          <p className="app-text-muted mt-1 text-sm">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const { user, loading, refreshUser, logout } = useUser();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const avatarInputRef = useRef<HTMLInputElement | null>(null);

  const [profileForm, setProfileForm] = useState({
    first_name: "",
    last_name: "",
    patronymic: "",
    birth_date: "",
  });
  const [contactsForm, setContactsForm] = useState({
    email: "",
    phone_number: "",
    telegram: "",
    whatsapp: "",
    wechat: "",
  });
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingContacts, setSavingContacts] = useState(false);

  const [preferences, setPreferences] = useState<NotificationPreferences>(defaultPreferences);
  const [savedPreferences, setSavedPreferences] = useState<NotificationPreferences | null>(null);
  const [verbTypes, setVerbTypes] = useState<VerbType[]>([]);
  const [preferencesLoading, setPreferencesLoading] = useState(true);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsUnavailable, setSessionsUnavailable] = useState(false);
  const [sessionActionKey, setSessionActionKey] = useState<string | null>(null);
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    new_password_confirm: "",
  });
  const [changingPassword, setChangingPassword] = useState(false);
  const [showPasswordFields, setShowPasswordFields] = useState({
    current: false,
    next: false,
    confirm: false,
  });
  const [directoryLogin, setDirectoryLogin] = useState<string | null>(null);
  const [directoryLoginLoading, setDirectoryLoginLoading] = useState(false);
  const [directoryLoginRefreshing, setDirectoryLoginRefreshing] = useState(false);
  const [directoryLoginError, setDirectoryLoginError] = useState<string | null>(null);

  const {
    isSupported,
    isSubscribed,
    permission,
    isLoading: pushLoading,
    subscribe,
    unsubscribe,
  } = useWebPush();

  useEffect(() => {
    if (!user) return;
    setProfileForm({
      first_name: user.first_name || "",
      last_name: user.last_name || "",
      patronymic: user.patronymic || "",
      birth_date: user.birth_date || "",
    });
    setContactsForm({
      email: user.email || "",
      phone_number: user.phone_number || "",
      telegram: user.telegram || "",
      whatsapp: user.whatsapp || "",
      wechat: user.wechat || "",
    });
    setDirectoryLogin(user.username?.trim() || null);
    setDirectoryLoginError(null);
  }, [user]);

  useEffect(() => {
    let mounted = true;

    async function loadDirectoryLogin() {
      if (!user?.is_ldap_managed || user.username?.trim()) {
        return;
      }

      try {
        setDirectoryLoginLoading(true);
        setDirectoryLoginError(null);
        const response = (await apiClient.getDirectoryLogin()) as DirectoryLoginResult;
        if (!mounted) return;
        setDirectoryLogin(response.username?.trim() || null);
      } catch (error) {
        console.error(error);
        if (!mounted) return;
        setDirectoryLoginError(
          error instanceof Error ? error.message : "Не удалось получить логин из каталога",
        );
      } finally {
        if (mounted) {
          setDirectoryLoginLoading(false);
        }
      }
    }

    void loadDirectoryLogin();

    return () => {
      mounted = false;
    };
  }, [user?.id, user?.is_ldap_managed, user?.username]);

  useEffect(() => {
    const section = new URLSearchParams(window.location.search).get("section");
    if (!section) return;
    const element = document.getElementById(section);
    if (element) {
      requestAnimationFrame(() => {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function loadNotificationSettings() {
      try {
        setPreferencesLoading(true);
        const [prefsResponse, verbsResponse] = await Promise.all([
          apiClient.getNotificationPreferences(),
          apiClient.getVerbTypes(),
        ]);

        if (!mounted) return;

        const normalized: NotificationPreferences = {
          ...defaultPreferences,
          ...prefsResponse,
          email_frequency:
            prefsResponse.email_frequency === "disabled"
              ? "never"
              : prefsResponse.email_frequency,
        };

        setPreferences(normalized);
        setSavedPreferences(normalized);
        setVerbTypes(verbsResponse.verb_types || []);
      } catch (error) {
        console.error("Failed to load notification settings", error);
        toast.error("Не удалось загрузить настройки уведомлений");
      } finally {
        if (mounted) {
          setPreferencesLoading(false);
        }
      }
    }

    void loadNotificationSettings();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!savedPreferences || pushLoading) return;
    if (!isSupported) return;

    setPreferences((prev) =>
      prev.push_enabled === isSubscribed ? prev : { ...prev, push_enabled: isSubscribed },
    );
    setSavedPreferences((prev) =>
      prev && prev.push_enabled === isSubscribed ? prev : prev ? { ...prev, push_enabled: isSubscribed } : prev,
    );
  }, [isSubscribed, isSupported, pushLoading, savedPreferences]);

  useEffect(() => {
    let mounted = true;

    async function loadSessions() {
      try {
        setSessionsLoading(true);
        setSessionsUnavailable(false);
        const response = await apiClient.getAuthSessions();
        if (!mounted) return;
        setSessions(response);
      } catch (error) {
        if (isApiNotFoundError(error)) {
          console.warn("Auth sessions endpoint is unavailable in the running backend process");
          if (mounted) {
            setSessionsUnavailable(true);
            setSessions([]);
          }
          return;
        }

        console.error("Failed to load sessions", error);
        if (mounted) {
          toast.error("Не удалось загрузить активные сессии");
        }
      } finally {
        if (mounted) {
          setSessionsLoading(false);
        }
      }
    }

    void loadSessions();

    return () => {
      mounted = false;
    };
  }, []);

  const fullName = useMemo(() => {
    if (!user) return "Пользователь";
    return `${user.last_name || ""} ${user.first_name || ""} ${user.patronymic || ""}`.trim() || "Пользователь";
  }, [user]);

  const profileDirty = useMemo(() => {
    if (!user) return false;
    return (
      profileForm.first_name !== (user.first_name || "") ||
      profileForm.last_name !== (user.last_name || "") ||
      profileForm.patronymic !== (user.patronymic || "") ||
      profileForm.birth_date !== (user.birth_date || "") ||
      Boolean(avatarFile)
    );
  }, [avatarFile, profileForm, user]);

  const contactsDirty = useMemo(() => {
    if (!user) return false;
    return (
      contactsForm.email !== (user.email || "") ||
      contactsForm.phone_number !== (user.phone_number || "") ||
      contactsForm.telegram !== (user.telegram || "") ||
      contactsForm.whatsapp !== (user.whatsapp || "") ||
      contactsForm.wechat !== (user.wechat || "")
    );
  }, [contactsForm, user]);

  const notificationDirty = useMemo(() => {
    return preferencesSignature(preferences) !== preferencesSignature(savedPreferences);
  }, [preferences, savedPreferences]);

  const unreadVerbCount = useMemo(
    () => verbTypes.reduce((sum, item) => sum + item.unread, 0),
    [verbTypes],
  );

  const activeVerbCount = useMemo(
    () => verbTypes.filter((item) => !preferences.disabled_verbs.includes(item.verb)).length,
    [preferences.disabled_verbs, verbTypes],
  );

  const summaryAvatar = avatarPreview || (user?.avatar ? resolveMediaUrl(user.avatar) : null);
  const currentSession = useMemo(
    () => sessions.find((session) => session.is_current) || null,
    [sessions],
  );
  const otherSessions = useMemo(
    () => sessions.filter((session) => !session.is_current),
    [sessions],
  );

  const handleAvatarChange = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Можно загрузить только изображение");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Максимальный размер файла 5 МБ");
      return;
    }

    setAvatarFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      setAvatarPreview(typeof reader.result === "string" ? reader.result : null);
    };
    reader.readAsDataURL(file);
  };

  const handlePushToggle = async (enabled: boolean) => {
    setPreferences((prev) => ({ ...prev, push_enabled: enabled }));

    if (enabled && !isSubscribed) {
      await subscribe();
    } else if (!enabled && isSubscribed) {
      await unsubscribe();
    }
  };

  const handleDndToggle = (enabled: boolean) => {
    if (enabled) {
      setPreferences((prev) => ({
        ...prev,
        dnd_enabled: true,
        dnd_start_time: prev.dnd_start_time || "00:00",
        dnd_end_time: prev.dnd_end_time || "23:59",
      }));
      return;
    }

    setPreferences((prev) => ({ ...prev, dnd_enabled: false }));
  };

  const saveProfile = async () => {
    if (!profileDirty) return;
    try {
      setSavingProfile(true);
      await apiClient.updateCurrentUserProfile({
        first_name: profileForm.first_name.trim(),
        last_name: profileForm.last_name.trim(),
        patronymic: profileForm.patronymic.trim(),
        birth_date: profileForm.birth_date.trim() || null,
        avatar: avatarFile || undefined,
      });
      await refreshUser();
      setAvatarFile(null);
      setAvatarPreview(null);
      toast.success("Профиль обновлен");
    } catch (error) {
      console.error(error);
      toast.error("Не удалось сохранить профиль");
    } finally {
      setSavingProfile(false);
    }
  };

  const saveContacts = async () => {
    if (!contactsDirty) return;
    try {
      setSavingContacts(true);
      await apiClient.updateCurrentUserProfile({
        email: contactsForm.email.trim(),
        phone_number: contactsForm.phone_number.trim(),
        telegram: contactsForm.telegram.trim(),
        whatsapp: contactsForm.whatsapp.trim(),
        wechat: contactsForm.wechat.trim(),
      });
      await refreshUser();
      toast.success("Контакты обновлены");
    } catch (error) {
      console.error(error);
      toast.error("Не удалось сохранить контакты");
    } finally {
      setSavingContacts(false);
    }
  };

  const savePreferences = async () => {
    if (!notificationDirty) return;
    try {
      setSavingPreferences(true);

      if (preferences.push_enabled !== isSubscribed) {
        if (preferences.push_enabled) {
          const success = await subscribe();
          if (!success) {
            throw new Error("Push subscribe failed");
          }
        } else {
          const success = await unsubscribe();
          if (!success && isSubscribed) {
            throw new Error("Push unsubscribe failed");
          }
        }
      }

      await apiClient.updateNotificationPreferences({
        ...preferences,
        dnd_start_time: preferences.dnd_start_time || undefined,
        dnd_end_time: preferences.dnd_end_time || undefined,
      });

      setSavedPreferences(preferences);
      toast.success("Настройки уведомлений сохранены");
    } catch (error) {
      console.error(error);
      toast.error("Не удалось сохранить настройки уведомлений");
    } finally {
      setSavingPreferences(false);
    }
  };

  const handleSessionLogout = async (session: AuthSession) => {
    const isCurrent = session.is_current;
    const busyKey = `delete:${session.session_id}`;

    try {
      setSessionActionKey(busyKey);
      await apiClient.deleteAuthSession(session.session_id);

      if (isCurrent) {
        toast.success("Текущая сессия завершена");
        logout();
        return;
      }

      setSessions((prev) => prev.filter((item) => item.session_id !== session.session_id));
      toast.success("Сессия завершена");
    } catch (error) {
      console.error(error);
      toast.error("Не удалось завершить сессию");
    } finally {
      setSessionActionKey(null);
    }
  };

  const handleLogoutOthers = async () => {
    try {
      setSessionActionKey("logout-others");
      const response = await apiClient.logoutOtherSessions();
      setSessions((prev) => prev.filter((session) => session.is_current));
      toast.success(
        response.revoked > 0
          ? `Завершено сессий: ${response.revoked}`
          : "Других активных сессий нет",
      );
    } catch (error) {
      console.error(error);
      toast.error("Не удалось завершить остальные сессии");
    } finally {
      setSessionActionKey(null);
    }
  };

  const handleChangePassword = async () => {
    if (!passwordForm.current_password || !passwordForm.new_password || !passwordForm.new_password_confirm) {
      toast.error("Заполните все поля пароля");
      return;
    }
    if (passwordForm.new_password !== passwordForm.new_password_confirm) {
      toast.error("Подтверждение пароля не совпадает");
      return;
    }

    try {
      setChangingPassword(true);
      await apiClient.changePassword(passwordForm);
      setPasswordForm({
        current_password: "",
        new_password: "",
        new_password_confirm: "",
      });
      toast.success("Пароль обновлен");
    } catch (error) {
      console.error(error);
      toast.error(
        error instanceof Error && error.message.includes("current_password")
          ? "Текущий пароль указан неверно"
          : "Не удалось изменить пароль",
      );
    } finally {
      setChangingPassword(false);
    }
  };

  const handleRefreshDirectoryLogin = async () => {
    try {
      setDirectoryLoginRefreshing(true);
      setDirectoryLoginError(null);
      const response =
        (await apiClient.refreshDirectoryLogin()) as DirectoryLoginResult;
      setDirectoryLogin(response.username?.trim() || null);
      await refreshUser();
      toast.success(
        response.username
          ? "Логин в каталоге обновлен"
          : "Логин в каталоге не найден",
      );
    } catch (error) {
      console.error(error);
      setDirectoryLoginError(
        error instanceof Error
          ? error.message
          : "Не удалось обновить логин из каталога",
      );
      toast.error("Не удалось обновить логин из каталога");
    } finally {
      setDirectoryLoginRefreshing(false);
    }
  };

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
                        {initials(user.first_name, user.last_name)}
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
                  <div className="app-surface-muted rounded-2xl p-4 md:col-span-2">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="app-text-muted text-xs uppercase tracking-[0.16em]">
                          Логин в каталоге
                        </p>
                        <p className="mt-2 text-sm font-semibold text-[var(--foreground)]">
                          {!user.is_ldap_managed
                            ? "Не используется"
                            : directoryLoginLoading
                              ? "Загружаем..."
                              : directoryLogin || "Не найден"}
                        </p>
                        {directoryLoginError ? (
                          <p className="mt-1 text-sm text-[var(--danger-foreground)]">
                            {directoryLoginError}
                          </p>
                        ) : user.is_ldap_managed ? (
                          <p className="app-text-muted mt-1 text-sm">
                            Берется из кэша БД и при необходимости обновляется из LDAP.
                          </p>
                        ) : (
                          <p className="app-text-muted mt-1 text-sm">
                            Для локального аккаунта логин каталога не используется.
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleRefreshDirectoryLogin()}
                        disabled={!user.is_ldap_managed || directoryLoginRefreshing}
                        className="app-action-secondary inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50"
                      >
                        <RefreshCw
                          size={16}
                          className={directoryLoginRefreshing ? "animate-spin" : ""}
                        />
                        Обновить
                      </button>
                    </div>
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
                {themeCards.map(({ value, title, description, icon: Icon }) => {
                  const active = theme === value;

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
                            className={`flex cursor-pointer items-center justify-between rounded-xl px-4 py-3 transition ${
                              enabled ? "app-surface" : "app-surface-muted opacity-80"
                            }`}
                          >
                            <div className="min-w-0 pr-4">
                              <p className="truncate text-sm font-medium text-[var(--foreground)]">
                                {getVerbName(verbType.verb) || verbType.name}
                              </p>
                              <p className="app-text-muted mt-1 text-xs">
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
  );
}
