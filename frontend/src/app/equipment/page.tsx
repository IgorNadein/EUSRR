"use client";

import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import Link from "next/link";
import { Archive, ArrowRightLeft, ArrowUpDown, ChevronDown, Filter, MessageSquare, Monitor, Pencil, Plus, QrCode, Search, Shield, Trash2, Wrench, X } from "lucide-react";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { formatDate, formatMoney } from "@/lib/shared";
import { useEquipmentPage } from "@/hooks/useEquipmentPage";
import { Modal } from "@/components/ui";

const listModeMeta = [
  { value: "all", label: "Весь реестр" },
  { value: "mine", label: "Мое оборудование" },
  { value: "warranty", label: "Истекает гарантия" },
] as const;

const orderingOptions = [
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at", label: "Сначала старые" },
  { value: "name", label: "По названию" },
  { value: "purchase_date", label: "По дате покупки ↑" },
  { value: "-purchase_date", label: "По дате покупки ↓" },
];

/* ──── status badges ──── */
const statusMeta: Record<string, { label: string; className: string; accentClass: string; surfaceClass: string }> = {
  available: {
    label: "Доступно",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    accentClass: "bg-emerald-500",
    surfaceClass: "border-emerald-100",
  },
  in_use: {
    label: "В использовании",
    className: "bg-sky-50 text-sky-700 ring-sky-100",
    accentClass: "bg-sky-500",
    surfaceClass: "border-sky-100",
  },
  maintenance: {
    label: "На обслуживании",
    className: "bg-amber-50 text-amber-700 ring-amber-100",
    accentClass: "bg-amber-500",
    surfaceClass: "border-amber-100",
  },
  retired: {
    label: "Списано",
    className: "bg-gray-100 text-gray-700 ring-gray-200",
    accentClass: "bg-gray-400",
    surfaceClass: "border-gray-200",
  },
  broken: {
    label: "Сломано",
    className: "bg-rose-50 text-rose-700 ring-rose-100",
    accentClass: "bg-rose-500",
    surfaceClass: "border-rose-100",
  },
};

const defaultStatusMeta = {
  label: "—",
  className: "bg-gray-50 text-gray-700 ring-gray-200",
  accentClass: "bg-gray-300",
  surfaceClass: "border-gray-200",
};

