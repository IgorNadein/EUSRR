"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import {
  formatProfileDate,
  formatProfileDateTime,
  getLatestEmployeeAction,
  getUserFullName,
  getWorkDuration,
  normalizeTelegramLink,
  normalizeWhatsAppLink,
  sortEmployeeActions,
} from "@/lib/users/userDetailUtils";
import type { DirectoryLoginResult, EmployeeAction } from "@/types/api";

type SkillOption = {
  id: number;
  name: string;
  description?: string;
};

export type ProfileContactKind =
  | "email"
  | "phone"
  | "telegram"
  | "whatsapp"
  | "wechat"
  | "directory-login";

export type ProfileContactEntry = {
  key: string;
  label: string;
  value: string;
  kind: ProfileContactKind;
  copied: boolean;
  copyValue?: string;
  canCopy?: boolean;
  canRefresh?: boolean;
  refreshing?: boolean;
};

export type ProfileInfoEntry = {
  label: string;
  value: string;
};

export type ProfileDepartmentSummary = {
  label: string;
  href?: string;
};

export type ProfilePageController = {
  availableSkills: SkillOption[];
  contactEntries: ProfileContactEntry[];
  currentAction: EmployeeAction | null;
  departmentSummary: ProfileDepartmentSummary | null;
  fullName: string;
  infoItems: ProfileInfoEntry[];
  loading: boolean;
  profileSkills: SkillOption[];
  skillName: string;
  skillsError: string | null;
  skillsLoading: boolean;
  skillsSaving: boolean;
  sortedActions: EmployeeAction[];
  user: ReturnType<typeof useUser>["user"];
  handleAddSkill: (forcedSkill?: Pick<SkillOption, "id" | "name">) => Promise<void>;
  handleCopyContact: (value: string, key: string) => Promise<void>;
  handleRefreshDirectoryLogin: () => Promise<void>;
  handleRemoveSkill: (skillId: number) => Promise<void>;
  onInputSkillName: (value: string) => void;
};

const getErrorMessage = (error: unknown, fallback: string) =>
  String((error as Error)?.message || fallback);

