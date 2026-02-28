"use client";

import { useEffect, useState } from "react";
import { X, Search, CheckCircle, AlertCircle, Users, Download } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-200 p-6">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Ведомость ознакомлений</h2>
            <p className="mt-1 text-sm text-gray-600">{documentTitle}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        </div>

        {/* Stats */}
        {data && (
          <div className="grid grid-cols-3 gap-4 border-b border-gray-200 p-6">
            <div className="rounded-xl bg-blue-50 p-4">
              <div className="flex items-center gap-2 text-blue-700">
                <Users size={20} />
                <span className="text-sm font-medium">Всего</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-blue-900">{data.counts.total}</p>
            </div>
            <div className="rounded-xl bg-green-50 p-4">
              <div className="flex items-center gap-2 text-green-700">
                <CheckCircle size={20} />
                <span className="text-sm font-medium">Ознакомлены</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-green-900">{data.counts.acknowledged}</p>
              <p className="text-xs text-green-600">
                {data.counts.total > 0 ? Math.round((data.counts.acknowledged / data.counts.total) * 100) : 0}%
              </p>
            </div>
            <div className="rounded-xl bg-amber-50 p-4">
              <div className="flex items-center gap-2 text-amber-700">
                <AlertCircle size={20} />
                <span className="text-sm font-medium">Не ознакомлены</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-amber-900">{data.counts.unacknowledged}</p>
              <p className="text-xs text-amber-600">
                {data.counts.total > 0 ? Math.round((data.counts.unacknowledged / data.counts.total) * 100) : 0}%
              </p>
            </div>
          </div>
        )}

        {/* Tabs & Search */}
        <div className="border-b border-gray-200 p-4">
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по ФИО или email..."
                className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-4 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
            <button
              onClick={exportToCSV}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              <Download size={16} />
              Экспорт CSV
            </button>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("all")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeTab === "all"
                  ? "bg-sky-100 text-sky-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Все ({data?.counts.total || 0})
            </button>
            <button
              onClick={() => setActiveTab("acknowledged")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeTab === "acknowledged"
                  ? "bg-green-100 text-green-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Ознакомлены ({data?.counts.acknowledged || 0})
            </button>
            <button
              onClick={() => setActiveTab("unacknowledged")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeTab === "unacknowledged"
                  ? "bg-amber-100 text-amber-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Не ознакомлены ({data?.counts.unacknowledged || 0})
            </button>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
            </div>
          ) : displayList.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-gray-500">Сотрудников не найдено</p>
            </div>
          ) : (
            <div className="space-y-2">
              {displayList.map((emp) => {
                const isAcknowledged = data!.acknowledged.some((a) => a.id === emp.id);
                return (
                  <div
                    key={emp.id}
                    className={`flex items-center justify-between rounded-lg border p-3 ${
                      isAcknowledged
                        ? "border-green-200 bg-green-50"
                        : "border-amber-200 bg-amber-50"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {isAcknowledged ? (
                        <CheckCircle size={20} className="shrink-0 text-green-600" />
                      ) : (
                        <AlertCircle size={20} className="shrink-0 text-amber-600" />
                      )}
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {emp.last_name} {emp.first_name} {emp.patronymic || ""}
                        </p>
                        <div className="flex flex-wrap gap-2 text-xs text-gray-600">
                          <span>{emp.email}</span>
                          {emp.position && <span>• {emp.position.name}</span>}
                          {emp.department && <span>• {emp.department.name}</span>}
                        </div>
                      </div>
                    </div>
                    <span
                      className={`text-xs font-medium ${
                        isAcknowledged ? "text-green-700" : "text-amber-700"
                      }`}
                    >
                      {isAcknowledged ? "Ознакомлен" : "Требуется"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
