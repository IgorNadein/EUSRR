"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import {
  ArrowLeft,
  Building2,
  Check,
  ChevronDown,
  ChevronRight,
  Crown,
  PencilLine,
  Plus,
  Search,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import {
  DEPARTMENT_MEMBERS_EMPTY_STATE_CLASSNAME,
  getDepartmentMembersListClassName,
} from "@/components/departments/layout";
import {
  getDepartmentMemberModalHelperText,
  getDepartmentMemberModalItems,
  getDepartmentMemberModalPlaceholder,
  getDepartmentMemberModalSubmitLabel,
  getDepartmentMemberModalTitle,
  isDepartmentMemberModalSubmitDisabled,
} from "@/components/departments/member-modal-state";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { Modal } from "@/components/ui/Modal";
import { useDepartmentPage } from "@/hooks/useDepartmentPage";
import { displayUserName, userProfileLink } from "@/lib/shared";
import type { DepartmentMemberLink, User } from "@/types/api";

type DepartmentMemberModalMode = "add" | "assignRole";

function MetaChip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "warning";
}) {
  const className =
    tone === "accent"
      ? "app-selected app-accent-text"
      : tone === "warning"
        ? "app-feedback-warning"
        : "app-badge";

  return (
    <span
      className={`${className} inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium`}
    >
      {children}
    </span>
  );
}

