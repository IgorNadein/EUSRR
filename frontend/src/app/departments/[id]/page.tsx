"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  Building2,
  Crown,
  PencilLine,
  Plus,
  Search,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";

import { DepartmentPersonChip } from "@/components/departments/DepartmentPersonChip";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { AppShell } from "@/components/AppShell";
import { Modal } from "@/components/ui/Modal";
import { useDepartmentPage } from "@/hooks/useDepartmentPage";
import type {
  DepartmentMemberLink,
  DepartmentPermissionChoice,
  DepartmentRole,
} from "@/types/api";

function PermissionBadge({
  active,
  children,
}: {
  active: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
        active
          ? "app-selected app-accent-text"
          : "app-surface-muted app-text-muted"
      }`}
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
  onRemoveMember,
  onSetHead,
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
  onRemoveMember: (employeeId: number) => Promise<void>;
  onSetHead: (employeeId: number) => Promise<void>;
}) {
  const isHead = currentHeadId === member.employee.id;
  const isBusy = pendingKey === `member-remove-${member.employee.id}`;
  const isRoleBusy = pendingKey === `member-role-${member.employee.id}`;
  const subtitle = member.employee.position?.name || member.employee.email || null;
  const roleItems = roleOptions.map((role) => ({ id: role.id, name: role.name }));

  return (
    <article className="app-surface-muted rounded-xl p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 space-y-3">
          <DepartmentPersonChip
            currentUserId={currentUserId}
            person={member.employee}
            subtitle={subtitle}
          />

          <div className="flex flex-wrap items-center gap-2">
            {isHead ? (
              <span className="app-feedback-warning inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium">
                <Crown size={12} />
                Руководитель
              </span>
            ) : null}
            {!member.is_active ? (
              <span className="app-feedback-danger inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
                Неактивное участие
              </span>
            ) : null}
            {member.role && !canAssignRoles ? (
              <span className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
                {member.role.name}
              </span>
            ) : null}
            {!member.role && !canAssignRoles ? (
              <span className="app-surface rounded-full px-2.5 py-1 text-xs text-[var(--muted-foreground)]">
                Без роли
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex w-full flex-col gap-3 lg:max-w-[420px] lg:items-end">
          {canAssignRoles ? (
            <div className="w-full lg:w-64">
              <SearchableSelectSingle
                label="Роль"
                items={roleItems}
                selectedId={member.role?.id ?? null}
                onSelect={(roleId) => void onAssignRole(member.employee.id, roleId)}
                placeholder="Без роли"
                disabled={isRoleBusy}
              />
            </div>
          ) : null}

          <div className="flex flex-wrap justify-start gap-2 lg:justify-end">
            {canChangeHead && !isHead ? (
              <button
                type="button"
                onClick={() => void onSetHead(member.employee.id)}
                className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
              >
                <Crown size={14} />
                Сделать руководителем
              </button>
            ) : null}
            {canManage && !isHead ? (
              <button
                type="button"
                onClick={() => void onRemoveMember(member.employee.id)}
                disabled={isBusy}
                className="app-action-danger inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
              >
                <Trash2 size={14} />
                Убрать
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

function DepartmentRoleCard({
  canAssignRoles,
  pendingKey,
  role,
  usageCount,
  onDelete,
  onEdit,
}: {
  canAssignRoles: boolean;
  pendingKey: string | null;
  role: DepartmentRole;
  usageCount: number;
  onDelete: (role: DepartmentRole) => Promise<void>;
  onEdit: (role: DepartmentRole) => void;
}) {
  const isDeleting = pendingKey === `role-delete-${role.id}`;

  return (
    <article className="app-surface-muted rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">
              {role.name}
            </h3>
            <span className="app-selected app-accent-text inline-flex rounded-full px-2.5 py-1 text-xs">
              {usageCount} участников
            </span>
          </div>
          <p className="app-text-muted mt-1 text-xs">
            {role.permissions_verbose.length
              ? "Набор прав для участников отдела"
              : "У роли пока нет назначенных прав"}
          </p>
        </div>

        {canAssignRoles ? (
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => onEdit(role)}
              className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
            >
              <PencilLine size={14} />
              Изменить
            </button>
            <button
              type="button"
              onClick={() => void onDelete(role)}
              disabled={isDeleting}
              className="app-action-danger inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm disabled:opacity-50"
            >
              <Trash2 size={14} />
              Удалить
            </button>
          </div>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {role.permissions_verbose.length ? (
          role.permissions_verbose.map((permission) => (
            <span
              key={permission.id}
              className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs font-medium"
            >
              {permission.name}
            </span>
          ))
        ) : (
          <span className="app-text-muted text-sm">Права ещё не выбраны</span>
        )}
      </div>
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
            placeholder="Например, Финансовый отдел"
          />
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
            Описание
          </label>
          <textarea
            value={draft.description}
            onChange={(event) => onChange({ description: event.target.value })}
            rows={5}
            className="app-input w-full rounded-lg px-3 py-2 text-sm resize-none"
            placeholder="Чем занимается отдел, какие зоны ответственности ведёт"
          />
        </section>
      </div>
    </Modal>
  );
}

function AddMemberModal({
  isOpen,
  items,
  loading,
  onClose,
  onSave,
  onSelect,
  selectedId,
}: {
  isOpen: boolean;
  items: Array<{ id: number; name: string }>;
  loading: boolean;
  onClose: () => void;
  onSave: () => Promise<void>;
  onSelect: (id: number | null) => void;
  selectedId: number | null;
}) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Добавить участника"
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
            disabled={loading || !selectedId}
            className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          >
            Добавить в отдел
          </button>
        </div>
      }
    >
      <section className="app-surface-muted rounded-xl p-4">
        <SearchableSelectSingle
          label="Сотрудник *"
          items={items}
          selectedId={selectedId}
          onSelect={onSelect}
          placeholder={
            items.length
              ? "Выберите сотрудника"
              : "Свободных сотрудников для добавления нет"
          }
          disabled={!items.length}
        />
        <p className="app-text-muted mt-3 text-sm">
          В список попадают только сотрудники, которые ещё не состоят в отделе.
        </p>
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
  permissionChoices,
  roleDraft,
}: {
  isOpen: boolean;
  loading: boolean;
  onClose: () => void;
  onDraftChange: (
    next:
      | { id: number | null; name: string; permissionCodes: string[] }
      | ((current: {
          id: number | null;
          name: string;
          permissionCodes: string[];
        }) => {
          id: number | null;
          name: string;
          permissionCodes: string[];
        }),
  ) => void;
  onSave: () => Promise<void>;
  permissionChoices: DepartmentPermissionChoice[];
  roleDraft: { id: number | null; name: string; permissionCodes: string[] };
}) {
  const togglePermission = (code: string) => {
    onDraftChange((current) => ({
      ...current,
      permissionCodes: current.permissionCodes.includes(code)
        ? current.permissionCodes.filter((item) => item !== code)
        : [...current.permissionCodes, code],
    }));
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={roleDraft.id ? "Редактирование роли" : "Новая роль отдела"}
      size="lg"
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
            {roleDraft.id ? "Сохранить роль" : "Создать роль"}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <section className="app-surface-muted rounded-xl p-4">
          <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
            Название роли *
          </label>
          <input
            value={roleDraft.name}
            onChange={(event) =>
              onDraftChange((current) => ({ ...current, name: event.target.value }))
            }
            className="app-input w-full rounded-lg px-3 py-2 text-sm"
            placeholder="Например, Координатор отдела"
          />
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-[var(--foreground)]">
                Права роли
              </h4>
              <p className="app-text-muted mt-1 text-sm">
                Выберите, какими действиями сможет пользоваться участник с этой ролью.
              </p>
            </div>
            <span className="app-selected app-accent-text inline-flex rounded-full px-2.5 py-1 text-xs">
              {roleDraft.permissionCodes.length} прав
            </span>
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            {permissionChoices.map((permission) => {
              const checked = roleDraft.permissionCodes.includes(permission.code);
              return (
                <label
                  key={permission.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-3 text-sm transition ${
                    checked
                      ? "app-selected border-[var(--accent-primary)]"
                      : "border-[var(--border-subtle)] hover:bg-[var(--surface-elevated)]"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => togglePermission(permission.code)}
                    className="mt-0.5 rounded border-[var(--border-strong)]"
                  />
                  <span className="min-w-0">
                    <span className="block font-medium text-[var(--foreground)]">
                      {permission.name}
                    </span>
                    <span className="app-text-muted mt-1 block text-xs">
                      {permission.code}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </section>
      </div>
    </Modal>
  );
}

export default function DepartmentDetailPage() {
  const params = useParams<{ id: string }>();
  const departmentId = Number(params?.id);
  const h = useDepartmentPage(departmentId);

  const activeMembersCount = h.members.filter((member) => member.is_active).length;
  const roleOptions = h.roles.map((role) => ({ id: role.id, name: role.name }));
  const permissionSummary = [
    h.userPerms.is_head ? "Руководитель отдела" : null,
    h.userPerms.can_manage ? "Управление составом" : null,
    h.userPerms.can_change_head ? "Смена руководителя" : null,
    h.userPerms.can_assign_roles ? "Назначение ролей" : null,
  ].filter(Boolean) as string[];

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
            <section className="app-surface rounded-2xl p-5 sm:p-6">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className="app-selected app-accent-text inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs">
                      <Building2 size={12} />
                      Отдел
                    </span>
                    <span className="app-badge inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs">
                      <Users size={12} />
                      {activeMembersCount} участников
                    </span>
                    <span className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs">
                      {h.roles.length} ролей
                    </span>
                  </div>

                  <h1 className="text-2xl font-semibold text-[var(--foreground)] sm:text-3xl">
                    {h.department.name}
                  </h1>
                  <p className="app-text-muted mt-3 max-w-3xl text-sm leading-relaxed sm:text-base">
                    {h.department.description || "Описание отдела ещё не заполнено."}
                  </p>

                  {permissionSummary.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {permissionSummary.map((label) => (
                        <PermissionBadge key={label} active>
                          {label}
                        </PermissionBadge>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2">
                  {h.userPerms.can_manage ? (
                    <button
                      type="button"
                      onClick={h.openDepartmentEditor}
                      className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
                    >
                      <PencilLine size={14} />
                      Редактировать отдел
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
                <div className="app-surface-muted rounded-xl p-4">
                  <p className="app-card-caption">Руководитель</p>
                  <div className="mt-3">
                    {h.department.head ? (
                      <DepartmentPersonChip
                        currentUserId={h.currentUserId}
                        person={h.department.head}
                        subtitle={h.department.head.position?.name || h.department.head.email}
                      />
                    ) : (
                      <div className="app-surface rounded-xl px-4 py-3 text-sm text-[var(--foreground)]">
                        Руководитель пока не назначен.
                      </div>
                    )}
                  </div>
                </div>

                {h.userPerms.can_change_head ? (
                  <div className="app-surface-muted rounded-xl p-4">
                    <SearchableSelectSingle
                      label="Назначить руководителя"
                      items={h.headCandidates}
                      selectedId={h.selectedHeadId}
                      onSelect={h.setSelectedHeadId}
                      placeholder="Выберите сотрудника"
                      disabled={!h.headCandidates.length}
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void h.submitHeadChange()}
                        disabled={h.pendingKey === "head"}
                        className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
                      >
                        Сохранить
                      </button>
                      {h.department.head ? (
                        <button
                          type="button"
                          onClick={() => void h.submitHeadRemoval()}
                          disabled={h.pendingKey === "head"}
                          className="app-action-secondary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
                        >
                          Снять
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <div className="space-y-6">
              <section className="app-surface rounded-2xl p-5">
                <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h2 className="app-card-caption">Команда отдела</h2>
                    <p className="app-text-muted mt-2 text-sm">
                      Основной рабочий блок отдела: состав команды, роли участников и быстрые действия.
                    </p>
                  </div>
                  {h.userPerms.can_manage ? (
                    <button
                      type="button"
                      onClick={h.openAddMember}
                      className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
                    >
                      <UserPlus size={14} />
                      Добавить участника
                    </button>
                  ) : null}
                </div>

                <div className="app-surface-muted mb-4 flex flex-col gap-3 rounded-xl p-3 md:flex-row md:items-center">
                  <div className="relative min-w-0 flex-1">
                    <Search
                      size={16}
                      className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
                    />
                    <input
                      value={h.membersQuery}
                      onChange={(event) => h.setMembersQuery(event.target.value)}
                      placeholder="Поиск по участникам, почте, должности или роли"
                      className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
                    />
                  </div>
                  <label className="app-text-muted inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm">
                    <input
                      type="checkbox"
                      checked={h.showInactiveMembers}
                      onChange={(event) =>
                        h.setShowInactiveMembers(event.target.checked)
                      }
                      className="rounded border-[var(--border-strong)]"
                    />
                    Показывать неактивных
                  </label>
                </div>

                <div className="space-y-3">
                  {h.filteredMembers.length ? (
                    h.filteredMembers.map((member) => (
                      <DepartmentMemberRow
                        key={`${member.employee.id}-${member.is_active ? "active" : "inactive"}`}
                        canAssignRoles={h.userPerms.can_assign_roles}
                        canChangeHead={h.userPerms.can_change_head}
                        canManage={h.userPerms.can_manage}
                        currentHeadId={h.department?.head?.id}
                        currentUserId={h.currentUserId}
                        member={member}
                        pendingKey={h.pendingKey}
                        roleOptions={roleOptions}
                        onAssignRole={h.submitMemberRole}
                        onRemoveMember={h.submitRemoveMember}
                        onSetHead={h.submitQuickHeadChange}
                      />
                    ))
                  ) : (
                    <div className="app-surface-muted rounded-xl p-8 text-center">
                      <Users size={24} className="app-text-muted mx-auto mb-3" />
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        Участники не найдены
                      </p>
                      <p className="app-text-muted mt-2 text-sm">
                        Измени поисковый запрос или включи показ неактивных связей.
                      </p>
                    </div>
                  )}
                </div>
              </section>

              <section className="app-surface rounded-2xl p-5">
                <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h2 className="app-card-caption">Роли отдела</h2>
                    <p className="app-text-muted mt-2 text-sm">
                      Наборы прав для участников. Это secondary-настройка состава, а не основной центр страницы.
                    </p>
                  </div>
                  {h.userPerms.can_assign_roles ? (
                    <button
                      type="button"
                      onClick={h.openCreateRole}
                      className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
                    >
                      <Plus size={14} />
                      Создать роль
                    </button>
                  ) : null}
                </div>

                <div className="space-y-3">
                  {h.roles.length ? (
                    h.roles.map((role) => (
                      <DepartmentRoleCard
                        key={role.id}
                        canAssignRoles={h.userPerms.can_assign_roles}
                        pendingKey={h.pendingKey}
                        role={role}
                        usageCount={h.roleUsage[role.id] || 0}
                        onDelete={h.submitRoleDelete}
                        onEdit={h.openEditRole}
                      />
                    ))
                  ) : (
                    <div className="app-surface-muted rounded-xl p-8 text-center">
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        Роли ещё не созданы
                      </p>
                      <p className="app-text-muted mt-2 text-sm">
                        Создай роли, если внутри отдела нужно разделить управленческие права.
                      </p>
                    </div>
                  )}
                </div>
              </section>
            </div>
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
        isOpen={h.addMemberOpen}
        items={h.selectableEmployees}
        loading={h.pendingKey === "member"}
        onClose={h.closeAddMember}
        onSave={h.submitAddMember}
        onSelect={h.setSelectedMemberId}
        selectedId={h.selectedMemberId}
      />

      <RoleEditorModal
        isOpen={h.roleEditorOpen}
        loading={h.pendingKey === "role"}
        onClose={h.closeRoleEditor}
        onDraftChange={h.setRoleDraft}
        onSave={h.saveRole}
        permissionChoices={h.permissionChoices}
        roleDraft={h.roleDraft}
      />
    </AppShell>
  );
}
