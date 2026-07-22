"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { 
  AlertCircle, 
  Loader2, 
  FolderOpen,
  Plus,
  ScrollText,
  Tag as TagIcon,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import type { Department, User } from "@/types/api";
import { toast } from "sonner";
import { processDocument, needsProcessing, type ProcessingProgress } from "@/lib/document-utils";
import { DocumentTagQuickCreate, type QuickDocumentTag } from "./DocumentTagQuickCreate";
import {
  DocumentAudienceSelector,
  type DocumentAudienceMode,
} from "./DocumentAudienceSelector";
import { DocumentFilePanel, DocumentFileRow } from "./DocumentFilePanel";

interface DocumentTagOption {
  id: number;
  name: string;
  color?: string;
}

interface FolderOption {
  id: number;
  name: string;
  parent_id: number | null;
  path?: string;
}

interface FolderOptionRow {
  folder: FolderOption;
  level: number;
}

interface DocumentUploadFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
  onFolderCreated?: () => void;
  currentFolderId?: number | null;
  mode?: "document" | "regulation";
}

interface UploadFileItem {
  id: string;
  file: File;
  processedFile?: File | Blob;
  extractedText: string;
  processingError?: string;
}

function getDefaultDocumentTitle(fileName: string): string {
  return fileName.replace(/\.[^/.]+$/, "").trim() || fileName;
}

function createUploadItem(file: File): UploadFileItem {
  return {
    id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
    file,
    extractedText: "",
  };
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
}

function getFileForUpload(item: UploadFileItem): File | Blob {
  if (!item.processedFile) return item.file;
  if (item.processedFile instanceof File) return item.processedFile;

  return new File([item.processedFile], item.file.name, {
    type: item.processedFile.type || item.file.type,
    lastModified: item.file.lastModified,
  });
}

function buildFolderOptionRows(folders: FolderOption[]): FolderOptionRow[] {
  const childrenByParent = new Map<number | null, FolderOption[]>();

  folders.forEach((folder) => {
    const parentId = folder.parent_id ?? null;
    const children = childrenByParent.get(parentId) || [];
    children.push(folder);
    childrenByParent.set(parentId, children);
  });

  childrenByParent.forEach((children) => {
    children.sort((a, b) => a.name.localeCompare(b.name, "ru"));
  });

  const rows: FolderOptionRow[] = [];
  const appendChildren = (parentId: number | null, level: number) => {
    (childrenByParent.get(parentId) || []).forEach((folder) => {
      rows.push({ folder, level });
      appendChildren(folder.id, level + 1);
    });
  };

  appendChildren(null, 0);
  return rows;
}

// Сообщения для различных этапов обработки
const STAGE_MESSAGES: Record<string, string> = {
  compressing: "Сжатие изображения...",
  ocr: "Распознавание текста (OCR)...",
  extracting_text: "Извлечение текста...",
  generating_thumbnail: "Создание миниатюры...",
  complete: "Обработка завершена",
};