function DepartmentMemberRow({
  canAssignRoles,
  canChangeHead,
  canManage,
  currentHeadId,
  currentUserId,
  member,
  pendingKey,
  roleOptions,
  onAssignRole,
  onCreateRole,
  onRemoveMember,
  onSetHead,
  onToggleRoleMenu,
  roleMenuOpenForId,
  roleMenuRef,
}: {
  canAssignRoles: boolean;
  canChangeHead: boolean;
  canManage: boolean;
  currentHeadId?: number | null;
  currentUserId?: number | null;
  member: DepartmentMemberLink;
  pendingKey: string | null;
  roleOptions: Array<{ id: number; name: string }>;
  onAssignRole: (employeeId: number, roleId: number | null) => Promise<void>;
  onCreateRole: () => void;
  onRemoveMember: (employeeId: number) => Promise<void>;
  onSetHead: (employeeId: number) => Promise<void>;
  onToggleRoleMenu: (employeeId: number | null) => void;
  roleMenuOpenForId: number | null;
  roleMenuRef: RefObject<HTMLDivElement | null>;
}) {
  const isHead = currentHeadId === member.employee.id;
  const isRemoving = pendingKey === `member-remove-${member.employee.id}`;
  const isRoleBusy = pendingKey === `member-role-${member.employee.id}`;
  const subtitle = member.employee.position?.name || null;
  const managementMode = canAssignRoles || canChangeHead || canManage;
  const roleLabel = member.role?.name || "Без роли";
  const isRoleMenuOpen = roleMenuOpenForId === member.employee.id;
  const personName = displayUserName(member.employee);
  const profileLink = userProfileLink(member.employee, currentUserId);
  const fallback = (
    member.employee.first_name?.[0] ||
    member.employee.last_name?.[0] ||
    member.employee.email?.[0] ||
    "?"
  ).toUpperCase();

  if (!managementMode) {
    const personBubble = (
      <span className="app-badge inline-flex max-w-full items-center gap-2 rounded-full px-2 py-1.5">
        <RequestAvatar
          alt={personName}
          fallback={fallback}
          size="lg"
          src={member.employee.avatar}
        />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-[var(--foreground)]">
            {personName}
          </span>
          {subtitle ? (
            <span className="app-text-muted block truncate text-xs">{subtitle}</span>
          ) : null}
        </span>
        {member.role ? (
          <span className="app-surface inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-xs font-medium text-[var(--muted-foreground)]">
            <span className="truncate">{roleLabel}</span>
          </span>
        ) : null}
        {isHead ? (
          <MetaChip tone="warning">
            <Crown size={12} />
          </MetaChip>
        ) : null}
      </span>
    );

    return (
      <>
        {profileLink ? (
          <Link href={profileLink} className="min-w-0 max-w-full">
            {personBubble}
          </Link>
        ) : (
          <span className="min-w-0 max-w-full">{personBubble}</span>
        )}
       
      </>
    );
  }

  return (
    <article className="flex max-w-full flex-wrap items-center gap-2">
      <span className="app-badge inline-flex max-w-full items-center gap-2 rounded-full px-2 py-1.5">
        {profileLink ? (
          <Link href={profileLink} className="inline-flex min-w-0 items-center gap-2">
            <RequestAvatar
              alt={personName}
              fallback={fallback}
              size="lg"
              src={member.employee.avatar}
            />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-[var(--foreground)]">
                {personName}
              </span>
              {subtitle ? (
                <span className="app-text-muted block truncate text-xs">{subtitle}</span>
              ) : null}
            </span>
          </Link>
        ) : (
          <span className="inline-flex min-w-0 items-center gap-2">
            <RequestAvatar
              alt={personName}
              fallback={fallback}
              size="lg"
              src={member.employee.avatar}
            />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-[var(--foreground)]">
                {personName}
              </span>
              {subtitle ? (
                <span className="app-text-muted block truncate text-xs">{subtitle}</span>
              ) : null}
            </span>
          </span>
        )}

        {canAssignRoles ? (
          <div className="relative" ref={isRoleMenuOpen ? roleMenuRef : null}>
            <button
              type="button"
              onClick={() => onToggleRoleMenu(isRoleMenuOpen ? null : member.employee.id)}
              aria-expanded={isRoleMenuOpen}
              className="app-surface inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition hover:border-[var(--border-strong)]"
            >
              <span className="truncate">{roleLabel}</span>
              <ChevronDown
                size={12}
                className={`shrink-0 transition-transform ${isRoleMenuOpen ? "rotate-180" : ""}`}
              />
            </button>

            {isRoleMenuOpen ? (
              <div className="app-menu absolute left-0 top-[calc(100%+0.5rem)] z-30 min-w-[220px] rounded-xl py-1.5">
                <div className="px-3 pb-1 pt-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
                  Роль участника
                </div>
                <div className="py-1">
                  {roleOptions.map((role) => {
                    const isSelected = member.role?.id === role.id;
                    return (
                      <button
                        key={role.id}
                        type="button"
                        onClick={() => {
                          onToggleRoleMenu(null);
                          void onAssignRole(member.employee.id, role.id);
                        }}
                        disabled={isRoleBusy}
                        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                      >
                        <span className="truncate">{role.name}</span>
                        {isSelected ? <Check size={14} className="app-accent-text shrink-0" /> : null}
                      </button>
                    );
                  })}

                  {member.role ? (
                    <div className="app-divider my-1 border-t" />
                  ) : null}

                  {member.role ? (
                    <button
                      type="button"
                      onClick={() => {
                        onToggleRoleMenu(null);
                        void onAssignRole(member.employee.id, null);
                      }}
                      disabled={isRoleBusy}
                      className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                    >
                      <span>Снять роль</span>
                      <Trash2 size={14} className="shrink-0 text-[var(--danger-foreground)]" />
                    </button>
                  ) : null}

                  <div className="app-divider my-1 border-t" />
                  <button
                    type="button"
                    onClick={() => {
                      onToggleRoleMenu(null);
                      onCreateRole();
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  >
                    <Plus size={14} className="app-text-muted shrink-0" />
                    Создать роль
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : member.role ? (
          <span className="app-surface inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-xs font-medium">
            <span className="truncate">{roleLabel}</span>
          </span>
        ) : null}

        {isHead ? (
          <MetaChip tone="warning">
            <Crown size={12} />
          </MetaChip>
        ) : null}

        {canChangeHead && !isHead ? (
          <button
            type="button"
            onClick={() => void onSetHead(member.employee.id)}
            aria-label="Назначить руководителем"
            title="Назначить руководителем"
            className="app-action-secondary inline-flex h-7 w-7 items-center justify-center rounded-full"
          >
            <Crown size={13} />
          </button>
        ) : null}

        {canManage && !isHead ? (
          <button
            type="button"
            onClick={() => void onRemoveMember(member.employee.id)}
            disabled={isRemoving}
            aria-label="Убрать из отдела"
            title="Убрать из отдела"
            className="app-action-danger inline-flex h-7 w-7 items-center justify-center rounded-full disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        ) : null}
      </span>
    </article>
  );
}

function DepartmentEditorModal({
  draft,
  isOpen,
  loading,
  onChange,
  onClose,
  onSave,
}: {
  draft: { name: string; description: string };
  isOpen: boolean;
  loading: boolean;
  onChange: (patch: Partial<{ name: string; description: string }>) => void;
  onClose: () => void;
  onSave: () => Promise<void>;
}) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Редактирование отдела"
      size="md"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="app-action-secondary rounded-lg px-4 py-2 text-sm"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={loading}
            className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          >
            Сохранить
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <section className="app-surface-muted rounded-xl p-4">
          <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
            Название отдела *
          </label>
          <input
            value={draft.name}
            onChange={(event) => onChange({ name: event.target.value })}
            className="app-input w-full rounded-lg px-3 py-2 text-sm"
            placeholder="Например, Отдел закупок"
          />
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
            Описание
          </label>
          <textarea
            value={draft.description}
            onChange={(event) => onChange({ description: event.target.value })}
            rows={4}
            className="app-input w-full rounded-xl px-3 py-2 text-sm"
            placeholder="Коротко опиши задачи и зону ответственности отдела."
          />
        </section>
      </div>
    </Modal>
  );
}

function DepartmentMembersEmptyState() {
  return (
    <div className={DEPARTMENT_MEMBERS_EMPTY_STATE_CLASSNAME}>
      <Users size={24} className="app-text-muted mx-auto mb-3" />
      <p className="text-sm font-medium text-[var(--foreground)]">
        Участники не найдены
      </p>
      <p className="app-text-muted mt-2 text-sm">
        Измени поисковый запрос.
      </p>
    </div>
  );
}

function AddMemberModal({
  canAssignRoles,
  directoryError,
  isOpen,
  items,
  loading,
  mode,
  optionsLoading,
  onClose,
  onCreateRole,
  onRetryEmployees,
  onSave,
  onSelect,
  onSelectRole,
  roleOptions,
  selectedId,
  selectedRoleId,
}: {
  canAssignRoles: boolean;
  directoryError: string | null;
  isOpen: boolean;
  items: User[];
  loading: boolean;
  mode: DepartmentMemberModalMode;
  optionsLoading: boolean;
  onClose: () => void;
  onCreateRole: () => void;
  onRetryEmployees: () => Promise<void>;
  onSave: () => Promise<void>;
  onSelect: (id: number | null) => void;
  onSelectRole: (id: number | null) => void;
  roleOptions: Array<{ id: number; name: string }>;
  selectedId: number | null;
  selectedRoleId: number | null;
}) {
  const [query, setQuery] = useState("");
  const handleClose = () => {
    setQuery("");
    onClose();
  };

  const helperText = getDepartmentMemberModalHelperText(
    mode,
    optionsLoading,
    items.length,
  );
  const selectDisabled = optionsLoading || !!directoryError || items.length === 0;
  const submitDisabled = isDepartmentMemberModalSubmitDisabled({
    loading,
    mode,
    selectedEmployeeId: selectedId,
    selectedRoleId,
  });
  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return items;

    return items.filter((employee) => {
      const personName = displayUserName(employee).toLowerCase();
      const email = (employee.email || "").toLowerCase();
      const position = (employee.position?.name || "").toLowerCase();
      return (
        personName.includes(normalizedQuery) ||
        email.includes(normalizedQuery) ||
        position.includes(normalizedQuery)
      );
    });
  }, [items, query]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={getDepartmentMemberModalTitle(mode)}
      size="md"
      className="overflow-visible"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={handleClose}
            className="app-action-secondary rounded-lg px-4 py-2 text-sm"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={submitDisabled}
            className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          >
            {getDepartmentMemberModalSubmitLabel(mode)}
          </button>
        </div>
      }
    >
      <section className="app-surface-muted space-y-4 rounded-xl p-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2.5">
            <Search size={16} className="app-text-muted shrink-0" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={getDepartmentMemberModalPlaceholder(mode, optionsLoading)}
              disabled={selectDisabled}
              className="min-w-0 flex-1 bg-transparent text-sm text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)] disabled:cursor-not-allowed"
            />
          </div>

          <div className="flex items-center justify-between px-1 text-xs">
            <span className="app-text-muted">
              {optionsLoading ? "Загружаем сотрудников..." : `Найдено: ${filteredItems.length}`}
            </span>
            <span className="app-accent-text font-medium">
              Выбрано: {selectedId ? 1 : 0}
            </span>
          </div>

          <div className="app-surface max-h-72 space-y-2 overflow-y-auto rounded-2xl p-2">
            {!directoryError && !optionsLoading && filteredItems.length > 0 ? (
              filteredItems.map((employee) => {
                const isSelected = selectedId === employee.id;
                const personName = displayUserName(employee);
                const fallback = (
                  employee.first_name?.[0] ||
                  employee.last_name?.[0] ||
                  employee.email?.[0] ||
                  "?"
                ).toUpperCase();

                return (
                  <button
                    key={employee.id}
                    type="button"
                    onClick={() => onSelect(isSelected ? null : employee.id)}
                    className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${
                      isSelected
                        ? "app-selected"
                        : "app-surface-muted hover:bg-[var(--surface-tertiary)]"
                    }`}
                  >
                    <RequestAvatar
                      alt={personName}
                      fallback={fallback}
                      size="lg"
                      src={employee.avatar}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-[var(--foreground)]">
                        {personName}
                      </div>
                      <div className="truncate text-xs text-[var(--muted-foreground)]">
                        {employee.email || employee.position?.name || "Сотрудник"}
                      </div>
                    </div>
                    <div
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition ${
                        isSelected
                          ? "border-[color:var(--accent-primary)] bg-[var(--accent-primary)] text-white"
                          : "border-[color:var(--border-strong)] text-transparent"
                      }`}
                      aria-hidden="true"
                    >
                      <Check size={14} />
                    </div>
                  </button>
                );
              })
            ) : !directoryError && !optionsLoading ? (
              <div className="app-surface-muted rounded-xl px-3 py-6 text-center">
                <p className="text-sm font-medium text-[var(--foreground)]">Ничего не найдено</p>
                <p className="app-text-muted mt-1 text-xs">
                  Попробуй изменить запрос или очистить поиск.
                </p>
              </div>
            ) : null}
          </div>
        </div>

        {directoryError ? (
          <div className="app-feedback-danger rounded-xl p-3 text-sm">
            <p>{directoryError}</p>
            <button
              type="button"
              onClick={() => void onRetryEmployees()}
              className="app-action-secondary mt-3 inline-flex rounded-lg px-3 py-2 text-sm"
            >
              Повторить загрузку
            </button>
          </div>
        ) : null}

        {canAssignRoles && !directoryError ? (
          <div className="space-y-3">
            <SearchableSelectSingle
              label={mode === "assignRole" ? "Роль *" : "Роль"}
              items={roleOptions}
              selectedId={selectedRoleId}
              onSelect={onSelectRole}
              placeholder={
                roleOptions.length
                  ? "Выберите роль"
                  : "Сначала создайте роль отдела"
              }
              disabled={loading || roleOptions.length === 0}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="app-text-muted text-sm">
                {mode === "add"
                  ? "Роль можно назначить сразу при добавлении, но это необязательно."
                  : "Роль можно выдать любому активному сотруднику, даже вне состава отдела."}
              </p>
              <button
                type="button"
                onClick={onCreateRole}
                className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
              >
                <Plus size={14} />
                Создать роль
              </button>
            </div>
          </div>
        ) : null}

        {!directoryError && helperText ? (
          <p className="app-text-muted mt-3 text-sm">
            {helperText}
          </p>
        ) : null}
      </section>
    </Modal>
  );
}

function RoleEditorModal({
  isOpen,
  loading,
  onClose,
  onDraftChange,
  onSave,
  roleDraft,
}: {
  isOpen: boolean;
  loading: boolean;
  onClose: () => void;
  onDraftChange: (
    next:
      | { id: number | null; name: string }
      | ((current: { id: number | null; name: string }) => {
          id: number | null;
          name: string;
        }),
  ) => void;
  onSave: () => Promise<void>;
  roleDraft: { id: number | null; name: string };
}) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={roleDraft.id ? "Переименование роли" : "Новая роль отдела"}
      size="md"
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="app-action-secondary rounded-lg px-4 py-2 text-sm"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={loading}
            className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          >
            {roleDraft.id ? "Сохранить" : "Создать"}
          </button>
        </div>
      }
    >
      <section className="app-surface-muted rounded-xl p-4">
        <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
          Название роли *
        </label>
        <input
          value={roleDraft.name}
          onChange={(event) =>
            onDraftChange((current) => ({
              ...current,
              name: event.target.value,
            }))
          }
          className="app-input w-full rounded-lg px-3 py-2 text-sm"
          placeholder="Например, Координатор отдела"
        />
        <p className="app-text-muted mt-3 text-sm">
          Роль нужна для аккуратного описания состава отдела и назначения участникам.
        </p>
      </section>
    </Modal>
  );
}

