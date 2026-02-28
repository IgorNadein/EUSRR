"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, FileText, AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

interface DocumentUploadFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function DocumentUploadForm({ onSuccess, onCancel }: DocumentUploadFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [tags, setTags] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      // Автоматически заполняем название, если оно пустое
      if (!title && acceptedFiles[0].name) {
        setTitle(acceptedFiles[0].name.replace(/\.[^/.]+$/, "")); // Убираем расширение
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

    if (!title || !documentType || !file) {
      setError("Заполните все обязательные поля");
      return;
    }

    setIsSubmitting(true);

    try {
      const tagsList = tags
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0);

      await apiClient.createDocument({
        title,
        description,
        document_type: documentType,
        file,
        tags: tagsList.length > 0 ? tagsList : undefined,
      });

      toast.success("Документ успешно загружен");
      
      // Сброс формы
      setTitle("");
      setDescription("");
      setDocumentType("");
      setFile(null);
      setTags("");
      
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
              onClick={() => setFile(null)}
              className="shrink-0 rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <X size={16} />
            </button>
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

      {/* Document Type */}
      <div>
        <label htmlFor="type" className="mb-1.5 block text-sm font-medium text-gray-700">
          Тип документа <span className="text-red-500">*</span>
        </label>
        <select
          id="type"
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value)}
          required
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
        >
          <option value="">Выберите тип</option>
          <option value="policy">Политика</option>
          <option value="procedure">Процедура</option>
          <option value="instruction">Инструкция</option>
          <option value="form">Форма</option>
          <option value="report">Отчет</option>
          <option value="contract">Договор</option>
          <option value="other">Другое</option>
        </select>
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

      {/* Tags */}
      <div>
        <label htmlFor="tags" className="mb-1.5 block text-sm font-medium text-gray-700">
          Теги
        </label>
        <input
          id="tags"
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="Введите теги через запятую"
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
        />
        <p className="mt-1 text-xs text-gray-500">Например: hr, политика, обязательно</p>
      </div>

      {/* Buttons */}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={isSubmitting || !title || !documentType || !file}
          className="flex-1 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Загрузка..." : "Загрузить документ"}
        </button>
        
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Отмена
          </button>
        )}
      </div>
    </form>
  );
}
