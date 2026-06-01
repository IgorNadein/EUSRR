"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { useDropzone } from "react-dropzone";
import { 
  Upload, 
  X, 
  FileText, 
  AlertCircle, 
  Loader2, 
  FolderOpen,
  Users,
  Building2,
  CheckCircle,
  Tag as TagIcon,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import { processDocument, needsProcessing, type ProcessingProgress } from "@/lib/document-utils";

interface Department {
  id: number;
  name: string;
}

interface User {
  id: number;
  first_name: string;
  last_name: string;
  email?: string;
}

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
  currentFolderId?: number | null;
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

export function DocumentUploadForm({ onSuccess, onCancel, currentFolderId }: DocumentUploadFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [uploadItems, setUploadItems] = useState<UploadFileItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState<ProcessingProgress | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New fields for extended functionality
  const [sentToAll, setSentToAll] = useState(true);
  const [acknowledgementRequired, setAcknowledgementRequired] = useState(false);
  const [selectedDepartments, setSelectedDepartments] = useState<number[]>([]);
  const [selectedRecipients, setSelectedRecipients] = useState<number[]>([]);
  
  // Metadata fields
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(currentFolderId ?? null);
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

  useEffect(() => {
    setSelectedFolderId(currentFolderId ?? null);
  }, [currentFolderId]);

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
        const empResponse = await apiClient.getEmployees({ limit: 1000 });
        setEmployees(empResponse.results || empResponse);
      } catch (err) {
        console.error("Ошибка загрузки сотрудников:", err);
      } finally {
        setLoadingEmployees(false);
      }

      try {
        setLoadingFolders(true);
        const foldersResponse = await apiClient.getFolders({});
        const foldersData = foldersResponse.results || foldersResponse;
        setFolders(Array.isArray(foldersData) ? foldersData : []);
      } catch (err) {
        console.error("Ошибка загрузки папок:", err);
      } finally {
        setLoadingFolders(false);
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
  }, []);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const newItems = acceptedFiles.map(createUploadItem);
    const totalAfterDrop = uploadItems.length + newItems.length;

    setUploadItems((prev) => [...prev, ...newItems]);
    setError(null);

    if (totalAfterDrop === 1 && !title.trim()) {
      setTitle(getDefaultDocumentTitle(newItems[0].file.name));
    } else if (totalAfterDrop > 1) {
      setTitle("");
    }

    if (!newItems.some((item) => needsProcessing(item.file))) return;

    setIsProcessing(true);
    setProcessingProgress({
      stage: "compressing",
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
            enableCompression: true,
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
        toast.success(newItems.length > 1 ? "Файлы обработаны успешно" : "Документ обработан успешно");
      }
    } finally {
      setIsProcessing(false);
      setProcessingProgress(null);
    }
  }, [title, uploadItems.length]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    disabled: isProcessing || isSubmitting,
  });

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (uploadItems.length === 0) {
      setError("Выберите хотя бы один файл");
      return;
    }

    // Validate recipients if sent_to_all is false
    if (!sentToAll && selectedDepartments.length === 0 && selectedRecipients.length === 0) {
      setError("Укажите получателей или отделы, либо выберите 'Отправить всем'");
      return;
    }

    setIsSubmitting(true);

    try {
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
          folder_id: selectedFolderId ?? undefined,
          sent_to_all: sentToAll,
          department_ids: sentToAll ? undefined : selectedDepartments,
          recipient_ids: sentToAll ? undefined : selectedRecipients,
          acknowledgement_required: acknowledgementRequired,
          tag_ids: selectedTags.length > 0 ? selectedTags : undefined,
        });
      }

      toast.success(
        uploadItems.length > 1
          ? `${uploadItems.length} документов успешно загружено`
          : "Документ успешно загружен"
      );
      
      // Сброс формы
      setTitle("");
      setDescription("");
      setUploadItems([]);
      setSelectedFolderId(currentFolderId ?? null);
      setSentToAll(true);
      setAcknowledgementRequired(false);
      setSelectedDepartments([]);
      setSelectedRecipients([]);
      setSelectedTags([]);
      
      if (onSuccess) {
        onSuccess();
      }
    } catch (err) {
      console.error("Ошибка загрузки документа:", err);
      setError(err instanceof Error ? err.message : "Не удалось загрузить документ");
      toast.error("Ошибка загрузки документа");
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

      {/* File Upload */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          Файлы <span className="text-red-500">*</span>
        </label>
        
        <div
          {...getRootProps()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
            isDragActive
              ? "border-[var(--accent-primary)] bg-[color:color-mix(in_srgb,var(--accent-primary)_10%,var(--surface-secondary))]"
              : "border-[var(--border-strong)] bg-[var(--surface-secondary)] hover:border-[var(--accent-primary)] hover:bg-[color:color-mix(in_srgb,var(--accent-primary)_8%,var(--surface-secondary))]"
          } ${isProcessing || isSubmitting ? "cursor-not-allowed opacity-60" : ""}`}
        >
          <input {...getInputProps()} />
          <Upload size={32} className="app-text-muted mx-auto mb-3" />
          <p className="text-sm font-medium text-[var(--foreground)]">
            {isDragActive
              ? "Отпустите файлы здесь"
              : uploadItems.length > 0
                ? "Добавьте ещё файлы или нажмите для выбора"
                : "Перетащите файлы или нажмите для выбора"}
          </p>
          <p className="app-text-muted mt-1 text-xs">
            Можно выбрать несколько файлов любых форматов
          </p>
        </div>

        {uploadItems.length > 0 && (
          <div className="mt-3 space-y-3">
            <div className="app-text-muted text-xs">
              Выбрано файлов: {uploadItems.length}
            </div>

            <div className="flex flex-wrap gap-2">
              {uploadItems.map((item) => (
                <span
                  key={item.id}
                  className={`inline-flex max-w-full items-center gap-2 rounded-full px-2.5 py-1.5 ${
                    item.processingError ? "app-feedback-danger" : "app-badge"
                  }`}
                  title={item.processingError || item.file.name}
                >
                  <FileText size={16} className="app-accent-text shrink-0" />
                  <span className="min-w-0">
                    <span className="block max-w-[14rem] truncate text-sm font-medium text-[var(--foreground)]">
                      {item.file.name}
                    </span>
                    <span className="app-text-muted block truncate text-xs">
                      {formatFileSize(item.file.size)}
                      {item.extractedText ? " · текст извлечён" : ""}
                      {item.processedFile
                        ? ` · сжато до ${formatFileSize(item.processedFile.size)}`
                        : ""}
                      {item.processingError ? " · ошибка обработки" : ""}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => removeUploadItem(item.id)}
                    disabled={isProcessing}
                    className="app-action-ghost app-text-muted -mr-1 shrink-0 rounded-full p-1 hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={`Убрать файл ${item.file.name}`}
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>

            {uploadItems.some((item) => item.processingError) && (
              <div className="space-y-1">
                {uploadItems.map((item) =>
                  item.processingError ? (
                    <p key={item.id} className="text-xs text-red-500">
                      {item.file.name}: {item.processingError}
                    </p>
                  ) : null
                )}
              </div>
            )}

            {/* Индикатор обработки */}
            {isProcessing && processingProgress && (
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
            )}
          </div>
        )}
      </div>

      {/* Title */}
      {uploadItems.length <= 1 ? (
        <div>
          <label htmlFor="title" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
            Название
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="По умолчанию — название файла"
            className="app-input w-full rounded-lg px-3 py-2 text-sm"
          />
          <p className="app-text-muted mt-1 text-xs">
            Поле необязательное. Если оставить пустым, будет использовано имя файла без расширения.
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
          placeholder="Краткое описание документа"
          rows={3}
          className="app-input w-full rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Divider */}
      <div className="app-divider border-t pt-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
          <TagIcon size={16} />
          Категоризация
        </h3>
      </div>

      {/* Folder */}
      <div>
        <label htmlFor="folder" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          <FolderOpen size={14} className="mr-1 inline" />
          Папка
        </label>
        <select
          id="folder"
          value={selectedFolderId ?? ""}
          onChange={(e) => setSelectedFolderId(e.target.value ? Number(e.target.value) : null)}
          disabled={loadingFolders}
          className="app-select w-full rounded-lg px-3 py-2 text-sm"
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
        <p className="app-text-muted mt-1 text-xs">
          Выбранная папка будет применена ко всем загружаемым документам.
        </p>
      </div>

      {/* Tags */}
      <div>
        <div id="document-upload-tags-label" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          Теги
        </div>
        <div
          role="group"
          aria-labelledby="document-upload-tags-label"
          className="app-surface-muted flex min-h-12 flex-wrap items-center gap-2 rounded-lg p-2"
        >
          {loadingDocumentTags ? (
            <span className="app-text-muted px-1 text-sm">Загрузка тегов...</span>
          ) : documentTags.length === 0 ? (
            <span className="app-text-muted px-1 text-sm">Нет доступных тегов</span>
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
                className={`inline-flex max-w-full items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  selectedTags.includes(tag.id)
                    ? "app-badge app-badge-accent"
                    : "app-badge hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
                }`}
                aria-pressed={selectedTags.includes(tag.id)}
              >
                {tag.color && (
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: tag.color }}
                  />
                )}
                <span className="truncate">{tag.name}</span>
              </button>
            ))
          )}
        </div>
        <p className="app-text-muted mt-1 text-xs">
          {selectedTags.length > 0 ? (
            <>Выбрано: {selectedTags.length}</>
          ) : (
            <>Нажмите на тег, чтобы добавить его к документу</>
          )}
        </p>
      </div>

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
            placeholder="Текст, извлеченный из документа"
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

      {/* Divider */}
      <div className="app-divider border-t pt-4">
        <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">Настройки доступа и уведомлений</h3>
      </div>

      {/* Sent to All Toggle */}
      <div className="app-surface-muted flex items-start gap-3 rounded-lg p-3">
        <input
          type="checkbox"
          id="sentToAll"
          checked={sentToAll}
          onChange={(e) => {
            setSentToAll(e.target.checked);
            if (e.target.checked) {
              setSelectedDepartments([]);
              setSelectedRecipients([]);
            }
          }}
          className="mt-0.5 h-4 w-4 rounded border-[var(--border-strong)] text-[var(--accent-primary)]"
        />
        <div className="flex-1">
          <label htmlFor="sentToAll" className="block cursor-pointer text-sm font-medium text-[var(--foreground)]">
            Отправить всем сотрудникам
          </label>
          <p className="app-text-muted mt-0.5 text-xs">
            Документ будет доступен всем активным сотрудникам
          </p>
        </div>
      </div>

      {/* Recipients section - only show when sentToAll is false */}
      {!sentToAll && (
        <div className="app-surface-muted space-y-4 rounded-lg p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
            <Users size={16} />
            <span>Выберите получателей</span>
          </div>

          {/* Departments */}
          <div>
            <label htmlFor="departments" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
              <Building2 size={14} className="mr-1 inline" />
              Отделы
            </label>
            <select
              id="departments"
              multiple
              value={selectedDepartments.map(String)}
              onChange={(e) => {
                const values = Array.from(e.target.selectedOptions, (option) => Number(option.value));
                setSelectedDepartments(values);
              }}
              disabled={loadingDepartments}
              className="app-select w-full rounded-lg px-3 py-2 text-sm"
              size={5}
            >
              {loadingDepartments ? (
                <option disabled>Загрузка...</option>
              ) : departments.length === 0 ? (
                <option disabled>Нет доступных отделов</option>
              ) : (
                departments.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name}
                  </option>
                ))
              )}
            </select>
            <p className="app-text-muted mt-1 text-xs">
              Удерживайте Ctrl/Cmd для выбора нескольких
            </p>
          </div>

          {/* Recipients */}
          <div>
            <label htmlFor="recipients" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
              <Users size={14} className="mr-1 inline" />
              Конкретные сотрудники
            </label>
            <select
              id="recipients"
              multiple
              value={selectedRecipients.map(String)}
              onChange={(e) => {
                const values = Array.from(e.target.selectedOptions, (option) => Number(option.value));
                setSelectedRecipients(values);
              }}
              disabled={loadingEmployees}
              className="app-select w-full rounded-lg px-3 py-2 text-sm"
              size={8}
            >
              {loadingEmployees ? (
                <option disabled>Загрузка...</option>
              ) : employees.length === 0 ? (
                <option disabled>Нет доступных сотрудников</option>
              ) : (
                employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.last_name} {emp.first_name} {emp.email && `(${emp.email})`}
                  </option>
                ))
              )}
            </select>
            <p className="app-text-muted mt-1 text-xs">
              Удерживайте Ctrl/Cmd для выбора нескольких
            </p>
          </div>

          {selectedDepartments.length === 0 && selectedRecipients.length === 0 && (
            <div className="app-feedback-warning flex items-start gap-2 rounded-lg p-3 text-xs">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>Выберите хотя бы один отдел или сотрудника</span>
            </div>
          )}
        </div>
      )}

      {/* Acknowledgement Required */}
      <div className="app-surface-muted flex items-start gap-3 rounded-lg p-3">
        <input
          type="checkbox"
          id="acknowledgementRequired"
          checked={acknowledgementRequired}
          onChange={(e) => setAcknowledgementRequired(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-[var(--border-strong)] text-[var(--accent-primary)]"
        />
        <div className="flex-1">
          <label htmlFor="acknowledgementRequired" className="block cursor-pointer text-sm font-medium text-[var(--foreground)]">
            <CheckCircle size={14} className="mr-1 inline" />
            Требуется подтверждение ознакомления
          </label>
          <p className="app-text-muted mt-0.5 text-xs">
            Получатели должны будут подтвердить, что ознакомились с документом
          </p>
        </div>
      </div>

      {/* Buttons */}
      <div className="app-divider sticky bottom-0 z-10 -mx-4 flex gap-3 border-t bg-[var(--surface-elevated)] px-4 py-3 sm:-mx-6 sm:px-6">
        <button
          type="submit"
          disabled={isSubmitting || isProcessing || uploadItems.length === 0}
          className="app-action-primary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting
            ? "Загрузка..."
            : isProcessing
              ? "Обработка..."
              : uploadItems.length > 1
                ? `Загрузить ${uploadItems.length} документов`
                : "Загрузить документ"}
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
