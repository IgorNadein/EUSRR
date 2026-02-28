"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, FileText, AlertCircle, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import { processDocument, needsProcessing, type ProcessingProgress } from "@/lib/document-utils";

interface DocumentUploadFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

// Сообщения для различных этапов обработки
const STAGE_MESSAGES: Record<string, string> = {
  compressing: "Сжатие изображения...",
  ocr: "Распознавание текста (OCR)...",
  extracting_text: "Извлечение текста...",
  generating_thumbnail: "Создание миниатюры...",
  complete: "Обработка завершена",
};

export function DocumentUploadForm({ onSuccess, onCancel }: DocumentUploadFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [processedFile, setProcessedFile] = useState<File | Blob | null>(null);
  const [extractedText, setExtractedText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState<ProcessingProgress | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    setIsSubmitting(true);

    try {
      // Используем обработанный файл, если он есть, иначе оригинальный
      const fileToUpload = processedFile || file;

      await apiClient.createDocument({
        title,
        description,
        file: fileToUpload,
        extracted_text: extractedText || undefined, // Отправляем извлеченный текст, если есть
      });

      toast.success("Документ успешно загружен");
      
      // Сброс формы
      setTitle("");
      setDescription("");
      setFile(null);
      setProcessedFile(null);
      setExtractedText("");
      
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
        <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* File Upload */}
      <div>
        <label className="mb-1.5 block text-sm font-medium text-gray-700">
          Файл <span className="text-red-500">*</span>
        </label>
        
        {!file ? (
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
              isDragActive
                ? "border-sky-500 bg-sky-50"
                : "border-gray-300 bg-gray-50 hover:border-sky-400 hover:bg-sky-50"
            }`}
          >
            <input {...getInputProps()} />
            <Upload size={32} className="mx-auto mb-3 text-gray-400" />
            <p className="text-sm font-medium text-gray-700">
              {isDragActive ? "Отпустите файл здесь" : "Перетащите файл или нажмите для выбора"}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              PDF, Word, Excel, изображения, текстовые файлы
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3">
              <FileText size={20} className="shrink-0 text-sky-600" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-900">{file.name}</p>
                <p className="text-xs text-gray-500">
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
                className="shrink-0 rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <X size={16} />
              </button>
            </div>

            {/* Индикатор обработки */}
            {isProcessing && processingProgress && (
              <div className="rounded-lg border border-sky-200 bg-sky-50 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Loader2 size={16} className="animate-spin text-sky-600" />
                  <span className="text-sm font-medium text-sky-900">
                    {STAGE_MESSAGES[processingProgress.stage] || "Обработка..."}
                  </span>
                </div>
                <div className="h-2 bg-sky-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-sky-600 transition-all duration-300"
                    style={{ width: `${processingProgress.progress}%` }}
                  />
                </div>
                <p className="text-xs text-sky-700 mt-1">
                  {processingProgress.progress}%
                </p>
              </div>
            )}

            {/* Сообщение о сжатии */}
            {processedFile && !isProcessing && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-2 text-xs text-green-800">
                ✓ Изображение сжато: {(file.size / 1024 / 1024).toFixed(2)} МБ → {(processedFile.size / 1024 / 1024).toFixed(2)} МБ
              </div>
            )}
          </div>
        )}
      </div>

      {/* Title */}
      <div>
        <label htmlFor="title" className="mb-1.5 block text-sm font-medium text-gray-700">
          Название <span className="text-red-500">*</span>
        </label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Введите название документа"
          required
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
        />
      </div>

      {/* Description */}
      <div>
        <label htmlFor="description" className="mb-1.5 block text-sm font-medium text-gray-700">
          Описание
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Краткое описание документа"
          rows={3}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
        />
      </div>

      {/* Извлеченный текст */}
      {extractedText && (
        <div>
          <label htmlFor="extractedText" className="mb-1.5 block text-sm font-medium text-gray-700">
            Извлеченный текст
            <span className="ml-1 text-xs font-normal text-gray-500">
              (будет использован для поиска, можно отредактировать)
            </span>
          </label>
          <textarea
            id="extractedText"
            value={extractedText}
            onChange={(e) => setExtractedText(e.target.value)}
            placeholder="Текст, извлеченный из документа"
            rows={5}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
          />
          <p className="mt-1 text-xs text-gray-500">
            Символов: {extractedText.length}
          </p>
        </div>
      )}

      {/* Buttons */}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={isSubmitting || isProcessing || !title || !file}
          className="flex-1 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Загрузка..." : isProcessing ? "Обработка..." : "Загрузить документ"}
        </button>
        
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isProcessing}
            className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
        )}
      </div>
    </form>
  );
}
