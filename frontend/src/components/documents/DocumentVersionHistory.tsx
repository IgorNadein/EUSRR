"use client";

import { useState, useEffect } from "react";
import { History, RotateCcw, User as UserIcon, Clock } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

interface Version {
  id: number;
  revision_id: number;
  date_created: string;
  user: {
    id: number;
    full_name: string;
  } | null;
  comment: string;
  data: any;
}

interface DocumentVersionHistoryProps {
  documentId: number;
  onRevert?: () => void;
}

export function DocumentVersionHistory({ documentId, onRevert }: DocumentVersionHistoryProps) {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(true);
  const [reverting, setReverting] = useState(false);

  useEffect(() => {
    loadVersions();
  }, [documentId]);

  const loadVersions = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getDocumentVersions(documentId);
      const data = Array.isArray(response) ? response : (response.results || []);
      setVersions(data);
    } catch (error) {
      console.error("Ошибка загрузки версий:", error);
      toast.error("Не удалось загрузить историю версий");
    } finally {
      setLoading(false);
    }
  };

  const handleRevert = async (versionId: number) => {
    const comment = prompt("Укажите причину отката (опционально):");
    if (comment === null) return; // User cancelled

    setReverting(true);
    try {
      await apiClient.revertDocumentToVersion(documentId, versionId);
      toast.success("Документ откачен к выбранной версии");
      if (onRevert) {
        onRevert();
      }
      await loadVersions();
    } catch (error) {
      console.error("Ошибка отката:", error);
      toast.error("Не удалось откатить документ");
    } finally {
      setReverting(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getChangedFields = (versionData: any): string[] => {
    if (!versionData || !versionData.data) return [];
    const fields = Object.keys(versionData.data);
    return fields.filter(f => !['id', 'created_at', 'updated_at'].includes(f));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="py-8 text-center">
        <History size={48} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm text-gray-500">
          История версий пока пуста
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <History size={18} className="text-gray-500" />
        <h3 className="text-sm font-medium text-gray-900">
          История изменений ({versions.length})
        </h3>
      </div>

      <div className="space-y-2">
        {versions.map((version, index) => {
          const isLatest = index === 0;
          const changedFields = getChangedFields(version);

          return (
            <div
              key={version.id}
              className={`rounded-lg border p-3 ${
                isLatest
                  ? "border-sky-300 bg-sky-50"
                  : "border-gray-200 bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 space-y-2">
                  {/* Header */}
                  <div className="flex items-center gap-2">
                    {isLatest && (
                      <span className="rounded-full bg-sky-600 px-2 py-0.5 text-xs font-medium text-white">
                        Текущая
                      </span>
                    )}
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <Clock size={12} />
                      {formatDate(version.date_created)}
                    </div>
                  </div>

                  {/* User */}
                  {version.user && (
                    <div className="flex items-center gap-1.5 text-sm">
                      <UserIcon size={14} className="text-gray-400" />
                      <span className="font-medium text-gray-700">
                        {version.user.full_name}
                      </span>
                    </div>
                  )}

                  {/* Comment */}
                  {version.comment && (
                    <p className="text-sm text-gray-600">{version.comment}</p>
                  )}

                  {/* Changed fields */}
                  {changedFields.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {changedFields.slice(0, 5).map((field) => (
                        <span
                          key={field}
                          className="inline-block rounded bg-gray-200 px-2 py-0.5 text-xs text-gray-600"
                        >
                          {field}
                        </span>
                      ))}
                      {changedFields.length > 5 && (
                        <span className="inline-block px-2 py-0.5 text-xs text-gray-500">
                          +{changedFields.length - 5} ещё
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Revert button */}
                {!isLatest && (
                  <button
                    onClick={() => handleRevert(version.id)}
                    disabled={reverting}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
                    title="Откатить к этой версии"
                  >
                    <RotateCcw size={12} />
                    Откатить
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
