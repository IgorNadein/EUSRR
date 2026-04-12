"use client";

import QRCode from "qrcode";
import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Archive, ArrowRightLeft, ArrowUpDown, Check, ChevronDown, ChevronRight, Copy, Download, ExternalLink, Filter, MessageSquare, Monitor, Pencil, Plus, QrCode, Search, Shield, Trash2, Wrench, X } from "lucide-react";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { formatDate, formatMoney } from "@/lib/shared";
import { useEquipmentPage } from "@/hooks/useEquipmentPage";
import { Modal } from "@/components/ui";
import type { Equipment, EquipmentTransferHistoryEntry, MaintenanceRecord } from "@/types/api";

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
    className: "app-feedback-success",
    accentClass: "bg-emerald-500",
    surfaceClass: "border-emerald-100",
  },
  in_use: {
    label: "В использовании",
    className: "app-selected",
    accentClass: "bg-sky-500",
    surfaceClass: "border-sky-100",
  },
  maintenance: {
    label: "На обслуживании",
    className: "app-feedback-warning",
    accentClass: "bg-amber-500",
    surfaceClass: "border-amber-100",
  },
  retired: {
    label: "Списано",
    className: "app-badge",
    accentClass: "bg-gray-400",
    surfaceClass: "border-gray-200",
  },
  broken: {
    label: "Сломано",
    className: "app-feedback-danger",
    accentClass: "bg-rose-500",
    surfaceClass: "border-rose-100",
  },
};

const defaultStatusMeta = {
  label: "—",
  className: "app-badge",
  accentClass: "bg-gray-300",
  surfaceClass: "border-gray-200",
};

type EquipmentMetaItem = {
  label: string;
  value: string;
};