export function useProfilePage(): ProfilePageController {
  const { user, loading } = useUser();
  const [copiedContactKey, setCopiedContactKey] = useState<string | null>(null);
  const [directoryLogin, setDirectoryLogin] = useState<string | null>(null);
  const [directoryLoginLoading, setDirectoryLoginLoading] = useState(false);
  const [directoryLoginRefreshing, setDirectoryLoginRefreshing] = useState(false);
  const [directoryLoginError, setDirectoryLoginError] = useState<string | null>(
    null,
  );
  const [availableSkills, setAvailableSkills] = useState<SkillOption[]>([]);
  const [profileSkills, setProfileSkills] = useState<SkillOption[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsSaving, setSkillsSaving] = useState(false);
  const [skillName, setSkillName] = useState("");
  const [skillsError, setSkillsError] = useState<string | null>(null);

  const fullName = useMemo(
    () => getUserFullName(user) || "Пользователь",
    [user],
  );
  const currentAction = useMemo(
    () => getLatestEmployeeAction(user?.actions),
    [user?.actions],
  );
  const sortedActions = useMemo(
    () => sortEmployeeActions(user?.actions),
    [user?.actions],
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
      } catch (error) {
        if (!mounted) return;
        setDirectoryLoginError(
          getErrorMessage(error, "Не удалось получить логин из каталога"),
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
        setSkillsError(null);
        const response = (await apiClient.getSkills()) as SkillOption[];
        if (!mounted) return;
        setAvailableSkills(response);
      } catch (error) {
        if (!mounted) return;
        setSkillsError(
          getErrorMessage(error, "Не удалось загрузить список навыков"),
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

  const handleRefreshDirectoryLogin = useCallback(async () => {
    try {
      setDirectoryLoginRefreshing(true);
      setDirectoryLoginError(null);
      const response =
        (await apiClient.refreshDirectoryLogin()) as DirectoryLoginResult;
      setDirectoryLogin(response.username?.trim() || null);
    } catch (error) {
      setDirectoryLoginError(
        getErrorMessage(error, "Не удалось обновить логин из каталога"),
      );
    } finally {
      setDirectoryLoginRefreshing(false);
    }
  }, []);

  const handleCopyContact = useCallback(async (value: string, key: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedContactKey(key);
      window.setTimeout(
        () =>
          setCopiedContactKey((current) => (current === key ? null : current)),
        2000,
      );
    } catch (error) {
      console.error("Ошибка копирования:", error);
    }
  }, []);

  const saveSkills = useCallback(async (skillIds: number[]) => {
    try {
      setSkillsSaving(true);
      setSkillsError(null);
      const response = (await apiClient.updateCurrentUserProfile({
        skills_ids: skillIds,
      })) as { skills?: SkillOption[] };
      setProfileSkills(response.skills || []);
    } catch (error) {
      setSkillsError(getErrorMessage(error, "Не удалось обновить навыки"));
    } finally {
      setSkillsSaving(false);
    }
  }, []);

  const handleRemoveSkill = useCallback(
    async (skillId: number) => {
      if (!user) return;
      const nextIds = profileSkills
        .map((skill) => skill.id)
        .filter((id) => id !== skillId);
      await saveSkills(nextIds);
    },
    [profileSkills, saveSkills, user],
  );

  const handleAddSkill = useCallback(
    async (forcedSkill?: Pick<SkillOption, "id" | "name">) => {
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
            (skill) =>
              skill.name.trim().toLowerCase() === trimmedName.toLowerCase(),
          );

        let skillId = existingSkill?.id;

        if (!skillId) {
          const createdSkill = (await apiClient.createSkill({
            name: trimmedName,
          })) as SkillOption;
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
        })) as { skills?: SkillOption[] };

        setProfileSkills(response.skills || []);
        setSkillName("");
      } catch (error) {
        setSkillsError(getErrorMessage(error, "Не удалось добавить навык"));
      } finally {
        setSkillsSaving(false);
      }
    },
    [availableSkills, profileSkills, skillName, skillsSaving, user],
  );

  const departmentSummary = useMemo<ProfileDepartmentSummary | null>(() => {
    if (!user?.departments?.length) return null;

    return {
      label:
        user.departments.length === 1
          ? user.departments[0].name
          : `${user.departments.length} отделов`,
      href:
        user.departments.length === 1
          ? `/departments/${user.departments[0].id}`
          : undefined,
    };
  }, [user?.departments]);

  const contactEntries = useMemo<ProfileContactEntry[]>(() => {
    if (!user) return [];

    const entries: ProfileContactEntry[] = [];

    if (user.email) {
      entries.push({
        key: "email",
        label: "Почта",
        value: user.email,
        kind: "email",
        copied: copiedContactKey === "email",
        copyValue: user.email,
        canCopy: true,
      });
    }

    if (user.phone_number) {
      entries.push({
        key: "phone",
        label: "Телефон",
        value: user.phone_number,
        kind: "phone",
        copied: copiedContactKey === "phone",
        copyValue: user.phone_number,
        canCopy: true,
      });
    }

    if (user.telegram) {
      entries.push({
        key: "telegram",
        label: "Telegram",
        value: user.telegram,
        kind: "telegram",
        copied: copiedContactKey === "telegram",
        copyValue: normalizeTelegramLink(user.telegram),
        canCopy: true,
      });
    }

    if (user.whatsapp) {
      entries.push({
        key: "whatsapp",
        label: "WhatsApp",
        value: user.whatsapp,
        kind: "whatsapp",
        copied: copiedContactKey === "whatsapp",
        copyValue: normalizeWhatsAppLink(user.whatsapp),
        canCopy: true,
      });
    }

    if (user.wechat) {
      entries.push({
        key: "wechat",
        label: "WeChat",
        value: user.wechat,
        kind: "wechat",
        copied: copiedContactKey === "wechat",
        copyValue: user.wechat,
        canCopy: true,
      });
    }

    if (
      user.is_ldap_managed ||
      directoryLoginLoading ||
      directoryLoginError ||
      directoryLogin
    ) {
      entries.push({
        key: "directory-login",
        label: "Логин в каталоге",
        value: directoryLoginLoading ? "Загружаем..." : directoryLogin || "Не найден",
        kind: "directory-login",
        copied: copiedContactKey === "directory-login",
        copyValue: directoryLogin || undefined,
        canCopy: Boolean(directoryLogin && !directoryLoginLoading),
        canRefresh: true,
        refreshing: directoryLoginRefreshing,
      });
    }

    return entries;
  }, [
    copiedContactKey,
    directoryLogin,
    directoryLoginError,
    directoryLoginLoading,
    directoryLoginRefreshing,
    user,
  ]);

  const infoItems = useMemo<ProfileInfoEntry[]>(
    () => [
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
        label: "Последняя активность",
        value: formatProfileDateTime(
          user?.last_activity_at || user?.last_login,
        ),
      },
    ],
    [user?.created_at, user?.date_joined, user?.last_activity_at, user?.last_login],
  );

  const onInputSkillName = useCallback((value: string) => {
    setSkillName(value);
  }, []);

  return {
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
  };
}
