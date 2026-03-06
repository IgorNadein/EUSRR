"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import type { Document } from "@/types/api";
import {
  FileText,
  User,
  Calendar,
  HardDrive,
  FolderOpen,
  Users,
  Building2,
  Tag,
  Clock,
  CheckCircle,
  Eye,
  Download,
  ChevronRight,
  Activity,
  Maximize2,
  Minimize2,
  Info,
  Edit,
  MessageSquare,
  Link2,
} from "lucide-react";
import { DocumentAcknowledgement } from "./DocumentAcknowledgement";
import { DocumentComments } from "./DocumentComments";
import { DocumentRelated } from "./DocumentRelated";

interface DocumentDetailModalProps {
  document: Document | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate?: () => void;
  onPreview?: (url: string, name: string) => void;
  onEditMetadata?: () => void;
  onViewReport?: () => void;
  onNavigateToRelated?: (docId: number) => void;
}

type TabType = "preview" | "info" | "activity" | "acknowledgements" | "comments" | "related";

export function DocumentDetailModal({
  document,
  isOpen,
  onClose,
  onUpdate,
  onPreview,
  onEditMetadata,
  onViewReport,
  onNavigateToRelated,
}: DocumentDetailModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("preview");
  const [isFullscreen, setIsFullscreen] = useState(false);

  if (!document) return null;

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
  };

  const tabs = [
    { id: "preview" as TabType, label: "Предпросмотр", icon: Eye },
    { id: "info" as TabType, label: "Информация", icon: Info },
    { id: "activity" as TabType, label: "Активность", icon: Activity },
    { id: "acknowledgements" as TabType, label: "Ознакомления", icon: CheckCircle },
    { id: "comments" as TabType, label: "Комментарии", icon: MessageSquare },
    { id: "related" as TabType, label: "Связанные", icon: Link2 },
  ];

  const renderPreview = () => {
    if (!document.file_url) {
      return (
        <div className="flex h-full items-center justify-center bg-gray-100">
          <div className="text-center">
            <FileText size={64} className="mx-auto text-gray-300" />
            <p className="mt-4 text-sm font-medium text-gray-600">Файл не прикреплен</p>
          </div>
        </div>
      );
    }

    const fileExt = document.file_name?.toLowerCase().split(".").pop() || "";
    const isImage = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"].includes(fileExt);
    const isPDF = fileExt === "pdf";

    if (isImage) {
      return (
        <div className="flex h-full items-center justify-center bg-gray-900 p-4">
          <img
            src={document.file_url}
            alt={document.file_name || "Preview"}
            className="max-h-full max-w-full object-contain"
          />
        </div>
      );
    }

    if (isPDF) {
      return (
        <iframe
          src={`${document.file_url}#page=1&view=FitH`}
          className="h-full w-full border-0"
          title="PDF Preview"
        />
      );
    }

    return (
      <div className="flex h-full items-center justify-center bg-gray-100">
        <div className="text-center">
          <FileText size={64} className="mx-auto text-gray-300" />
          <p className="mt-4 text-sm font-medium text-gray-600">{document.file_name}</p>
          <p className="mt-1 text-xs uppercase text-gray-400">{fileExt} файл</p>
          <p className="mt-3 text-xs text-gray-500">Предпросмотр недоступен</p>
        </div>
      </div>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="full"
      showCloseButton
      className="flex flex-col"
    >
      <div className="flex h-full min-h-0 flex-col">
        {/* Header with Title and Actions */}
        <div className="shrink-0 border-b border-gray-200 bg-white px-4 py-4 sm:px-6">
          <div className="flex flex-col gap-3">
            {/* Title Row */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-gray-900 sm:text-xl">{document.title}</h2>
              </div>

              {/* Quick Actions */}
              <div className="flex shrink-0 items-center gap-2">
                {onEditMetadata && (
                  <button
                    onClick={onEditMetadata}
                    className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-blue-50 p-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
                    title="Редактировать метаданные"
                  >
                    <Edit size={16} />
                    <span className="hidden sm:inline">Редактировать</span>
                  </button>
                )}
                {document.file_url && (
                  <>
                    <a
                      href={document.file_url}
                      download
                      className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white p-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
                      title="Скачать"
                    >
                      <Download size={16} />
                      <span className="hidden sm:inline">Скачать</span>
                    </a>
                    <button
                      onClick={() => setIsFullscreen(!isFullscreen)}
                      className="hidden items-center gap-2 rounded-lg border border-gray-300 bg-white p-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 lg:inline-flex"
                      title={isFullscreen ? "Обычный режим" : "Полный экран"}
                    >
                      {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Metadata Row - Always visible */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-gray-600">
              {document.file_name && (
                <div className="flex items-center gap-1.5">
                  <HardDrive size={14} className="shrink-0 text-gray-400" />
                  <span className="truncate font-medium">{document.file_name}</span>
                  {document.file_size && (
                    <span className="shrink-0 text-gray-500">({formatFileSize(document.file_size)})</span>
                  )}
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <Calendar size={14} className="shrink-0 text-gray-400" />
                <span>{formatDate(document.uploaded_at || document.created_at)}</span>
              </div>
              {document.uploaded_by && (
                <div className="flex items-center gap-1.5">
                  <User size={14} className="shrink-0 text-gray-400" />
                  <span>{document.uploaded_by.last_name} {document.uploaded_by.first_name}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Mobile Tabs Navigation */}
        <div className="shrink-0 border-b border-gray-200 bg-gray-50 px-4 sm:px-6 lg:hidden">
          <nav className="flex gap-1 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${
                    isActive
                      ? "border-sky-600 text-sky-600"
                      : "border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900"
                  }`}
                >
                  <Icon size={16} />
                  <span className="whitespace-nowrap">{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content Area */}
        <div className="min-h-0 flex-1 overflow-hidden">
          {/* Desktop Layout: Side-by-side */}
          <div className="hidden h-full lg:flex">
            {/* Preview Panel (Left) */}
            <div className={`${isFullscreen ? "w-full" : "w-3/5"} shrink-0 border-r border-gray-200 transition-all`}>
              {renderPreview()}
            </div>

            {/* Info Panel (Right) */}
            {!isFullscreen && (
              <div className="flex min-w-0 flex-1 flex-col">
                {/* Desktop Tabs */}
                <div className="shrink-0 border-b border-gray-200 bg-gray-50 px-6">
                  <nav className="flex gap-1">
                    {tabs.slice(1).map((tab) => {
                      const Icon = tab.icon;
                      const isActive = activeTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition ${
                            isActive
                              ? "border-sky-600 text-sky-600"
                              : "border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900"
                          }`}
                        >
                          <Icon size={16} />
                          {tab.label}
                        </button>
                      );
                    })}
                  </nav>
                </div>

                {/* Desktop Tab Content */}
                <div className="min-h-0 flex-1 overflow-y-auto bg-gray-50">
                  {activeTab === "info" && (
                    <div className="p-6">
                      <div className="space-y-4">
                        {/* Description */}
                        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                            Описание
                          </h3>
                          <p className="text-sm leading-relaxed text-gray-600">
                            {document.description || "Описание отсутствует"}
                          </p>
                        </div>

                        {/* Author & Dates */}
                        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                            Информация
                          </h3>
                          <div className="space-y-3">
                            <div className="flex items-start gap-3">
                              <div className="rounded-lg bg-sky-50 p-2">
                                <User size={16} className="text-sky-600" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs text-gray-500">Автор</p>
                                <p className="truncate text-sm font-medium text-gray-900">
                                  {document.uploaded_by
                                    ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                                    : "Не указан"}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-start gap-3">
                              <div className="rounded-lg bg-green-50 p-2">
                                <Calendar size={16} className="text-green-600" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs text-gray-500">Создан</p>
                                <p className="text-sm font-medium text-gray-900">
                                  {formatDate(document.uploaded_at || document.created_at)}
                                </p>
                              </div>
                            </div>

                            {document.modified_at && (
                              <div className="flex items-start gap-3">
                                <div className="rounded-lg bg-orange-50 p-2">
                                  <Clock size={16} className="text-orange-600" />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <p className="text-xs text-gray-500">Изменен</p>
                                  <p className="text-sm font-medium text-gray-900">
                                    {formatDate(document.modified_at)}
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Folder Location */}
                        {document.folder_path && (
                          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                              Расположение
                            </h3>
                            <div className="flex items-center gap-2 text-sm">
                              <FolderOpen size={16} className="shrink-0 text-sky-600" />
                              <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
                                {document.folder_path.split(" / ").map((folder, index, arr) => (
                                  <div key={index} className="flex items-center gap-1">
                                    <span className="truncate text-gray-700">{folder}</span>
                                    {index < arr.length - 1 && (
                                      <ChevronRight size={14} className="shrink-0 text-gray-400" />
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Tags */}
                        {document.tags && document.tags.length > 0 && (
                          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                              Теги
                            </h3>
                            <div className="flex flex-wrap gap-2">
                              {document.tags.map((tag) => (
                                <span
                                  key={tag.id}
                                  className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
                                >
                                  <Tag size={12} />
                                  {tag.name}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Recipients */}
                        {(document.sent_to_all ||
                          (document.departments && document.departments.length > 0) ||
                          (document.recipients && document.recipients.length > 0)) && (
                          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                              Получатели
                            </h3>
                            <div className="space-y-3">
                              {document.sent_to_all && (
                                <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs font-medium text-blue-700">
                                  <CheckCircle size={14} />
                                  Все сотрудники
                                </div>
                              )}

                              {document.departments && document.departments.length > 0 && (
                                <div>
                                  <div className="mb-2 flex items-center gap-2 text-xs font-medium text-gray-500">
                                    <Building2 size={14} />
                                    Отделы ({document.departments.length})
                                  </div>
                                  <div className="space-y-1">
                                    {document.departments.map((dept) => (
                                      <div
                                        key={dept.id}
                                        className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700"
                                      >
                                        <Building2 size={12} className="text-gray-400" />
                                        {dept.name}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {document.recipients && document.recipients.length > 0 && (
                                <div>
                                  <div className="mb-2 flex items-center gap-2 text-xs font-medium text-gray-500">
                                    <Users size={14} />
                                    Получатели ({document.recipients.length})
                                  </div>
                                  <div className="max-h-40 space-y-1 overflow-y-auto">
                                    {document.recipients.slice(0, 5).map((recipient) => (
                                      <div
                                        key={recipient.id}
                                        className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700"
                                      >
                                        <User size={12} className="text-gray-400" />
                                        {recipient.last_name} {recipient.first_name}
                                      </div>
                                    ))}
                                    {document.recipients.length > 5 && (
                                      <div className="px-3 py-2 text-xs text-gray-500">
                                        ... и ещё {document.recipients.length - 5}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {activeTab === "activity" && (
                    <div className="p-6">
                      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                        <h3 className="mb-4 text-lg font-semibold text-gray-900">История активности</h3>
                        <div className="space-y-4">
                          <div className="flex gap-4">
                            <div className="flex flex-col items-center">
                              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-100">
                                <Activity size={20} className="text-sky-600" />
                              </div>
                              <div className="w-px flex-1 bg-gray-200"></div>
                            </div>
                            <div className="flex-1 pb-8">
                              <p className="text-sm font-medium text-gray-900">Создан</p>
                              <p className="mt-1 text-xs text-gray-500">
                                {document.uploaded_by
                                  ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                                  : "Система"}{" "}
                                • {formatDate(document.uploaded_at || document.created_at)}
                              </p>
                            </div>
                          </div>

                          <div className="rounded-lg bg-gray-50 p-4 text-center">
                            <Activity size={32} className="mx-auto text-gray-300" />
                            <p className="mt-2 text-sm text-gray-500">
                              История изменений будет доступна после интеграции с django-reversion API
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === "acknowledgements" && (
                    <div className="p-6">
                      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                        {document.acknowledgement_required ? (
                          <>
                            {onViewReport && (
                              <div className="mb-4 flex items-center justify-between">
                                <h3 className="text-sm font-medium text-gray-700">Подтверждение прочтения</h3>
                                <button
                                  onClick={onViewReport}
                                  className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 ring-1 ring-blue-200 hover:bg-blue-100"
                                >
                                  Посмотреть ведомость
                                </button>
                              </div>
                            )}
                            <DocumentAcknowledgement document={document} onAcknowledge={() => onUpdate?.()} />
                          </>
                        ) : (
                          <div className="py-12 text-center">
                            <CheckCircle size={48} className="mx-auto text-gray-300" />
                            <p className="mt-4 text-sm text-gray-500">
                              Для этого документа не требуется подтверждение ознакомления
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {activeTab === "comments" && (
                    <div className="p-6">
                      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                        <DocumentComments documentId={document.id} />
                      </div>
                    </div>
                  )}

                  {activeTab === "related" && (
                    <div className="p-6">
                      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                        <DocumentRelated
                          documentId={document.id}
                          onNavigate={(docId) => onNavigateToRelated?.(docId)}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Mobile Layout: Tabs */}
          <div className="h-full overflow-y-auto bg-gray-50 lg:hidden">
            {activeTab === "preview" && (
              <div className="h-full min-h-[400px]">{renderPreview()}</div>
            )}

            {activeTab === "info" && (
              <div className="p-4 sm:p-6">
                <div className="space-y-4">
                  {/* Description */}
                  <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Описание
                    </h3>
                    <p className="text-sm leading-relaxed text-gray-600">
                      {document.description || "Описание отсутствует"}
                    </p>
                  </div>

                  {/* Author & Dates */}
                  <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Информация
                    </h3>
                    <div className="space-y-3">
                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-sky-50 p-2">
                          <User size={16} className="text-sky-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs text-gray-500">Автор</p>
                          <p className="truncate text-sm font-medium text-gray-900">
                            {document.uploaded_by
                              ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                              : "Не указан"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-green-50 p-2">
                          <Calendar size={16} className="text-green-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs text-gray-500">Создан</p>
                          <p className="text-sm font-medium text-gray-900">
                            {formatDate(document.uploaded_at || document.created_at)}
                          </p>
                        </div>
                      </div>

                      {document.modified_at && (
                        <div className="flex items-start gap-3">
                          <div className="rounded-lg bg-orange-50 p-2">
                            <Clock size={16} className="text-orange-600" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs text-gray-500">Изменен</p>
                            <p className="text-sm font-medium text-gray-900">
                              {formatDate(document.modified_at)}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Folder Location */}
                  {document.folder_path && (
                    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Расположение
                      </h3>
                      <div className="flex items-center gap-2 text-sm">
                        <FolderOpen size={16} className="shrink-0 text-sky-600" />
                        <div className="flex min-w-0 flex-1 flex-col gap-1 overflow-hidden">
                          {document.folder_path.split(" / ").map((folder, index, arr) => (
                            <div key={index} className="flex items-center gap-1">
                              <span className="truncate text-gray-700">{folder}</span>
                              {index < arr.length - 1 && (
                                <ChevronRight size={14} className="shrink-0 text-gray-400" />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {document.tags && document.tags.length > 0 && (
                    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Теги
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {document.tags.map((tag) => (
                          <span
                            key={tag.id}
                            className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
                          >
                            <Tag size={12} />
                            {tag.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recipients */}
                  {(document.sent_to_all ||
                    (document.departments && document.departments.length > 0) ||
                    (document.recipients && document.recipients.length > 0)) && (
                    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Получатели
                      </h3>
                      <div className="space-y-3">
                        {document.sent_to_all && (
                          <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs font-medium text-blue-700">
                            <CheckCircle size={14} />
                            Все сотрудники
                          </div>
                        )}

                        {document.departments && document.departments.length > 0 && (
                          <div>
                            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-gray-500">
                              <Building2 size={14} />
                              Отделы ({document.departments.length})
                            </div>
                            <div className="space-y-1">
                              {document.departments.map((dept) => (
                                <div
                                  key={dept.id}
                                  className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700"
                                >
                                  <Building2 size={12} className="text-gray-400" />
                                  {dept.name}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {document.recipients && document.recipients.length > 0 && (
                          <div>
                            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-gray-500">
                              <Users size={14} />
                              Получатели ({document.recipients.length})
                            </div>
                            <div className="max-h-40 space-y-1 overflow-y-auto">
                              {document.recipients.slice(0, 5).map((recipient) => (
                                <div
                                  key={recipient.id}
                                  className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700"
                                >
                                  <User size={12} className="text-gray-400" />
                                  {recipient.last_name} {recipient.first_name}
                                </div>
                              ))}
                              {document.recipients.length > 5 && (
                                <div className="px-3 py-2 text-xs text-gray-500">
                                  ... и ещё {document.recipients.length - 5}
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === "activity" && (
              <div className="p-4 sm:p-6">
                <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-6">
                  <h3 className="mb-4 text-lg font-semibold text-gray-900">История активности</h3>
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-100">
                          <Activity size={20} className="text-sky-600" />
                        </div>
                        <div className="w-px flex-1 bg-gray-200"></div>
                      </div>
                      <div className="flex-1 pb-8">
                        <p className="text-sm font-medium text-gray-900">Создан</p>
                        <p className="mt-1 text-xs text-gray-500">
                          {document.uploaded_by
                            ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                            : "Система"}{" "}
                          • {formatDate(document.uploaded_at || document.created_at)}
                        </p>
                      </div>
                    </div>

                    <div className="rounded-lg bg-gray-50 p-4 text-center">
                      <Activity size={32} className="mx-auto text-gray-300" />
                      <p className="mt-2 text-sm text-gray-500">
                        История изменений будет доступна после интеграции с django-reversion API
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "acknowledgements" && (
              <div className="p-4 sm:p-6">
                <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-6">
                  {document.acknowledgement_required ? (
                    <>
                      {onViewReport && (
                        <div className="mb-4 flex items-center justify-between">
                          <h3 className="text-sm font-medium text-gray-700">Подтверждение прочтения</h3>
                          <button
                            onClick={onViewReport}
                            className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 ring-1 ring-blue-200 hover:bg-blue-100"
                          >
                            Посмотреть ведомость
                          </button>
                        </div>
                      )}
                      <DocumentAcknowledgement document={document} onAcknowledge={() => onUpdate?.()} />
                    </>
                  ) : (
                    <div className="py-12 text-center">
                      <CheckCircle size={48} className="mx-auto text-gray-300" />
                      <p className="mt-4 text-sm text-gray-500">
                        Для этого документа не требуется подтверждение ознакомления
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === "comments" && (
              <div className="p-4 sm:p-6">
                <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-6">
                  <DocumentComments documentId={document.id} />
                </div>
              </div>
            )}

            {activeTab === "related" && (
              <div className="p-4 sm:p-6">
                <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-6">
                  <DocumentRelated
                    documentId={document.id}
                    onNavigate={(docId) => onNavigateToRelated?.(docId)}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}
