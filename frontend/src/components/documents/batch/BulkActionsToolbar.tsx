"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import {
  ChevronDown,
  CheckSquare,
  Download,
  Folder,
  Tag,
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
  folder?: string | { id: number; name: string };
  tags?: string[] | Array<{ id: number; name: string; color?: string }>;
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
  onMove?: (folderId: string, documentIds: number[]) => Promise<void>;
  onAddTags?: (tagIds: string[], documentIds: number[]) => Promise<void>;
  onChangeStatus?: (status: string, documentIds: number[]) => Promise<void>;
  onDownload?: (documentIds: number[]) => Promise<void>;
  onDelete?: (documentIds: number[]) => Promise<void>;
  onClearSelection: () => void;
  availableFolders?: Array<{ id: string; name: string }>;
  availableTags?: Array<{ id: string; name: string }>;
  availableStatuses?: Array<{ id: string; name: string }>;
}

export function BulkActionsToolbar({
  selectedIds,
  onMove,
  onAddTags,
  onChangeStatus,
  onDownload,
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
  const [openActionMenu, setOpenActionMenu] = useState<"move" | "tag" | "status" | null>(null);
  const actionMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!openActionMenu) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (actionMenuRef.current && !actionMenuRef.current.contains(event.target as Node)) {
        setOpenActionMenu(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [openActionMenu]);

  // Выполнение batch операции с прогрессом
  const executeBatchOperation = useCallback(
    async (
      action: string,
      operation: () => Promise<void>,
      onSuccess?: () => void
    ) => {
      setIsProcessing(true);
      setCurrentAction(action);
      setProgress(15);

      try {
        await operation();
        setProgress(100);

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
    []
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

  // Скачать выбранные
  const handleDownload = useCallback(async () => {
    if (!onDownload) return;

    await executeBatchOperation("Подготовка архива", async () => {
      await onDownload(selectedIds);
    });
  }, [selectedIds, onDownload, executeBatchOperation]);

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
      <div className="app-selected sticky top-0 z-10 rounded-xl px-3 py-2.5 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center gap-2">
          <div className="app-accent-text flex h-8 shrink-0 items-center gap-2 rounded-full bg-[color:var(--accent-soft)] px-3 text-sm font-semibold">
            <CheckSquare size={16} className="shrink-0" />
            <span>
              Выбрано: <span className="font-bold">{selectedIds.length}</span>
            </span>
          </div>

          {/* Действия */}
          <div ref={actionMenuRef} className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {/* Переместить */}
            {onMove && availableFolders.length > 0 && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setOpenActionMenu((prev) => (prev === "move" ? null : "move"))}
                  disabled={isProcessing}
                  className="app-action-secondary flex h-8 items-center gap-1.5 rounded-full px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                  title="Переместить выбранные"
                  aria-expanded={openActionMenu === "move"}
                  aria-haspopup="menu"
                >
                  <Folder size={14} />
                  Переместить
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${openActionMenu === "move" ? "rotate-180" : ""}`}
                  />
                </button>

                {openActionMenu === "move" && (
                  <div className="app-menu absolute left-0 top-full z-30 mt-2 max-h-64 w-64 overflow-y-auto rounded-xl py-1.5">
                    {availableFolders.map((folder) => (
                      <button
                        key={folder.id}
                        type="button"
                        onClick={() => {
                          setOpenActionMenu(null);
                          void handleMove(folder.id);
                        }}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                      >
                        <Folder size={14} className="shrink-0" />
                        <span className="truncate">{folder.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Добавить теги */}
            {onAddTags && availableTags.length > 0 && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setOpenActionMenu((prev) => (prev === "tag" ? null : "tag"))}
                  disabled={isProcessing}
                  className="app-action-secondary flex h-8 items-center gap-1.5 rounded-full px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                  title="Добавить тег к выбранным"
                  aria-expanded={openActionMenu === "tag"}
                  aria-haspopup="menu"
                >
                  <Tag size={14} />
                  Тег
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${openActionMenu === "tag" ? "rotate-180" : ""}`}
                  />
                </button>

                {openActionMenu === "tag" && (
                  <div className="app-menu absolute left-0 top-full z-30 mt-2 max-h-64 w-56 overflow-y-auto rounded-xl py-1.5">
                    {availableTags.map((tag) => (
                      <button
                        key={tag.id}
                        type="button"
                        onClick={() => {
                          setOpenActionMenu(null);
                          void handleAddTags([tag.id]);
                        }}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                      >
                        <Tag size={14} className="shrink-0" />
                        <span className="truncate">{tag.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Изменить статус */}
            {onChangeStatus && availableStatuses.length > 0 && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setOpenActionMenu((prev) => (prev === "status" ? null : "status"))}
                  disabled={isProcessing}
                  className="app-action-secondary flex h-8 items-center gap-1.5 rounded-full px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                  title="Изменить статус выбранных"
                  aria-expanded={openActionMenu === "status"}
                  aria-haspopup="menu"
                >
                  Статус
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${openActionMenu === "status" ? "rotate-180" : ""}`}
                  />
                </button>

                {openActionMenu === "status" && (
                  <div className="app-menu absolute left-0 top-full z-30 mt-2 max-h-64 w-56 overflow-y-auto rounded-xl py-1.5">
                    {availableStatuses.map((status) => (
                      <button
                        key={status.id}
                        type="button"
                        onClick={() => {
                          setOpenActionMenu(null);
                          void handleChangeStatus(status.id);
                        }}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                      >
                        <span className="truncate">{status.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Скачать */}
            {onDownload && (
              <button
                onClick={handleDownload}
                disabled={isProcessing}
                className="app-action-secondary flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                title="Скачать выбранные архивом"
              >
                <Download size={14} />
                Скачать
              </button>
            )}

            {/* Удалить */}
            {onDelete && (
              <button
                onClick={handleDelete}
                disabled={isProcessing}
                className="app-action-danger flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                title="Удалить выбранные"
              >
                <Trash2 size={14} />
                Удалить
              </button>
            )}
          </div>

          {/* Очистить выбор */}
          <button
            onClick={onClearSelection}
            disabled={isProcessing}
            className="app-text-muted ml-auto flex h-8 shrink-0 items-center gap-1 rounded-full px-2.5 text-sm hover:bg-[var(--surface-secondary)] hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X size={14} />
            Отменить
          </button>
        </div>
        {/* Прогресс */}
        {isProcessing && (
          <div className="mt-3">
            <div className="app-accent-text mb-1 flex items-center gap-2 text-xs">
              <Loader2 size={12} className="animate-spin" />
              <span>{currentAction}...</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[color:var(--accent-soft-strong)]">
              <div
                className="h-full bg-[var(--accent-primary)] transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Undo уведомление */}
      {showUndoNotification && history.length > 0 && (
        <div className="app-feedback-success fixed bottom-4 right-4 z-50 flex items-center gap-3 rounded-lg px-4 py-3 shadow-[var(--shadow-elevated)]">
          <CheckCircle2 size={20} />
          <span className="text-sm font-medium">
            Операция выполнена успешно
          </span>
          <button
            onClick={handleUndo}
            className="app-action-primary flex items-center gap-1 rounded px-3 py-1 text-xs"
          >
            <Undo2 size={12} />
            Отменить
          </button>
          <button
            onClick={() => setShowUndoNotification(false)}
            className="transition hover:opacity-80"
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
