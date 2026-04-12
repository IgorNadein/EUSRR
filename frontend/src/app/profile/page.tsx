"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  Mail,
  MessageCircle,
  Phone,
  RefreshCw,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
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
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import {
  formatBirthdayWithYear,
  formatProfileDate,
  formatProfileDateTime,
  getEmployeeActionTone,
  getLatestEmployeeAction,
  getWorkDuration,
  getUserFullName,
  normalizeTelegramLink,
  normalizeWhatsAppLink,
  sortEmployeeActions,
} from "@/lib/users/userDetailUtils";
import type { DirectoryLoginResult } from "@/types/api";

function initials(firstName?: string, lastName?: string) {
  return `${lastName?.[0] || ""}${firstName?.[0] || ""}`.trim() || "П";
}

export default function ProfilePage() {
  const { user, loading } = useUser();
  const [copiedContactKey, setCopiedContactKey] = useState<string | null>(null);
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
    return getUserFullName(user) || "Пользователь";
  }, [user]);

  const currentAction = useMemo(() => {
    return getLatestEmployeeAction(user?.actions);
  }, [user?.actions]);

  const sortedActions = useMemo(() => {
    return sortEmployeeActions(user?.actions);
  }, [user?.actions]);

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

  const handleCopyContact = async (value: string, key: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedContactKey(key);
      window.setTimeout(() => setCopiedContactKey((current) => (current === key ? null : current)), 2000);
    } catch (error) {
      console.error("Ошибка копирования:", error);
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

  const departmentBadge = useMemo(() => {
    if (!user?.departments?.length) return null;
    const label = user.departments.length === 1
      ? user.departments[0].name
      : `${user.departments.length} отделов`;

    return (
      <ProfileDepartmentBadge
        label={label}
        href={user.departments.length === 1 ? `/departments/${user.departments[0].id}` : undefined}
      />
    );
  }, [user?.departments]);

  const contactRows = useMemo<ProfileContactRow[]>(() => {
    if (!user) return [];

    const rows: ProfileContactRow[] = [];

    const email = user.email;
    if (email) {
      rows.push({
        key: "email",
        label: "Почта",
        value: email,
        icon: <Mail size={18} />,
        onClick: () => void handleCopyContact(email, "email"),
        copied: copiedContactKey === "email",
      });
    }

    const phone = user.phone_number;
    if (phone) {
      rows.push({
        key: "phone",
        label: "Телефон",
        value: phone,
        icon: <Phone size={18} />,
        onClick: () => void handleCopyContact(phone, "phone"),
        copied: copiedContactKey === "phone",
      });
    }

    const telegram = user.telegram;
    if (telegram) {
      rows.push({
        key: "telegram",
        label: "Telegram",
        value: telegram,
        icon: <MessageCircle size={18} />,
        onClick: () => void handleCopyContact(normalizeTelegramLink(telegram), "telegram"),
        copied: copiedContactKey === "telegram",
      });
    }

    const whatsapp = user.whatsapp;
    if (whatsapp) {
      rows.push({
        key: "whatsapp",
        label: "WhatsApp",
        value: whatsapp,
        icon: <MessageCircle size={18} />,
        onClick: () => void handleCopyContact(normalizeWhatsAppLink(whatsapp), "whatsapp"),
        copied: copiedContactKey === "whatsapp",
      });
    }

    const wechat = user.wechat;
    if (wechat) {
      rows.push({
        key: "wechat",
        label: "WeChat",
        value: wechat,
        icon: <MessageCircle size={18} />,
        onClick: () => void handleCopyContact(wechat, "wechat"),
        copied: copiedContactKey === "wechat",
      });
    }

    if (user.is_ldap_managed || directoryLoginLoading || directoryLoginError || directoryLogin) {
      const directoryLoginValue = directoryLoginLoading
        ? "Загружаем..."
        : directoryLogin || "Не найден";
      rows.push({
        key: "directory-login",
        label: "Логин в каталоге",
        value: directoryLoginValue,
        icon: (
          <RefreshCw
            size={18}
            className={directoryLoginRefreshing ? "animate-spin" : ""}
          />
        ),
        onClick: directoryLogin && !directoryLoginLoading
          ? () => void handleCopyContact(directoryLogin, "directory-login")
          : undefined,
        copied: copiedContactKey === "directory-login",
        action: (
          <button
            type="button"
            onClick={() => void handleRefreshDirectoryLogin()}
            disabled={directoryLoginRefreshing}
            className="app-action-secondary shrink-0 rounded-xl px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            Обновить
          </button>
        ),
      });
    }

    return rows;
  }, [
    copiedContactKey,
    directoryLogin,
    directoryLoginLoading,
    directoryLoginRefreshing,
    directoryLoginError,
    user,
  ]);

  const infoItems = useMemo<ProfileInfoItem[]>(() => ([
    {
      label: "В компании",
      value: getWorkDuration(user?.date_joined) || "—",
    },
    {
      label: "Дата найма",
      value: formatProfileDate(user?.date_joined),
    },
    {
      label: "Профиль создан",
      value: formatProfileDate(user?.created_at),
    },
    {
      label: "Последний вход",
      value: formatProfileDateTime(user?.last_login),
    },
  ]), [user?.created_at, user?.date_joined, user?.last_login]);

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
          }
          fullName={fullName}
          secondaryLine={formatBirthdayWithYear(user.birth_date) || "Не указана"}
          roleText={user.position?.name || "Должность не указана"}
          departmentBadge={departmentBadge}
          bottomPanel={<ProfileContactsPanel rows={contactRows} />}
        />

        <ProfileSkillsCard
          inputValue={skillName}
          onInputChange={setSkillName}
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
      </div>
    </AppShell>
  );
}
