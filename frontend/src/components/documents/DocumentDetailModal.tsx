"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
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
  ScrollText,
} from "lucide-react";
import { DocumentAcknowledgement } from "./DocumentAcknowledgement";
import { DocumentComments } from "./DocumentComments";
import { DocumentRelated } from "./DocumentRelated";

const DocumentPreviewPane = dynamic(
  () => import("./DocumentPreview").then((mod) => mod.DocumentPreviewPane),
  {
    ssr: false,
    loading: () => (
      <div className="app-surface-muted flex h-full items-center justify-center">
        <p className="app-text-muted text-sm">Загружаем предпросмотр...</p>
      </div>
    ),
  },
);

interface DocumentDetailModalProps {
  document: Document | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate?: () => void;
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
  onEditMetadata,
  onViewReport,
  onNavigateToRelated,
}: DocumentDetailModalProps) {
  const [activeTabState, setActiveTabState] = useState<{ documentId: number | null; value: TabType }>({
    documentId: null,
    value: "preview",
  });
  const [fullscreenState, setFullscreenState] = useState<{ documentId: number | null; value: boolean }>({
    documentId: null,
    value: false,
  });
  const documentId = document?.id ?? null;
  const documentHasFile = Boolean(document?.file_url);
  const documentRequiresAcknowledgement = Boolean(document?.acknowledgement_required);

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
    ...(documentHasFile ? [{ id: "preview" as TabType, label: "Предпросмотр", icon: Eye }] : []),
    { id: "info" as TabType, label: "Информация", icon: Info },
    { id: "activity" as TabType, label: "Активность", icon: Activity },
    ...(documentRequiresAcknowledgement ? [{ id: "acknowledgements" as TabType, label: "Ознакомления", icon: CheckCircle }] : []),
    { id: "comments" as TabType, label: "Комментарии", icon: MessageSquare },
    { id: "related" as TabType, label: "Связанные", icon: Link2 },
  ];
  const defaultTab: TabType = documentHasFile ? "preview" : "info";
  const activeTab: TabType = activeTabState.documentId === documentId
    ? activeTabState.value
    : defaultTab;
  const currentActiveTab = tabs.some((tab) => tab.id === activeTab) ? activeTab : defaultTab;
  const isFullscreen = fullscreenState.documentId === documentId ? fullscreenState.value : false;
  const detailTabs = tabs.filter((tab) => tab.id !== "preview");
  const setDocumentActiveTab = (value: TabType) => {
    setActiveTabState({ documentId, value });
  };
  const setDocumentFullscreen = (value: boolean) => {
    setFullscreenState({ documentId, value });
  };

  const renderPreview = () => {
    if (!document.file_url) {
      return (
        <div className="app-surface-muted flex h-full items-center justify-center">
          <div className="text-center">
            <FileText size={64} className="app-text-muted mx-auto" />
            <p className="app-text-muted mt-4 text-sm font-medium">Файл не прикреплен</p>
          </div>
        </div>
      );
    }

    return (
      <DocumentPreviewPane
        fileUrl={document.file_url}
        fileName={document.file_name || document.title}
      />
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
        <div className="app-divider app-header shrink-0 border-b px-4 py-4 sm:px-6">
          <div className="flex flex-col gap-3">
            {/* Title Row */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-[var(--foreground)] sm:text-xl">{document.title}</h2>
              </div>

              {/* Quick Actions */}
              <div className="flex shrink-0 items-center gap-2">
                {onEditMetadata && (
                  <button
                    onClick={onEditMetadata}
                    className="app-selected app-accent-text inline-flex items-center gap-2 rounded-lg p-2 text-sm font-medium transition hover:opacity-90"
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
                      className="app-action-secondary inline-flex items-center gap-2 rounded-lg p-2 text-sm font-medium"
                      title="Скачать"
                    >
                      <Download size={16} />
                      <span className="hidden sm:inline">Скачать</span>
                    </a>
                    <button
                      onClick={() => setDocumentFullscreen(!isFullscreen)}
                      className="app-action-secondary hidden items-center gap-2 rounded-lg p-2 text-sm font-medium lg:inline-flex"
                      title={isFullscreen ? "Обычный режим" : "Полный экран"}
                    >
                      {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Metadata Row - Always visible */}
            <div className="app-text-muted flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
              {document.is_regulation && (
                <div className="app-selected app-accent-text flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium">
                  <ScrollText size={14} className="shrink-0" />
                  <span>Регламент</span>
                </div>
              )}
              {document.file_name && (
                <div className="flex items-center gap-1.5">
                  <HardDrive size={14} className="app-text-muted shrink-0" />
                  <span className="truncate font-medium">{document.file_name}</span>
                  {document.file_size && (
                    <span className="app-text-muted shrink-0">({formatFileSize(document.file_size)})</span>
                  )}
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <Calendar size={14} className="app-text-muted shrink-0" />
                <span>{formatDate(document.uploaded_at || document.created_at)}</span>
              </div>
              {document.uploaded_by && (
                <div className="flex items-center gap-1.5">
                  <User size={14} className="app-text-muted shrink-0" />
                  <span>{document.uploaded_by.last_name} {document.uploaded_by.first_name}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Mobile Tabs Navigation */}
        <div className="app-divider app-surface-muted shrink-0 border-b px-4 sm:px-6 lg:hidden">
          <nav className="app-tabs-scroll flex gap-1 overflow-x-auto overflow-y-hidden pb-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = currentActiveTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setDocumentActiveTab(tab.id)}
                  className={`flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition ${
                    isActive
                      ? "border-[var(--accent-primary)] text-[var(--accent-primary-strong)]"
                      : "border-transparent text-[var(--muted-foreground)] hover:border-[var(--border-strong)] hover:text-[var(--foreground)]"
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
            {documentHasFile && (
              <div className={`${isFullscreen ? "w-full" : "w-3/5"} shrink-0 border-r border-[var(--border-subtle)] transition-all`}>
                {renderPreview()}
              </div>
            )}

            {/* Info Panel (Right) */}
            {!(documentHasFile && isFullscreen) && (
              <div className="flex min-w-0 flex-1 flex-col">
                {/* Desktop Tabs */}
                <div className="app-divider app-surface-muted shrink-0 border-b px-6">
                  <nav className="app-tabs-scroll flex gap-1 overflow-x-auto overflow-y-hidden pb-1">
                    {detailTabs.map((tab) => {
                      const Icon = tab.icon;
                      const isActive = currentActiveTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setDocumentActiveTab(tab.id)}
                          className={`flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition ${
                            isActive
                              ? "border-[var(--accent-primary)] text-[var(--accent-primary-strong)]"
                              : "border-transparent text-[var(--muted-foreground)] hover:border-[var(--border-strong)] hover:text-[var(--foreground)]"
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
                <div className="min-h-0 flex-1 overflow-y-auto bg-[var(--surface-secondary)]">
                  {currentActiveTab === "info" && (
                    <div className="p-6">
                      <div className="space-y-4">
                        {/* Description */}
                        <div className="app-surface rounded-xl p-4">
                          <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                            Описание
                          </h3>
                          <p className="app-text-wrap app-text-muted text-sm leading-relaxed">
                            {document.description || "Описание отсутствует"}
                          </p>
                        </div>

                        {/* Author & Dates */}
                        <div className="app-surface rounded-xl p-4">
                          <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                            Информация
                          </h3>
                          <div className="space-y-3">
                            <div className="flex items-start gap-3">
                              <div className="app-selected app-accent-text rounded-lg p-2">
                                <User size={16} />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="app-text-muted text-xs">Автор</p>
                                <p className="truncate text-sm font-medium text-[var(--foreground)]">
                                  {document.uploaded_by
                                    ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                                    : "Не указан"}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-start gap-3">
                              <div className="app-feedback-success rounded-lg p-2">
                                <Calendar size={16} />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="app-text-muted text-xs">Создан</p>
                                <p className="text-sm font-medium text-[var(--foreground)]">
                                  {formatDate(document.uploaded_at || document.created_at)}
                                </p>
                              </div>
                            </div>

                            {document.modified_at && (
                              <div className="flex items-start gap-3">
                                <div className="app-feedback-warning rounded-lg p-2">
                                  <Clock size={16} />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <p className="app-text-muted text-xs">Изменен</p>
                                  <p className="text-sm font-medium text-[var(--foreground)]">
                                    {formatDate(document.modified_at)}
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Folder Location */}
                        {document.folder_path && (
                          <div className="app-surface rounded-xl p-4">
                            <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                              Расположение
                            </h3>
                            <div className="flex items-center gap-2 text-sm">
                              <FolderOpen size={16} className="app-accent-text shrink-0" />
                              <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
                                {document.folder_path.split(" / ").map((folder, index, arr) => (
                                  <div key={index} className="flex items-center gap-1">
                                    <span className="truncate text-[var(--foreground)]">{folder}</span>
                                    {index < arr.length - 1 && (
                                      <ChevronRight size={14} className="app-text-muted shrink-0" />
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Tags */}
                        {document.tags && document.tags.length > 0 && (
                          <div className="app-surface rounded-xl p-4">
                            <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                              Теги
                            </h3>
                            <div className="flex flex-wrap gap-2">
                              {document.tags.map((tag) => (
                                <span
                                  key={tag.id}
                                  className="app-badge inline-flex items-center gap-1 px-3 py-1 text-xs font-medium"
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
                          <div className="app-surface rounded-xl p-4">
                            <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                              Получатели
                            </h3>
                            <div className="space-y-3">
                              {document.sent_to_all && (
                                <div className="app-selected app-accent-text flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium">
                                  <CheckCircle size={14} />
                                  Все сотрудники
                                </div>
                              )}

                              {document.departments && document.departments.length > 0 && (
                                <div>
                                  <div className="app-text-muted mb-2 flex items-center gap-2 text-xs font-medium">
                                    <Building2 size={14} />
                                    Отделы ({document.departments.length})
                                  </div>
                                  <div className="space-y-1">
                                    {document.departments.map((dept) => (
                                      <div
                                        key={dept.id}
                                        className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"
                                      >
                                        <Building2 size={12} className="app-text-muted" />
                                        {dept.name}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {document.recipients && document.recipients.length > 0 && (
                                <div>
                                  <div className="app-text-muted mb-2 flex items-center gap-2 text-xs font-medium">
                                    <Users size={14} />
                                    Получатели ({document.recipients.length})
                                  </div>
                                  <div className="max-h-40 space-y-1 overflow-y-auto">
                                    {document.recipients.slice(0, 5).map((recipient) => (
                                      <div
                                        key={recipient.id}
                                        className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"
                                      >
                                        <User size={12} className="app-text-muted" />
                                        {recipient.last_name} {recipient.first_name}
                                      </div>
                                    ))}
                                    {document.recipients.length > 5 && (
                                      <div className="app-text-muted px-3 py-2 text-xs">
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

                  {currentActiveTab === "activity" && (
                    <div className="p-6">
                      <div className="app-surface rounded-xl p-6">
                        <h3 className="mb-4 text-lg font-semibold text-[var(--foreground)]">История активности</h3>
                        <div className="space-y-4">
                          <div className="flex gap-4">
                            <div className="flex flex-col items-center">
                              <div className="app-selected app-accent-text flex h-10 w-10 items-center justify-center rounded-full">
                                <Activity size={20} />
                              </div>
                              <div className="w-px flex-1 bg-[var(--border-subtle)]"></div>
                            </div>
                            <div className="flex-1 pb-8">
                              <p className="text-sm font-medium text-[var(--foreground)]">Создан</p>
                              <p className="app-text-muted mt-1 text-xs">
                                {document.uploaded_by
                                  ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                                  : "Система"}{" "}
                                • {formatDate(document.uploaded_at || document.created_at)}
                              </p>
                            </div>
                          </div>

                          <div className="app-surface-muted rounded-lg p-4 text-center">
                            <Activity size={32} className="app-text-muted mx-auto" />
                            <p className="app-text-muted mt-2 text-sm">
                              История изменений будет доступна после интеграции с django-reversion API
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {currentActiveTab === "acknowledgements" && (
                    <div className="p-6">
                      <div className="app-surface rounded-xl p-6">
                        {document.acknowledgement_required ? (
                          <>
                            {onViewReport && (
                              <div className="mb-4 flex items-center justify-between">
                                <h3 className="text-sm font-medium text-[var(--foreground)]">Подтверждение прочтения</h3>
                                <button
                                  onClick={onViewReport}
                                  className="app-selected app-accent-text inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium hover:opacity-90"
                                >
                                  Посмотреть ведомость
                                </button>
                              </div>
                            )}
                            <DocumentAcknowledgement document={document} onAcknowledge={() => onUpdate?.()} />
                          </>
                        ) : (
                          <div className="py-12 text-center">
                            <CheckCircle size={48} className="app-text-muted mx-auto" />
                            <p className="app-text-muted mt-4 text-sm">
                              Для этого документа не требуется подтверждение ознакомления
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {currentActiveTab === "comments" && (
                    <div className="p-6">
                      <div className="app-surface rounded-xl p-6">
                        <DocumentComments documentId={document.id} />
                      </div>
                    </div>
                  )}

                  {currentActiveTab === "related" && (
                    <div className="p-6">
                      <div className="app-surface rounded-xl p-6">
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
          <div className="h-full overflow-y-auto bg-[var(--surface-secondary)] lg:hidden">
            {currentActiveTab === "preview" && (
              <div className="h-full min-h-[400px]">{renderPreview()}</div>
            )}

            {currentActiveTab === "info" && (
              <div className="p-4 sm:p-6">
                <div className="space-y-4">
                  {/* Description */}
                  <div className="app-surface rounded-xl p-4">
                    <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                      Описание
                    </h3>
                    <p className="app-text-wrap app-text-muted text-sm leading-relaxed">
                      {document.description || "Описание отсутствует"}
                    </p>
                  </div>

                  {/* Author & Dates */}
                  <div className="app-surface rounded-xl p-4">
                    <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                      Информация
                    </h3>
                    <div className="space-y-3">
                      <div className="flex items-start gap-3">
                        <div className="app-selected app-accent-text rounded-lg p-2">
                          <User size={16} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="app-text-muted text-xs">Автор</p>
                          <p className="truncate text-sm font-medium text-[var(--foreground)]">
                            {document.uploaded_by
                              ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                              : "Не указан"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-start gap-3">
                        <div className="app-feedback-success rounded-lg p-2">
                          <Calendar size={16} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="app-text-muted text-xs">Создан</p>
                          <p className="text-sm font-medium text-[var(--foreground)]">
                            {formatDate(document.uploaded_at || document.created_at)}
                          </p>
                        </div>
                      </div>

                      {document.modified_at && (
                        <div className="flex items-start gap-3">
                          <div className="app-feedback-warning rounded-lg p-2">
                            <Clock size={16} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="app-text-muted text-xs">Изменен</p>
                            <p className="text-sm font-medium text-[var(--foreground)]">
                              {formatDate(document.modified_at)}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Folder Location */}
                  {document.folder_path && (
                    <div className="app-surface rounded-xl p-4">
                      <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                        Расположение
                      </h3>
                      <div className="flex items-center gap-2 text-sm">
                        <FolderOpen size={16} className="app-accent-text shrink-0" />
                        <div className="flex min-w-0 flex-1 flex-col gap-1 overflow-hidden">
                          {document.folder_path.split(" / ").map((folder, index, arr) => (
                            <div key={index} className="flex items-center gap-1">
                              <span className="truncate text-[var(--foreground)]">{folder}</span>
                              {index < arr.length - 1 && (
                                <ChevronRight size={14} className="app-text-muted shrink-0" />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {document.tags && document.tags.length > 0 && (
                    <div className="app-surface rounded-xl p-4">
                      <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                        Теги
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {document.tags.map((tag) => (
                          <span
                            key={tag.id}
                            className="app-badge inline-flex items-center gap-1 px-3 py-1 text-xs font-medium"
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
                    <div className="app-surface rounded-xl p-4">
                      <h3 className="app-text-muted mb-3 text-xs font-semibold uppercase tracking-wide">
                        Получатели
                      </h3>
                      <div className="space-y-3">
                        {document.sent_to_all && (
                          <div className="app-selected app-accent-text flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium">
                            <CheckCircle size={14} />
                            Все сотрудники
                          </div>
                        )}

                        {document.departments && document.departments.length > 0 && (
                          <div>
                            <div className="app-text-muted mb-2 flex items-center gap-2 text-xs font-medium">
                              <Building2 size={14} />
                              Отделы ({document.departments.length})
                            </div>
                            <div className="space-y-1">
                              {document.departments.map((dept) => (
                                <div
                                  key={dept.id}
                                  className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"
                                >
                                  <Building2 size={12} className="app-text-muted" />
                                  {dept.name}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {document.recipients && document.recipients.length > 0 && (
                          <div>
                            <div className="app-text-muted mb-2 flex items-center gap-2 text-xs font-medium">
                              <Users size={14} />
                              Получатели ({document.recipients.length})
                            </div>
                            <div className="max-h-40 space-y-1 overflow-y-auto">
                              {document.recipients.slice(0, 5).map((recipient) => (
                                <div
                                  key={recipient.id}
                                  className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"
                                >
                                  <User size={12} className="app-text-muted" />
                                  {recipient.last_name} {recipient.first_name}
                                </div>
                              ))}
                              {document.recipients.length > 5 && (
                                <div className="app-text-muted px-3 py-2 text-xs">
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

            {currentActiveTab === "activity" && (
              <div className="p-4 sm:p-6">
                <div className="app-surface rounded-xl p-4 sm:p-6">
                  <h3 className="mb-4 text-lg font-semibold text-[var(--foreground)]">История активности</h3>
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className="app-selected app-accent-text flex h-10 w-10 items-center justify-center rounded-full">
                          <Activity size={20} />
                        </div>
                        <div className="w-px flex-1 bg-[var(--border-subtle)]"></div>
                      </div>
                      <div className="flex-1 pb-8">
                        <p className="text-sm font-medium text-[var(--foreground)]">Создан</p>
                        <p className="app-text-muted mt-1 text-xs">
                          {document.uploaded_by
                            ? `${document.uploaded_by.last_name} ${document.uploaded_by.first_name}`
                            : "Система"}{" "}
                          • {formatDate(document.uploaded_at || document.created_at)}
                        </p>
                      </div>
                    </div>

                    <div className="app-surface-muted rounded-lg p-4 text-center">
                      <Activity size={32} className="app-text-muted mx-auto" />
                      <p className="app-text-muted mt-2 text-sm">
                        История изменений будет доступна после интеграции с django-reversion API
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {currentActiveTab === "acknowledgements" && (
              <div className="p-4 sm:p-6">
                <div className="app-surface rounded-xl p-4 sm:p-6">
                  {document.acknowledgement_required ? (
                    <>
                      {onViewReport && (
                        <div className="mb-4 flex items-center justify-between">
                          <h3 className="text-sm font-medium text-[var(--foreground)]">Подтверждение прочтения</h3>
                          <button
                            onClick={onViewReport}
                            className="app-selected app-accent-text inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium hover:opacity-90"
                          >
                            Посмотреть ведомость
                          </button>
                        </div>
                      )}
                      <DocumentAcknowledgement document={document} onAcknowledge={() => onUpdate?.()} />
                    </>
                  ) : (
                    <div className="py-12 text-center">
                      <CheckCircle size={48} className="app-text-muted mx-auto" />
                      <p className="app-text-muted mt-4 text-sm">
                        Для этого документа не требуется подтверждение ознакомления
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {currentActiveTab === "comments" && (
              <div className="p-4 sm:p-6">
                <div className="app-surface rounded-xl p-4 sm:p-6">
                  <DocumentComments documentId={document.id} />
                </div>
              </div>
            )}

            {currentActiveTab === "related" && (
              <div className="p-4 sm:p-6">
                <div className="app-surface rounded-xl p-4 sm:p-6">
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