/* ──── main page ──── */
export default function EquipmentPage() {
  const { user } = useUser();
  const {
    auth,
    actionError,
    actionSuccess,
    activeFilterCount,
    busyKey,
    canManage,
    categories,
    categoryFilter,
    closeModal,
    closeOperationModal,
    commentDrafts,
    commentsMap,
    createOptions,
    dateFromFilter,
    dateToFilter,
    departmentFilter,
    departments,
    detailsMap,
    displayUserName,
    employees,
    error,
    expandedComments,
    expandedRows,
    filteredDepartmentsForForm,
    filteredEmployeesForForm,
    filteredItems,
    filtersOpen,
    form,
    getEquipmentMeta,
    getResponsibleLink,
    getResponsibleName,
    handleAddComment,
    handleDelete,
    handleDeleteComment,
    handleLoadMore,
    handleMaintenance,
    handleOpenQr,
    handleSave,
    handleTransfer,
    handleWriteOff,
    isCreateMode,
    isModalOpen,
    listMode,
    loading,
    loadingMore,
    loadingRowDetails,
    maintenanceForm,
    maintenanceMap,
    modalMode,
    nextPage,
    openCreateModal,
    openEdit,
    openOperationModal,
    operationModal,
    ordering,
    previewInventoryNumber,
    responsibleFilter,
    searchQuery,
    selectedEquipment,
    setCategoryFilter,
    setCommentDrafts,
    setDateFromFilter,
    setDateToFilter,
    setDepartmentFilter,
    setFiltersOpen,
    setForm,
    setListMode,
    setMaintenanceForm,
    setOrdering,
    setResponsibleFilter,
    setSearchQuery,
    setStatusFilter,
    setTransferForm,
    setWriteOffReason,
    statusFilter,
    transferForm,
    transferHistoryMap,
    toggleComments,
    toggleRow,
    writeOffReason,
  } = useEquipmentPage(user);
  /* ──── render ──── */
  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка оборудования...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          {/* Header */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Оборудование</p>
            <button
              type="button"
              onClick={() => { void openCreateModal(); }}
              className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600"
            >
              <Plus size={14} /> Добавить оборудование
            </button>
          </div>

          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p>}

          {/* Search + filter toggle */}
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по оборудованию"
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <button
              type="button"
              title="Фильтры"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${filtersOpen ? "border-sky-400 bg-sky-50 text-sky-600" : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"}`}
            >
              <Filter size={16} />
              {activeFilterCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <div className="relative w-[148px] shrink-0">
              <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <select
                value={ordering}
                onChange={(e) => setOrdering(e.target.value)}
                className="w-full appearance-none rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-8 text-xs font-medium text-gray-700 transition hover:bg-gray-100 focus:border-sky-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                aria-label="Сортировка списка оборудования"
              >
                {orderingOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {listModeMeta.map((mode) => (
              <button
                key={mode.value}
                type="button"
                onClick={() => setListMode(mode.value)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  listMode === mode.value
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>{mode.label}</span>
              </button>
            ))}
          </div>

          {/* Filters panel */}
          {filtersOpen && (
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все статусы</option>
                  {Object.entries(statusMeta).map(([key, meta]) => (
                    <option key={key} value={key}>{meta.label}</option>
                  ))}
                </select>
                <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все категории</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все отделы</option>
                  {departments.map((dep) => (
                    <option key={dep.id} value={dep.id}>{dep.name}</option>
                  ))}
                </select>
                <select value={responsibleFilter} onChange={(e) => setResponsibleFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все сотрудники</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>{displayUserName(emp)}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="shrink-0 text-xs text-gray-500">Дата покупки:</span>
                <input type="date" value={dateFromFilter} onChange={(e) => setDateFromFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" placeholder="С" />
                <span className="text-xs text-gray-400">—</span>
                <input type="date" value={dateToFilter} onChange={(e) => setDateToFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" placeholder="По" />
              </div>
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setStatusFilter(""); setCategoryFilter(""); setDepartmentFilter(""); setResponsibleFilter(""); setDateFromFilter(""); setDateToFilter(""); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100">
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* Items list */}
          <div className="space-y-2">
            {filteredItems.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <Monitor size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Записи об оборудовании не найдены</p>
              </div>
            ) : (
              <>
                {filteredItems.map((item) => {
                const responsibleName = getResponsibleName(item);
                const responsibleId = typeof item.responsible_person === "number" ? item.responsible_person : null;
                const responsibleLink = getResponsibleLink(item);
                const statusKey = String(item.status || "").toLowerCase();
                const st = statusMeta[statusKey] ?? defaultStatusMeta;
                const canEditThis = canManage;
                const canDeleteThis = canManage;
                const comments = commentsMap[item.id] || [];
                const rowOpen = Boolean(expandedRows[item.id]);
                const commentsOpen = Boolean(expandedComments[item.id]);
                const commentsTotal = item.comments_count ?? comments.length;
                const detailItem = detailsMap[item.id] || item;
                const metaItems = getEquipmentMeta(detailItem);
                const transferHistory = transferHistoryMap[item.id] || [];
                const maintenanceRecords = maintenanceMap[item.id] || [];
                const rowLoading = Boolean(loadingRowDetails[item.id]);

                return (
                  <article key={item.id} className="overflow-hidden rounded-xl border border-gray-200 bg-white transition hover:border-gray-300">
                    <div className="px-4 py-3">
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={() => toggleRow(item.id)}
                          aria-label={rowOpen ? "Свернуть детали" : "Развернуть детали"}
                          className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"
                        >
                          <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className={`h-2 w-2 shrink-0 rounded-full ${st.accentClass}`} />
                                <h3 className="truncate text-sm font-semibold text-gray-900">{item.name || "Без названия"}</h3>
                              </div>
                              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                                <span className="font-medium text-gray-700">{item.inventory_number || "Без инв. номера"}</span>
                                {item.serial_number && <span>SN: {item.serial_number}</span>}
                              </div>
                            </div>

                            <div className="flex shrink-0 items-center gap-1.5">
                              <button type="button" title={`Комментарии (${commentsTotal})`} onClick={() => toggleComments(item.id)} className="relative inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 transition hover:border-sky-200 hover:bg-sky-50 hover:text-sky-700">
                                <MessageSquare size={15} />
                                {commentsTotal > 0 && (
                                  <span className="absolute -right-1 -top-1 inline-flex min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 py-0.5 text-[10px] font-bold text-white">{commentsTotal}</span>
                                )}
                              </button>
                              {canEditThis && (
                                <button type="button" title="Редактировать" onClick={() => openEdit(item)} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50">
                                  <Pencil size={15} />
                                </button>
                              )}
                              {canDeleteThis && (
                                <button type="button" title="Удалить" onClick={() => handleDelete(item.id)} disabled={busyKey === `delete-${item.id}`} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-rose-200 bg-rose-50 text-rose-600 transition hover:bg-rose-100 disabled:opacity-60">
                                  <Trash2 size={15} />
                                </button>
                              )}
                            </div>
                          </div>

                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            {statusKey && <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${st.className}`}>{st.label}</span>}
                            {item.is_under_warranty && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200" title="На гарантии">
                                <Shield size={11} /> Гарантия
                              </span>
                            )}
                          </div>

                          <div className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs text-gray-500 sm:grid-cols-2">
                            <div>
                              <span className="text-gray-400">Стоимость:</span>{" "}
                              <span className="font-medium text-gray-700">{formatMoney(item.purchase_cost)}</span>
                            </div>
                            <div>
                              <span className="text-gray-400">Покупка:</span>{" "}
                              <span className="font-medium text-gray-700">{formatDate(item.purchase_date) || "—"}</span>
                            </div>
                            {responsibleId ? (
                              <div className="col-span-2 min-w-0">
                                <span className="text-gray-400">Ответственный:</span>{" "}
                                <Link href={responsibleLink} className="font-medium text-sky-700 hover:text-sky-800">
                                  {responsibleName}
                                </Link>
                              </div>
                            ) : (
                              <div className="col-span-2 text-gray-400">Ответственный не назначен</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {(rowOpen || commentsOpen) && (
                      <div className="app-surface-muted mt-4 rounded-xl p-4">
                        {commentsOpen && (
                          <div className="app-surface rounded-xl p-3">
                            <div className="space-y-2">
                              {comments.length === 0 ? (
                                <p className="app-text-muted text-xs">Комментариев пока нет</p>
                              ) : (
                                comments.map((c) => {
                                  const canDel = Boolean(c.author?.id && (user?.id === c.author.id || auth?.is_staff || auth?.is_superuser));
                                  return (
                                    <div key={c.id} className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]">
                                      <div className="mb-1 flex items-center justify-between gap-2">
                                        <span className="font-medium">{displayUserName(c.author)}</span>
                                        <div className="flex items-center gap-2">
                                          <span className="app-text-muted">{formatDate(c.created_at)}</span>
                                          {canDel && <button type="button" onClick={() => handleDeleteComment(item.id, c.id)} className="app-action-danger rounded-md px-1.5 py-0.5">удалить</button>}
                                        </div>
                                      </div>
                                      <p>{c.text}</p>
                                    </div>
                                  );
                                })
                              )}
                            </div>
                            <div className="mt-2 flex items-center gap-2">
                              <input value={commentDrafts[item.id] || ""} onChange={(e) => setCommentDrafts((p) => ({ ...p, [item.id]: e.target.value }))} placeholder="Добавить комментарий" className="app-input flex-1 rounded-lg px-3 py-2 text-xs" />
                              <button type="button" onClick={() => handleAddComment(item.id)} disabled={busyKey === `comment-${item.id}`} className="app-action-primary rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60">Отправить</button>
                            </div>
                          </div>
                        )}

                        {rowOpen && (
                          <>
                            {rowLoading && (
                              <div className={`${commentsOpen ? "mt-3 " : ""}app-selected mb-3 rounded-xl px-3 py-2 text-sm`}>
                                Загружаем детали оборудования...
                              </div>
                            )}

                            <div className={`${commentsOpen ? "mt-3 " : ""}mb-3 flex flex-wrap gap-2`}>
                              <button type="button" onClick={() => openOperationModal("transfer", detailItem)} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
                                <ArrowRightLeft size={15} /> Перевести
                              </button>
                              <button type="button" onClick={() => openOperationModal("maintenance", detailItem)} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
                                <Wrench size={15} /> Обслуживание
                              </button>
                              <button type="button" onClick={() => handleOpenQr(item.id)} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
                                <QrCode size={15} /> QR-код
                              </button>
                              {item.status !== "retired" && (
                                <button type="button" onClick={() => openOperationModal("writeoff", detailItem)} className="app-action-danger inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
                                  <Archive size={15} /> Списать
                                </button>
                              )}
                            </div>

                            {detailItem.notes && (
                              <div className="app-surface mb-3 rounded-xl p-4">
                                <p className="app-text-muted text-xs font-medium uppercase tracking-wide">Заметки</p>
                                <p className="mt-2 text-sm leading-6 text-[var(--foreground)]">{detailItem.notes}</p>
                              </div>
                            )}

                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                              {metaItems.map((meta) => (
                                <div key={meta.label} className="app-surface rounded-xl px-3 py-3">
                                  <p className="app-text-muted text-[11px] font-medium uppercase tracking-wide">{meta.label}</p>
                                  <p className="mt-1 text-sm font-medium text-[var(--foreground)]">{meta.value}</p>
                                </div>
                              ))}
                            </div>

                            <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
                              <div className="app-surface rounded-xl p-4">
                                <p className="app-text-muted mb-3 text-xs font-medium uppercase tracking-wide">История переводов</p>
                                {transferHistory.length === 0 ? (
                                  <p className="app-text-muted text-sm">Переводы пока не выполнялись</p>
                                ) : (
                                  <div className="space-y-2">
                                    {transferHistory.map((entry) => (
                                      <div key={entry.id} className="app-surface-muted rounded-lg px-3 py-2 text-sm text-[var(--foreground)]">
                                        <div className="flex items-center justify-between gap-3">
                                          <span className="font-medium">{formatDate(entry.date)}</span>
                                          <span className="app-text-muted text-xs">{entry.created_by || "—"}</span>
                                        </div>
                                        <p className="app-text-muted mt-1 text-xs">{entry.from_department || "—"} → {entry.to_department || "—"}</p>
                                        {(entry.from_person || entry.to_person) && <p className="app-text-muted mt-1 text-xs">{entry.from_person || "—"} → {entry.to_person || "—"}</p>}
                                        {entry.reason && <p className="app-text-muted mt-1 text-xs">Причина: {entry.reason}</p>}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              <div className="app-surface rounded-xl p-4">
                                <p className="app-text-muted mb-3 text-xs font-medium uppercase tracking-wide">История обслуживания</p>
                                {maintenanceRecords.length === 0 ? (
                                  <p className="app-text-muted text-sm">Записей обслуживания пока нет</p>
                                ) : (
                                  <div className="space-y-2">
                                    {maintenanceRecords.map((record) => (
                                      <div key={record.id} className="app-surface-muted rounded-lg px-3 py-2 text-sm text-[var(--foreground)]">
                                        <div className="flex items-center justify-between gap-3">
                                          <span className="font-medium">{record.type_display || record.type}</span>
                                          <span className="app-text-muted text-xs">{formatDate(record.date)}</span>
                                        </div>
                                        {record.description && <p className="app-text-muted mt-1 text-xs">{record.description}</p>}
                                        <div className="app-text-muted mt-1 flex items-center justify-between gap-3 text-xs">
                                          <span>{record.performed_by_name || "—"}</span>
                                          <span>{formatMoney(record.cost)}</span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </>
                        )}

                      </div>
                    )}
                  </article>
                );
              })}
              </>
            )}
          </div>

          {/* Load more */}
          {nextPage && (
            <div className="mt-4 flex justify-center">
              <button type="button" onClick={handleLoadMore} disabled={loadingMore} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60">
                {loadingMore ? "Загружаем..." : "Загрузить ещё"}
              </button>
            </div>
          )}
        </section>
      )}

      {/* ===== Modal create/edit ===== */}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={modalMode === "create" ? "Добавить оборудование" : "Редактировать оборудование"} size="md" footer={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button type="button" onClick={closeModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={() => handleSave(modalMode)} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                {modalMode === "create" ? "Добавить" : "Сохранить"}
              </button>
            </div>
      }>
            {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}

            <div className="flex flex-col gap-3">
              {/* Название */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Название оборудования *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Ноутбук Lenovo ThinkPad X1..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Категория */}
              <SearchableSelectSingle
                label="Категория *"
                placeholder="Выберите категорию..."
                items={categories.map((c) => ({ id: c.id, name: c.name }))}
                selectedId={form.category}
                onSelect={(id) => setForm((p) => ({ ...p, category: id }))}
              />

              {isCreateMode && previewInventoryNumber && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
                  Следующий инвентарный номер: <span className="font-semibold text-gray-900">{previewInventoryNumber}</span>
                </div>
              )}

              {/* Отдел */}
              <SearchableSelectSingle
                label="Отдел *"
                placeholder="Выберите отдел..."
                items={filteredDepartmentsForForm.map((d) => ({ id: d.id, name: d.name }))}
                selectedId={form.department}
                onSelect={(id) => setForm((p) => ({ ...p, department: id }))}
                disabled={Boolean(isCreateMode && createOptions && !createOptions.can_choose_department)}
              />

              {/* Ответственный */}
              <SearchableSelectSingle
                label="Ответственный"
                placeholder="Выберите сотрудника..."
                items={filteredEmployeesForForm.map((emp) => ({ id: emp.id, name: displayUserName(emp) }))}
                selectedId={form.responsible_person}
                onSelect={(id) => setForm((p) => ({ ...p, responsible_person: id }))}
                disabled={Boolean(isCreateMode && createOptions && !createOptions.can_choose_responsible)}
              />

              {modalMode === "create" && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Количество</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={form.quantity}
                    onChange={(e) => setForm((p) => ({ ...p, quantity: Math.max(1, Math.min(100, Number(e.target.value) || 1)) }))}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              )}

              {/* Дата покупки + стоимость */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Дата покупки *</label>
                  <input
                    type="date"
                    value={form.purchase_date}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_date: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Стоимость (₽) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.purchase_cost}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_cost: e.target.value }))}
                    placeholder="0.00"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              </div>

              {/* Серийный номер */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Серийный номер</label>
                <input
                  value={form.serial_number}
                  onChange={(e) => setForm((p) => ({ ...p, serial_number: e.target.value }))}
                  placeholder="SN-XXXXX"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Расположение */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Расположение</label>
                <input
                  value={form.location}
                  onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
                  placeholder="Офис 305, стол 2..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Заметки */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Заметки</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
                  placeholder="Заметки об оборудовании..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>
            </div>
      </Modal>

      <Modal isOpen={!!operationModal && !!selectedEquipment} onClose={closeOperationModal} title={
            operationModal === "transfer" ? "Перевод оборудования" :
            operationModal === "writeoff" ? "Списание оборудования" :
            "Добавить обслуживание"
      } size="md" footer={
            <div className="flex items-center justify-end gap-2">
              <button type="button" onClick={closeOperationModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              {operationModal === "transfer" && <button type="button" onClick={() => { void handleTransfer(); }} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">Перевести</button>}
              {operationModal === "writeoff" && <button type="button" onClick={() => { void handleWriteOff(); }} disabled={busyKey !== null} className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-60">Списать</button>}
              {operationModal === "maintenance" && <button type="button" onClick={() => { void handleMaintenance(); }} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">Добавить</button>}
            </div>
      }>
            {operationModal === "transfer" && (
              <div className="space-y-3">
                <SearchableSelectSingle
                  label="Новый отдел"
                  placeholder="Выберите отдел..."
                  items={departments.map((dept) => ({ id: dept.id, name: dept.name }))}
                  selectedId={transferForm.to_department}
                  onSelect={(id) => setTransferForm((prev) => ({ ...prev, to_department: id }))}
                />
                <SearchableSelectSingle
                  label="Новый ответственный"
                  placeholder="Выберите сотрудника..."
                  items={employees.map((employee) => ({ id: employee.id, name: displayUserName(employee) }))}
                  selectedId={transferForm.to_person}
                  onSelect={(id) => setTransferForm((prev) => ({ ...prev, to_person: id }))}
                />
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Причина</label>
                  <textarea value={transferForm.reason} onChange={(e) => setTransferForm((prev) => ({ ...prev, reason: e.target.value }))} rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                </div>
              </div>
            )}

            {operationModal === "writeoff" && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Причина списания</label>
                <textarea value={writeOffReason} onChange={(e) => setWriteOffReason(e.target.value)} rows={4} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
              </div>
            )}

            {operationModal === "maintenance" && (
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Тип обслуживания</label>
                  <select value={maintenanceForm.type} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, type: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-800 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100">
                    <option value="repair">Ремонт</option>
                    <option value="maintenance">Обслуживание</option>
                    <option value="inspection">Осмотр</option>
                    <option value="upgrade">Модернизация</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-500">Дата</label>
                    <input type="date" value={maintenanceForm.date} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, date: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-500">Стоимость</label>
                    <input type="number" step="0.01" value={maintenanceForm.cost} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, cost: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Описание</label>
                  <textarea value={maintenanceForm.description} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, description: e.target.value }))} rows={4} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                </div>
              </div>
            )}
      </Modal>

      {/* ===== Attachment preview removed (no attachment fields in model) ===== */}
    </AppShell>
  );
}
