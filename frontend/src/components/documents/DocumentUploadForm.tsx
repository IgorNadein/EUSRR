"use client";

import { useState, useCallback, useEffect } from "react";
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

interface DocumentUploadFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
  currentFolderId?: number | null;
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
  const [file, setFile] = useState<File | null>(null);
  const [processedFile, setProcessedFile] = useState<File | Blob | null>(null);
  const [extractedText, setExtractedText] = useState("");
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
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  
  // Data for selects
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [documentTags, setDocumentTags] = useState<any[]>([]);
  
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [loadingDocumentTags, setLoadingDocumentTags] = useState(false);

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
    if (acceptedFiles.length > 0) {
      const selectedFile = acceptedFiles[0];
      setFile(selectedFile);
      setError(null);
      
      // Автоматически заполняем название, если оно пустое
      if (!title && selectedFile.name) {
        setTitle(selectedFile.name.replace(/\.[^/.]+$/, "")); // Убираем расширение
      }

      // Проверяем, требуется ли обработка файла
      if (needsProcessing(selectedFile)) {
        setIsProcessing(true);
        setProcessingProgress({ 
          stage: "compressing", 
          progress: 0,
          message: "Начало обработки..."
        });

        try {
          const result = await processDocument(selectedFile, {
            enableOCR: true,
            enableCompression: true,
            enableTextExtraction: true,
            enableThumbnail: true,
            onProgress: (progress) => {
              setProcessingProgress(progress);
            },
          });

          // Сохраняем извлеченный текст
          if (result.extractedText) {
            setExtractedText(result.extractedText);
          }

          // Если файл был обработан (сжат), используем обработанную версию
          if (result.processedFile) {
            setProcessedFile(result.processedFile);
          }

          toast.success("Документ обработан успешно");
        } catch (err) {
          console.error("Ошибка обработки документа:", err);
          setError(err instanceof Error ? err.message : "Не удалось обработать документ");
          toast.error("Ошибка обработки документа");
        } finally {
          setIsProcessing(false);
          setProcessingProgress(null);
        }
      }
    }
  }, [title]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'image/*': ['.png', '.jpg', '.jpeg', '.gif'],
      'text/*': ['.txt', '.csv'],
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title || !file) {
      setError("Заполните все обязательные поля");
      return;
    }

    // Validate recipients if sent_to_all is false
    if (!sentToAll && selectedDepartments.length === 0 && selectedRecipients.length === 0) {
      setError("Укажите получателей или отделы, либо выберите 'Отправить всем'");
      return;
    }

    setIsSubmitting(true);

    try {
      // Используем обработанный файл, если он есть, иначе оригинальный
      const fileToUpload = processedFile || file;

      await apiClient.createDocument({
        title,
        description,
        file: fileToUpload,
        extracted_text: extractedText || undefined,
        folder_id: currentFolderId || undefined,
        sent_to_all: sentToAll,
        department_ids: sentToAll ? undefined : selectedDepartments,
        recipient_ids: sentToAll ? undefined : selectedRecipients,
        acknowledgement_required: acknowledgementRequired,
        tag_ids: selectedTags.length > 0 ? selectedTags : undefined,
      });

      toast.success("Документ успешно загружен");
      
      // Сброс формы
      setTitle("");
      setDescription("");
      setFile(null);
      setProcessedFile(null);
      setExtractedText("");
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

      {/* Current folder info */}
      {currentFolderId && (
        <div className="app-selected app-accent-text rounded-lg p-3 text-sm">
          <div className="flex items-center gap-2">
            <FolderOpen size={16} />
            <span>Документ будет сохранён в выбранной папке</span>
          </div>
        </div>
      )}

      {/* File Upload */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          Файл <span className="text-red-500">*</span>
        </label>
        
        {!file ? (
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
              isDragActive
                ? "border-[var(--accent-primary)] bg-[color:color-mix(in_srgb,var(--accent-primary)_10%,var(--surface-secondary))]"
                : "border-[var(--border-strong)] bg-[var(--surface-secondary)] hover:border-[var(--accent-primary)] hover:bg-[color:color-mix(in_srgb,var(--accent-primary)_8%,var(--surface-secondary))]"
            }`}
          >
            <input {...getInputProps()} />
            <Upload size={32} className="app-text-muted mx-auto mb-3" />
            <p className="text-sm font-medium text-[var(--foreground)]">
              {isDragActive ? "Отпустите файл здесь" : "Перетащите файл или нажмите для выбора"}
            </p>
            <p className="app-text-muted mt-1 text-xs">
              PDF, Word, Excel, изображения, текстовые файлы
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="app-surface flex items-center gap-3 rounded-lg p-3">
              <FileText size={20} className="app-accent-text shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[var(--foreground)]">{file.name}</p>
                <p className="app-text-muted text-xs">
                  {(file.size / 1024 / 1024).toFixed(2)} МБ
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setProcessedFile(null);
                  setExtractedText("");
                }}
                disabled={isProcessing}
                className="app-action-ghost app-text-muted shrink-0 rounded-full p-1 hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <X size={16} />
              </button>
            </div>

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
                  {processingProgress.progress}%
                </p>
              </div>
            )}

            {/* Сообщение о сжатии */}
            {processedFile && !isProcessing && (
              <div className="app-feedback-success rounded-lg p-2 text-xs">
                ✓ Изображение сжато: {(file.size / 1024 / 1024).toFixed(2)} МБ → {(processedFile.size / 1024 / 1024).toFixed(2)} МБ
              </div>
            )}
          </div>
        )}
      </div>

      {/* Title */}
      <div>
        <label htmlFor="title" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          Название <span className="text-red-500">*</span>
        </label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Введите название документа"
          required
          className="app-input w-full rounded-lg px-3 py-2 text-sm"
        />
      </div>

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

      {/* Tags */}
      <div>
        <label htmlFor="tags" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
          Теги
        </label>
        <select
          id="tags"
          multiple
          value={selectedTags.map(String)}
          onChange={(e) => {
            const values = Array.from(e.target.selectedOptions, (option) => Number(option.value));
            setSelectedTags(values);
          }}
          disabled={loadingDocumentTags}
          className="app-select w-full rounded-lg px-3 py-2 text-sm"
          size={4}
        >
          {loadingDocumentTags ? (
            <option disabled>Загрузка...</option>
          ) : documentTags.length === 0 ? (
            <option disabled>Нет доступных тегов</option>
          ) : (
            documentTags.map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))
          )}
        </select>
        <p className="app-text-muted mt-1 text-xs">
          Удерживайте Ctrl/Cmd для выбора нескольких тегов
        </p>
      </div>

      {/* Извлеченный текст */}
      {extractedText && (
        <div>
          <label htmlFor="extractedText" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
            Извлеченный текст
            <span className="app-text-muted ml-1 text-xs font-normal">
              (будет использован для поиска, можно отредактировать)
            </span>
          </label>
          <textarea
            id="extractedText"
            value={extractedText}
            onChange={(e) => setExtractedText(e.target.value)}
            placeholder="Текст, извлеченный из документа"
            rows={5}
            className="app-input w-full rounded-lg px-3 py-2 text-sm font-mono"
          />
          <p className="app-text-muted mt-1 text-xs">
            Символов: {extractedText.length}
          </p>
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
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={isSubmitting || isProcessing || !title || !file}
          className="app-action-primary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Загрузка..." : isProcessing ? "Обработка..." : "Загрузить документ"}
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
