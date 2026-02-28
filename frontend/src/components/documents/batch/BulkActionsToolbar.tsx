"use client";

import { useState, useCallback, useMemo } from "react";
import {
  CheckSquare,
  Square,
  Folder,
  Tag,
  RefreshCw,
  Trash2,
  X,
  Loader2,
  Undo2,
  CheckCircle2,
} from "lucide-react";

export interface Document {
  id: number;
  title: string;
  status?: string;
  folder?: string;
  tags?: string[];
}

export interface BatchAction {
  type: "move" | "add_tags" | "change_status" | "delete";
  documentIds: number[];
  params?: {
    folderId?: string;
    tagIds?: string[];
    status?: string;
  };
}

export interface BatchOperationResult {
  success: boolean;
  affectedIds: number[];
  action: BatchAction;
  timestamp: number;
}

interface BulkActionsToolbarProps {
  selectedIds: number[];
  documents: Document[];
  onMove?: (folderId: string, documentIds: number[]) => Promise<void>;
  onAddTags?: (tagIds: string[], documentIds: number[]) => Promise<void>;
  onChangeStatus?: (status: string, documentIds: number[]) => Promise<void>;
  onDelete?: (documentIds: number[]) => Promise<void>;
  onClearSelection: () => void;
  availableFolders?: Array<{ id: string; name: string }>;
  availableTags?: Array<{ id: string; name: string }>;
  availableStatuses?: Array<{ id: string; name: string }>;
}

