"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { useTheme } from "@/contexts/ThemeContext";
import { useUser } from "@/contexts/UserContext";
import { useWebPush } from "@/hooks/useWebPush";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import type { ThemePreference } from "@/lib/theme";
import type { AuthSession } from "@/types/api";

export type NotificationPreferences = {
  web_enabled: boolean;
  email_enabled: boolean;
  email_frequency: "instant" | "daily" | "weekly" | "never";
  push_enabled: boolean;
  dnd_enabled: boolean;
  dnd_start_time: string | null;
  dnd_end_time: string | null;
  disabled_verbs: string[];
};

export type VerbType = {
  verb: string;
  name: string;
  total: number;
  unread: number;
};

export const settingsThemeCards: Array<{
  value: ThemePreference;
  title: string;
  description: string;
  iconName: "Sun" | "Moon" | "Monitor";
}> = [
  {
    value: "light",
    title: "Светлая",
    description: "Светлые поверхности и нейтральный фон.",
    iconName: "Sun",
  },
  {
    value: "dark",
    title: "Темная",
    description: "Темные поверхности без browser force-dark.",
    iconName: "Moon",
  },
  {
    value: "auto",
    title: "Авто",
    description: "Следует системной теме устройства.",
    iconName: "Monitor",
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

const preferencesSignature = (value: NotificationPreferences | null) => {
  if (!value) return "";
  return JSON.stringify({
    ...value,
    disabled_verbs: [...value.disabled_verbs].sort(),
    dnd_start_time: value.dnd_start_time || null,
    dnd_end_time: value.dnd_end_time || null,
  });
};

const isApiNotFoundError = (error: unknown) =>
  error instanceof Error && error.message.includes("API Error: 404");

export function settingsInitials(firstName?: string, lastName?: string) {
  return `${lastName?.[0] || ""}${firstName?.[0] || ""}`.trim() || "П";
}

export function formatSessionDateTime(value?: string | null) {
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

export function getSessionDeviceName(session: AuthSession) {
  return session.device_name?.trim() || "Неизвестное устройство";
}

export function getSessionDeviceKind(deviceName?: string | null) {
  const normalized = (deviceName || "").toLowerCase();
  return /iphone|android|mobile|ipad|phone/.test(normalized)
    ? "mobile"
    : "desktop";
}

export function useSettingsPage() {
  const { user, loading, refreshUser, logout } = useUser();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const avatarInputRef = useRef<HTMLInputElement | null>(null);
  const {
    isSupported,
    isSubscribed,
    permission,
    isLoading: pushLoading,
    subscribe,
    unsubscribe,
  } = useWebPush();

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

  const [preferences, setPreferences] =
    useState<NotificationPreferences>(defaultPreferences);
  const [savedPreferences, setSavedPreferences] =
    useState<NotificationPreferences | null>(null);
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
  }, [user]);

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
    if (!savedPreferences || pushLoading || !isSupported) return;

    setPreferences((current) =>
      current.push_enabled === isSubscribed
        ? current
        : { ...current, push_enabled: isSubscribed },
    );
    setSavedPreferences((current) =>
      current && current.push_enabled === isSubscribed
        ? current
        : current
          ? { ...current, push_enabled: isSubscribed }
          : current,
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
          console.warn(
            "Auth sessions endpoint is unavailable in the running backend process",
          );
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
    return (
      `${user.last_name || ""} ${user.first_name || ""} ${user.patronymic || ""}`.trim() ||
      "Пользователь"
    );
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

  const notificationDirty = useMemo(
    () => preferencesSignature(preferences) !== preferencesSignature(savedPreferences),
    [preferences, savedPreferences],
  );

  const unreadVerbCount = useMemo(
    () => verbTypes.reduce((sum, item) => sum + item.unread, 0),
    [verbTypes],
  );

  const activeVerbCount = useMemo(
    () =>
      verbTypes.filter((item) => !preferences.disabled_verbs.includes(item.verb))
        .length,
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
    setPreferences((current) => ({ ...current, push_enabled: enabled }));

    if (enabled && !isSubscribed) {
      await subscribe();
    } else if (!enabled && isSubscribed) {
      await unsubscribe();
    }
  };

  const handleDndToggle = (enabled: boolean) => {
    if (enabled) {
      setPreferences((current) => ({
        ...current,
        dnd_enabled: true,
        dnd_start_time: current.dnd_start_time || "00:00",
        dnd_end_time: current.dnd_end_time || "23:59",
      }));
      return;
    }

    setPreferences((current) => ({ ...current, dnd_enabled: false }));
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

      setSessions((current) =>
        current.filter((item) => item.session_id !== session.session_id),
      );
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
      setSessions((current) => current.filter((session) => session.is_current));
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
    if (
      !passwordForm.current_password ||
      !passwordForm.new_password ||
      !passwordForm.new_password_confirm
    ) {
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

  return {
    activeVerbCount,
    avatarInputRef,
    changingPassword,
    contactsDirty,
    contactsForm,
    currentSession,
    fullName,
    isSupported,
    isSubscribed,
    loading,
    notificationDirty,
    otherSessions,
    permission,
    preferences,
    preferencesLoading,
    profileDirty,
    profileForm,
    pushLoading,
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
    avatarPreview,
    handleAvatarChange,
    handleChangePassword,
    handleDndToggle,
    handleLogoutOthers,
    handlePushToggle,
    handleSessionLogout,
    logout,
    passwordForm,
    saveContacts,
    savePreferences,
    saveProfile,
    setContactsForm,
    setPasswordForm,
    setPreferences,
    setProfileForm,
    setShowPasswordFields,
    setTheme,
    settingsThemeCards,
    settingsInitials,
  };
}
