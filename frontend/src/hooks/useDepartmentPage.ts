"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { loadAllPages } from "@/lib/shared";
import type {
  Department,
  DepartmentMemberLink,
  DepartmentRole,
  DepartmentUserPermissions,
  PaginatedResponse,
  User,
} from "@/types/api";

type DepartmentRoleDraft = {
  id: number | null;
  name: string;
};

type SavingKey =
  | "department"
  | "head"
  | "member"
  | "role"
  | `member-role-${number}`
  | `member-remove-${number}`
  | `role-delete-${number}`;

export type DepartmentPageController = {
  addMemberOpen: boolean;
  allEmployees: User[];
  currentUserId: number | null;
  department: Department | null;
  departmentDraft: { name: string; description: string };
  departmentId: number;
  editDepartmentOpen: boolean;
  error: string | null;
  filteredMembers: DepartmentMemberLink[];
  headCandidates: Array<{ id: number; name: string }>;
  loading: boolean;
  members: DepartmentMemberLink[];
  membersQuery: string;
  pendingKey: SavingKey | null;
  roleDraft: DepartmentRoleDraft;
  roleEditorOpen: boolean;
  roleUsage: Record<number, number>;
  roles: DepartmentRole[];
  selectableEmployees: Array<{ id: number; name: string }>;
  selectedHeadId: number | null;
  selectedMemberId: number | null;
  userPerms: DepartmentUserPermissions;
  closeAddMember: () => void;
  closeDepartmentEditor: () => void;
  closeRoleEditor: () => void;
  openAddMember: () => void;
  openCreateRole: () => void;
  openDepartmentEditor: () => void;
  openEditRole: (role: DepartmentRole) => void;
  refreshPage: () => Promise<void>;
  saveDepartment: () => Promise<void>;
  saveRole: () => Promise<void>;
  setMembersQuery: (value: string) => void;
  setRoleDraft: (next: DepartmentRoleDraft | ((current: DepartmentRoleDraft) => DepartmentRoleDraft)) => void;
  setSelectedHeadId: (id: number | null) => void;
  setSelectedMemberId: (id: number | null) => void;
  submitAddMember: () => Promise<void>;
  submitHeadChange: () => Promise<void>;
  submitQuickHeadChange: (headId: number) => Promise<void>;
  submitHeadRemoval: () => Promise<void>;
  submitMemberRole: (employeeId: number, roleId: number | null) => Promise<void>;
  submitRemoveMember: (employeeId: number) => Promise<void>;
  submitRoleDelete: (role: DepartmentRole) => Promise<void>;
  updateDepartmentDraft: (patch: Partial<{ name: string; description: string }>) => void;
};

const EMPTY_USER_PERMS: DepartmentUserPermissions = {
  is_head: false,
  can_manage: false,
  can_change_head: false,
  can_assign_roles: false,
};

function getErrorMessage(error: unknown, fallback: string) {
  const raw = String((error as Error)?.message || fallback).trim();
  const prefix = "API Error:";
  if (!raw.startsWith(prefix)) return raw || fallback;

  const payload = raw.slice(prefix.length).trim();
  const jsonStart = payload.indexOf("{");
  if (jsonStart >= 0) {
    try {
      const parsed = JSON.parse(payload.slice(jsonStart)) as Record<string, unknown>;
      const detail = parsed.detail;
      if (typeof detail === "string" && detail.trim()) return detail;
      const firstEntry = Object.entries(parsed)[0];
      if (firstEntry) {
        const value = firstEntry[1];
        if (Array.isArray(value) && value[0]) return String(value[0]);
        if (typeof value === "string" && value.trim()) return value;
      }
    } catch {
      return fallback;
    }
  }

  return fallback;
}

function sortEmployeesByName(items: User[]) {
  return [...items].sort((a, b) => {
    const aName = `${a.last_name || ""} ${a.first_name || ""}`.trim();
    const bName = `${b.last_name || ""} ${b.first_name || ""}`.trim();
    return aName.localeCompare(bName, "ru");
  });
}

