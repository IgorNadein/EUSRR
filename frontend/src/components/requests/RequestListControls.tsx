import { orderingOptions, requestTypeLabels, statusMeta } from "@/hooks/useRequestsPage";
import { displayUserName } from "@/lib/shared";
import type { User } from "@/types/api";
import { ArrowUpDown, ChevronDown, Filter, Plus, Search, X, Zap } from "lucide-react";

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
    <div className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Заявления</p>
          {state.pendingDecisionCount > 0 ? (
            <span className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
              {state.pendingDecisionCount} на рассмотрении
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {state.pendingDecisionCount > 0 ? (
            <button
              type="button"
              onClick={actions.openSwipeMode}
              className="app-feedback-warning inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition"
              title="Быстрый разбор"
            >
              <Zap size={14} />
              Быстрый разбор
            </button>
          ) : null}
          <button
            type="button"
            onClick={actions.openCreate}
            className="app-action-primary inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium"
          >
            <Plus size={14} />
            Создать заявление
          </button>
        </div>
      </div>

      {feedback.actionError ? (
        <p className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{feedback.actionError}</p>
      ) : null}
      {feedback.actionSuccess ? (
        <p className="app-feedback-success rounded-lg px-3 py-2 text-sm">{feedback.actionSuccess}</p>
      ) : null}

      <section className="app-surface-muted rounded-xl p-3">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search
              size={16}
              className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
            />
            <input
              value={state.search}
              onChange={(event) => actions.setSearch(event.target.value)}
              placeholder="Поиск по заявлениям"
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              title="Фильтры"
              onClick={actions.toggleFilters}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition ${state.filtersOpen ? "app-selected app-accent-text" : "app-surface app-text-muted hover:bg-[var(--surface-tertiary)]"}`}
            >
              <Filter size={16} />
              <span>Фильтры</span>
              {state.activeFiltersCount > 0 ? (
                <span className="app-counter flex h-5 min-w-5 items-center justify-center px-1 text-[10px] font-bold">
                  {state.activeFiltersCount}
                </span>
              ) : null}
            </button>

            <div className="relative min-w-[168px] flex-1 sm:flex-none">
              <ArrowUpDown
                size={15}
                className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              />
              <select
                value={state.ordering}
                onChange={(event) => actions.setOrdering(event.target.value)}
                className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-sm font-medium"
                aria-label="Сортировка"
              >
                {orderingOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="app-text-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2"
              />
            </div>
          </div>
        </div>

        {state.filtersOpen ? (
          <div className="mt-3 space-y-3 border-t border-[var(--border-subtle)] pt-3">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
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
            </div>

            <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
              <div className="space-y-1.5">
                <label className="app-text-muted px-1 text-xs font-medium">Дата создания</label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <input
                    type="date"
                    value={state.createdFromFilter}
                    onChange={(event) => actions.setCreatedFromFilter(event.target.value)}
                    className="app-input rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    type="date"
                    value={state.createdToFilter}
                    onChange={(event) => actions.setCreatedToFilter(event.target.value)}
                    className="app-input rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="app-text-muted px-1 text-xs font-medium">Период заявления</label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <input
                    type="date"
                    value={state.periodFromFilter}
                    onChange={(event) => actions.setPeriodFromFilter(event.target.value)}
                    className="app-input rounded-lg px-3 py-2 text-sm"
                  />
                  <input
                    type="date"
                    value={state.periodToFilter}
                    onChange={(event) => actions.setPeriodToFilter(event.target.value)}
                    className="app-input rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
            </div>

            {state.hasActiveFilters ? (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={actions.clearFilters}
                  className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition"
                >
                  <X size={14} />
                  Очистить фильтры
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