export function DocumentUploadForm({
  onSuccess,
  onCancel,
  onFolderCreated,
  currentFolderId,
  mode = "document",
}: DocumentUploadFormProps) {
  const isDedicatedRegulation = mode === "regulation";
  const [isRegulation, setIsRegulation] = useState(isDedicatedRegulation);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [uploadItems, setUploadItems] = useState<UploadFileItem[]>([]);
  const [filesOpen, setFilesOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState<ProcessingProgress | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New fields for extended functionality
  const [sentToAll, setSentToAll] = useState(true);
  const [acknowledgementMode, setAcknowledgementMode] = useState<DocumentAudienceMode>("all");
  const [selectedDepartments, setSelectedDepartments] = useState<number[]>([]);
  const [selectedRecipients, setSelectedRecipients] = useState<number[]>([]);
  const [acknowledgementDepartments, setAcknowledgementDepartments] = useState<number[]>([]);
  const [acknowledgementRecipients, setAcknowledgementRecipients] = useState<number[]>([]);
  
  // Metadata fields
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(
    isDedicatedRegulation ? null : currentFolderId ?? null,
  );
  const [newFolderName, setNewFolderName] = useState("");
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [folderCreateError, setFolderCreateError] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  
  // Data for selects
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [documentTags, setDocumentTags] = useState<DocumentTagOption[]>([]);
  
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [loadingFolders, setLoadingFolders] = useState(false);
  const [loadingDocumentTags, setLoadingDocumentTags] = useState(false);
  const folderOptionRows = useMemo(() => buildFolderOptionRows(folders), [folders]);
  const selectedFolder = useMemo(
    () => folders.find((folder) => folder.id === selectedFolderId) || null,
    [folders, selectedFolderId],
  );

  useEffect(() => {
    setSelectedFolderId(isDedicatedRegulation ? null : currentFolderId ?? null);
  }, [currentFolderId, isDedicatedRegulation]);

  // Load departments and employees
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoadingDepartments(true);
        const deptResponse = await apiClient.getDepartments({ limit: 1000 });
        setDepartments(deptResponse.results || deptResponse);
      } catch (err) {
        console.error("Ошибка загрузки отделов:", err);
      } finally {
        setLoadingDepartments(false);
      }

      try {
        setLoadingEmployees(true);
        const empResponse = await apiClient.getEmployees({
          limit: 1000,
          is_active: true,
          ordering: "last_name,first_name",
        });
        setEmployees(empResponse.results || empResponse);
      } catch (err) {
        console.error("Ошибка загрузки сотрудников:", err);
      } finally {
        setLoadingEmployees(false);
      }

      if (!isDedicatedRegulation) {
        try {
          setLoadingFolders(true);
          const foldersResponse = await apiClient.getFolders({ limit: 1000 });
          const foldersData = foldersResponse.results || foldersResponse;
          setFolders(Array.isArray(foldersData) ? foldersData : []);
        } catch (err) {
          console.error("Ошибка загрузки папок:", err);
        } finally {
          setLoadingFolders(false);
        }
      }
      
      try {
        setLoadingDocumentTags(true);
        const tagsResponse = await apiClient.getDocumentTags();
        setDocumentTags(tagsResponse.results || tagsResponse);
      } catch (err) {
        console.error("Ошибка загрузки тегов:", err);
      } finally {
        setLoadingDocumentTags(false);
      }
    };
    
    loadData();
  }, [isDedicatedRegulation]);

  const acknowledgementEmployees = useMemo(() => {
    if (sentToAll) return employees;
    const departmentIds = new Set(selectedDepartments);
    const recipientIds = new Set(selectedRecipients);
    return employees.filter((employee) => (
      recipientIds.has(employee.id)
      || (employee.departments || []).some((department) => departmentIds.has(department.id))
    ));
  }, [employees, selectedDepartments, selectedRecipients, sentToAll]);

  const acknowledgementDepartmentOptions = useMemo(() => {
    if (sentToAll) return departments;
    const departmentIds = new Set(selectedDepartments);
    return departments.filter((department) => departmentIds.has(department.id));
  }, [departments, selectedDepartments, sentToAll]);

  useEffect(() => {
    if (sentToAll) return;
    const allowedEmployeeIds = new Set(acknowledgementEmployees.map((employee) => employee.id));
    const allowedDepartmentIds = new Set(selectedDepartments);
    setAcknowledgementRecipients((current) => current.filter((id) => allowedEmployeeIds.has(id)));
    setAcknowledgementDepartments((current) => current.filter((id) => allowedDepartmentIds.has(id)));
  }, [acknowledgementEmployees, selectedDepartments, sentToAll]);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const newItems = (isDedicatedRegulation ? acceptedFiles.slice(0, 1) : acceptedFiles).map(createUploadItem);
    const totalAfterDrop = isDedicatedRegulation ? newItems.length : uploadItems.length + newItems.length;

    setUploadItems((prev) => isDedicatedRegulation ? newItems : [...prev, ...newItems]);
    setFilesOpen(true);
    setError(null);

    if (totalAfterDrop === 1 && !title.trim()) {
      setTitle(getDefaultDocumentTitle(newItems[0].file.name));
    } else if (totalAfterDrop > 1) {
      setTitle("");
    }

    if (!newItems.some((item) => needsProcessing(item.file))) return;

    setIsProcessing(true);
    setProcessingProgress({
      stage: "extracting_text",
      progress: 0,
      message: "Начало обработки...",
    });

    let hasProcessingErrors = false;

    try {
      for (const [index, item] of newItems.entries()) {
        if (!needsProcessing(item.file)) continue;

        try {
          const result = await processDocument(item.file, {
            enableOCR: true,
            enableTextExtraction: true,
            enableThumbnail: true,
            onProgress: (progress) => {
              setProcessingProgress({
                ...progress,
                progress: Math.round(progress.progress),
                message:
                  newItems.length > 1
                    ? `Файл ${index + 1} из ${newItems.length}: ${progress.message}`
                    : progress.message,
              });
            },
          });

          setUploadItems((prev) =>
            prev.map((current) =>
              current.id === item.id
                ? {
                    ...current,
                    processedFile: result.processedFile,
                    extractedText: result.extractedText || current.extractedText,
                    processingError: undefined,
                  }
                : current
            )
          );
        } catch (err) {
          hasProcessingErrors = true;
          console.error("Ошибка обработки документа:", err);
          setUploadItems((prev) =>
            prev.map((current) =>
              current.id === item.id
                ? {
                    ...current,
                    processingError:
                      err instanceof Error ? err.message : "Не удалось обработать документ",
                  }
                : current
            )
          );
        }
      }

      if (hasProcessingErrors) {
        setError("Некоторые файлы не удалось обработать. Они будут загружены в исходном виде.");
        toast("Некоторые файлы не удалось обработать");
      } else {
        toast.success(
          newItems.length > 1
            ? "Файлы обработаны успешно"
            : isRegulation
              ? "Регламент обработан успешно"
              : "Документ обработан успешно",
        );
      }
    } finally {
      setIsProcessing(false);
      setProcessingProgress(null);
    }
  }, [isDedicatedRegulation, isRegulation, title, uploadItems.length]);

  const removeUploadItem = (id: string) => {
    const next = uploadItems.filter((item) => item.id !== id);

    setUploadItems(next);

    if (next.length === 0) {
      setTitle("");
    } else if (next.length === 1 && !title.trim()) {
      setTitle(getDefaultDocumentTitle(next[0].file.name));
    }
  };

  const updateSingleExtractedText = (value: string) => {
    setUploadItems((prev) =>
      prev.map((item, index) =>
        index === 0 ? { ...item, extractedText: value } : item
      )
    );
  };

  const handleCreatedTag = (tag: QuickDocumentTag) => {
    setDocumentTags((prev) => {
      const next = prev.some((item) => item.id === tag.id) ? prev : [...prev, tag];
      return [...next].sort((left, right) => left.name.localeCompare(right.name, "ru"));
    });
    setSelectedTags((prev) => (prev.includes(tag.id) ? prev : [...prev, tag.id]));
  };

  const handleCreateFolder = async () => {
    const normalizedName = newFolderName.trim();
    setFolderCreateError(null);

    if (!normalizedName) {
      setFolderCreateError("Введите название папки");
      return;
    }

    const duplicateExists = folders.some((folder) => (
      folder.parent_id === selectedFolderId
      && folder.name.trim().toLocaleLowerCase("ru") === normalizedName.toLocaleLowerCase("ru")
    ));
    if (duplicateExists) {
      setFolderCreateError("В этой папке уже есть папка с таким названием");
      return;
    }

    setIsCreatingFolder(true);
    try {
      const created = await apiClient.createFolder({
        name: normalizedName,
        parent: selectedFolderId,
      });
      const parentId = created.parent_id
        ?? (typeof created.parent === "number" ? created.parent : created.parent?.id)
        ?? selectedFolderId
        ?? null;
      const createdFolder: FolderOption = {
        id: created.id,
        name: created.name || normalizedName,
        parent_id: parentId,
        path: created.path || [selectedFolder?.path || selectedFolder?.name, normalizedName]
          .filter(Boolean)
          .join(" / "),
      };

      setFolders((current) => (
        current.some((folder) => folder.id === createdFolder.id)
          ? current
          : [...current, createdFolder]
      ));
      setSelectedFolderId(createdFolder.id);
      setNewFolderName("");
      onFolderCreated?.();
      toast.success("Папка создана");
    } catch (error) {
      console.error("Ошибка создания папки:", error);
      setFolderCreateError(error instanceof Error ? error.message : "Не удалось создать папку");
    } finally {
      setIsCreatingFolder(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isDedicatedRegulation && !title.trim()) {
      setError("Укажите название регламента");
      return;
    }

    // Validate recipients if sent_to_all is false
    if (!sentToAll && selectedDepartments.length === 0 && selectedRecipients.length === 0) {
      setError(
        `Выберите хотя бы один отдел или сотрудника с доступом к ${
          isRegulation ? "регламенту" : "документу"
        }`,
      );
      return;
    }

    if (
      acknowledgementMode === "restricted"
      && acknowledgementDepartments.length === 0
      && acknowledgementRecipients.length === 0
    ) {
      setError("Выберите хотя бы один отдел или сотрудника для ознакомления");
      return;
    }

    setIsSubmitting(true);

    try {
      if (uploadItems.length === 0) {
        await apiClient.createDocument({
          title: title.trim() || undefined,
          description,
          folder_id: isDedicatedRegulation ? undefined : selectedFolderId ?? undefined,
          sent_to_all: sentToAll,
          is_regulation: isRegulation,
          department_ids: sentToAll ? undefined : selectedDepartments,
          recipient_ids: sentToAll ? undefined : selectedRecipients,
          acknowledgement_required: acknowledgementMode !== "none",
          acknowledgement_for_all: acknowledgementMode === "all",
          acknowledgement_department_ids:
            acknowledgementMode === "restricted" ? acknowledgementDepartments : undefined,
          acknowledgement_recipient_ids:
            acknowledgementMode === "restricted" ? acknowledgementRecipients : undefined,
          tag_ids: selectedTags.length > 0 ? selectedTags : undefined,
        });
      } else {
        for (const item of uploadItems) {
          const documentTitle =
            uploadItems.length === 1
              ? title.trim() || getDefaultDocumentTitle(item.file.name)
              : getDefaultDocumentTitle(item.file.name);

          await apiClient.createDocument({
            title: documentTitle,
            description,
            file: getFileForUpload(item),
            extracted_text: item.extractedText || undefined,
            folder_id: isDedicatedRegulation ? undefined : selectedFolderId ?? undefined,
            sent_to_all: sentToAll,
            is_regulation: isRegulation,
            department_ids: sentToAll ? undefined : selectedDepartments,
            recipient_ids: sentToAll ? undefined : selectedRecipients,
            acknowledgement_required: acknowledgementMode !== "none",
            acknowledgement_for_all: acknowledgementMode === "all",
            acknowledgement_department_ids:
              acknowledgementMode === "restricted" ? acknowledgementDepartments : undefined,
            acknowledgement_recipient_ids:
              acknowledgementMode === "restricted" ? acknowledgementRecipients : undefined,
            tag_ids: selectedTags.length > 0 ? selectedTags : undefined,
          });
        }
      }

      toast.success(
        isRegulation
          ? isDedicatedRegulation || uploadItems.length === 0
            ? "Регламент успешно создан"
            : uploadItems.length > 1
              ? `${uploadItems.length} регламентов успешно загружено`
              : "Регламент успешно загружен"
          : uploadItems.length === 0
            ? "Документ успешно создан"
            : uploadItems.length > 1
              ? `${uploadItems.length} документов успешно загружено`
              : "Документ успешно загружен",
      );
      
      // Сброс формы
      setTitle("");
      setDescription("");
      setUploadItems([]);
      setFilesOpen(false);
      setSelectedFolderId(isDedicatedRegulation ? null : currentFolderId ?? null);
      setNewFolderName("");
      setFolderCreateError(null);
      setSentToAll(true);
      setIsRegulation(isDedicatedRegulation);
      setAcknowledgementMode("all");
      setSelectedDepartments([]);
      setSelectedRecipients([]);
      setAcknowledgementDepartments([]);
      setAcknowledgementRecipients([]);
      setSelectedTags([]);
      
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      console.error(`Ошибка создания ${isRegulation ? "регламента" : "документа"}:`, err);
      setError(
        err instanceof Error
          ? err.message
          : `Не удалось создать ${isRegulation ? "регламент" : "документ"}`,
      );
      toast.error(`Ошибка создания ${isRegulation ? "регламента" : "документа"}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="app-feedback-danger flex items-start gap-2 rounded-lg p-3 text-sm">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {isDedicatedRegulation && (
        <div className="app-selected flex items-start gap-3 rounded-xl p-4">
          <span className="app-badge-accent flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
            <ScrollText size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">Основные сведения</p>
            <p className="app-text-muted mt-1 text-xs leading-relaxed">
              Добавьте регламент, настройте доступ и укажите, кто должен подтвердить ознакомление.
            </p>
          </div>
        </div>
      )}

      {/* File Upload */}
      <DocumentFilePanel
        title={isDedicatedRegulation ? "Файл регламента" : "Файлы"}
        count={uploadItems.length}
        open={filesOpen}
        onOpenChange={setFilesOpen}
        onFilesSelected={(files) => void onDrop(files)}
        multiple={!isDedicatedRegulation}
        disabled={isSubmitting}
        busy={isProcessing}
        addLabel={
          isDedicatedRegulation && uploadItems.length > 0 ? "Заменить файл регламента" : undefined
        }
        emptyText={isDedicatedRegulation ? "Файл регламента пока не выбран" : "Файлов пока нет"}
      >
        {uploadItems.length > 0 || (isProcessing && processingProgress) ? (
          <div className="space-y-3">
            {uploadItems.length > 0 ? (
              <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                {uploadItems.map((item) => (
                  <DocumentFileRow
                    key={item.id}
                    name={item.file.name}
                    meta={[
                      formatFileSize(item.file.size),
                      item.extractedText ? "текст извлечён" : null,
                      item.processedFile
                        ? `сжато до ${formatFileSize(item.processedFile.size)}`
                        : null,
                    ].filter(Boolean).join(" · ")}
                    error={item.processingError}
                    pending
                    onRemove={() => removeUploadItem(item.id)}
                    disabled={isProcessing}
                  />
                ))}
              </div>
            ) : null}

            {isProcessing && processingProgress ? (
              <div className="app-selected rounded-lg p-3">
                <div className="mb-2 flex items-center gap-2">
                  <Loader2 size={16} className="app-accent-text animate-spin" />
                  <span className="text-sm font-medium text-[var(--foreground)]">
                    {STAGE_MESSAGES[processingProgress.stage] || "Обработка..."}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[color:color-mix(in_srgb,var(--accent-primary)_18%,var(--surface-primary))]">
                  <div
                    className="h-full bg-[var(--accent-primary)] transition-all duration-300"
                    style={{ width: `${processingProgress.progress}%` }}
                  />
                </div>
                <p className="app-accent-text mt-1 text-xs">
                  {processingProgress.message} · {processingProgress.progress}%
                </p>
              </div>
            ) : null}
          </div>
        ) : undefined}
      </DocumentFilePanel>

      {/* Title */}
      {uploadItems.length <= 1 ? (
        <div>
          <label htmlFor="title" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
            Название
            {isDedicatedRegulation && <span className="ml-1 text-red-500">*</span>}
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={
              isDedicatedRegulation
                ? "Например, Регламент работы с обращениями"
                : uploadItems.length === 0
                  ? "Название документа"
                  : "По умолчанию — название файла"
            }
            required={isDedicatedRegulation}
            className="app-input w-full rounded-lg px-3 py-2 text-sm"
          />
          <p className="app-text-muted mt-1 text-xs">
            {isDedicatedRegulation
              ? "Название будет отображаться в списке регламентов и результатах поиска."
              : uploadItems.length === 0
                ? 'Поле необязательное. Если оставить пустым, будет использовано название "Документ".'
                : "Поле необязательное. Если оставить пустым, будет использовано имя файла без расширения."}
          </p>
        </div>
      ) : (
        <div className="app-selected app-accent-text rounded-lg p-3 text-sm">
          Для каждого документа название будет взято из имени соответствующего файла.
        </div>
      )}

      {/* Description */}
      <div>
        <label htmlFor="description" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          Описание
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={
            isDedicatedRegulation
              ? "Кратко опишите назначение и область применения регламента"
              : "Краткое описание документа"
          }
          rows={3}
          className="app-input w-full rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Divider */}
      <div className="app-divider border-t pt-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
          <TagIcon size={16} />
          {isDedicatedRegulation ? "Оформление" : "Категоризация"}
        </h3>
      </div>

      {/* Folder */}
      {!isDedicatedRegulation && (
        <div>
          <div id="document-upload-folder-label" className="mb-2 flex items-center gap-2">
            <FolderOpen size={15} className="app-text-muted" />
            <span className="app-text-muted text-xs font-medium">Папка</span>
          </div>
          <select
            id="folder"
            value={selectedFolderId ?? ""}
            onChange={(event) => {
              setSelectedFolderId(event.target.value ? Number(event.target.value) : null);
              setFolderCreateError(null);
            }}
            disabled={loadingFolders || isSubmitting || isCreatingFolder}
            className="app-select w-full rounded-xl px-3 py-2 text-sm"
            aria-labelledby="document-upload-folder-label"
          >
            <option value="">Без папки</option>
            {loadingFolders ? (
              <option disabled>Загрузка...</option>
            ) : folderOptionRows.length === 0 ? (
              <option disabled>Нет доступных папок</option>
            ) : (
              folderOptionRows.map(({ folder, level }) => (
                <option key={folder.id} value={folder.id}>
                  {`${"— ".repeat(level)}${folder.name}`}
                </option>
              ))
            )}
          </select>

          <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
            <input
              value={newFolderName}
              onChange={(event) => {
                setNewFolderName(event.target.value);
                setFolderCreateError(null);
              }}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                if (!isCreatingFolder && newFolderName.trim()) {
                  void handleCreateFolder();
                }
              }}
              disabled={loadingFolders || isSubmitting || isCreatingFolder}
              maxLength={255}
              className="app-input min-w-0 rounded-xl px-3 py-2 text-sm"
              placeholder="Новая папка"
              aria-label="Название новой папки"
            />
            <button
              type="button"
              onClick={() => void handleCreateFolder()}
              disabled={loadingFolders || isSubmitting || isCreatingFolder || !newFolderName.trim()}
              className="app-action-secondary inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isCreatingFolder ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Plus size={15} />
              )}
              Добавить
            </button>
          </div>

          {folderCreateError ? (
            <p className="mt-1 text-xs text-red-500">{folderCreateError}</p>
          ) : (
            <p className="app-text-muted mt-1 text-xs">
              {selectedFolder
                ? `Новая папка будет создана внутри «${selectedFolder.name}».`
                : "Новая папка будет создана в корне."}
            </p>
          )}
        </div>
      )}

      {/* Tags */}
      <div>
        <div id="document-upload-tags-label" className="mb-2 flex items-center gap-2">
          <TagIcon size={15} className="app-text-muted" />
          <span className="app-text-muted text-xs font-medium">Теги</span>
        </div>
        <div
          role="group"
          aria-labelledby="document-upload-tags-label"
          className="flex min-h-7 flex-wrap items-center gap-2"
        >
          {loadingDocumentTags ? (
            <span className="app-text-muted text-xs">Загрузка тегов...</span>
          ) : documentTags.length === 0 ? (
            <span className="app-text-muted text-xs">Тегов пока нет</span>
          ) : (
            documentTags.map((tag) => (
              <button
                key={tag.id}
                type="button"
                onClick={() =>
                  setSelectedTags((prev) =>
                    prev.includes(tag.id)
                      ? prev.filter((id) => id !== tag.id)
                      : [...prev, tag.id]
                  )
                }
                className={`inline-flex max-w-full items-center rounded-full border px-3 py-1 text-xs font-medium transition ${
                  selectedTags.includes(tag.id)
                    ? "border-transparent text-white"
                    : "border-[var(--border-subtle)] text-[var(--muted-foreground)] hover:border-[var(--border-strong)]"
                }`}
                style={
                  selectedTags.includes(tag.id)
                    ? { backgroundColor: tag.color || "#38bdf8" }
                    : undefined
                }
                aria-pressed={selectedTags.includes(tag.id)}
              >
                <span className="truncate">{tag.name}</span>
              </button>
            ))
          )}
        </div>
        <DocumentTagQuickCreate
          existingTags={documentTags}
          disabled={loadingDocumentTags || isSubmitting}
          onCreated={handleCreatedTag}
          layout="inline"
          className="mt-3"
        />
      </div>

      {!isDedicatedRegulation ? (
        <label
          htmlFor="documentIsRegulation"
          className="app-surface-muted flex cursor-pointer items-start gap-3 rounded-xl border border-[var(--border-subtle)] p-3"
        >
          <input
            id="documentIsRegulation"
            type="checkbox"
            checked={isRegulation}
            onChange={(event) => setIsRegulation(event.target.checked)}
            disabled={isSubmitting}
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-[var(--border-strong)] accent-[var(--accent-primary)] disabled:opacity-50"
          />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5 text-sm font-medium text-[var(--foreground)]">
              <ScrollText size={14} />
              Регламент
            </span>
            <span className="app-text-muted mt-1 block text-xs">
              Документ будет отображаться в отдельном разделе регламентов.
            </span>
          </span>
        </label>
      ) : null}

      {/* Извлеченный текст */}
      {uploadItems.length === 1 && uploadItems[0].extractedText && (
        <div>
          <label htmlFor="extractedText" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
            Извлеченный текст
            <span className="app-text-muted ml-1 text-xs font-normal">
              (будет использован для поиска, можно отредактировать)
            </span>
          </label>
          <textarea
            id="extractedText"
            value={uploadItems[0].extractedText}
            onChange={(e) => updateSingleExtractedText(e.target.value)}
            placeholder={`Текст, извлеченный из ${isRegulation ? "регламента" : "документа"}`}
            rows={5}
            className="app-input w-full rounded-lg px-3 py-2 text-sm font-mono"
          />
          <p className="app-text-muted mt-1 text-xs">
            Символов: {uploadItems[0].extractedText.length}
          </p>
        </div>
      )}

      {uploadItems.length > 1 && uploadItems.some((item) => item.extractedText) && (
        <div className="app-selected app-accent-text rounded-lg p-3 text-sm">
          Текст извлечён для {uploadItems.filter((item) => item.extractedText).length} файлов и будет сохранён для поиска.
        </div>
      )}

      <div className="app-divider border-t pt-4">
        <div className="space-y-6">
          <DocumentAudienceSelector
            kind="access"
            resource={isRegulation ? "regulation" : "document"}
            mode={sentToAll ? "all" : "restricted"}
            onModeChange={(mode) => setSentToAll(mode === "all")}
            employees={employees}
            departments={departments}
            selectedEmployeeIds={selectedRecipients}
            selectedDepartmentIds={selectedDepartments}
            onSelectedEmployeeIdsChange={setSelectedRecipients}
            onSelectedDepartmentIdsChange={setSelectedDepartments}
            loading={loadingEmployees || loadingDepartments}
            disabled={isSubmitting}
          />

          <div className="app-divider border-t pt-5">
            <DocumentAudienceSelector
              kind="acknowledgement"
              resource={isRegulation ? "regulation" : "document"}
              mode={acknowledgementMode}
              onModeChange={setAcknowledgementMode}
              employees={acknowledgementEmployees}
              departments={acknowledgementDepartmentOptions}
              selectedEmployeeIds={acknowledgementRecipients}
              selectedDepartmentIds={acknowledgementDepartments}
              onSelectedEmployeeIdsChange={setAcknowledgementRecipients}
              onSelectedDepartmentIdsChange={setAcknowledgementDepartments}
              loading={loadingEmployees || loadingDepartments}
              disabled={isSubmitting}
            />
          </div>
        </div>
      </div>

      {/* Buttons */}
      <div className="app-divider sticky bottom-0 z-10 -mx-4 flex gap-3 border-t bg-[var(--surface-elevated)] px-4 py-3 sm:-mx-6 sm:px-6">
        <button
          type="submit"
          disabled={isSubmitting || isProcessing}
          className="app-action-primary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting
            ? isDedicatedRegulation || uploadItems.length === 0
              ? "Создание..."
              : "Загрузка..."
            : isProcessing
              ? "Обработка..."
              : isDedicatedRegulation
                ? "Создать регламент"
                : isRegulation
                  ? uploadItems.length > 1
                    ? `Загрузить ${uploadItems.length} регламентов`
                    : uploadItems.length === 1
                      ? "Загрузить регламент"
                      : "Создать регламент"
                  : uploadItems.length > 1
                    ? `Загрузить ${uploadItems.length} документов`
                    : uploadItems.length === 1
                      ? "Загрузить документ"
                      : "Создать документ"}
        </button>
        
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isProcessing}
            className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
        )}
      </div>
    </form>
  );
}

export function RegulationCreateForm(
  props: Omit<DocumentUploadFormProps, "currentFolderId" | "mode">,
) {
  return <DocumentUploadForm {...props} mode="regulation" />;
}
