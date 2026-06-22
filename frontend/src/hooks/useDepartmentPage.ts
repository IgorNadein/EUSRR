"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { extractDepartmentApiErrorMessage } from "@/components/departments/api-error";
import { getDepartmentMemberModalError } from "@/components/departments/member-modal-state";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { loadAllPages } from "@/lib/shared";
import type {
  Department,
  DepartmentMemberLink,
  DepartmentPermissionChoice,
  DepartmentRole,
  DepartmentUserPermissions,
  PaginatedResponse,
  User,
} from "@/types/api";

type DepartmentRoleDraft = {
  id: number | null;
  name: string;
  permissionIds: number[];
};

type DepartmentMemberModalMode = "add" | "assignRole";

type SavingKey =
  | "department"
  | "department-delete"
  | "head"
  | "member"
  | "role"
  | `member-role-${number}`
  | `member-remove-${number}`
  | `role-delete-${number}`;

export type DepartmentPageController = {
  addMemberOpen: boolean;
  allEmployees: User[];
  assignableEmployees: User[];
  currentUserId: number | null;
  department: Department | null;
  departmentDraft: { name: string; description: string };
  departmentId: number;
  editDepartmentOpen: boolean;
  employeesDirectoryError: string | null;
  error: string | null;
  filteredMembers: DepartmentMemberLink[];
  headCandidates: Array<{ id: number; name: string }>;
  employeesDirectoryLoading: boolean;
  loading: boolean;
  memberModalMode: DepartmentMemberModalMode;
  memberModalError: string | null;
  members: DepartmentMemberLink[];
  pendingKey: SavingKey | null;
  roleDraft: DepartmentRoleDraft;
  roleEditorOpen: boolean;
  rolePermissionChoices: DepartmentPermissionChoice[];
  rolePermissionChoicesLoading: boolean;
  roleUsage: Record<number, number>;
  roles: DepartmentRole[];
  selectableEmployees: User[];
  selectedHeadId: number | null;
  selectedMemberId: number | null;
  selectedRoleId: number | null;
  userPerms: DepartmentUserPermissions;
  closeAddMember: () => void;
  closeDepartmentEditor: () => void;
  closeRoleEditor: () => void;
  openAddMember: () => void;
  openAssignRoleModal: () => void;
  openCreateRole: () => void;
  openDepartmentEditor: () => void;
  openEditRole: (role: DepartmentRole) => void;
  reloadEmployeesDirectory: () => Promise<void>;
  refreshPage: () => Promise<void>;
  saveDepartment: () => Promise<void>;
  saveRole: () => Promise<void>;
  setRoleDraft: (next: DepartmentRoleDraft | ((current: DepartmentRoleDraft) => DepartmentRoleDraft)) => void;
  setMemberModalMode: (mode: DepartmentMemberModalMode) => void;
  setSelectedHeadId: (id: number | null) => void;
  setSelectedMemberId: (id: number | null) => void;
  setSelectedRoleId: (id: number | null) => void;
  submitAddMember: () => Promise<void>;
  submitDeleteDepartment: () => Promise<boolean>;
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
  can_publish_posts: false,
  can_manage_feed: false,
};