export function useDepartmentPage(departmentId: number): DepartmentPageController {
  const { user } = useUser();
  const currentUserId = user?.id ?? null;

  const [department, setDepartment] = useState<Department | null>(null);
  const [members, setMembers] = useState<DepartmentMemberLink[]>([]);
  const [roles, setRoles] = useState<DepartmentRole[]>([]);
  const [userPerms, setUserPerms] = useState<DepartmentUserPermissions | null>(null);
  const [allEmployees, setAllEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingKey, setPendingKey] = useState<SavingKey | null>(null);
  const [membersQuery, setMembersQuery] = useState("");

  const [editDepartmentOpen, setEditDepartmentOpen] = useState(false);
  const [departmentDraft, setDepartmentDraft] = useState({ name: "", description: "" });

  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);

  const [selectedHeadId, setSelectedHeadId] = useState<number | null>(null);

  const [roleEditorOpen, setRoleEditorOpen] = useState(false);
  const [roleDraft, setRoleDraft] = useState<DepartmentRoleDraft>({
    id: null,
    name: "",
  });

  const hydrateDepartmentDraft = useCallback((nextDepartment: Department | null) => {
    setDepartmentDraft({
      name: nextDepartment?.name || "",
      description: nextDepartment?.description || "",
    });
    setSelectedHeadId(nextDepartment?.head?.id ?? null);
  }, []);

  const loadEmployeesDirectory = useCallback(async () => {
    const employees = await loadAllPages<User>((params) => apiClient.getEmployees(params));
    setAllEmployees(sortEmployeesByName(employees.filter((employee) => employee.is_active)));
  }, []);

  const loadCore = useCallback(async () => {
    if (!departmentId || Number.isNaN(departmentId)) {
      setDepartment(null);
      setMembers([]);
      setRoles([]);
      setUserPerms(null);
      setAllEmployees([]);
      setError("Некорректный идентификатор отдела");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [
        departmentResponse,
        membersResponse,
        userPermsResponse,
        rolesResponse,
      ] = await Promise.all([
        apiClient.getDepartment(departmentId) as Promise<Department>,
        apiClient.getDepartmentMembers(departmentId) as Promise<PaginatedResponse<DepartmentMemberLink>>,
        apiClient.getDepartmentUserPerms(departmentId) as Promise<DepartmentUserPermissions>,
        apiClient.getDepartmentRoles({ department: departmentId, limit: 200 }) as Promise<PaginatedResponse<DepartmentRole> | DepartmentRole[]>,
      ]);

      const nextDepartment = departmentResponse;
      const nextMembers = (membersResponse.results || []).sort((a, b) => {
        const aIsHead = nextDepartment.head?.id === a.employee.id ? 1 : 0;
        const bIsHead = nextDepartment.head?.id === b.employee.id ? 1 : 0;
        if (aIsHead !== bIsHead) return bIsHead - aIsHead;
        const aName = `${a.employee.last_name || ""} ${a.employee.first_name || ""}`.trim();
        const bName = `${b.employee.last_name || ""} ${b.employee.first_name || ""}`.trim();
        return aName.localeCompare(bName, "ru");
      });
      const roleResults = Array.isArray(rolesResponse)
        ? rolesResponse
        : (rolesResponse.results || []);

      setDepartment(nextDepartment);
      setMembers(nextMembers);
      setRoles([...roleResults].sort((a, b) => a.name.localeCompare(b.name, "ru")));
      setUserPerms(userPermsResponse);
      hydrateDepartmentDraft(nextDepartment);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "Не удалось загрузить отдел"));
    } finally {
      setLoading(false);
    }
  }, [departmentId, hydrateDepartmentDraft]);

  useEffect(() => {
    void loadCore();
  }, [loadCore]);

  useEffect(() => {
    if (!userPerms || (!userPerms.can_manage && !userPerms.can_change_head)) {
      return;
    }
    if (allEmployees.length > 0) {
      return;
    }
    void loadEmployeesDirectory().catch((loadError) => {
      toast.error(getErrorMessage(loadError, "Не удалось загрузить сотрудников"));
    });
  }, [allEmployees.length, loadEmployeesDirectory, userPerms]);

  const filteredMembers = useMemo(() => {
    const q = membersQuery.trim().toLowerCase();

    return members.filter((item) => {
      if (!item.is_active) {
        return false;
      }

      if (!q) {
        return true;
      }

      const employeeName = `${item.employee.last_name || ""} ${item.employee.first_name || ""} ${item.employee.patronymic || ""}`
        .trim()
        .toLowerCase();
      const email = item.employee.email?.toLowerCase() || "";
      const position = item.employee.position?.name?.toLowerCase() || "";
      const roleName = item.role?.name?.toLowerCase() || "";

      return (
        employeeName.includes(q) ||
        email.includes(q) ||
        position.includes(q) ||
        roleName.includes(q)
      );
    });
  }, [members, membersQuery]);

  const selectableEmployees = useMemo(() => {
    const activeIds = new Set(
      members.filter((member) => member.is_active).map((member) => member.employee.id),
    );

    return allEmployees
      .filter((employee) => !activeIds.has(employee.id))
      .map((employee) => ({
        id: employee.id,
        name: `${employee.last_name || ""} ${employee.first_name || ""}`.trim() || employee.email,
      }));
  }, [allEmployees, members]);

  const headCandidates = useMemo(() => {
    return allEmployees.map((employee) => ({
      id: employee.id,
      name: `${employee.last_name || ""} ${employee.first_name || ""}`.trim() || employee.email,
    }));
  }, [allEmployees]);

  const roleUsage = useMemo(() => {
    return members.reduce<Record<number, number>>((acc, member) => {
      const roleId = member.role?.id;
      if (!roleId || !member.is_active) return acc;
      acc[roleId] = (acc[roleId] || 0) + 1;
      return acc;
    }, {});
  }, [members]);

  const refreshPage = useCallback(async () => {
    await loadCore();
  }, [loadCore]);

  const updateDepartmentDraft = useCallback((patch: Partial<{ name: string; description: string }>) => {
    setDepartmentDraft((current) => ({ ...current, ...patch }));
  }, []);

  const openDepartmentEditor = useCallback(() => {
    hydrateDepartmentDraft(department);
    setEditDepartmentOpen(true);
  }, [department, hydrateDepartmentDraft]);

  const closeDepartmentEditor = useCallback(() => {
    hydrateDepartmentDraft(department);
    setEditDepartmentOpen(false);
  }, [department, hydrateDepartmentDraft]);

  const saveDepartment = useCallback(async () => {
    if (!department) return;

    const name = departmentDraft.name.trim();
    if (!name) {
      toast.error("Укажите название отдела");
      return;
    }

    try {
      setPendingKey("department");
      const response = await apiClient.updateDepartment(department.id, {
        name,
        description: departmentDraft.description.trim(),
      }) as Department;
      setDepartment(response);
      hydrateDepartmentDraft(response);
      setEditDepartmentOpen(false);
      toast.success("Отдел обновлён");
    } catch (saveError) {
      toast.error(getErrorMessage(saveError, "Не удалось сохранить отдел"));
    } finally {
      setPendingKey(null);
    }
  }, [department, departmentDraft.description, departmentDraft.name, hydrateDepartmentDraft]);

  const openAddMember = useCallback(() => {
    setSelectedMemberId(null);
    setAddMemberOpen(true);
  }, []);

  const closeAddMember = useCallback(() => {
    setSelectedMemberId(null);
    setAddMemberOpen(false);
  }, []);

  const submitAddMember = useCallback(async () => {
    if (!department || !selectedMemberId) {
      toast.error("Выберите сотрудника");
      return;
    }

    try {
      setPendingKey("member");
      await apiClient.addDepartmentMember(department.id, selectedMemberId);
      await loadCore();
      setAddMemberOpen(false);
      setSelectedMemberId(null);
      toast.success("Сотрудник добавлен в отдел");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось добавить сотрудника"));
    } finally {
      setPendingKey(null);
    }
  }, [department, loadCore, selectedMemberId]);

  const submitHeadChange = useCallback(async () => {
    if (!department) return;

    try {
      setPendingKey("head");
      const response = await apiClient.setDepartmentHead(department.id, selectedHeadId) as Department;
      setDepartment(response);
      hydrateDepartmentDraft(response);
      await loadCore();
      toast.success(selectedHeadId ? "Руководитель назначен" : "Руководитель снят");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось изменить руководителя"));
    } finally {
      setPendingKey(null);
    }
  }, [department, hydrateDepartmentDraft, loadCore, selectedHeadId]);

  const submitQuickHeadChange = useCallback(async (headId: number) => {
    if (!department) return;

    try {
      setPendingKey("head");
      const response = await apiClient.setDepartmentHead(department.id, headId) as Department;
      setDepartment(response);
      hydrateDepartmentDraft(response);
      setSelectedHeadId(headId);
      await loadCore();
      toast.success("Руководитель назначен");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось изменить руководителя"));
    } finally {
      setPendingKey(null);
    }
  }, [department, hydrateDepartmentDraft, loadCore]);

  const submitHeadRemoval = useCallback(async () => {
    if (!department) return;

    try {
      setPendingKey("head");
      const response = await apiClient.setDepartmentHead(department.id, null) as Department;
      setDepartment(response);
      hydrateDepartmentDraft(response);
      setSelectedHeadId(null);
      await loadCore();
      toast.success("Руководитель снят");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось снять руководителя"));
    } finally {
      setPendingKey(null);
    }
  }, [department, hydrateDepartmentDraft, loadCore]);

  const submitMemberRole = useCallback(async (employeeId: number, roleId: number | null) => {
    if (!department) return;

    try {
      setPendingKey(`member-role-${employeeId}`);
      await apiClient.setDepartmentMemberRole(department.id, {
        employee_id: employeeId,
        role_id: roleId,
      });
      const nextRole = roles.find((role) => role.id === roleId) || null;
      setMembers((current) =>
        current.map((member) =>
          member.employee.id === employeeId
            ? { ...member, role: nextRole ? { id: nextRole.id, name: nextRole.name } : null }
            : member,
        ),
      );
      toast.success(roleId ? "Роль назначена" : "Роль снята");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось обновить роль участника"));
    } finally {
      setPendingKey(null);
    }
  }, [department, roles]);

  const submitRemoveMember = useCallback(async (employeeId: number) => {
    if (!department) return;
    if (!window.confirm("Убрать сотрудника из отдела?")) return;

    try {
      setPendingKey(`member-remove-${employeeId}`);
      await apiClient.removeDepartmentMember(department.id, employeeId);
      await loadCore();
      toast.success("Сотрудник убран из отдела");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось убрать сотрудника"));
    } finally {
      setPendingKey(null);
    }
  }, [department, loadCore]);

  const openCreateRole = useCallback(() => {
    setRoleDraft({ id: null, name: "" });
    setRoleEditorOpen(true);
  }, []);

  const openEditRole = useCallback((role: DepartmentRole) => {
    setRoleDraft({
      id: role.id,
      name: role.name,
    });
    setRoleEditorOpen(true);
  }, []);

  const closeRoleEditor = useCallback(() => {
    setRoleEditorOpen(false);
    setRoleDraft({ id: null, name: "" });
  }, []);

  const saveRole = useCallback(async () => {
    if (!department) return;

    const name = roleDraft.name.trim();
    if (!name) {
      toast.error("Укажите название роли");
      return;
    }

    try {
      setPendingKey("role");
      if (roleDraft.id) {
        await apiClient.updateDepartmentRole(roleDraft.id, {
          name,
        });
        toast.success("Роль обновлена");
      } else {
        await apiClient.createDepartmentRole({
          department: department.id,
          name,
        });
        toast.success("Роль создана");
      }
      await loadCore();
      closeRoleEditor();
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось сохранить роль"));
    } finally {
      setPendingKey(null);
    }
  }, [closeRoleEditor, department, loadCore, roleDraft.id, roleDraft.name]);

  const submitRoleDelete = useCallback(async (role: DepartmentRole) => {
    if (!window.confirm(`Удалить роль «${role.name}»?`)) return;

    try {
      setPendingKey(`role-delete-${role.id}`);
      await apiClient.deleteDepartmentRole(role.id);
      await loadCore();
      toast.success("Роль удалена");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось удалить роль"));
    } finally {
      setPendingKey(null);
    }
  }, [loadCore]);

  return {
    addMemberOpen,
    allEmployees,
    currentUserId,
    department,
    departmentDraft,
    departmentId,
    editDepartmentOpen,
    error,
    filteredMembers,
    headCandidates,
    loading,
    members,
    membersQuery,
    pendingKey,
    roleDraft,
    roleEditorOpen,
    roleUsage,
    roles,
    selectableEmployees,
    selectedHeadId,
    selectedMemberId,
    userPerms: userPerms || EMPTY_USER_PERMS,
    closeAddMember,
    closeDepartmentEditor,
    closeRoleEditor,
    openAddMember,
    openCreateRole,
    openDepartmentEditor,
    openEditRole,
    refreshPage,
    saveDepartment,
    saveRole,
    setMembersQuery,
    setRoleDraft,
    setSelectedHeadId,
    setSelectedMemberId,
    submitAddMember,
    submitHeadChange,
    submitQuickHeadChange,
    submitHeadRemoval,
    submitMemberRole,
    submitRemoveMember,
    submitRoleDelete,
    updateDepartmentDraft,
  };
}