export default function DepartmentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const departmentId = Number(params?.id);
  const h = useDepartmentPage(departmentId);
  const [managementMode, setManagementMode] = useState(false);
  const [roleMenuOpenForId, setRoleMenuOpenForId] = useState<number | null>(null);
  const roleMenuRef = useRef<HTMLDivElement | null>(null);
  const [departmentMenuOpen, setDepartmentMenuOpen] = useState(false);
  const departmentMenuRef = useRef<HTMLDivElement | null>(null);

  const activeMembersCount = h.members.filter((member) => member.is_active).length;
  const roleOptions = h.roles.map((role) => ({ id: role.id, name: role.name }));
  const canUseManagementMode =
    h.userPerms.can_manage ||
    h.userPerms.can_change_head ||
    h.userPerms.can_assign_roles;

  const isManagementMode = canUseManagementMode && managementMode;

  useEffect(() => {
    if (roleMenuOpenForId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (roleMenuRef.current && !roleMenuRef.current.contains(event.target as Node)) {
        setRoleMenuOpenForId(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setRoleMenuOpenForId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [roleMenuOpenForId]);

  useEffect(() => {
    if (!departmentMenuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (departmentMenuRef.current && !departmentMenuRef.current.contains(event.target as Node)) {
        setDepartmentMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDepartmentMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [departmentMenuOpen]);

  return (
    <AppShell>
      <div className="space-y-6">
        <Link
          href="/departments"
          className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
        >
          <ArrowLeft size={14} />
          К списку отделов
        </Link>

        {h.loading ? (
          <div className="app-surface rounded-2xl p-8 text-center">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка отдела...</p>
          </div>
        ) : h.error ? (
          <div className="app-feedback-danger rounded-2xl p-6 text-center">
            <p className="text-sm">{h.error}</p>
          </div>
        ) : h.department ? (
          <>
            <section className="app-surface rounded-2xl p-5">
              <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <MetaChip tone="accent">
                      <Building2 size={12} />
                      Отдел
                    </MetaChip>
                    <MetaChip>
                      <Users size={12} />
                      {activeMembersCount} участников
                    </MetaChip>
                    <MetaChip>{h.roles.length} ролей</MetaChip>
                    {isManagementMode ? (
                      <MetaChip tone="warning">Режим управления</MetaChip>
                    ) : null}
                  </div>
                  <h1 className="text-2xl font-semibold text-[var(--foreground)] sm:text-3xl">
                    {h.department.name}
                  </h1>
                  <p className="app-text-muted mt-2 text-sm">
                    {h.department.description}
                  </p>
                </div>
                {(canUseManagementMode || h.userPerms.can_manage) ? (
                  <div ref={departmentMenuOpen ? departmentMenuRef : null} className="relative shrink-0">
                    <button
                      type="button"
                      onClick={() => setDepartmentMenuOpen((current) => !current)}
                      className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                      title="Действия с отделом"
                      aria-label="Действия с отделом"
                      aria-expanded={departmentMenuOpen}
                      aria-haspopup="menu"
                    >
                      <ChevronRight
                        size={15}
                        className={`transition-transform duration-200 ${departmentMenuOpen ? "rotate-90" : ""}`}
                      />
                    </button>

                    {departmentMenuOpen ? (
                      <div className="app-menu absolute right-0 top-full z-20 mt-2 w-56 rounded-xl py-1.5">
                        {h.userPerms.can_manage ? (
                      <button
                        type="button"
                        onClick={() => {
                          setDepartmentMenuOpen(false);
                          setManagementMode(true);
                          h.openAddMember();
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                          <UserPlus size={14} className="app-text-muted" />
                          Добавить участников
                        </button>
                      ) : null}

                        {h.userPerms.can_assign_roles ? (
                          <button
                            type="button"
                            onClick={() => {
                              setDepartmentMenuOpen(false);
                              setManagementMode(true);
                              h.openAssignRoleModal();
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                            <Plus size={14} className="app-text-muted" />
                            Выдать роль
                          </button>
                        ) : null}

                        {h.userPerms.can_manage ? (
                          <button
                            type="button"
                            onClick={() => {
                              setDepartmentMenuOpen(false);
                              setManagementMode(true);
                              h.openDepartmentEditor();
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                            <PencilLine size={14} className="app-text-muted" />
                            Редактировать отдел
                          </button>
                        ) : null}

                        {canUseManagementMode ? (
                          <button
                            type="button"
                            onClick={() => {
                              setDepartmentMenuOpen(false);
                              setRoleMenuOpenForId(null);
                              setManagementMode((current) => !current);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                            <ChevronDown
                              size={14}
                              className={`transition-transform ${isManagementMode ? "rotate-180" : "-rotate-90"}`}
                            />
                            {isManagementMode ? "Вернуться к просмотру" : "Открыть управление"}
                          </button>
                        ) : null}

                        {h.userPerms.can_manage ? (
                          <>
                            <div className="app-divider my-1 border-t" />
                            <button
                              type="button"
                              disabled={h.pendingKey === "department-delete"}
                              onClick={() => {
                                setDepartmentMenuOpen(false);
                                void (async () => {
                                  const deleted = await h.submitDeleteDepartment();
                                  if (deleted) {
                                    router.push("/departments");
                                  }
                                })();
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                            >
                              <Trash2 size={14} className="text-[var(--danger-foreground)]" />
                              Удалить отдел
                            </button>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className={getDepartmentMembersListClassName(isManagementMode)}>
                {h.filteredMembers.length ? (
                  h.filteredMembers.map((member) => (
                    <DepartmentMemberRow
                      key={`${member.employee.id}-${member.is_active ? "active" : "inactive"}`}
                      canAssignRoles={isManagementMode && h.userPerms.can_assign_roles}
                      canChangeHead={isManagementMode && h.userPerms.can_change_head}
                      canManage={isManagementMode && h.userPerms.can_manage}
                      currentHeadId={h.department?.head?.id}
                      currentUserId={h.currentUserId}
                      member={member}
                      pendingKey={h.pendingKey}
                      roleOptions={roleOptions}
                      onAssignRole={h.submitMemberRole}
                      onCreateRole={h.openCreateRole}
                      onRemoveMember={h.submitRemoveMember}
                      onSetHead={h.submitQuickHeadChange}
                      onToggleRoleMenu={setRoleMenuOpenForId}
                      roleMenuOpenForId={roleMenuOpenForId}
                      roleMenuRef={roleMenuRef}
                    />
                  ))
                ) : (
                  <DepartmentMembersEmptyState />
                )}
              </div>

            </section>
          </>
        ) : null}
      </div>

      <DepartmentEditorModal
        draft={h.departmentDraft}
        isOpen={h.editDepartmentOpen}
        loading={h.pendingKey === "department"}
        onChange={h.updateDepartmentDraft}
        onClose={h.closeDepartmentEditor}
        onSave={h.saveDepartment}
      />

      <AddMemberModal
        canAssignRoles={h.userPerms.can_assign_roles}
        directoryError={h.employeesDirectoryError}
        isOpen={h.addMemberOpen}
        items={getDepartmentMemberModalItems(
          h.memberModalMode,
          h.selectableEmployees,
          h.assignableEmployees,
        )}
        loading={h.pendingKey === "member"}
        mode={h.memberModalMode}
        optionsLoading={h.employeesDirectoryLoading}
        onClose={h.closeAddMember}
        onCreateRole={() => {
          h.closeAddMember();
          h.openCreateRole();
        }}
        onRetryEmployees={h.reloadEmployeesDirectory}
        onSave={h.submitAddMember}
        onSelect={h.setSelectedMemberId}
        onSelectRole={h.setSelectedRoleId}
        roleOptions={roleOptions}
        selectedId={h.selectedMemberId}
        selectedRoleId={h.selectedRoleId}
      />

      <RoleEditorModal
        isOpen={h.roleEditorOpen}
        loading={h.pendingKey === "role"}
        onClose={h.closeRoleEditor}
        onDraftChange={h.setRoleDraft}
        onSave={h.saveRole}
        roleDraft={h.roleDraft}
      />
    </AppShell>
  );
}
