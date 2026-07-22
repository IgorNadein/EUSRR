"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { RequestAvatar } from "@/components/requests/RequestAvatar";
import type { Department, User } from "@/types/api";

export type DocumentAudienceMode = "all" | "none" | "restricted";

type DocumentAudienceSelectorProps = {
  kind: "access" | "acknowledgement";
  resource?: "document" | "regulation";
  mode: DocumentAudienceMode;
  onModeChange: (mode: DocumentAudienceMode) => void;
  employees: User[];
  departments: Department[];
  selectedEmployeeIds: number[];
  selectedDepartmentIds: number[];
  onSelectedEmployeeIdsChange: (ids: number[]) => void;
  onSelectedDepartmentIdsChange: (ids: number[]) => void;
  loading?: boolean;
  disabled?: boolean;
};

function employeeName(employee: User) {
  return [employee.last_name, employee.first_name, employee.patronymic]
    .filter(Boolean)
    .join(" ")
    .trim() || employee.email || `Сотрудник #${employee.id}`;
}

function employeeInitials(employee: User) {
  return `${employee.last_name?.[0] || ""}${employee.first_name?.[0] || ""}`.toUpperCase() || "С";
}

function normalizeSearch(value: string) {
  return value.trim().toLocaleLowerCase("ru");
}

export function DocumentAudienceSelector({
  kind,
  resource = "document",
  mode,
  onModeChange,
  employees,
  departments,
  selectedEmployeeIds,
  selectedDepartmentIds,
  onSelectedEmployeeIdsChange,
  onSelectedDepartmentIdsChange,
  loading = false,
  disabled = false,
}: DocumentAudienceSelectorProps) {
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [departmentSearch, setDepartmentSearch] = useState("");
  const isAcknowledgement = kind === "acknowledgement";
  const resourceDative = resource === "regulation" ? "регламенту" : "документу";
  const resourceAccusative = resource === "regulation" ? "регламент" : "документ";

  const options: Array<{ value: DocumentAudienceMode; label: string }> = isAcknowledgement
    ? [
        { value: "all", label: "Для всех с доступом" },
        { value: "none", label: "Не требуется" },
        { value: "restricted", label: "Выборочно" },
      ]
    : [
        { value: "all", label: "Для всех" },
        { value: "restricted", label: "Выборочно" },
      ];

  const filteredEmployees = useMemo(() => {
    const query = normalizeSearch(employeeSearch);
    if (!query) return employees;
    return employees.filter((employee) => (
      `${employeeName(employee)} ${employee.email || ""}`.toLocaleLowerCase("ru").includes(query)
    ));
  }, [employeeSearch, employees]);

  const filteredDepartments = useMemo(() => {
    const query = normalizeSearch(departmentSearch);
    if (!query) return departments;
    return departments.filter((department) => department.name.toLocaleLowerCase("ru").includes(query));
  }, [departmentSearch, departments]);

  const toggleEmployee = (employeeId: number) => {
    onSelectedEmployeeIdsChange(
      selectedEmployeeIds.includes(employeeId)
        ? selectedEmployeeIds.filter((id) => id !== employeeId)
        : [...selectedEmployeeIds, employeeId],
    );
  };

  const toggleDepartment = (departmentId: number) => {
    onSelectedDepartmentIdsChange(
      selectedDepartmentIds.includes(departmentId)
        ? selectedDepartmentIds.filter((id) => id !== departmentId)
        : [...selectedDepartmentIds, departmentId],
    );
  };

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-[var(--foreground)]">
          {isAcknowledgement ? "Требование ознакомления" : `Доступ к ${resourceDative}`}
        </h3>
        <p className="app-text-muted mt-1 text-xs">
          {isAcknowledgement
            ? "Выберите сотрудников, которые должны подтвердить ознакомление."
            : `Выберите сотрудников, которые смогут открыть ${resourceAccusative}.`}
        </p>
      </div>

      <div className={`grid gap-2 ${options.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onModeChange(option.value)}
            disabled={disabled}
            aria-pressed={mode === option.value}
            className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition disabled:opacity-50 ${
              mode === option.value
                ? "app-selected border-[var(--accent-primary)]"
                : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {mode === "restricted" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="app-text-muted text-xs font-medium">Сотрудники</span>
              <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                {selectedEmployeeIds.length}
              </span>
            </div>
            <div className="relative mb-2">
              <Search
                size={14}
                className="app-text-muted pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
              />
              <input
                value={employeeSearch}
                onChange={(event) => setEmployeeSearch(event.target.value)}
                disabled={disabled}
                className="app-input w-full rounded-xl py-2 pl-8 pr-3 text-xs"
                placeholder="Поиск сотрудников"
                aria-label={`${isAcknowledgement ? "Ознакомление" : "Доступ"}: поиск сотрудников`}
              />
            </div>
            <div className="tasks-column-scroll app-surface-muted max-h-52 space-y-1 overflow-y-auto rounded-xl border border-[var(--border-subtle)] p-2">
              {loading ? (
                <p className="app-text-muted px-2 py-4 text-center text-xs">Загрузка сотрудников...</p>
              ) : filteredEmployees.length > 0 ? (
                filteredEmployees.map((employee) => {
                  const name = employeeName(employee);
                  return (
                    <label
                      key={employee.id}
                      className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition hover:bg-[var(--surface-elevated)]"
                    >
                      <input
                        type="checkbox"
                        checked={selectedEmployeeIds.includes(employee.id)}
                        onChange={() => toggleEmployee(employee.id)}
                        disabled={disabled}
                        className="h-4 w-4 shrink-0"
                      />
                      <RequestAvatar
                        alt={name}
                        fallback={employeeInitials(employee)}
                        src={employee.avatar}
                        size="sm"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-xs font-medium text-[var(--foreground)]">{name}</span>
                        {employee.email ? (
                          <span className="app-text-muted block truncate text-[10px]">{employee.email}</span>
                        ) : null}
                      </span>
                    </label>
                  );
                })
              ) : (
                <p className="app-text-muted px-2 py-4 text-center text-xs">Сотрудники не найдены</p>
              )}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="app-text-muted text-xs font-medium">Отделы</span>
              <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">
                {selectedDepartmentIds.length}
              </span>
            </div>
            <div className="relative mb-2">
              <Search
                size={14}
                className="app-text-muted pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
              />
              <input
                value={departmentSearch}
                onChange={(event) => setDepartmentSearch(event.target.value)}
                disabled={disabled}
                className="app-input w-full rounded-xl py-2 pl-8 pr-3 text-xs"
                placeholder="Поиск отделов"
                aria-label={`${isAcknowledgement ? "Ознакомление" : "Доступ"}: поиск отделов`}
              />
            </div>
            <div className="tasks-column-scroll app-surface-muted max-h-52 space-y-1 overflow-y-auto rounded-xl border border-[var(--border-subtle)] p-2">
              {loading ? (
                <p className="app-text-muted px-2 py-4 text-center text-xs">Загрузка отделов...</p>
              ) : filteredDepartments.length > 0 ? (
                filteredDepartments.map((department) => (
                  <label
                    key={department.id}
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition hover:bg-[var(--surface-elevated)]"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDepartmentIds.includes(department.id)}
                      onChange={() => toggleDepartment(department.id)}
                      disabled={disabled}
                      className="h-4 w-4 shrink-0"
                    />
                    <span className="min-w-0 truncate text-xs font-medium text-[var(--foreground)]">
                      {department.name}
                    </span>
                  </label>
                ))
              ) : (
                <p className="app-text-muted px-2 py-4 text-center text-xs">Отделы не найдены</p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