const getErrorMessage = extractDepartmentApiErrorMessage;

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
  const [employeesDirectoryLoading, setEmployeesDirectoryLoading] = useState(false);
  const [employeesDirectoryError, setEmployeesDirectoryError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingKey, setPendingKey] = useState<SavingKey | null>(null);

  const [editDepartmentOpen, setEditDepartmentOpen] = useState(false);
  const [departmentDraft, setDepartmentDraft] = useState({ name: "", description: "" });

  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [memberModalMode, setMemberModalMode] = useState<DepartmentMemberModalMode>("add");
  const [memberModalError, setMemberModalError] = useState<string | null>(null);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);

  const [selectedHeadId, setSelectedHeadId] = useState<number | null>(null);

  const [roleEditorOpen, setRoleEditorOpen] = useState(false);
  const [roleDraft, setRoleDraft] = useState<DepartmentRoleDraft>({
    id: null,
    name: "",
    permissionIds: [],
  });
  const [rolePermissionChoices, setRolePermissionChoices] = useState<DepartmentPermissionChoice[]>([]);
  const [rolePermissionChoicesLoading, setRolePermissionChoicesLoading] = useState(false);

  const hydrateDepartmentDraft = useCallback((nextDepartment: Department | null) => {
    setDepartmentDraft({
      name: nextDepartment?.name || "",
      description: nextDepartment?.description || "",
    });
    setSelectedHeadId(nextDepartment?.head?.id ?? null);
  }, []);

  const loadEmployeesDirectory = useCallback(async () => {
    setEmployeesDirectoryLoading(true);
    setEmployeesDirectoryError(null);
    try {
      const employees = await loadAllPages<User>((params) =>
        apiClient.getEmployees({ ...params, is_active: true }),
      );
      setAllEmployees(sortEmployeesByName(employees));
    } catch (loadError) {
      const message = getErrorMessage(loadError, "Не удалось загрузить сотрудников");
      setEmployeesDirectoryError(message);
      throw loadError;
    } finally {
      setEmployeesDirectoryLoading(false);
    }
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
    if (
      !userPerms ||
      (!userPerms.can_manage &&
        !userPerms.can_change_head &&
        !userPerms.can_assign_roles)
    ) {
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
    return members.filter((item) => {
      if (!item.is_active) {
        return false;
      }
      return true;
    });
  }, [members]);

  const selectableEmployees = useMemo(() => {
    const activeIds = new Set(
      members.filter((member) => member.is_active).map((member) => member.employee.id),
    );

    return allEmployees.filter((employee) => !activeIds.has(employee.id));
  }, [allEmployees, members]);

  const assignableEmployees = useMemo(() => {
    return allEmployees;
  }, [allEmployees]);

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

  const reloadEmployeesDirectory = useCallback(async () => {
    await loadEmployeesDirectory();
  }, [loadEmployeesDirectory]);

  const loadRolePermissionChoices = useCallback(async () => {
    if (rolePermissionChoices.length > 0 || rolePermissionChoicesLoading) return;

    try {
      setRolePermissionChoicesLoading(true);
      const response = await apiClient.getDepartmentRolePermChoices() as PaginatedResponse<DepartmentPermissionChoice> | { results?: DepartmentPermissionChoice[] } | DepartmentPermissionChoice[];
      const results = Array.isArray(response) ? response : (response.results || []);
      setRolePermissionChoices([...results].sort((a, b) => a.name.localeCompare(b.name, "ru")));
    } catch (loadError) {
      toast.error(getErrorMessage(loadError, "Не удалось загрузить права ролей"));
    } finally {
      setRolePermissionChoicesLoading(false);
    }
  }, [rolePermissionChoices.length, rolePermissionChoicesLoading]);

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
    setMemberModalMode("add");
    setMemberModalError(null);
    setSelectedMemberId(null);
    setSelectedRoleId(null);
    setAddMemberOpen(true);
    if (allEmployees.length === 0) {
      void loadEmployeesDirectory().catch((loadError) => {
        toast.error(getErrorMessage(loadError, "Не удалось загрузить сотрудников"));
      });
    }
  }, [allEmployees.length, loadEmployeesDirectory]);

  const openAssignRoleModal = useCallback(() => {
    setMemberModalMode("assignRole");
    setMemberModalError(null);
    setSelectedMemberId(null);
    setSelectedRoleId(null);
    setAddMemberOpen(true);
    if (allEmployees.length === 0) {
      void loadEmployeesDirectory().catch((loadError) => {
        toast.error(getErrorMessage(loadError, "Не удалось загрузить сотрудников"));
      });
    }
  }, [allEmployees.length, loadEmployeesDirectory]);

  const closeAddMember = useCallback(() => {
    setMemberModalError(null);
    setSelectedMemberId(null);
    setSelectedRoleId(null);
    setMemberModalMode("add");
    setAddMemberOpen(false);
  }, []);

  const selectMember = useCallback((id: number | null) => {
    setMemberModalError(null);
    setSelectedMemberId(id);
  }, []);

  const selectRole = useCallback((id: number | null) => {
    setMemberModalError(null);
    setSelectedRoleId(id);
  }, []);

  const submitAddMember = useCallback(async () => {
    if (!department || !selectedMemberId) {
      toast.error("Выберите сотрудника");
      return;
    }

    if (memberModalMode === "assignRole" && !selectedRoleId) {
      toast.error("Выберите роль");
      return;
    }

    try {
      setPendingKey("member");
      if (memberModalMode === "add") {
        await apiClient.addDepartmentMember(department.id, selectedMemberId);
        if (selectedRoleId && userPerms?.can_assign_roles) {
          await apiClient.setDepartmentMemberRole(department.id, {
            employee_id: selectedMemberId,
            role_id: selectedRoleId,
          });
        }
      } else {
        await apiClient.setDepartmentMemberRole(department.id, {
          employee_id: selectedMemberId,
          role_id: selectedRoleId,
        });
      }
      await loadCore();
      setAddMemberOpen(false);
      setMemberModalError(null);
      setSelectedMemberId(null);
      setSelectedRoleId(null);
      setMemberModalMode("add");
      toast.success(
        memberModalMode === "add"
          ? "Сотрудник добавлен в отдел"
          : "Роль назначена сотруднику",
      );
    } catch (submitError) {
      const message = getErrorMessage(
        submitError,
        memberModalMode === "add"
          ? "Не удалось добавить сотрудника"
          : "Не удалось назначить роль сотруднику",
      );
      const inlineMessage = getDepartmentMemberModalError(
        message,
        memberModalMode,
      );
      if (inlineMessage) {
        setMemberModalError(inlineMessage);
      } else {
        toast.error(message);
      }
    } finally {
      setPendingKey(null);
    }
  }, [
    department,
    loadCore,
    memberModalMode,
    selectedMemberId,
    selectedRoleId,
    userPerms,
  ]);

  const submitDeleteDepartment = useCallback(async () => {
    if (!department) return false;
    if (!window.confirm(`Удалить отдел «${department.name}»?`)) return false;

    try {
      setPendingKey("department-delete");
      await apiClient.deleteDepartment(department.id);
      toast.success("Отдел удалён");
      return true;
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось удалить отдел"));
      return false;
    } finally {
      setPendingKey(null);
    }
  }, [department]);

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
    setRoleDraft({ id: null, name: "", permissionIds: [] });
    setRoleEditorOpen(true);
    void loadRolePermissionChoices();
  }, [loadRolePermissionChoices]);

  const openEditRole = useCallback((role: DepartmentRole) => {
    setRoleDraft({
      id: role.id,
      name: role.name,
      permissionIds: [...(role.permissions || [])],
    });
    setRoleEditorOpen(true);
    void loadRolePermissionChoices();
  }, [loadRolePermissionChoices]);

  const closeRoleEditor = useCallback(() => {
    setRoleEditorOpen(false);
    setRoleDraft({ id: null, name: "", permissionIds: [] });
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
          scoped_permissions: roleDraft.permissionIds,
        });
        toast.success("Роль обновлена");
      } else {
        await apiClient.createDepartmentRole({
          department: department.id,
          name,
          scoped_permissions: roleDraft.permissionIds,
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
  }, [closeRoleEditor, department, loadCore, roleDraft.id, roleDraft.name, roleDraft.permissionIds]);

  const submitRoleDelete = useCallback(async (role: DepartmentRole) => {
    const activeAssignmentsCount = role.active_assignments_count ?? roleUsage[role.id] ?? 0;
    const message = activeAssignmentsCount > 0
      ? `Удалить роль «${role.name}»? Она выдана сотрудникам: ${activeAssignmentsCount}. Назначения будут сняты.`
      : `Удалить роль «${role.name}»?`;
    if (!window.confirm(message)) return;

    try {
      setPendingKey(`role-delete-${role.id}`);
      await apiClient.deleteDepartmentRole(role.id, { force: activeAssignmentsCount > 0 });
      await loadCore();
      toast.success("Роль удалена");
    } catch (submitError) {
      toast.error(getErrorMessage(submitError, "Не удалось удалить роль"));
    } finally {
      setPendingKey(null);
    }
  }, [loadCore, roleUsage]);

  return {
    addMemberOpen,
    allEmployees,
    assignableEmployees,
    currentUserId,
    department,
    departmentDraft,
    departmentId,
    editDepartmentOpen,
    employeesDirectoryError,
    employeesDirectoryLoading,
    error,
    filteredMembers,
    headCandidates,
    loading,
    memberModalMode,
    memberModalError,
    members,
    pendingKey,
    roleDraft,
    roleEditorOpen,
    rolePermissionChoices,
    rolePermissionChoicesLoading,
    roleUsage,
    roles,
    selectableEmployees,
    selectedHeadId,
    selectedMemberId,
    selectedRoleId,
    userPerms: userPerms || EMPTY_USER_PERMS,
    closeAddMember,
    closeDepartmentEditor,
    closeRoleEditor,
    openAddMember,
    openAssignRoleModal,
    openCreateRole,
    openDepartmentEditor,
    openEditRole,
    reloadEmployeesDirectory,
    refreshPage,
    saveDepartment,
    saveRole,
    setRoleDraft,
    setMemberModalMode,
    setSelectedHeadId,
    setSelectedMemberId: selectMember,
    setSelectedRoleId: selectRole,
    submitAddMember,
    submitDeleteDepartment,
    submitHeadChange,
    submitQuickHeadChange,
    submitHeadRemoval,
    submitMemberRole,
    submitRemoveMember,
    submitRoleDelete,
    updateDepartmentDraft,
  };
}
