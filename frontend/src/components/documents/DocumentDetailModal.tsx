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
  Share2,
  MoreVertical,
  ChevronRight,
  Activity,
  History,
  MessageSquare,
} from "lucide-react";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DocumentWorkflowButtons } from "./DocumentWorkflowButtons";
import { DocumentAcknowledgement } from "./DocumentAcknowledgement";

interface DocumentDetailModalProps {
  document: Document | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate?: () => void;
  onPreview?: (url: string, name: string) => void;
}

type TabType = "overview" | "activity" | "acknowledgements" | "versions";

export function DocumentDetailModal({
  document,
  isOpen,
  onClose,
  onUpdate,
  onPreview,
}: DocumentDetailModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("overview");

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
    { id: "overview" as TabType, label: "Обзор", icon: FileText },
    { id: "activity" as TabType, label: "Активность", icon: Activity },
    { id: "acknowledgements" as TabType, label: "Ознакомления", icon: CheckCircle },
    { id: "versions" as TabType, label: "Версии", icon: History },
  ];

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
          <div className="shrink-0 border-b border-gray-200 bg-white px-6 py-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h2 className="text-xl font-semibold text-gray-900">{document.title}</h2>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-gray-500">
                  {document.document_type && (
                    <span className="flex items-center gap-1">
                      <FileText size={14} />
                      {document.document_type.name}
                    </span>
                  )}
                  {document.file_name && (
                    <span className="flex items-center gap-1">
                      <HardDrive size={14} />
                      {document.file_size && formatFileSize(document.file_size)}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Calendar size={14} />
                    {formatDate(document.uploaded_at || document.created_at)}
                  </span>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="flex items-center gap-2">
                <DocumentStatusBadge
                  status={document.status}
                  statusCode={document.status_code}
                />
                {document.file_url && (
                  <>
                    <button
                      onClick={() => onPreview?.(document.file_url!, document.file_name || document.title)}
                      className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
                    >
                      <Eye size={16} />
                      Открыть
                    </button>
                    <a
                      href={document.file_url}
                      download
                      className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
                    >
                      <Download size={16} />
                    </a>
                  </>
                )}
                <button className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">
                  <Share2 size={16} />
                </button>
                <button className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-2 text-gray-700 transition hover:bg-gray-50">
                  <MoreVertical size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Tabs Navigation */}
          <div className="shrink-0 border-b border-gray-200 bg-gray-50 px-6">
            <nav className="flex gap-1">
              {tabs.map((tab) => {
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

          {/* Tab Content */}
          <div className="min-h-0 flex-1 overflow-y-auto bg-gray-50">
            {activeTab === "overview" && (
              <div className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-3">
                {/* Main Content - Preview & Description */}
                <div className="space-y-6 lg:col-span-2">
                  {/* Document Preview */}
                  {document.file_url && (
                    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
                      <div className="aspect-[4/3] bg-gray-100">
                        {(() => {
                          const fileExt = document.file_name?.toLowerCase().split(".").pop() || "";
                          const isImage = ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"].includes(fileExt);
                          const isPDF = fileExt === "pdf";

                          if (isImage) {
                            return (
                              <img
                                src={document.file_url}
                                alt={document.file_name || "Preview"}
                                className="h-full w-full object-contain"
                              />
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
                            <div className="flex h-full items-center justify-center">
                              <div className="text-center">
                                <FileText size={64} className="mx-auto text-gray-300" />
                                <p className="mt-4 text-sm font-medium text-gray-600">
                                  {document.file_name}
                                </p>
                                <p className="mt-1 text-xs uppercase text-gray-400">{fileExt} файл</p>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  )}

                  {/* Description */}
                  <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                    <h3 className="mb-3 text-sm font-semibold text-gray-900">Описание</h3>
                    <p className="text-sm leading-relaxed text-gray-600">
                      {document.description || "Описание отсутствует"}
                    </p>
                  </div>

                  {/* Workflow Actions */}
                  <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                    <h3 className="mb-3 text-sm font-semibold text-gray-900">Действия с документом</h3>
                    <DocumentWorkflowButtons
                      documentId={document.id}
                      currentStatus={document.status_code}
                      onStatusChange={() => onUpdate?.()}
                    />
                  </div>
                </div>

                {/* Sidebar - Metadata */}
                <div className="space-y-4">
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
                <div className="mx-auto max-w-4xl">
                  <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                    <h3 className="mb-4 text-lg font-semibold text-gray-900">История активности</h3>
                    <div className="space-y-4">
                      {/* Timeline placeholder - будет реализовано через django-reversion API */}
                      <div className="flex gap-4">
                        <div className="flex flex-col items-center">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-100">
                            <Activity size={20} className="text-sky-600" />
                          </div>
                          <div className="w-px flex-1 bg-gray-200"></div>
                        </div>
                        <div className="flex-1 pb-8">
                          <p className="text-sm font-medium text-gray-900">
                            {document.status === "Опубликован" ? "Опубликован" : "Создан"}
                          </p>
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
              </div>
            )}

            {activeTab === "acknowledgements" && (
              <div className="p-6">
                <div className="mx-auto max-w-4xl">
                  <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                    {document.acknowledgement_required ? (
                      <DocumentAcknowledgement
                        document={document}
                        onAcknowledge={() => onUpdate?.()}
                      />
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
              </div>
            )}

            {activeTab === "versions" && (
              <div className="p-6">
                <div className="mx-auto max-w-4xl">
                  <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                    <h3 className="mb-4 text-lg font-semibold text-gray-900">История версий</h3>
                    <div className="rounded-lg bg-gray-50 p-8 text-center">
                      <History size={48} className="mx-auto text-gray-300" />
                      <p className="mt-4 text-sm text-gray-500">
                        Версионирование реализовано через django-reversion
                      </p>
                      <p className="mt-2 text-xs text-gray-400">
                        Требуется создать API endpoint для получения истории версий
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
    </Modal>
  );
}
