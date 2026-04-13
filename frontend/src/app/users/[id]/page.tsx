"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Mail,
  MessageCircle,
  Pencil,
  Phone,
} from "lucide-react";

import { AppShell } from "../../../components/AppShell";
import EditUserProfileModal from "@/components/users/EditUserProfileModal";
import EmployeeActionModal from "@/components/users/EmployeeActionModal";
import EmployeeActionsTimeline from "@/components/users/EmployeeActionsTimeline";
import {
  ProfileContactsPanel,
  ProfileDepartmentBadge,
  ProfileHeroCard,
  ProfileInfoCard,
  ProfileSkillsCard,
  type ProfileContactRow,
  type ProfileInfoItem,
} from "@/components/users/ProfileSections";
import { useUser } from "@/contexts/UserContext";
import { useUserDetailPage } from "@/hooks/useUserDetailPage";
import { apiClient } from "@/lib/api";
import {
  formatBirthdayWithYear,
  formatProfileDate,
  formatProfileDateTime,
  formatPhoneForLink,
  getEmployeeActionTone,
  getWorkDuration,
  normalizeTelegramLink,
  normalizeWhatsAppLink,
} from "@/lib/users/userDetailUtils";

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
      } catch (error: unknown) {
        if (!mounted) return;
        setSkillsError(
          String((error as Error)?.message || "Не удалось загрузить список навыков"),
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

  const contactRows = useMemo<ProfileContactRow[]>(() => {
    if (!person) return [];

    const rows: ProfileContactRow[] = [];

    const email = person.email;
    if (email) {
      rows.push({
        key: "email",
        label: "Почта",
        value: email,
        icon: <Mail size={18} />,
        onClick: () => void handleCopyToClipboard(email, "email"),
        copied: copySuccess === "email",
      });
    }

    const phone = person.phone_number;
    if (phone) {
      rows.push({
        key: "phone",
        label: "Телефон",
        value: phone,
        icon: <Phone size={18} />,
        onClick: () => void handleCopyToClipboard(phone, "phone"),
        copied: copySuccess === "phone",
      });
    }

    const telegram = person.telegram;
    if (telegram) {
      rows.push({
        key: "telegram",
        label: "Telegram",
        value: telegram,
        icon: <MessageCircle size={18} />,
        onClick: () => void handleCopyToClipboard(normalizeTelegramLink(telegram), "telegram"),
        copied: copySuccess === "telegram",
      });
    }

    const whatsapp = person.whatsapp;
    if (whatsapp) {
      rows.push({
        key: "whatsapp",
        label: "WhatsApp",
        value: whatsapp,
        icon: <MessageCircle size={18} />,
        onClick: () => void handleCopyToClipboard(normalizeWhatsAppLink(whatsapp), "whatsapp"),
        copied: copySuccess === "whatsapp",
      });
    }

    const wechat = person.wechat;
    if (wechat) {
      rows.push({
        key: "wechat",
        label: "WeChat",
        value: wechat,
        icon: <MessageCircle size={18} />,
        onClick: () => void handleCopyToClipboard(wechat, "wechat"),
        copied: copySuccess === "wechat",
      });
    }

    return rows;
  }, [copySuccess, handleCopyToClipboard, person]);

  const infoItems = useMemo<ProfileInfoItem[]>(() => ([
    {
      label: "В компании",
      value: getWorkDuration(person?.date_joined) || "—",
    },
    {
      label: "Дата найма",
      value: formatProfileDate(person?.date_joined),
    },
    {
      label: "Профиль создан",
      value: formatProfileDate(person?.created_at),
    },
    {
      label: "Последний вход",
      value: formatProfileDateTime(person?.last_login),
    },
  ]), [person?.created_at, person?.date_joined, person?.last_login]);

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
    } catch (error: unknown) {
      setSkillsError(
        String((error as Error)?.message || "Не удалось добавить навык"),
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
          <section className="app-surface rounded-2xl p-8 text-center">
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка сотрудника...</p>
          </section>
        ) : error ? (
          <section className="app-surface rounded-2xl p-6 text-center">
            <p className="text-sm text-red-400">{error}</p>
          </section>
        ) : person ? (
          <>
            <ProfileHeroCard
              caption="Профиль сотрудника"
              statusBadge={
                latestAction ? (
                  <span
                    className={`app-status-pill ${getEmployeeActionTone(latestAction.action).badgeClass}`}
                  >
                    {latestAction.action_display || latestAction.action}
                  </span>
                ) : null
              }
              avatar={
                <div
                  className={`flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-full text-2xl font-semibold ${avatarUrl && !avatarFailed ? "app-avatar-frame" : "app-avatar-fallback"}`}
                >
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
                    initials
                  )}
                </div>
              }
              fullName={fullName}
              secondaryLine={formatBirthdayWithYear(person.birth_date) || "Не указана"}
              roleText={person.position?.name || "Должность не указана"}
              departmentBadge={
                primaryDepartment ? (
                  <ProfileDepartmentBadge
                    label={primaryDepartment.name}
                    href={`/departments/${primaryDepartment.id}`}
                  />
                ) : undefined
              }
              headerActions={
                canEdit ? (
                  <button
                    type="button"
                    onClick={handleOpenEditModal}
                    className="app-action-secondary inline-flex h-10 w-10 items-center justify-center rounded-xl"
                    aria-label="Редактировать профиль"
                    title="Редактировать профиль"
                  >
                    <Pencil size={16} />
                  </button>
                ) : undefined
              }
              actionRow={
                currentUser && currentUser.id !== person.id ? (
                  <>
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
                  </>
                ) : undefined
              }
              bottomPanel={
                <ProfileContactsPanel
                  rows={contactRows}
                  emptyText="Контакты не указаны"
                />
              }
            />

            <ProfileSkillsCard
              inputValue={skillName}
              onInputChange={setSkillName}
              onSubmit={() => void handleAddSkill()}
              submitDisabled={!skillName.trim() || skillsSaving}
              inputDisabled={skillsSaving}
              availableSkills={availableSkills}
              skills={personSkills}
              error={skillsError}
              loading={skillsLoading}
              emptyText="Навыки не указаны"
            />

            <ProfileInfoCard items={infoItems} />

            {person.departments?.length ? (
              <section className="app-surface rounded-2xl p-5">
                <div className="mb-4">
                  <h2 className="app-card-caption">Отделы</h2>
                </div>
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
              truncateCommentLength={120}
              expandedCommentLength={240}
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
