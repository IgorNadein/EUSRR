"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  BriefcaseBusiness,
  ChevronRight,
  History,
  Link2,
  Mail,
  MessageCircle,
  Pencil,
  Phone,
} from "lucide-react";

import { AppShell } from "../../../components/AppShell";
import EmployeeAttendanceCard from "@/components/attendance/EmployeeAttendanceCard";
import { EmployeeTaskLinks } from "@/components/employees/EmployeeTaskLinks";
import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import ChangeUserPositionModal from "@/components/users/ChangeUserPositionModal";
import EditUserProfileModal from "@/components/users/EditUserProfileModal";
import EmployeeActionModal from "@/components/users/EmployeeActionModal";
import EmployeeActionsTimeline from "@/components/users/EmployeeActionsTimeline";
import {
  ProfileContactsPanel,
  ProfileAttendanceStatusPill,
  ProfileDepartmentBadge,
  ProfileDepartmentsCard,
  ProfileHeroCard,
  ProfileInfoCard,
  ProfileSkillsCard,
  ProfileWorkScheduleCard,
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
  getProfileDepartmentSummary,
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
    handleClosePositionModal,
    handleCopyToClipboard,
    handleDeleteAction,
    handleEditAction,
    handleOpenActionModal,
    handleOpenEditModal,
    handleOpenPositionModal,
    handleSaveAction,
    handleSaveEdit,
    handleSavePosition,
    handleStartChat,
    initials,
    isActionModalOpen,
    isEditModalOpen,
    isPositionModalOpen,
    latestAction,
    loading,
    person,
    positionValue,
    positions,
    positionsError,
    positionsLoading,
    refreshPerson,
    setActionField,
    setAvatarFailed,
    setEditField,
    setPositionValue,
    sortedActions,
  } = useUserDetailPage(userId, currentUser);

  useEffect(() => {
    if (currentUser?.id && userId && currentUser.id === userId) {
      router.replace("/profile");
    }
  }, [currentUser?.id, router, userId]);

  const departmentSummary = useMemo(
    () => getProfileDepartmentSummary(person?.departments),
    [person?.departments],
  );
  const canViewAttendance = Boolean(
    currentUser
      && person
      && (
        currentUser.id === person.id
        || currentUser.auth?.is_staff
        || currentUser.auth?.is_superuser
      ),
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
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [taskLinksOpen, setTaskLinksOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    if (!profileMenuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setProfileMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [profileMenuOpen]);

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
      label: "Последняя активность",
      value: formatProfileDateTime(
        person?.last_activity_at || person?.last_login,
      ),
    },
  ]), [person?.created_at, person?.date_joined, person?.last_activity_at, person?.last_login]);

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
                (person.personnel_state || person.attendance_status || latestAction || currentUser) ? (
                  <div
                    ref={profileMenuOpen ? profileMenuRef : null}
                    className="relative flex max-w-full flex-wrap items-center justify-end gap-2"
                  >
                    {person.personnel_state ? (
                      <span
                        className={`app-status-pill ${getEmployeeActionTone(person.personnel_state.status).badgeClass}`}
                      >
                        {person.personnel_state.label || person.personnel_state.status}
                      </span>
                    ) : null}
                    <ProfileAttendanceStatusPill status={person.attendance_status} />
                    {currentUser ? (
                      <>
                        <button
                          type="button"
                          onClick={() => setProfileMenuOpen((current) => !current)}
                          className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                          aria-label="Действия профиля"
                          aria-expanded={profileMenuOpen}
                          title="Действия профиля"
                          aria-haspopup="menu"
                        >
                          <ChevronRight
                            size={15}
                            className={`transition-transform duration-200 ${profileMenuOpen ? "rotate-90" : ""}`}
                          />
                        </button>
                        {profileMenuOpen ? (
                          <div className="app-menu absolute right-0 top-full z-20 mt-2 w-64 rounded-xl py-1.5">
                            <button
                              type="button"
                              onClick={() => {
                                setProfileMenuOpen(false);
                                setTaskLinksOpen(true);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                            >
                              <Link2 size={14} className="app-text-muted" />
                              Связать с задачей
                            </button>
                            {canEdit ? (
                              <button
                                type="button"
                                onClick={() => {
                                  setProfileMenuOpen(false);
                                  handleOpenEditModal();
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                              >
                                <Pencil size={14} className="app-text-muted" />
                                Редактировать профиль
                              </button>
                            ) : null}
                            {canManageActions ? (
                              <button
                                type="button"
                                onClick={() => {
                                  setProfileMenuOpen(false);
                                  handleOpenActionModal();
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                              >
                                <History size={14} className="app-text-muted" />
                                Добавить кадровое событие
                              </button>
                            ) : null}
                            {canManageActions ? (
                              <button
                                type="button"
                                onClick={() => {
                                  setProfileMenuOpen(false);
                                  void handleOpenPositionModal();
                                }}
                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                              >
                                <BriefcaseBusiness size={14} className="app-text-muted" />
                                Изменить должность
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </div>
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
                departmentSummary ? (
                  <ProfileDepartmentBadge
                    label={departmentSummary.label}
                    href={departmentSummary.href}
                  />
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

            <section className="app-surface rounded-2xl p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="app-card-caption">Связанные задачи</p>
                  <p className="app-text-muted mt-1 text-xs">
                    Задачи, привязанные к этому сотруднику
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setTaskLinksOpen(true)}
                  className="app-action-primary inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
                >
                  <Link2 size={14} />
                  Связать
                </button>
              </div>
              {person.linked_tasks && person.linked_tasks.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {person.linked_tasks.map((task) => (
                    <TaskLinkPill
                      key={task.link_id || task.id}
                      task={task}
                      maxTitleClassName="max-w-56"
                    />
                  ))}
                </div>
              ) : (
                <div className="app-surface-muted rounded-xl border border-dashed border-[var(--border-subtle)] px-3 py-4 text-center">
                  <p className="app-text-muted text-sm">Связанных задач нет</p>
                </div>
              )}
            </section>

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
              <ProfileDepartmentsCard departments={person.departments} />
            ) : null}

            <EmployeeActionsTimeline
              actionLoading={actionLoading}
              canManageActions={canManageActions}
              canViewActions={canViewActions}
              latestActionId={person.personnel_state?.action_id ?? latestAction?.id ?? null}
              onAddAction={handleOpenActionModal}
              onDeleteAction={handleDeleteAction}
              onEditAction={handleEditAction}
              personnelState={person.personnel_state}
              sortedActions={sortedActions}
              truncateCommentLength={120}
              expandedCommentLength={240}
            />

            {canViewAttendance ? (
              <>
                <ProfileWorkScheduleCard
                  canEdit={Boolean(currentUser?.auth?.is_staff || currentUser?.auth?.is_superuser)}
                  employeeId={person.id}
                  personnelState={person.personnel_state}
                />

                <EmployeeAttendanceCard
                  attendanceAliases={person.attendance_aliases}
                  employeeActions={person.actions}
                  employeeId={person.id}
                />
              </>
            ) : null}
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

      <ChangeUserPositionModal
        actionLoading={actionLoading}
        error={positionsError}
        isOpen={isPositionModalOpen}
        onClose={handleClosePositionModal}
        onPositionChange={setPositionValue}
        onSave={handleSavePosition}
        person={person}
        positionValue={positionValue}
        positions={positions}
        positionsLoading={positionsLoading}
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

      {person && taskLinksOpen ? (
        <EmployeeTaskLinks
          employee={person}
          variant="dialog"
          open={taskLinksOpen}
          onClose={() => setTaskLinksOpen(false)}
          onLinked={() => void refreshPerson()}
        />
      ) : null}
    </AppShell>
  );
}
