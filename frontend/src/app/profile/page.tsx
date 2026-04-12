"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  Mail,
  MessageCircle,
  Phone,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import {
  getEmployeeActionTone,
  getWorkDuration,
} from "@/lib/users/userDetailUtils";
import type { DirectoryLoginResult } from "@/types/api";

function formatDate(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatDateTime(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatBirthdayWithYear(value?: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function getActionTimestamp(action: {
  date?: string;
  created_at?: string;
}): number {
  return new Date(action.date || action.created_at || 0).getTime();
}

function initials(firstName?: string, lastName?: string) {
  return `${lastName?.[0] || ""}${firstName?.[0] || ""}`.trim() || "П";
}

function normalizeTelegram(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://t.me/${trimmed.replace(/^@/, "")}`;
}

function normalizeWhatsApp(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  const digits = trimmed.replace(/[^\d]/g, "");
  return digits ? `https://wa.me/${digits}` : "";
}

function truncateText(value?: string, maxLength = 120) {
  if (!value) return "";
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength).trimEnd()}…`;
}

function SectionTitle({
  title,
  icon,
  action,
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="app-card-caption">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export default function ProfilePage() {
  const { user, loading } = useUser();
  const [showAllActions, setShowAllActions] = useState(false);
  const [directoryLogin, setDirectoryLogin] = useState<string | null>(null);
  const [directoryLoginLoading, setDirectoryLoginLoading] = useState(false);
  const [directoryLoginRefreshing, setDirectoryLoginRefreshing] =
    useState(false);
  const [directoryLoginError, setDirectoryLoginError] = useState<string | null>(
    null,
  );
  const [availableSkills, setAvailableSkills] = useState<
    Array<{ id: number; name: string; description?: string }>
  >([]);
  const [profileSkills, setProfileSkills] = useState<
    Array<{ id: number; name: string; description?: string }>
  >([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsSaving, setSkillsSaving] = useState(false);
  const [skillName, setSkillName] = useState("");
  const [skillsError, setSkillsError] = useState<string | null>(null);

  const fullName = useMemo(() => {
    if (!user) return "Пользователь";
    return `${user.last_name || ""} ${user.first_name || ""} ${
      user.patronymic || ""
    }`.trim() || "Пользователь";
  }, [user]);

  const currentAction = useMemo(() => {
    if (!user?.actions?.length) return null;
    const now = Date.now();
    return [...user.actions]
      .filter((action) => getActionTimestamp(action) <= now)
      .sort((left, right) => getActionTimestamp(right) - getActionTimestamp(left))[0] || null;
  }, [user?.actions]);

  const sortedActions = useMemo(() => {
    if (!user?.actions?.length) return [];
    return [...user.actions].sort(
      (left, right) => getActionTimestamp(right) - getActionTimestamp(left),
    );
  }, [user?.actions]);

  const currentActionId = useMemo(
    () => currentAction?.id ?? null,
    [currentAction?.id],
  );

  const visibleActions = useMemo(
    () => (showAllActions ? sortedActions : sortedActions.slice(0, 3)),
    [showAllActions, sortedActions],
  );

  useEffect(() => {
    setDirectoryLogin(user?.username?.trim() || null);
    setDirectoryLoginError(null);
  }, [user?.username]);

  useEffect(() => {
    setProfileSkills(user?.skills || []);
  }, [user?.skills]);

  useEffect(() => {
    let mounted = true;

    async function loadDirectoryLogin() {
      if (!user?.is_ldap_managed || user.username?.trim()) {
        return;
      }

      try {
        setDirectoryLoginLoading(true);
        setDirectoryLoginError(null);
        const response =
          (await apiClient.getDirectoryLogin()) as DirectoryLoginResult;
        if (!mounted) return;
        setDirectoryLogin(response.username?.trim() || null);
      } catch (error: any) {
        if (!mounted) return;
        setDirectoryLoginError(
          String(error?.message || "Не удалось получить логин из каталога"),
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
    let mounted = true;

    async function loadSkills() {
      try {
        setSkillsLoading(true);
        const response = (await apiClient.getSkills()) as Array<{
          id: number;
          name: string;
          description?: string;
        }>;
        if (!mounted) return;
        setAvailableSkills(response);
      } catch (error: any) {
        if (!mounted) return;
        setSkillsError(
          String(error?.message || "Не удалось загрузить список навыков"),
        );
      } finally {
        if (mounted) {
          setSkillsLoading(false);
        }
      }
    }

    void loadSkills();

    return () => {
      mounted = false;
    };
  }, []);

  const handleRefreshDirectoryLogin = async () => {
    try {
      setDirectoryLoginRefreshing(true);
      setDirectoryLoginError(null);
      const response =
        (await apiClient.refreshDirectoryLogin()) as DirectoryLoginResult;
      setDirectoryLogin(response.username?.trim() || null);
    } catch (error: any) {
      setDirectoryLoginError(
        String(error?.message || "Не удалось обновить логин из каталога"),
      );
    } finally {
      setDirectoryLoginRefreshing(false);
    }
  };

  const saveSkills = async (skillIds: number[]) => {
    try {
      setSkillsSaving(true);
      setSkillsError(null);
      const response = (await apiClient.updateCurrentUserProfile({
        skills_ids: skillIds,
      })) as {
        skills?: Array<{ id: number; name: string; description?: string }>;
      };
      setProfileSkills(response.skills || []);
    } catch (error: any) {
      setSkillsError(
        String(error?.message || "Не удалось обновить навыки"),
      );
    } finally {
      setSkillsSaving(false);
    }
  };

  const handleRemoveSkill = async (skillId: number) => {
    if (!user) return;
    const nextIds = profileSkills
      .map((skill) => skill.id)
      .filter((id) => id !== skillId);
    await saveSkills(nextIds);
  };

  const handleAddSkill = async (forcedSkill?: { id: number; name: string }) => {
    if (!user) return;
    const rawName = forcedSkill?.name || skillName;
    const trimmedName = rawName.trim();
    if (!trimmedName || skillsSaving) return;

    try {
      setSkillsSaving(true);
      setSkillsError(null);

      const existingSkill =
        forcedSkill ||
        availableSkills.find(
          (skill) => skill.name.trim().toLowerCase() === trimmedName.toLowerCase(),
        );

      let skillId = existingSkill?.id;

      if (!skillId) {
        const createdSkill = (await apiClient.createSkill({
          name: trimmedName,
        })) as { id: number; name: string; description?: string };
        skillId = createdSkill.id;
        setAvailableSkills((current) =>
          [...current, createdSkill].sort((left, right) =>
            left.name.localeCompare(right.name, "ru"),
          ),
        );
      }

      const nextIds = Array.from(
        new Set([...profileSkills.map((skill) => skill.id), skillId]),
      );

      const response = (await apiClient.updateCurrentUserProfile({
        skills_ids: nextIds,
      })) as {
        skills?: Array<{ id: number; name: string; description?: string }>;
      };
      setProfileSkills(response.skills || []);
      setSkillName("");
    } catch (error: any) {
      setSkillsError(
        String(error?.message || "Не удалось добавить навык"),
      );
    } finally {
      setSkillsSaving(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка профиля...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-4">
        <section className="app-surface rounded-[28px] p-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <p className="app-card-caption">Мой профиль</p>
            {currentAction ? (
              <span
                className={`app-status-pill ${getEmployeeActionTone(currentAction.action).badgeClass}`}
              >
                {currentAction.action_display || currentAction.action}
              </span>
            ) : null}
          </div>
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <div className="h-20 w-20 shrink-0 overflow-hidden rounded-full app-avatar-frame">
                {user.avatar ? (
                  <Image
                    src={resolveMediaUrl(user.avatar)}
                    alt={fullName}
                    width={80}
                    height={80}
                    className="h-full w-full object-cover"
                    unoptimized
                  />
                ) : (
                  <div className="app-avatar-fallback flex h-full w-full items-center justify-center text-2xl font-semibold">
                    {initials(user.first_name, user.last_name)}
                  </div>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <h1 className="text-[2rem] font-semibold leading-tight text-[var(--foreground)]">
                  {fullName}
                </h1>
                <p className="app-text-muted mt-1.5 text-sm">
                  {formatBirthdayWithYear(user.birth_date) || "Не указана"}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="app-text-muted text-sm">
                    {user.position?.name || "Должность не указана"}
                  </span>
                  {!!user.departments?.length && (
                    <span className="app-pill inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
                      {user.departments.length === 1
                        ? user.departments[0].name
                        : `${user.departments.length} отделов`}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="app-surface-muted rounded-2xl p-4">
              <div>
                <div className="flex items-start gap-3 px-4 py-4">
                  <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                    <Mail size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      Почта
                    </p>
                    {user.email ? (
                      <a
                        href={`mailto:${user.email.trim()}`}
                        className="app-text-muted mt-1 block truncate text-sm hover:text-[var(--accent-primary)]"
                      >
                        {user.email}
                      </a>
                    ) : (
                      <p className="app-text-muted mt-1 text-sm">Не указана</p>
                    )}
                  </div>
                </div>
                <div className="mx-4 border-t border-[var(--border-subtle)]" />
                <div className="flex items-start gap-3 px-4 py-4">
                  <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                    <Phone size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      Телефон
                    </p>
                    {user.phone_number ? (
                      <a
                        href={`tel:${user.phone_number.trim()}`}
                        className="app-text-muted mt-1 block truncate text-sm hover:text-[var(--accent-primary)]"
                      >
                        {user.phone_number}
                      </a>
                    ) : (
                      <p className="app-text-muted mt-1 text-sm">Не указан</p>
                    )}
                  </div>
                </div>
                {!!user.telegram && (
                  <>
                    <div className="mx-4 border-t border-[var(--border-subtle)]" />
                    <div className="flex items-start gap-3 px-4 py-4">
                      <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                        <MessageCircle size={18} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[var(--foreground)]">
                          Telegram
                        </p>
                        <a
                          href={normalizeTelegram(user.telegram)}
                          target="_blank"
                          rel="noreferrer"
                          className="app-text-muted mt-1 block truncate text-sm hover:text-[var(--accent-primary)]"
                        >
                          {user.telegram}
                        </a>
                      </div>
                    </div>
                  </>
                )}
                {!!user.whatsapp && (
                  <>
                    <div className="mx-4 border-t border-[var(--border-subtle)]" />
                    <div className="flex items-start gap-3 px-4 py-4">
                      <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                        <MessageCircle size={18} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[var(--foreground)]">
                          WhatsApp
                        </p>
                        <a
                          href={normalizeWhatsApp(user.whatsapp)}
                          target="_blank"
                          rel="noreferrer"
                          className="app-text-muted mt-1 block truncate text-sm hover:text-[var(--accent-primary)]"
                        >
                          {user.whatsapp}
                        </a>
                      </div>
                    </div>
                  </>
                )}
                {!!user.wechat && (
                  <>
                    <div className="mx-4 border-t border-[var(--border-subtle)]" />
                    <div className="flex items-start gap-3 px-4 py-4">
                      <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                        <MessageCircle size={18} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[var(--foreground)]">
                          WeChat
                        </p>
                        <p className="app-text-muted mt-1 truncate text-sm">
                          {user.wechat}
                        </p>
                      </div>
                    </div>
                  </>
                )}
                {(user.is_ldap_managed ||
                  directoryLoginLoading ||
                  directoryLoginError ||
                  directoryLogin) && (
                  <>
                    <div className="mx-4 border-t border-[var(--border-subtle)]" />
                    <div className="flex items-start gap-3 px-4 py-4">
                      <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                        <RefreshCw
                          size={18}
                          className={directoryLoginRefreshing ? "animate-spin" : ""}
                        />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[var(--foreground)]">
                              Логин в каталоге
                            </p>
                            <p className="app-text-muted mt-1 truncate text-sm">
                              {directoryLoginLoading
                                ? "Загружаем..."
                                : directoryLogin || "Не найден"}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => void handleRefreshDirectoryLogin()}
                            disabled={directoryLoginRefreshing}
                            className="app-action-secondary shrink-0 rounded-xl px-3 py-2 text-sm font-medium disabled:opacity-50"
                          >
                            Обновить
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="app-surface rounded-[24px] p-5">
          <SectionTitle title="Навыки" />
          <div className="app-surface-muted rounded-2xl p-3.5">
            <div className="flex flex-col gap-2.5 md:flex-row">
              <div className="min-w-0 flex-1">
                <input
                  list="profile-skills-list"
                  value={skillName}
                  onChange={(event) => setSkillName(event.target.value)}
                  placeholder="Добавить навык"
                  className="app-input w-full rounded-xl px-4 py-2.5 text-sm"
                  disabled={skillsSaving}
                />
                <datalist id="profile-skills-list">
                  {availableSkills.map((skill) => (
                    <option key={skill.id} value={skill.name} />
                  ))}
                </datalist>
              </div>
              <button
                type="button"
                onClick={() => void handleAddSkill()}
                disabled={!skillName.trim() || skillsSaving}
                className="app-action-primary inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-50"
              >
                <Plus size={16} />
                Добавить
              </button>
            </div>

            {skillsError ? (
              <p className="mt-3 text-sm text-red-400">{skillsError}</p>
            ) : null}

            <div className="mt-3">
              {profileSkills.length ? (
                <div className="flex flex-wrap gap-2">
                  {profileSkills.map((skill) => (
                    <button
                      key={skill.id}
                      type="button"
                      onClick={() => void handleRemoveSkill(skill.id)}
                      disabled={skillsSaving}
                      className="app-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] disabled:opacity-50"
                      title="Удалить навык"
                    >
                      <span>{skill.name}</span>
                      <X size={14} />
                    </button>
                  ))}
                </div>
              ) : (
                <p className="app-text-muted text-sm">Навыки пока не указаны</p>
              )}
            </div>

            {skillsLoading ? (
              <p className="app-text-muted mt-2.5 text-sm">Загружаем навыки...</p>
            ) : null}
          </div>
        </section>

        <section className="app-surface rounded-[24px] p-5">
          <SectionTitle title="Информация" />
          <div className="app-surface-muted overflow-hidden rounded-2xl">
            <div className="grid md:grid-cols-2">
              <div className="px-4 py-3.5">
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  В компании
                </p>
                <p className="app-text-muted mt-1 text-sm">
                  {getWorkDuration(user.date_joined) || "—"}
                </p>
              </div>
              <div className="border-t border-[var(--border-subtle)] px-4 py-3.5 md:border-l md:border-t-0">
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  Дата найма
                </p>
                <p className="app-text-muted mt-1 text-sm">
                  {formatDate(user.date_joined)}
                </p>
              </div>
            </div>
            <div className="border-t border-[var(--border-subtle)]" />
            <div className="grid md:grid-cols-2">
              <div className="px-4 py-3.5">
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  Профиль создан
                </p>
                <p className="app-text-muted mt-1 text-sm">
                  {formatDate(user.created_at)}
                </p>
              </div>
              <div className="border-t border-[var(--border-subtle)] px-4 py-3.5 md:border-l md:border-t-0">
                <p className="text-sm font-semibold text-[var(--foreground)]">
                  Последний вход
                </p>
                <p className="app-text-muted mt-1 text-sm">
                  {formatDateTime(user.last_login)}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="app-surface rounded-[24px] p-5">
          <SectionTitle
            title="Кадровые события"
            action={
              sortedActions.length > 3 ? (
                <button
                  type="button"
                  onClick={() => setShowAllActions((current) => !current)}
                  className="app-action-secondary rounded-xl px-3 py-2 text-sm font-medium"
                >
                  {showAllActions
                    ? "Свернуть"
                    : `Показать все (${sortedActions.length})`}
                </button>
              ) : undefined
            }
          />
          {sortedActions.length ? (
            <div className="space-y-2.5">
              {!showAllActions && sortedActions.length > 3 ? (
                <p className="app-text-muted text-sm">
                  Последние {visibleActions.length} из {sortedActions.length}
                </p>
              ) : null}
              {visibleActions.map((action) => {
                const tone = getEmployeeActionTone(action.action);
                const isCurrentAction = action.id === currentActionId;
                return (
                  <div key={action.id} className="relative pl-5">
                    <span
                      className="absolute bottom-0 left-1.5 top-0 w-px"
                      style={{ backgroundColor: tone.lineColor }}
                    />
                    {isCurrentAction ? (
                      <span
                        className="absolute left-0 top-2 h-3.5 w-3.5 rounded-full border-4 border-[var(--surface-primary)]"
                        style={{ backgroundColor: tone.lineColor }}
                      />
                    ) : null}
                    <div className="app-surface-muted rounded-2xl px-4 py-2.5">
                      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <span
                            className={`app-status-pill ${tone.badgeClass}`}
                          >
                            {action.action_display || action.action}
                          </span>
                          {isCurrentAction ? (
                            <span className="app-text-muted ml-2 inline-flex text-xs font-medium">
                              текущий
                            </span>
                          ) : null}
                          {action.comment ? (
                            <p className="app-text-muted mt-2 text-sm leading-6">
                              {truncateText(
                                action.comment,
                                showAllActions ? 240 : 120,
                              )}
                            </p>
                          ) : null}
                        </div>
                        <p className="app-text-muted shrink-0 text-sm md:pt-1">
                          {formatDateTime(action.date || action.created_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="app-text-muted text-sm">Событий нет</p>
          )}
        </section>
      </div>
    </AppShell>
  );
}