export function BulkActionsToolbar({
  selectedIds,
  documents,
  onMove,
  onAddTags,
  onChangeStatus,
  onDelete,
  onClearSelection,
  availableFolders = [],
  availableTags = [],
  availableStatuses = [],
}: BulkActionsToolbarProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [history, setHistory] = useState<BatchOperationResult[]>([]);
  const [showUndoNotification, setShowUndoNotification] = useState(false);

  // Выбранные документы
  const selectedDocuments = useMemo(
    () => documents.filter((doc) => selectedIds.includes(doc.id)),
    [documents, selectedIds]
  );

  // Выполнение batch операции с прогрессом
  const executeBatchOperation = useCallback(
    async (
      action: string,
      operation: (id: number) => Promise<void>,
      onSuccess?: () => void
    ) => {
      setIsProcessing(true);
      setCurrentAction(action);
      setProgress(0);

      const total = selectedIds.length;
      let completed = 0;

      try {
        // Выполняем операцию для каждого документа
        for (const id of selectedIds) {
          await operation(id);
          completed++;
          setProgress(Math.round((completed / total) * 100));
        }

        // Успех
        if (onSuccess) onSuccess();
        
        setShowUndoNotification(true);
        setTimeout(() => setShowUndoNotification(false), 5000);
      } catch (error) {
        console.error(`Batch operation failed: ${action}`, error);
      } finally {
        setIsProcessing(false);
        setCurrentAction(null);
        setProgress(0);
      }
    },
    [selectedIds]
  );

  // Переместить в папку
  const handleMove = useCallback(
    async (folderId: string) => {
      if (!onMove || !folderId) return;

      const action: BatchAction = {
        type: "move",
        documentIds: [...selectedIds],
        params: { folderId },
      };

      await executeBatchOperation(
        "Перемещение",
        async () => {
          await onMove(folderId, selectedIds);
        },
        () => {
          setHistory((prev) => [
            ...prev,
            {
              success: true,
              affectedIds: [...selectedIds],
              action,
              timestamp: Date.now(),
            },
          ]);
          onClearSelection();
        }
      );
    },
    [selectedIds, onMove, executeBatchOperation, onClearSelection]
  );

  // Добавить теги
  const handleAddTags = useCallback(
    async (tagIds: string[]) => {
      if (!onAddTags || !tagIds.length) return;

      const action: BatchAction = {
        type: "add_tags",
        documentIds: [...selectedIds],
        params: { tagIds },
      };

      await executeBatchOperation(
        "Добавление тегов",
        async () => {
          await onAddTags(tagIds, selectedIds);
        },
        () => {
          setHistory((prev) => [
            ...prev,
            {
              success: true,
              affectedIds: [...selectedIds],
              action,
              timestamp: Date.now(),
            },
          ]);
          onClearSelection();
        }
      );
    },
    [selectedIds, onAddTags, executeBatchOperation, onClearSelection]
  );

  // Изменить статус
  const handleChangeStatus = useCallback(
    async (status: string) => {
      if (!onChangeStatus || !status) return;

      const action: BatchAction = {
        type: "change_status",
        documentIds: [...selectedIds],
        params: { status },
      };

      await executeBatchOperation(
        "Изменение статуса",
        async () => {
          await onChangeStatus(status, selectedIds);
        },
        () => {
          setHistory((prev) => [
            ...prev,
            {
              success: true,
              affectedIds: [...selectedIds],
              action,
              timestamp: Date.now(),
            },
          ]);
          onClearSelection();
        }
      );
    },
    [selectedIds, onChangeStatus, executeBatchOperation, onClearSelection]
  );

  // Удалить
  const handleDelete = useCallback(async () => {
    if (!onDelete) return;

    const confirmed = confirm(
      `Вы уверены, что хотите удалить ${selectedIds.length} документов?`
    );
    if (!confirmed) return;

    const action: BatchAction = {
      type: "delete",
      documentIds: [...selectedIds],
    };

    await executeBatchOperation(
      "Удаление",
      async () => {
        await onDelete(selectedIds);
      },
      () => {
        setHistory((prev) => [
          ...prev,
          {
            success: true,
            affectedIds: [...selectedIds],
            action,
            timestamp: Date.now(),
          },
        ]);
        onClearSelection();
      }
    );
  }, [selectedIds, onDelete, executeBatchOperation, onClearSelection]);

  // Отмена последнего действия (базовая реализация)
  const handleUndo = useCallback(() => {
    const lastOperation = history[history.length - 1];
    if (!lastOperation) return;

    // В реальном приложении здесь должна быть реверсия операции
    console.log("Undo operation:", lastOperation);
    setHistory((prev) => prev.slice(0, -1));
    setShowUndoNotification(false);
  }, [history]);

  if (selectedIds.length === 0) return null;

  return (
    <>
      {/* Toolbar */}
      <div className="sticky top-0 z-10 rounded-lg border border-sky-200 bg-sky-50 p-3 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm font-medium text-sky-900">
              <CheckSquare size={16} />
              <span>
                Выбрано: <span className="font-bold">{selectedIds.length}</span>
              </span>
            </div>

            {/* Действия */}
            <div className="flex items-center gap-2">
              {/* Переместить */}
              {onMove && availableFolders.length > 0 && (
                <select
                  onChange={(e) => handleMove(e.target.value)}
                  value=""
                  disabled={isProcessing}
                  className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-sky-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="">Переместить в...</option>
                  {availableFolders.map((folder) => (
                    <option key={folder.id} value={folder.id}>
                      📁 {folder.name}
                    </option>
                  ))}
                </select>
              )}

              {/* Добавить теги */}
              {onAddTags && availableTags.length > 0 && (
                <select
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value) {
                      handleAddTags([value]);
                      e.target.value = "";
                    }
                  }}
                  value=""
                  disabled={isProcessing}
                  className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-sky-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="">Добавить тег...</option>
                  {availableTags.map((tag) => (
                    <option key={tag.id} value={tag.id}>
                      🏷️ {tag.name}
                    </option>
                  ))}
                </select>
              )}

              {/* Изменить статус */}
              {onChangeStatus && availableStatuses.length > 0 && (
                <select
                  onChange={(e) => handleChangeStatus(e.target.value)}
                  value=""
                  disabled={isProcessing}
                  className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm focus:border-sky-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="">Изменить статус...</option>
                  {availableStatuses.map((status) => (
                    <option key={status.id} value={status.id}>
                      {status.name}
                    </option>
                  ))}
                </select>
              )}

              {/* Удалить */}
              {onDelete && (
                <button
                  onClick={handleDelete}
                  disabled={isProcessing}
                  className="flex items-center gap-1 rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                  title="Удалить выбранные"
                >
                  <Trash2 size={14} />
                  Удалить
                </button>
              )}
            </div>
          </div>

          {/* Очистить выбор */}
          <button
            onClick={onClearSelection}
            disabled={isProcessing}
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X size={14} />
            Отменить
          </button>
        </div>

        {/* Прогресс */}
        {isProcessing && (
          <div className="mt-3">
            <div className="mb-1 flex items-center gap-2 text-xs text-sky-700">
              <Loader2 size={12} className="animate-spin" />
              <span>{currentAction}...</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-sky-200">
              <div
                className="h-full bg-sky-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Undo уведомление */}
      {showUndoNotification && history.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 shadow-lg">
          <CheckCircle2 size={20} className="text-green-600" />
          <span className="text-sm font-medium text-green-900">
            Операция выполнена успешно
          </span>
          <button
            onClick={handleUndo}
            className="flex items-center gap-1 rounded bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700"
          >
            <Undo2 size={12} />
            Отменить
          </button>
          <button
            onClick={() => setShowUndoNotification(false)}
            className="text-green-600 hover:text-green-800"
          >
            <X size={16} />
          </button>
        </div>
      )}
    </>
  );
}

// Хук для управления выбором документов
export function useDocumentSelection(documents: Document[]) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const toggleDocument = useCallback((id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  }, []);

  const toggleAll = useCallback(() => {
    setSelectedIds((prev) =>
      prev.length === documents.length ? [] : documents.map((doc) => doc.id)
    );
  }, [documents]);

  const clearSelection = useCallback(() => {
    setSelectedIds([]);
  }, []);

  const isSelected = useCallback(
    (id: number) => selectedIds.includes(id),
    [selectedIds]
  );

  const isAllSelected = useMemo(
    () => documents.length > 0 && selectedIds.length === documents.length,
    [documents.length, selectedIds.length]
  );

  return {
    selectedIds,
    toggleDocument,
    toggleAll,
    clearSelection,
    isSelected,
    isAllSelected,
  };
}
