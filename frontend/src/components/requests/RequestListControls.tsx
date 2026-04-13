import { orderingOptions, requestTypeLabels, statusMeta } from "@/hooks/useRequestsPage";
import { displayUserName } from "@/lib/shared";
import type { User } from "@/types/api";
import { ArrowUpDown, ChevronDown, Filter, Plus, Search, Zap } from "lucide-react";

type RequestListControlsState = {
  activeFiltersCount: number;
  createdFromFilter: string;
  createdToFilter: string;
  employeeFilter: string;
  employees: User[];
  filtersOpen: boolean;
  hasActiveFilters: boolean;
  ordering: string;
  pendingDecisionCount: number;
  periodFromFilter: string;
  periodToFilter: string;
  search: string;
  statusFilter: string;
  typeFilter: string;
  view: "" | "mine" | "addressed";
};

type RequestListControlsFeedback = {
  actionError: string | null;
  actionSuccess: string | null;
};

type RequestListControlsActions = {
  clearFilters: () => void;
  openCreate: () => void;
  openSwipeMode: () => void;
  setCreatedFromFilter: (value: string) => void;
  setCreatedToFilter: (value: string) => void;
  setEmployeeFilter: (value: string) => void;
  setOrdering: (value: string) => void;
  setPeriodFromFilter: (value: string) => void;
  setPeriodToFilter: (value: string) => void;
  setSearch: (value: string) => void;
  setStatusFilter: (value: string) => void;
  setTypeFilter: (value: string) => void;
  setView: (value: "" | "mine" | "addressed") => void;
  toggleFilters: () => void;
};

type RequestListControlsProps = {
  actions: RequestListControlsActions;
  feedback: RequestListControlsFeedback;
  state: RequestListControlsState;
};

export function RequestListControls({
  actions,
  feedback,
  state,
}: RequestListControlsProps) {
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Заявления</p>
          {state.pendingDecisionCount > 0 ? (
            <button
              type="button"
              onClick={actions.openSwipeMode}
              className="app-feedback-warning group flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition"
              title="Быстрый разбор"
            >
              <Zap size={11} className="transition group-hover:text-amber-700" />
            </button>
          ) : null}
        </div>
        <button
          type="button"
          onClick={actions.openCreate}
          className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium"
        >
          <Plus size={14} /> Создать заявление
        </button>
      </div>

      {feedback.actionError ? (
        <p className="app-feedback-danger mb-3 rounded-lg px-3 py-2 text-sm">{feedback.actionError}</p>
      ) : null}
      {feedback.actionSuccess ? (
        <p className="app-feedback-success mb-3 rounded-lg px-3 py-2 text-sm">{feedback.actionSuccess}</p>
      ) : null}

      <div className="mb-4 flex items-center gap-2">
        <div className="relative flex-1">
          <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={state.search}
            onChange={(event) => actions.setSearch(event.target.value)}
            placeholder="Поиск по заявлениям"
            className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>

        <button
          type="button"
          title="Фильтры"
          onClick={actions.toggleFilters}
          className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${state.filtersOpen ? "app-selected app-accent-text" : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"}`}
        >
          <Filter size={16} />
          {state.activeFiltersCount > 0 ? (
            <span className="app-counter absolute -right-1 -top-1 flex h-4 min-w-4 px-1 text-[10px] font-bold">
              {state.activeFiltersCount}
            </span>
          ) : null}
        </button>

        <div className="relative w-[148px] shrink-0">
          <ArrowUpDown size={15} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
          <select
            value={state.ordering}
            onChange={(event) => actions.setOrdering(event.target.value)}
            className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-xs font-medium"
            aria-label="Сортировка"
          >
            {orderingOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="app-text-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2" />
        </div>
      </div>

      {state.filtersOpen ? (
        <div className="app-surface-muted mb-4 flex flex-col gap-2 rounded-xl p-3">
          <select
            value={state.view}
            onChange={(event) => actions.setView(event.target.value as "" | "mine" | "addressed")}
            className="app-select rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Все заявления</option>
            <option value="mine">Мои заявления</option>
            <option value="addressed">Адресованные мне</option>
          </select>

          <select
            value={state.typeFilter}
            onChange={(event) => actions.setTypeFilter(event.target.value)}
            className="app-select rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Тип заявления</option>
            {Object.entries(requestTypeLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={state.statusFilter}
            onChange={(event) => actions.setStatusFilter(event.target.value)}
            className="app-select rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Статус заявления</option>
            {Object.entries(statusMeta).map(([value, meta]) => (
              <option key={value} value={value}>
                {meta.label}
              </option>
            ))}
          </select>

          <select
            value={state.employeeFilter}
            onChange={(event) => actions.setEmployeeFilter(event.target.value)}
            className="app-select rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Все сотрудники</option>
            {state.employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {displayUserName(employee)}
              </option>
            ))}
          </select>

          <div className="space-y-1.5">
            <label className="app-text-muted px-1 text-xs font-medium">Дата создания</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={state.createdFromFilter}
                onChange={(event) => actions.setCreatedFromFilter(event.target.value)}
                className="app-input flex-1 rounded-lg px-3 py-2 text-sm"
              />
              <input
                type="date"
                value={state.createdToFilter}
                onChange={(event) => actions.setCreatedToFilter(event.target.value)}
                className="app-input flex-1 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="app-text-muted px-1 text-xs font-medium">Период заявления</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={state.periodFromFilter}
                onChange={(event) => actions.setPeriodFromFilter(event.target.value)}
                className="app-input flex-1 rounded-lg px-3 py-2 text-sm"
              />
              <input
                type="date"
                value={state.periodToFilter}
                onChange={(event) => actions.setPeriodToFilter(event.target.value)}
                className="app-input flex-1 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>

          {state.hasActiveFilters ? (
            <button
              type="button"
              onClick={actions.clearFilters}
              className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium transition"
            >
              Очистить фильтры
            </button>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