function EquipmentDetailContent({
  detailItem,
  metaItems,
  transferHistory,
  maintenanceRecords,
  canManage,
  onTransfer,
  onMaintenance,
  onWriteOff,
}: {
  detailItem: Equipment;
  metaItems: EquipmentMetaItem[];
  transferHistory: EquipmentTransferHistoryEntry[];
  maintenanceRecords: MaintenanceRecord[];
  canManage: boolean;
  onTransfer: () => void;
  onMaintenance: () => void;
  onWriteOff: () => void;
}) {
  return (
    <div className="space-y-3">
      {canManage && (
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onTransfer} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
            <ArrowRightLeft size={15} /> Перевести
          </button>
          <button type="button" onClick={onMaintenance} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
            <Wrench size={15} /> Обслуживание
          </button>
          {detailItem.status !== "retired" && (
            <button type="button" onClick={onWriteOff} className="app-action-danger inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
              <Archive size={15} /> Списать
            </button>
          )}
        </div>
      )}

      {detailItem.notes && (
        <div className="app-surface-muted rounded-xl p-4">
          <p className="app-text-muted text-xs font-medium uppercase tracking-wide">Заметки</p>
          <p className="app-text-wrap mt-2 text-sm leading-6 text-[var(--foreground)]">{detailItem.notes}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {metaItems.map((meta) => (
          <div key={meta.label} className="app-surface-muted rounded-xl px-3 py-3">
            <p className="app-text-muted text-[11px] font-medium uppercase tracking-wide">{meta.label}</p>
            <p className="app-text-wrap mt-1 text-sm font-medium text-[var(--foreground)]">{meta.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="app-surface-muted rounded-xl p-4">
          <p className="app-text-muted mb-3 text-xs font-medium uppercase tracking-wide">История переводов</p>
          {transferHistory.length === 0 ? (
            <p className="app-text-muted text-sm">Переводы пока не выполнялись</p>
          ) : (
            <div className="space-y-2">
              {transferHistory.map((entry) => (
                <div key={entry.id} className="app-surface rounded-lg px-3 py-2 text-sm text-[var(--foreground)]">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{formatDate(entry.date)}</span>
                    <span className="app-text-muted text-xs">{entry.created_by || "—"}</span>
                  </div>
                  <p className="app-text-wrap app-text-muted mt-1 text-xs">{entry.from_department || "—"} → {entry.to_department || "—"}</p>
                  {(entry.from_person || entry.to_person) && <p className="app-text-wrap app-text-muted mt-1 text-xs">{entry.from_person || "—"} → {entry.to_person || "—"}</p>}
                  {entry.reason && <p className="app-text-wrap app-text-muted mt-1 text-xs">Причина: {entry.reason}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="app-surface-muted rounded-xl p-4">
          <p className="app-text-muted mb-3 text-xs font-medium uppercase tracking-wide">История обслуживания</p>
          {maintenanceRecords.length === 0 ? (
            <p className="app-text-muted text-sm">Записей обслуживания пока нет</p>
          ) : (
            <div className="space-y-2">
              {maintenanceRecords.map((record) => (
                <div key={record.id} className="app-surface rounded-lg px-3 py-2 text-sm text-[var(--foreground)]">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{record.type_display || record.type}</span>
                    <span className="app-text-muted text-xs">{formatDate(record.date)}</span>
                  </div>
                  {record.description && <p className="app-text-wrap app-text-muted mt-1 text-xs">{record.description}</p>}
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
    </div>
  );
}

export default function EquipmentPage() {
  return (
    <Suspense fallback={<AppShell><div className="app-surface rounded-2xl p-8 text-center"><p className="app-text-muted text-sm">Загрузка оборудования...</p></div></AppShell>}>
      <EquipmentPageContent />
    </Suspense>
  );
}

/* ──── main page ──── */
function EquipmentPageContent() {
  const { user } = useUser();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
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
    openEquipmentById,
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

  const [qrEquipment, setQrEquipment] = useState<typeof filteredItems[number] | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const [qrCopySuccess, setQrCopySuccess] = useState(false);
  const handledLinkedEquipmentRef = useRef<number | null>(null);
  const equipmentMenuRef = useRef<HTMLDivElement | null>(null);
  const [equipmentMenuOpenId, setEquipmentMenuOpenId] = useState<number | null>(null);

  const linkedEquipmentParam = searchParams.get("item");
  const linkedEquipmentId = Number(linkedEquipmentParam || "");
  const linkedEquipment = useMemo(
    () => (linkedEquipmentId > 0 ? detailsMap[linkedEquipmentId] || filteredItems.find((item) => item.id === linkedEquipmentId) || null : null),
    [detailsMap, filteredItems, linkedEquipmentId],
  );
  const linkedEquipmentMeta = useMemo(
    () => (linkedEquipment ? getEquipmentMeta(linkedEquipment) : []),
    [getEquipmentMeta, linkedEquipment],
  );
  const linkedTransferHistory = linkedEquipmentId > 0 ? transferHistoryMap[linkedEquipmentId] || [] : [];
  const linkedMaintenanceRecords = linkedEquipmentId > 0 ? maintenanceMap[linkedEquipmentId] || [] : [];

  const buildEquipmentLink = useCallback((equipmentId: number) => {
    if (typeof window === "undefined") return `/equipment?item=${equipmentId}`;
    return `${window.location.origin}/equipment?item=${equipmentId}`;
  }, []);

  useEffect(() => {
    if (!linkedEquipmentParam || !Number.isFinite(linkedEquipmentId) || linkedEquipmentId <= 0) {
      handledLinkedEquipmentRef.current = null;
      return;
    }

    if (handledLinkedEquipmentRef.current === linkedEquipmentId) {
      return;
    }

    handledLinkedEquipmentRef.current = linkedEquipmentId;

    let cancelled = false;

    void (async () => {
      await openEquipmentById(linkedEquipmentId, { expand: false });
      if (cancelled) return;
    })();

    return () => {
      cancelled = true;
    };
  }, [linkedEquipmentId, linkedEquipmentParam, openEquipmentById]);

  useEffect(() => {
    if (!qrEquipment) {
      setQrDataUrl(null);
      setQrError(null);
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        setQrError(null);
        const nextDataUrl = await QRCode.toDataURL(buildEquipmentLink(qrEquipment.id), {
          width: 320,
          margin: 1,
          errorCorrectionLevel: "M",
          color: {
            dark: "#0f172a",
            light: "#ffffffff",
          },
        });
        if (!cancelled) {
          setQrDataUrl(nextDataUrl);
        }
      } catch (error) {
        if (!cancelled) {
          setQrError(String((error as Error)?.message || "Не удалось сформировать QR-код"));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [buildEquipmentLink, qrEquipment]);

  useEffect(() => {
    if (equipmentMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (equipmentMenuRef.current && !equipmentMenuRef.current.contains(event.target as Node)) {
        setEquipmentMenuOpenId(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setEquipmentMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [equipmentMenuOpenId]);

  const handleOpenQrModal = useCallback((equipment: typeof filteredItems[number]) => {
    setQrCopySuccess(false);
    setQrEquipment(equipment);
  }, []);

  const handleCloseQrModal = useCallback(() => {
    setQrEquipment(null);
    setQrDataUrl(null);
    setQrError(null);
    setQrCopySuccess(false);
  }, []);

  const handleCopyQrLink = useCallback(async () => {
    if (!qrEquipment) return;
    try {
      await navigator.clipboard.writeText(buildEquipmentLink(qrEquipment.id));
      setQrCopySuccess(true);
      window.setTimeout(() => setQrCopySuccess(false), 1600);
    } catch {
      setQrError("Не удалось скопировать ссылку");
    }
  }, [buildEquipmentLink, qrEquipment]);

  const handleDownloadQr = useCallback(() => {
    if (!qrEquipment || !qrDataUrl) return;
    const link = document.createElement("a");
    link.href = qrDataUrl;
    link.download = `${qrEquipment.inventory_number || `equipment-${qrEquipment.id}`}.png`;
    link.click();
  }, [qrDataUrl, qrEquipment]);

  const handleOpenEquipmentLink = useCallback(() => {
    if (!qrEquipment) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.set("item", String(qrEquipment.id));
    router.replace(`${pathname}?${nextParams.toString()}`, { scroll: false });
    handleCloseQrModal();
  }, [handleCloseQrModal, pathname, qrEquipment, router, searchParams]);

  const handleCloseLinkedEquipmentModal = useCallback(() => {
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("item");
    const nextQuery = nextParams.toString();
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  const qrLink = useMemo(
    () => (qrEquipment ? buildEquipmentLink(qrEquipment.id) : ""),
    [buildEquipmentLink, qrEquipment],
  );
  /* ──── render ──── */
  return (
    <AppShell>
      {loading ? (
        <div className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="app-text-muted text-sm">Загрузка оборудования...</p>
        </div>
      ) : error ? (
        <div className="app-feedback-danger rounded-2xl p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          {/* Header */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Оборудование</p>
            <button
              type="button"
              onClick={() => { void openCreateModal(); }}
              className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium"
            >
              <Plus size={14} /> Добавить оборудование
            </button>
          </div>

          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="app-feedback-success mb-3 rounded-lg px-3 py-2 text-sm">{actionSuccess}</p>}

          {/* Search + filter toggle */}
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по оборудованию"
                className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              />
            </div>
            <button
              type="button"
              title="Фильтры"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${filtersOpen ? "app-selected app-accent-text" : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"}`}
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
                className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-xs font-medium"
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
                    ? "app-pill-active"
                    : "app-pill"
                }`}
              >
                <span>{mode.label}</span>
              </button>
            ))}
          </div>

          {/* Filters panel */}
          {filtersOpen && (
            <div className="app-surface-muted mb-3 flex flex-col gap-2 rounded-xl p-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                  <option value="">Все статусы</option>
                  {Object.entries(statusMeta).map(([key, meta]) => (
                    <option key={key} value={key}>{meta.label}</option>
                  ))}
                </select>
                <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                  <option value="">Все категории</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                  <option value="">Все отделы</option>
                  {departments.map((dep) => (
                    <option key={dep.id} value={dep.id}>{dep.name}</option>
                  ))}
                </select>
                <select value={responsibleFilter} onChange={(e) => setResponsibleFilter(e.target.value)} className="app-select rounded-lg px-3 py-2 text-sm">
                  <option value="">Все сотрудники</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>{displayUserName(emp)}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="app-text-muted shrink-0 text-xs">Дата покупки:</span>
                <input type="date" value={dateFromFilter} onChange={(e) => setDateFromFilter(e.target.value)} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" placeholder="С" />
                <span className="app-text-muted text-xs">—</span>
                <input type="date" value={dateToFilter} onChange={(e) => setDateToFilter(e.target.value)} className="app-input flex-1 rounded-lg px-3 py-2 text-sm" placeholder="По" />
              </div>
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setStatusFilter(""); setCategoryFilter(""); setDepartmentFilter(""); setResponsibleFilter(""); setDateFromFilter(""); setDateToFilter(""); }} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium transition">
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* Items list */}
          <div className="space-y-2">
            {filteredItems.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-8 text-center">
                <Monitor size={22} className="app-text-muted mx-auto mb-2" />
                <p className="app-text-muted text-sm">Записи об оборудовании не найдены</p>
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
                const hasSecondaryActions = canEditThis || canDeleteThis;
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
                  <article id={`equipment-${item.id}`} key={item.id} className={`app-surface-muted rounded-xl transition hover:border-[var(--border-strong)] ${equipmentMenuOpenId === item.id ? "relative z-20 overflow-visible" : "overflow-hidden"}`}>
                    <div className="px-4 py-3">
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={() => toggleRow(item.id)}
                          aria-label={rowOpen ? "Свернуть детали" : "Развернуть детали"}
                          className="app-action-secondary mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                        >
                          <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className={`h-2 w-2 shrink-0 rounded-full ${st.accentClass}`} />
                                <h3 className="truncate text-sm font-semibold text-[var(--foreground)]">{item.name || "Без названия"}</h3>
                              </div>
                              <div className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                <span className="font-medium text-[var(--foreground)]">{item.inventory_number || "Без инв. номера"}</span>
                                {item.serial_number && <span>SN: {item.serial_number}</span>}
                              </div>
                            </div>

                            <div
                              ref={equipmentMenuOpenId === item.id ? equipmentMenuRef : null}
                              className="flex shrink-0 items-center gap-2"
                            >
                              {statusKey && <span className={`app-status-pill shrink-0 ${st.className}`}>{st.label}</span>}
                              {hasSecondaryActions ? (
                                <div className="relative">
                                  <button
                                    type="button"
                                    onClick={() => setEquipmentMenuOpenId((prev) => (prev === item.id ? null : item.id))}
                                    className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                                    title="Действия с оборудованием"
                                    aria-label="Действия с оборудованием"
                                    aria-expanded={equipmentMenuOpenId === item.id}
                                    aria-haspopup="menu"
                                  >
                                    <ChevronRight
                                      size={15}
                                      className={`transition-transform duration-200 ${equipmentMenuOpenId === item.id ? "rotate-90" : ""}`}
                                    />
                                  </button>
                                  {equipmentMenuOpenId === item.id ? (
                                    <div className="app-menu absolute right-0 top-full z-20 mt-2 w-44 rounded-xl py-1.5">
                                      {canEditThis ? (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setEquipmentMenuOpenId(null);
                                            openEdit(item);
                                          }}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                        >
                                          <Pencil size={14} className="app-text-muted" />
                                          Редактировать
                                        </button>
                                      ) : null}
                                      {canDeleteThis ? (
                                        <button
                                          type="button"
                                          title="Удалить"
                                          onClick={() => {
                                            setEquipmentMenuOpenId(null);
                                            void handleDelete(item.id);
                                          }}
                                          disabled={busyKey === `delete-${item.id}`}
                                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                                        >
                                          <Trash2 size={13} className="text-[var(--danger-foreground)]" />
                                          Удалить
                                        </button>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                          </div>

                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            {item.is_under_warranty && (
                              <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium" title="На гарантии">
                                <Shield size={11} /> Гарантия
                              </span>
                            )}
                          </div>

                          <div className="app-text-muted mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
                            <div>
                              <span>Стоимость:</span>{" "}
                              <span className="font-medium text-[var(--foreground)]">{formatMoney(item.purchase_cost)}</span>
                            </div>
                            <div>
                              <span>Покупка:</span>{" "}
                              <span className="font-medium text-[var(--foreground)]">{formatDate(item.purchase_date) || "—"}</span>
                            </div>
                            {responsibleId ? (
                              <div className="col-span-2 min-w-0">
                                <span>Ответственный:</span>{" "}
                                <Link href={responsibleLink} className="font-medium text-[var(--accent-primary-strong)] hover:text-[var(--accent-primary)]">
                                  {responsibleName}
                                </Link>
                              </div>
                            ) : (
                              <div className="col-span-2">Ответственный не назначен</div>
                            )}
                          </div>

                          <div className="mt-3 flex flex-wrap items-center gap-1.5">
                            <button type="button" title={`Комментарии (${commentsTotal})`} onClick={() => toggleComments(item.id)} className="app-action-secondary relative inline-flex h-8 w-8 items-center justify-center rounded-lg">
                              <MessageSquare size={15} />
                              {commentsTotal > 0 && (
                                <span className="app-counter absolute -right-1 -top-1 inline-flex min-w-4 items-center justify-center px-1 py-0.5 text-[10px] font-bold text-white">{commentsTotal}</span>
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {(rowOpen || commentsOpen) && (
                      <div className="mt-4 space-y-3 px-4 pb-4">
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
                                      <p className="app-text-wrap">{c.text}</p>
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
                              <div className="app-selected rounded-xl px-3 py-2 text-sm">
                                Загружаем детали оборудования...
                              </div>
                            )}

                            <div className="flex flex-wrap gap-2">
                              <button type="button" onClick={() => openOperationModal("transfer", detailItem)} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
                                <ArrowRightLeft size={15} /> Перевести
                              </button>
                              <button type="button" onClick={() => openOperationModal("maintenance", detailItem)} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
                                <Wrench size={15} /> Обслуживание
                              </button>
                              <button type="button" onClick={() => handleOpenQrModal(detailItem)} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
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
                                <p className="app-text-wrap mt-2 text-sm leading-6 text-[var(--foreground)]">{detailItem.notes}</p>
                              </div>
                            )}

                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                              {metaItems.map((meta) => (
                                <div key={meta.label} className="app-surface rounded-xl px-3 py-3">
                                  <p className="app-text-muted text-[11px] font-medium uppercase tracking-wide">{meta.label}</p>
                                  <p className="app-text-wrap mt-1 text-sm font-medium text-[var(--foreground)]">{meta.value}</p>
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
                                        <p className="app-text-wrap app-text-muted mt-1 text-xs">{entry.from_department || "—"} → {entry.to_department || "—"}</p>
                                        {(entry.from_person || entry.to_person) && <p className="app-text-wrap app-text-muted mt-1 text-xs">{entry.from_person || "—"} → {entry.to_person || "—"}</p>}
                                        {entry.reason && <p className="app-text-wrap app-text-muted mt-1 text-xs">Причина: {entry.reason}</p>}
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
                                        {record.description && <p className="app-text-wrap app-text-muted mt-1 text-xs">{record.description}</p>}
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
              <button type="button" onClick={handleLoadMore} disabled={loadingMore} className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60">
                {loadingMore ? "Загружаем..." : "Загрузить ещё"}
              </button>
            </div>
          )}
        </section>
      )}

      {/* ===== Modal create/edit ===== */}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={modalMode === "create" ? "Добавить оборудование" : "Редактировать оборудование"} size="md" footer={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button type="button" onClick={closeModal} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium">Отмена</button>
              <button type="button" onClick={() => handleSave(modalMode)} disabled={busyKey !== null} className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">
                {modalMode === "create" ? "Добавить" : "Сохранить"}
              </button>
            </div>
      }>
            {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}

            <div className="flex flex-col gap-3">
              {/* Название */}
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Название оборудования *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Ноутбук Lenovo ThinkPad X1..."
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
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
                <div className="app-surface-muted rounded-lg px-3 py-2 text-sm text-[var(--muted-foreground)]">
                  Следующий инвентарный номер: <span className="font-semibold text-[var(--foreground)]">{previewInventoryNumber}</span>
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
                  <label className="app-text-muted mb-1 block text-xs font-medium">Количество</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={form.quantity}
                    onChange={(e) => setForm((p) => ({ ...p, quantity: Math.max(1, Math.min(100, Number(e.target.value) || 1)) }))}
                    className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              )}

              {/* Дата покупки + стоимость */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="app-text-muted mb-1 block text-xs font-medium">Дата покупки *</label>
                  <input
                    type="date"
                    value={form.purchase_date}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_date: e.target.value }))}
                    className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="app-text-muted mb-1 block text-xs font-medium">Стоимость (₽) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.purchase_cost}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_cost: e.target.value }))}
                    placeholder="0.00"
                    className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {/* Серийный номер */}
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Серийный номер</label>
                <input
                  value={form.serial_number}
                  onChange={(e) => setForm((p) => ({ ...p, serial_number: e.target.value }))}
                  placeholder="SN-XXXXX"
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>

              {/* Расположение */}
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Расположение</label>
                <input
                  value={form.location}
                  onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
                  placeholder="Офис 305, стол 2..."
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </div>

              {/* Заметки */}
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Заметки</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
                  placeholder="Заметки об оборудовании..."
                  rows={3}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
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
              <button type="button" onClick={closeOperationModal} className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium">Отмена</button>
              {operationModal === "transfer" && <button type="button" onClick={() => { void handleTransfer(); }} disabled={busyKey !== null} className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">Перевести</button>}
              {operationModal === "writeoff" && <button type="button" onClick={() => { void handleWriteOff(); }} disabled={busyKey !== null} className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-60">Списать</button>}
              {operationModal === "maintenance" && <button type="button" onClick={() => { void handleMaintenance(); }} disabled={busyKey !== null} className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">Добавить</button>}
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
                  <label className="app-text-muted mb-1 block text-xs font-medium">Причина</label>
                  <textarea value={transferForm.reason} onChange={(e) => setTransferForm((prev) => ({ ...prev, reason: e.target.value }))} rows={3} className="app-input w-full rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
            )}

            {operationModal === "writeoff" && (
              <div>
                <label className="app-text-muted mb-1 block text-xs font-medium">Причина списания</label>
                <textarea value={writeOffReason} onChange={(e) => setWriteOffReason(e.target.value)} rows={4} className="app-input w-full rounded-lg px-3 py-2 text-sm" />
              </div>
            )}

            {operationModal === "maintenance" && (
              <div className="space-y-3">
                <div>
                  <label className="app-text-muted mb-1 block text-xs font-medium">Тип обслуживания</label>
                  <select value={maintenanceForm.type} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, type: e.target.value }))} className="app-select w-full rounded-lg px-3 py-2 text-sm">
                    <option value="repair">Ремонт</option>
                    <option value="maintenance">Обслуживание</option>
                    <option value="inspection">Осмотр</option>
                    <option value="upgrade">Модернизация</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="app-text-muted mb-1 block text-xs font-medium">Дата</label>
                    <input type="date" value={maintenanceForm.date} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, date: e.target.value }))} className="app-input w-full rounded-lg px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="app-text-muted mb-1 block text-xs font-medium">Стоимость</label>
                    <input type="number" step="0.01" value={maintenanceForm.cost} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, cost: e.target.value }))} className="app-input w-full rounded-lg px-3 py-2 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="app-text-muted mb-1 block text-xs font-medium">Описание</label>
                  <textarea value={maintenanceForm.description} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, description: e.target.value }))} rows={4} className="app-input w-full rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
            )}
      </Modal>

      <Modal
        isOpen={Boolean(linkedEquipmentParam && linkedEquipmentId > 0)}
        onClose={handleCloseLinkedEquipmentModal}
        title="Карточка оборудования"
        size="lg"
      >
        {linkedEquipment ? (
          <div className="space-y-4">
            <div className="app-surface-muted rounded-xl p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${(statusMeta[String(linkedEquipment.status || "").toLowerCase()] ?? defaultStatusMeta).accentClass}`} />
                    <h3 className="text-base font-semibold text-[var(--foreground)]">
                      {linkedEquipment.name || "Без названия"}
                    </h3>
                  </div>
                  <p className="app-text-muted mt-1 text-sm">
                    {linkedEquipment.inventory_number || `ID ${linkedEquipment.id}`}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {String(linkedEquipment.status || "").toLowerCase() && (
                    <span className={`app-status-pill ${(statusMeta[String(linkedEquipment.status || "").toLowerCase()] ?? defaultStatusMeta).className}`}>
                      {(statusMeta[String(linkedEquipment.status || "").toLowerCase()] ?? defaultStatusMeta).label}
                    </span>
                  )}
                  {linkedEquipment.is_under_warranty && (
                    <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium">
                      <Shield size={11} /> Гарантия
                    </span>
                  )}
                </div>
              </div>
            </div>

            <EquipmentDetailContent
              detailItem={linkedEquipment}
              metaItems={linkedEquipmentMeta}
              transferHistory={linkedTransferHistory}
              maintenanceRecords={linkedMaintenanceRecords}
              canManage={canManage}
              onTransfer={() => openOperationModal("transfer", linkedEquipment)}
              onMaintenance={() => openOperationModal("maintenance", linkedEquipment)}
              onWriteOff={() => openOperationModal("writeoff", linkedEquipment)}
            />
          </div>
        ) : (
          <div className="app-surface-muted rounded-xl p-6 text-center">
            <p className="app-text-muted text-sm">Загружаем карточку оборудования...</p>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={!!qrEquipment}
        onClose={handleCloseQrModal}
        title="QR-код оборудования"
        size="md"
        footer={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button type="button" onClick={handleCopyQrLink} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
              {qrCopySuccess ? <Check size={15} /> : <Copy size={15} />}
              {qrCopySuccess ? "Скопировано" : "Скопировать ссылку"}
            </button>
            <button type="button" onClick={handleDownloadQr} disabled={!qrDataUrl} className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-60">
              <Download size={15} />
              Скачать PNG
            </button>
            <button type="button" onClick={handleOpenEquipmentLink} className="app-action-primary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
              <ExternalLink size={15} />
              Открыть запись
            </button>
          </div>
        }
      >
        {qrEquipment ? (
          <div className="space-y-4">
            <div className="app-surface-muted rounded-xl p-4">
              <p className="text-sm font-semibold text-[var(--foreground)]">
                {qrEquipment.name || "Без названия"}
              </p>
              <p className="app-text-muted mt-1 text-sm">
                {qrEquipment.inventory_number || `ID ${qrEquipment.id}`}
              </p>
            </div>

            <div className="app-surface-muted flex items-center justify-center rounded-2xl p-5">
              {qrError ? (
                <p className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{qrError}</p>
              ) : qrDataUrl ? (
                <img
                  src={qrDataUrl}
                  alt={`QR-код для ${qrEquipment.inventory_number || qrEquipment.name || "оборудования"}`}
                  className="h-72 w-72 rounded-xl bg-white p-3"
                />
              ) : (
                <div className="app-text-muted flex h-72 w-72 items-center justify-center rounded-xl bg-white text-sm">
                  Формируем QR-код...
                </div>
              )}
            </div>

            <div className="app-surface-muted rounded-xl p-4">
              <p className="text-sm font-semibold text-[var(--foreground)]">Содержимое</p>
              <p className="app-text-wrap app-text-muted mt-2 text-sm">{qrLink}</p>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* ===== Attachment preview removed (no attachment fields in model) ===== */}
    </AppShell>
  );
}
