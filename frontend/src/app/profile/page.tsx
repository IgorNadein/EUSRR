"use client";

import Image from "next/image";
import { Mail, MessageCircle, Phone, RefreshCw } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import EmployeeAttendanceCard from "@/components/attendance/EmployeeAttendanceCard";
import EmployeeActionsTimeline from "@/components/users/EmployeeActionsTimeline";
import {
  ProfileContactsPanel,
  ProfileDepartmentBadge,
  ProfileDepartmentsCard,
  ProfileHeroCard,
  ProfileInfoCard,
  ProfileSkillsCard,
  type ProfileContactRow,
} from "@/components/users/ProfileSections";
import {
  useProfilePage,
  type ProfileContactEntry,
} from "@/hooks/useProfilePage";
import { formatBirthdayWithYear, getEmployeeActionTone } from "@/lib/users/userDetailUtils";
import { resolveMediaUrl } from "@/lib/url";

function initials(firstName?: string, lastName?: string) {
  return `${lastName?.[0] || ""}${firstName?.[0] || ""}`.trim() || "П";
}

function getContactIcon(entry: ProfileContactEntry) {
  switch (entry.kind) {
    case "email":
      return <Mail size={18} />;
    case "phone":
      return <Phone size={18} />;
    case "directory-login":
      return (
        <RefreshCw
          size={18}
          className={entry.refreshing ? "animate-spin" : ""}
        />
      );
    case "telegram":
    case "whatsapp":
    case "wechat":
    default:
      return <MessageCircle size={18} />;
  }
}

export default function ProfilePage() {
  const {
    availableSkills,
    contactEntries,
    currentAction,
    departmentSummary,
    fullName,
    infoItems,
    loading,
    profileSkills,
    skillName,
    skillsError,
    skillsLoading,
    skillsSaving,
    sortedActions,
    user,
    handleAddSkill,
    handleCopyContact,
    handleRefreshDirectoryLogin,
    handleRemoveSkill,
    onInputSkillName,
  } = useProfilePage();

  const contactRows: ProfileContactRow[] = contactEntries.map((entry) => ({
    key: entry.key,
    label: entry.label,
    value: entry.value,
    icon: getContactIcon(entry),
    onClick:
      entry.canCopy && entry.copyValue
        ? () => void handleCopyContact(entry.copyValue!, entry.key)
        : undefined,
    copied: entry.copied,
    action: entry.canRefresh ? (
      <button
        type="button"
        onClick={() => void handleRefreshDirectoryLogin()}
        disabled={entry.refreshing}
        className="app-action-secondary shrink-0 rounded-xl px-3 py-2 text-sm font-medium disabled:opacity-50"
      >
        Обновить
      </button>
    ) : undefined,
  }));

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
        <ProfileHeroCard
          caption="Мой профиль"
          statusBadge={
            currentAction ? (
              <span
                className={`app-status-pill ${getEmployeeActionTone(currentAction.action).badgeClass}`}
              >
                {currentAction.action_display || currentAction.action}
              </span>
            ) : null
          }
          avatar={
            <div
              className={`${user.avatar ? "app-avatar-frame" : "app-avatar-fallback"} flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-full text-2xl font-semibold`}
            >
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
                initials(user.first_name, user.last_name)
              )}
            </div>
          }
          fullName={fullName}
          secondaryLine={formatBirthdayWithYear(user.birth_date) || "Не указана"}
          roleText={user.position?.name || "Должность не указана"}
          departmentBadge={
            departmentSummary ? (
              <ProfileDepartmentBadge
                label={departmentSummary.label}
                href={departmentSummary.href}
              />
            ) : undefined
          }
          bottomPanel={<ProfileContactsPanel rows={contactRows} />}
        />

        <ProfileSkillsCard
          inputValue={skillName}
          onInputChange={onInputSkillName}
          onSubmit={() => void handleAddSkill()}
          submitDisabled={!skillName.trim() || skillsSaving}
          inputDisabled={skillsSaving}
          availableSkills={availableSkills}
          skills={profileSkills}
          error={skillsError}
          loading={skillsLoading}
          onRemoveSkill={(skillId) => void handleRemoveSkill(skillId)}
          removeDisabled={skillsSaving}
          emptyText="Навыки пока не указаны"
        />

        <ProfileInfoCard items={infoItems} />

        {user.departments?.length ? (
          <ProfileDepartmentsCard departments={user.departments} />
        ) : null}

        <EmployeeActionsTimeline
          actionLoading={null}
          canManageActions={false}
          canViewActions
          latestActionId={currentAction?.id ?? null}
          sortedActions={sortedActions}
          initialVisibleCount={3}
          showCountLabel={false}
          truncateCommentLength={120}
          expandedCommentLength={240}
        />

        <EmployeeAttendanceCard employeeActions={user.actions} employeeId={user.id} />
      </div>
    </AppShell>
  );
}
