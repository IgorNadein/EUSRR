"use client";

import { useEffect, useState } from "react";
import { X, Search, CheckCircle, AlertCircle, Users, Download } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import { Modal } from "@/components/ui";

interface Employee {
  id: number;
  first_name: string;
  last_name: string;
  patronymic?: string;
  email: string;
  position?: {
    name: string;
  };
  department?: {
    name: string;
  };
}

interface AcknowledgementsData {
  acknowledged: Employee[];
  unacknowledged: Employee[];
  counts: {
    acknowledged: number;
    unacknowledged: number;
    total: number;
  };
}

interface DocumentAcknowledgementsReportProps {
  documentId: number;
  documentTitle: string;
  onClose: () => void;
}

export function DocumentAcknowledgementsReport({
  documentId,
  documentTitle,
  onClose,
}: DocumentAcknowledgementsReportProps) {
  const [data, setData] = useState<AcknowledgementsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "acknowledged" | "unacknowledged">("all");

  useEffect(() => {
    loadData();
  }, [documentId, search]);

  const loadData = async () => {
    setLoading(true);
    try {
      const result = await apiClient.getDocumentAcknowledgements(documentId, search || undefined);
      setData(result);
    } catch (err) {
      console.error("Ошибка загрузки ведомости:", err);
      toast.error("Не удалось загрузить ведомость");
    } finally {
      setLoading(false);
    }
  };

  const exportToCSV = () => {
    if (!data) return;

    const rows: string[][] = [
      ["ФИО", "Email", "Должность", "Отдел", "Статус"],
    ];

    // Добавляем ознакомившихся
    data.acknowledged.forEach((emp) => {
      rows.push([
        `${emp.last_name} ${emp.first_name} ${emp.patronymic || ""}`.trim(),
        emp.email,
        emp.position?.name || "-",
        emp.department?.name || "-",
        "Ознакомлен",
      ]);
    });

    // Добавляем не ознакомившихся
    data.unacknowledged.forEach((emp) => {
      rows.push([
        `${emp.last_name} ${emp.first_name} ${emp.patronymic || ""}`.trim(),
        emp.email,
        emp.position?.name || "-",
        emp.department?.name || "-",
        "Не ознакомлен",
      ]);
    });

    const csvContent = rows.map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");
    const blob = new Blob(["\ufeff" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ознакомления_${documentTitle.replace(/[^a-zA-Zа-яА-Я0-9]/g, "_")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const getDisplayList = (): Employee[] => {
    if (!data) return [];
    
    switch (activeTab) {
      case "acknowledged":
        return data.acknowledged;
      case "unacknowledged":
        return data.unacknowledged;
      default:
        return [...data.acknowledged, ...data.unacknowledged];
    }
  };

  const displayList = getDisplayList();

  return (
    <Modal isOpen onClose={onClose} noHeader noPadding size="xl" className="h-[95vh] sm:h-[90vh]">
        {/* Header */}
        <div className="app-divider flex shrink-0 items-start justify-between gap-2 border-b p-3 sm:gap-3 sm:p-6">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-[var(--foreground)] sm:text-lg">Ведомость ознакомлений</h2>
            <p className="app-text-muted mt-1 truncate text-xs" title={documentTitle}>{documentTitle}</p>
          </div>
          <button
            onClick={onClose}
            className="app-action-secondary shrink-0 rounded-lg p-1.5 sm:p-2"
          >
            <X size={18} className="sm:w-5 sm:h-5" />
          </button>
        </div>

        {/* Stats */}
        {data && (
          <div className="app-divider grid shrink-0 grid-cols-1 gap-2 border-b p-3 sm:grid-cols-3 sm:gap-4 sm:p-6">
            <div className="app-selected rounded-lg p-3 sm:rounded-xl sm:p-4">
              <div className="app-accent-text flex items-center gap-1.5 sm:gap-2">
                <Users size={16} className="sm:w-5 sm:h-5" />
                <span className="text-xs sm:text-sm font-medium">Всего</span>
              </div>
              <p className="mt-1 text-xl font-bold text-[var(--foreground)] sm:mt-2 sm:text-2xl">{data.counts.total}</p>
            </div>
            <div className="app-feedback-success rounded-lg p-3 sm:rounded-xl sm:p-4">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <CheckCircle size={16} className="sm:w-5 sm:h-5" />
                <span className="text-xs sm:text-sm font-medium">Ознакомлены</span>
              </div>
              <p className="mt-1 text-xl font-bold sm:mt-2 sm:text-2xl">{data.counts.acknowledged}</p>
              <p className="text-xs opacity-80">
                {data.counts.total > 0 ? Math.round((data.counts.acknowledged / data.counts.total) * 100) : 0}%
              </p>
            </div>
            <div className="app-feedback-warning rounded-lg p-3 sm:rounded-xl sm:p-4">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <AlertCircle size={16} className="sm:w-5 sm:h-5" />
                <span className="text-xs sm:text-sm font-medium">Не ознакомлены</span>
              </div>
              <p className="mt-1 text-xl font-bold sm:mt-2 sm:text-2xl">{data.counts.unacknowledged}</p>
              <p className="text-xs opacity-80">
                {data.counts.total > 0 ? Math.round((data.counts.unacknowledged / data.counts.total) * 100) : 0}%
              </p>
            </div>
          </div>
        )}

        {/* Tabs & Search */}
        <div className="app-divider shrink-0 border-b p-3 sm:p-4">
          <div className="mb-3 flex flex-col items-stretch gap-2 sm:mb-4 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search size={14} className="app-text-muted absolute left-2.5 top-1/2 -translate-y-1/2 sm:left-3 sm:h-4 sm:w-4" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по ФИО или email..."
                className="app-input w-full py-1.5 pl-8 pr-3 text-xs sm:py-2 sm:pl-10 sm:pr-4 sm:text-sm"
              />
            </div>
            <button
              onClick={exportToCSV}
              className="app-action-secondary inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium sm:gap-2 sm:px-4 sm:py-2 sm:text-sm"
            >
              <Download size={14} className="sm:w-4 sm:h-4" />
              <span className="hidden sm:inline">Экспорт CSV</span>
              <span className="sm:hidden">Экспорт</span>
            </button>
          </div>

          <div className="flex gap-1.5 sm:gap-2 overflow-x-auto pb-1">
            <button
              onClick={() => setActiveTab("all")}
              className={`shrink-0 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm ${
                activeTab === "all"
                  ? "app-pill-active"
                  : "app-pill"
              }`}
            >
              Все ({data?.counts.total || 0})
            </button>
            <button
              onClick={() => setActiveTab("acknowledged")}
              className={`shrink-0 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm ${
                activeTab === "acknowledged"
                  ? "app-pill-active"
                  : "app-pill"
              }`}
            >
              Ознакомлены ({data?.counts.acknowledged || 0})
            </button>
            <button
              onClick={() => setActiveTab("unacknowledged")}
              className={`shrink-0 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm ${
                activeTab === "unacknowledged"
                  ? "app-pill-active"
                  : "app-pill"
              }`}
            >
              Не ознакомлены ({data?.counts.unacknowledged || 0})
            </button>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8 sm:py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-[3px] border-[var(--border-subtle)] border-t-[var(--accent-primary)] sm:h-8 sm:w-8 sm:border-4" />
            </div>
          ) : displayList.length === 0 ? (
            <div className="py-8 sm:py-12 text-center">
              <p className="app-text-muted text-xs sm:text-sm">Сотрудников не найдено</p>
            </div>
          ) : (
            <div className="space-y-1.5 sm:space-y-2">
              {displayList.map((emp) => {
                const isAcknowledged = data!.acknowledged.some((a) => a.id === emp.id);
                return (
                  <div
                    key={emp.id}
                    className={`flex items-center justify-between gap-2 rounded-lg p-2 sm:p-3 ${
                      isAcknowledged
                        ? "app-feedback-success"
                        : "app-feedback-warning"
                    }`}
                  >
                    <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
                      {isAcknowledged ? (
                        <CheckCircle size={16} className="shrink-0 sm:h-5 sm:w-5" />
                      ) : (
                        <AlertCircle size={16} className="shrink-0 sm:h-5 sm:w-5" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-[var(--foreground)] sm:text-sm">
                          {emp.last_name} {emp.first_name} {emp.patronymic || ""}
                        </p>
                        <div className="app-text-muted flex flex-wrap gap-1 text-xs sm:gap-2">
                          <span className="truncate">{emp.email}</span>
                          {emp.position && <span className="shrink-0">• {emp.position.name}</span>}
                          {emp.department && <span className="shrink-0 hidden sm:inline">• {emp.department.name}</span>}
                        </div>
                      </div>
                    </div>
                    <span
                      className="shrink-0 text-xs font-medium"
                    >
                      {isAcknowledged ? "Ознакомлен" : "Требуется"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
    </Modal>
  );
}
