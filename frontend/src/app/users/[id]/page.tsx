"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Building2,
  CalendarDays,
  Check,
  Copy,
  Mail,
  MessageCircle,
  Pencil,
  Phone,
  Plus,
} from "lucide-react";

import { AppShell } from "../../../components/AppShell";
import EditUserProfileModal from "@/components/users/EditUserProfileModal";
import EmployeeActionModal from "@/components/users/EmployeeActionModal";
import EmployeeActionsTimeline from "@/components/users/EmployeeActionsTimeline";
import { useUser } from "@/contexts/UserContext";
import { useUserDetailPage } from "@/hooks/useUserDetailPage";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import {
  formatBirthday,
  formatPhoneForLink,
  getEmployeeActionTone,
  getWorkDuration,
} from "@/lib/users/userDetailUtils";

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

function SectionTitle({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <h2 className="app-card-caption">{title}</h2>
      {action}
    </div>
  );
}

export default function UserDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user: currentUser } = useUser();
  const userId = Number(params?.id);

  const {
    actionForm,
    actionLoading,
    actionTypes,
    avatarFailed,
    avatarUrl,
    canEdit,
    canManageActions,
    canViewActions,
    copySuccess,
    creatingChat,
    editForm,
    error,
    fullName,
    handleAvatarChange,
    handleCloseActionModal,
    handleCloseEditModal,
    handleCopyToClipboard,
    handleDeleteAction,
    handleEditAction,
    handleOpenActionModal,
    handleOpenEditModal,
    handleSaveAction,
    handleSaveEdit,
    handleStartChat,
    initials,
    isActionModalOpen,
    isEditModalOpen,
    latestAction,
    loading,
    person,
    setActionField,
    setAvatarFailed,
    setEditField,
    sortedActions,
  } = useUserDetailPage(userId, currentUser);

  useEffect(() => {
    if (currentUser?.id && userId && currentUser.id === userId) {
      router.replace("/profile");
    }
  }, [currentUser?.id, router, userId]);

  const primaryDepartment = useMemo(
    () => person?.departments?.[0] || null,
    [person?.departments],
  );
  const [availableSkills, setAvailableSkills] = useState<
    Array<{ id: number; name: string; description?: string }>
  >([]);
  const [personSkills, setPersonSkills] = useState<
    Array<{ id: number; name: string; description?: string }>
  >([]);
  const [skillName, setSkillName] = useState("");
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsSaving, setSkillsSaving] = useState(false);
  const [skillsError, setSkillsError] = useState<string | null>(null);

  useEffect(() => {
    setPersonSkills(person?.skills || []);
  }, [person?.skills]);

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

  const contactRows = useMemo(
    () =>
      person
        ? [
            person.email
              ? {
                  key: "email",
                  label: "Почта",
                  value: person.email,
                  href: `mailto:${person.email}`,
                  icon: <Mail size={18} />,
                }
              : null,
            person.phone_number
              ? {
                  key: "phone",
                  label: "Телефон",
                  value: person.phone_number,
                  href: `tel:${formatPhoneForLink(person.phone_number)}`,
                  icon: <Phone size={18} />,
                }
              : null,
            person.telegram
              ? {
                  key: "telegram",
                  label: "Telegram",
                  value: person.telegram,
                  href: normalizeTelegram(person.telegram),
                  icon: <MessageCircle size={18} />,
                }
              : null,
            person.whatsapp
              ? {
                  key: "whatsapp",
                  label: "WhatsApp",
                  value: person.whatsapp,
                  href: normalizeWhatsApp(person.whatsapp),
                  icon: <MessageCircle size={18} />,
                }
              : null,
            person.wechat
              ? {
                  key: "wechat",
                  label: "WeChat",
                  value: person.wechat,
                  href: null,
                  icon: <MessageCircle size={18} />,
                }
              : null,
          ].filter(Boolean) as Array<{
            key: string;
            label: string;
            value: string;
            href: string | null;
            icon: React.ReactNode;
          }>
        : [],
    [person],
  );

  const handleAddSkill = async (forcedSkill?: { id: number; name: string }) => {
    if (!person || skillsSaving) return;
    const rawName = forcedSkill?.name || skillName;
    const trimmedName = rawName.trim();
    if (!trimmedName) return;

    try {
      setSkillsSaving(true);
      setSkillsError(null);

      const existingSkill =
        forcedSkill ||
        availableSkills.find(
          (skill) => skill.name.trim().toLowerCase() === trimmedName.toLowerCase(),
        );

      const response = (await apiClient.addEmployeeSkill(
        person.id,
        existingSkill ? { skill_id: existingSkill.id } : { name: trimmedName },
      )) as { skills?: Array<{ id: number; name: string; description?: string }> };

      setPersonSkills(response.skills || []);

      if (!existingSkill && trimmedName) {
        const created = (response.skills || []).find(
          (skill) => skill.name.trim().toLowerCase() === trimmedName.toLowerCase(),
        );
        if (created) {
          setAvailableSkills((current) =>
            current.some((skill) => skill.id === created.id)
              ? current
              : [...current, created].sort((left, right) =>
                  left.name.localeCompare(right.name, "ru"),
                ),
          );
        }
      }

      setSkillName("");
    } catch (error: any) {
      setSkillsError(
        String(error?.message || "Не удалось добавить навык"),
      );
    } finally {
      setSkillsSaving(false);
    }
  };

  if (currentUser?.id && userId && currentUser.id === userId) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-16">
          <p className="app-text-muted text-sm">Перенаправляем в профиль...</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex items-center justify-between gap-4">
          <Link
            href="/employees"
            className="app-action-secondary inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-medium"
          >
            ← К списку сотрудников
          </Link>
        </div>

        {loading ? (
          <section className="app-surface rounded-[24px] p-8 text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка сотрудника...</p>
          </section>
        ) : error ? (
          <section className="app-surface rounded-[24px] p-6 text-center">
            <p className="text-sm text-red-400">{error}</p>
          </section>
        ) : person ? (
          <>
            <section className="app-surface rounded-[28px] p-5">
              <div className="mb-4 flex items-start justify-between gap-4">
                <p className="app-card-caption">Профиль сотрудника</p>
                {latestAction ? (
                  <span
                    className={`app-status-pill ${getEmployeeActionTone(latestAction.action).badgeClass}`}
                  >
                    {latestAction.action_display || latestAction.action}
                  </span>
                ) : null}
              </div>

              <div className="space-y-4">
                <div className="flex items-start gap-4">
                  <div className="h-20 w-20 shrink-0 overflow-hidden rounded-full app-avatar-frame">
                    {avatarUrl && !avatarFailed ? (
                      <Image
                        src={avatarUrl}
                        alt={fullName}
                        width={80}
                        height={80}
                        className="h-full w-full object-cover"
                        onError={() => setAvatarFailed(true)}
                        unoptimized
                      />
                    ) : (
                      <div className="app-avatar-fallback flex h-full w-full items-center justify-center text-2xl font-semibold">
                        {initials}
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <h1 className="text-[2rem] font-semibold leading-tight text-[var(--foreground)]">
                          {fullName}
                        </h1>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2">
                          <span className="app-text-muted text-sm">
                            {person.position?.name || "Должность не указана"}
                          </span>
                          {primaryDepartment ? (
                            <Link
                              href={`/departments/${primaryDepartment.id}`}
                              className="app-pill inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
                            >
                              {primaryDepartment.name}
                            </Link>
                          ) : null}
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        {canEdit ? (
                          <button
                            type="button"
                            onClick={handleOpenEditModal}
                            className="app-action-secondary inline-flex h-10 w-10 items-center justify-center rounded-xl"
                            aria-label="Редактировать профиль"
                            title="Редактировать профиль"
                          >
                            <Pencil size={16} />
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {currentUser && currentUser.id !== person.id ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={handleStartChat}
                          disabled={creatingChat}
                          className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-50"
                        >
                          <MessageCircle size={16} />
                          {creatingChat ? "Загрузка..." : "Написать"}
                        </button>
                        {person.phone_number ? (
                          <a
                            href={`tel:${formatPhoneForLink(person.phone_number)}`}
                            className="app-action-secondary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium"
                          >
                            <Phone size={16} />
                            Позвонить
                          </a>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div className="app-surface-muted rounded-2xl p-4">
                  <div>
                    {contactRows.length ? (
                      contactRows.map((contact, index) => (
                        <div key={contact.key}>
                          {index > 0 ? (
                            <div className="mx-4 border-t border-[var(--border-subtle)]" />
                          ) : null}
                          <div className="flex items-start gap-3 px-4 py-4">
                            <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                              {contact.icon}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-semibold text-[var(--foreground)]">
                                {contact.label}
                              </p>
                              {contact.href ? (
                                <a
                                  href={contact.href}
                                  target={
                                    contact.key === "telegram" ||
                                    contact.key === "whatsapp"
                                      ? "_blank"
                                      : undefined
                                  }
                                  rel={
                                    contact.key === "telegram" ||
                                    contact.key === "whatsapp"
                                      ? "noreferrer"
                                      : undefined
                                  }
                                  className="app-text-muted mt-1 block truncate text-sm hover:text-[var(--accent-primary)]"
                                >
                                  {contact.value}
                                </a>
                              ) : (
                                <p className="app-text-muted mt-1 truncate text-sm">
                                  {contact.value}
                                </p>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                handleCopyToClipboard(contact.value, contact.key)
                              }
                              className="app-action-secondary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                              title="Скопировать"
                            >
                              {copySuccess === contact.key ? (
                                <Check size={14} />
                              ) : (
                                <Copy size={14} />
                              )}
                            </button>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="app-text-muted px-4 py-2 text-sm">
                        Контакты не указаны
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <section className="app-surface rounded-[24px] p-5">
              <SectionTitle title="Навыки" />
              <div className="app-surface-muted rounded-2xl p-4">
                <div className="flex flex-col gap-3 md:flex-row">
                  <div className="min-w-0 flex-1">
                    <input
                      list="employee-skills-list"
                      value={skillName}
                      onChange={(event) => setSkillName(event.target.value)}
                      placeholder="Добавить навык"
                      className="app-input w-full rounded-xl px-4 py-3 text-sm"
                      disabled={skillsSaving}
                    />
                    <datalist id="employee-skills-list">
                      {availableSkills.map((skill) => (
                        <option key={skill.id} value={skill.name} />
                      ))}
                    </datalist>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleAddSkill()}
                    disabled={!skillName.trim() || skillsSaving}
                    className="app-action-primary inline-flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium disabled:opacity-50"
                  >
                    <Plus size={16} />
                    Добавить
                  </button>
                </div>

                {skillsError ? (
                  <p className="mt-3 text-sm text-red-400">{skillsError}</p>
                ) : null}

                <div className="mt-4">
                  {personSkills.length ? (
                    <div className="flex flex-wrap gap-2">
                      {personSkills.map((skill) => (
                        <span
                          key={skill.id}
                          className="app-pill inline-flex items-center rounded-full px-3 py-2 text-sm font-medium"
                        >
                          {skill.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="app-text-muted text-sm">Навыки не указаны</p>
                  )}
                </div>

                {skillsLoading ? (
                  <p className="app-text-muted mt-3 text-sm">
                    Загружаем навыки...
                  </p>
                ) : null}
              </div>
            </section>

            <section className="app-surface rounded-[24px] p-5">
              <SectionTitle title="Информация" />
              <div className="app-surface-muted overflow-hidden rounded-2xl">
                <div className="grid md:grid-cols-2">
                  <div className="px-4 py-4">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      В компании
                    </p>
                    <p className="app-text-muted mt-1 text-sm">
                      {getWorkDuration(person.date_joined) || "—"}
                    </p>
                  </div>
                  <div className="border-t border-[var(--border-subtle)] px-4 py-4 md:border-l md:border-t-0">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      Дата найма
                    </p>
                    <p className="app-text-muted mt-1 text-sm">
                      {formatDate(person.date_joined)}
                    </p>
                  </div>
                </div>
                <div className="border-t border-[var(--border-subtle)]" />
                <div className="grid md:grid-cols-2">
                  <div className="px-4 py-4">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      День рождения
                    </p>
                    <p className="app-text-muted mt-1 text-sm">
                      {formatBirthday(person.birth_date) || "—"}
                    </p>
                  </div>
                  <div className="border-t border-[var(--border-subtle)] px-4 py-4 md:border-l md:border-t-0">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      Последний вход
                    </p>
                    <p className="app-text-muted mt-1 text-sm">
                      {formatDateTime(person.last_login)}
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {person.departments?.length ? (
              <section className="app-surface rounded-[24px] p-5">
                <SectionTitle title="Отделы" />
                <div className="app-surface-muted rounded-2xl p-4">
                  <div className="space-y-3">
                    {person.departments.map((department) => (
                      <Link
                        key={department.id}
                        href={`/departments/${department.id}`}
                        className="app-surface block rounded-2xl px-4 py-3 transition hover:border-[var(--accent-primary)]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[var(--foreground)]">
                              {department.name}
                            </p>
                            {department.role_name ? (
                              <p className="app-text-muted mt-1 text-sm">
                                {department.role_name}
                              </p>
                            ) : null}
                          </div>
                          {department.is_head ? (
                            <span className="app-pill-active inline-flex rounded-full px-3 py-1 text-xs font-medium">
                              Руководитель
                            </span>
                          ) : null}
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}

            <EmployeeActionsTimeline
              actionLoading={actionLoading}
              canManageActions={canManageActions}
              canViewActions={canViewActions}
              latestActionId={latestAction?.id ?? null}
              onAddAction={handleOpenActionModal}
              onDeleteAction={handleDeleteAction}
              onEditAction={handleEditAction}
              sortedActions={sortedActions}
            />
          </>
        ) : null}
      </div>

      <EditUserProfileModal
        actionLoading={actionLoading}
        avatarFailed={avatarFailed}
        avatarUrl={avatarUrl}
        form={editForm}
        initials={initials}
        isOpen={isEditModalOpen}
        onAvatarChange={handleAvatarChange}
        onClose={handleCloseEditModal}
        onSave={handleSaveEdit}
        onTextFieldChange={(field, value) => setEditField(field, value)}
        person={person}
      />

      <EmployeeActionModal
        actionLoading={actionLoading}
        actionTypes={actionTypes}
        form={actionForm}
        isOpen={isActionModalOpen}
        onClose={handleCloseActionModal}
        onFieldChange={(field, value) => setActionField(field, value)}
        onSave={handleSaveAction}
      />
    </AppShell>
  );
}
