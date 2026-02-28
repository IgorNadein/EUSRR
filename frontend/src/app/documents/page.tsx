"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import type { Document, DocumentStatus } from "@/types/api";
import {
  Search,
  FileText,
  Plus,
  Eye,
  X,
  LayoutDashboard,
  FolderOpen,
  Tags,
  LayoutGrid,
  CheckSquare,
  SlidersHorizontal,
  CheckCircle,
  AlertCircle,
  Calendar,
  User,
  File,
  HardDrive,
  Users,
  Building2,
} from "lucide-react";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { DocumentWorkflowButtons } from "@/components/documents/DocumentWorkflowButtons";
import { DocumentAcknowledgement } from "@/components/documents/DocumentAcknowledgement";
import { DocumentAcknowledgementsReport } from "@/components/documents/DocumentAcknowledgementsReport";
import { FolderTree, type FolderNode } from "@/components/documents/folders";
import { AdvancedSearch } from "@/components/documents/search";
import { BulkActionsToolbar, useDocumentSelection } from "@/components/documents/batch";
import { DocumentsDashboard } from "@/components/documents/dashboard";
import { Modal } from "@/components/ui";

// Динамический импорт компонентов с PDF обработкой (избегаем SSR ошибок с DOMMatrix)
const DocumentUploadForm = dynamic(
  () => import("@/components/documents/DocumentUploadForm").then(mod => ({ default: mod.DocumentUploadForm })),
  { ssr: false }
);

const EnhancedPDFViewer = dynamic(
  () => import("@/components/documents/viewer").then(mod => ({ default: mod.EnhancedPDFViewer })),
  { ssr: false }
);

const DocumentPreview = dynamic(
  () => import("@/components/documents/DocumentPreview").then(mod => ({ default: mod.DocumentPreview })),
  { ssr: false }
);

function formatDate(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

type ViewMode = "documents" | "dashboard";

export default function DocumentsPage() {
  // State
  const [documents, setDocuments] = useState<Document[]>([]);
  const [folders, setFolders] = useState<FolderNode[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("documents");
  
  // Modals
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [showAcknowledgementsReport, setShowAcknowledgementsReport] = useState<{
    documentId: number;
    documentTitle: string;
  } | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [previewFile, setPreviewFile] = useState<{ url: string; name: string } | null>(null);
  const [pdfViewerFile, setPdfViewerFile] = useState<{ url: string; name: string } | null>(null);
  
  // Folder dropdown
  const [showFolderDropdown, setShowFolderDropdown] = useState(false);
  
  // Bulk selection
  const selection = useDocumentSelection(documents);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {};
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      if (selectedFolderId !== null) {
        params.folder_id = selectedFolderId;
      }
      console.log("📁 Загрузка документов с параметрами:", params);
      const response = await apiClient.getDocuments(params);
      console.log("📄 Получено документов:", response.results?.length || 0);
      setDocuments(response.results || []);
    } catch (err) {
      console.error("Ошибка загрузки документов:", err);
      setError("Не удалось загрузить документы");
    } finally {
      setLoading(false);
    }
  };

  const loadFolders = async () => {
    try {
      const response = await apiClient.getFolders({ root: true });
      setFolders(response.results || response || []);
    } catch (err) {
      console.error("Ошибка загрузки папок:", err);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [statusFilter, selectedFolderId]);

  useEffect(() => {
    loadFolders();
  }, []);

  useEffect(() => {
    loadFolders();
  }, []);

  const filteredDocuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...documents].sort((a, b) => {
      const aTime = new Date(a.created_at).getTime() || 0;
      const bTime = new Date(b.created_at).getTime() || 0;
      return bTime - aTime;
    });

    if (!q) return sorted;

    return sorted.filter((doc) => {
      const title = doc.title.toLowerCase();
      const description = (doc.description || "").toLowerCase();
      const author = doc.created_by
        ? `${doc.created_by.last_name} ${doc.created_by.first_name}`.toLowerCase()
        : "";
      return title.includes(q) || description.includes(q) || author.includes(q);
    });
  }, [documents, search]);

  // Find selected folder and build breadcrumb path
  const selectedFolder = useMemo(() => {
    if (!selectedFolderId) return null;
    
    const findFolder = (foldersArray: FolderNode[]): FolderNode | null => {
      for (const folder of foldersArray) {
        if (folder.id === selectedFolderId) return folder;
        if (folder.children) {
          const found = findFolder(folder.children);
          if (found) return found;
        }
      }
      return null;
    };
    
    return findFolder(folders);
  }, [selectedFolderId, folders]);

  const breadcrumbs = useMemo(() => {
    if (!selectedFolder) return [];
    return selectedFolder.path.split(' / ');
  }, [selectedFolder]);

  // Mock dashboard stats
  const dashboardStats = useMemo(() => {
    const byStatus = documents.reduce((acc: any[], doc) => {
      const existing = acc.find((s) => s.status === doc.status);
      if (existing) {
        existing.count++;
      } else {
        acc.push({ status: doc.status, count: 1 });
      }
      return acc;
    }, []);

    return {
      totalDocuments: documents.length,
      documentsByType: [{ type: "Общие", count: documents.length }],
      documentsByStatus: byStatus,
      uploadsOverTime: [],
      myDocuments: documents.filter((d) => d.created_by).length,
      recentActivity: [],
    };
  }, [documents]);

  return (
    <AppShell>
      <div className="space-y-4">
        {/* Top Bar */}
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            {/* Left: Tabs + Folder Dropdown */}
            <div className="flex flex-wrap items-center gap-3">
              {/* View Mode Tabs */}
              <div className="flex gap-1 rounded-lg bg-gray-100 p-1">
                <button
                  onClick={() => setViewMode("documents")}
                  className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition ${
                    viewMode === "documents"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  <FileText size={16} />
                  Документы
                </button>
                <button
                  onClick={() => setViewMode("dashboard")}
                  className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition ${
                    viewMode === "dashboard"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  <LayoutDashboard size={16} />
                  Дашборд
                </button>
              </div>

              {/* Folder Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowFolderDropdown(!showFolderDropdown)}
                  className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition ${
                    selectedFolderId
                      ? "border-sky-300 bg-sky-50 text-sky-700 hover:bg-sky-100"
                      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <FolderOpen size={16} />
                  <span className="max-w-[200px] truncate">
                    {selectedFolder ? selectedFolder.name : "Все папки"}
                  </span>
                  {selectedFolderId && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFolderId(null);
                      }}
                      className="rounded p-0.5 hover:bg-sky-200"
                      title="Сбросить фильтр"
                    >
                      <X size={14} />
                    </button>
                  )}
                </button>
                {showFolderDropdown && (
                  <div className="absolute left-0 top-full z-10 mt-2 w-72 rounded-lg border border-gray-200 bg-white shadow-lg">
                    <div className="max-h-96 overflow-y-auto p-2">
                      <FolderTree
                        folders={folders}
                        selectedFolderId={selectedFolderId}
                        onSelectFolder={(id) => {
                          console.log("🗂️ Выбрана папка:", id);
                          setSelectedFolderId(id);
                          setShowFolderDropdown(false);
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Actions */}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setShowAdvancedSearch(!showAdvancedSearch)}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
              >
                <SlidersHorizontal size={16} />
                {showAdvancedSearch ? "Простой поиск" : "Расширенный"}
              </button>
              <button
                onClick={() => setShowCreateFolder(true)}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
              >
                <FolderOpen size={16} />
                Создать папку
              </button>
              <button
                onClick={() => setShowUploadForm(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
              >
                <Plus size={16} />
                Загрузить
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="space-y-4">
          {loading ? (
            <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
              <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
              <p className="text-sm text-gray-500">Загрузка документов...</p>
            </div>
          ) : error ? (
            <div className="rounded-2xl bg-red-50 p-6 text-center">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          ) : (
            <>
              {/* Dashboard View */}
              {viewMode === "dashboard" && (
                <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-100">
                  <DocumentsDashboard
                    stats={dashboardStats}
                    recentDocuments={filteredDocuments.slice(0, 5).map((doc) => ({
                      id: doc.id,
                      title: doc.title,
                      type: doc.status,
                      uploaded_at: doc.created_at,
                      uploaded_by: doc.created_by
                        ? `${doc.created_by.last_name} ${doc.created_by.first_name}`
                        : undefined,
                    }))}
                    myDocuments={filteredDocuments
                      .filter((d) => d.created_by)
                      .slice(0, 5)
                      .map((doc) => ({
                        id: doc.id,
                        title: doc.title,
                        status: doc.status,
                        uploaded_at: doc.created_at,
                      }))}
                  />
                </div>
              )}

              {/* Documents View */}
              {viewMode === "documents" && (
                <>
                  {/* Search & Filters */}
                  <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                    {showAdvancedSearch ? (
                      <AdvancedSearch
                        onSearch={(filters) => {
                          setSearch(filters.query);
                          if (filters.statuses && filters.statuses.length > 0) {
                            setStatusFilter(filters.statuses[0] as DocumentStatus);
                          }
                        }}
                        results={filteredDocuments.map((doc) => ({
                          id: doc.id,
                          title: doc.title,
                          description: doc.description || "",
                          type: doc.status,
                          status: doc.status,
                          uploaded_at: doc.created_at,
                          uploaded_by: doc.created_by
                            ? `${doc.created_by.last_name} ${doc.created_by.first_name}`
                            : undefined,
                        }))}
                        availableStatuses={[
                          { id: "draft", name: "Черновик" },
                          { id: "in_review", name: "На рассмотрении" },
                          { id: "approved", name: "Утверждено" },
                          { id: "published", name: "Опубликовано" },
                          { id: "archived", name: "В архиве" },
                          { id: "rejected", name: "Отклонено" },
                        ]}
                      />
                  ) : (
                    /* Simple Filters */
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <div className="relative flex-1">
                        <Search
                          size={16}
                          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                        />
                        <input
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          placeholder="Поиск по документам"
                          className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                        />
                      </div>

                      <select
                        value={statusFilter}
                        onChange={(e) =>
                          setStatusFilter(e.target.value as DocumentStatus | "all")
                        }
                        className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                      >
                        <option value="all">Все статусы</option>
                        <option value="draft">Черновик</option>
                        <option value="in_review">На рассмотрении</option>
                        <option value="approved">Утверждено</option>
                        <option value="published">Опубликовано</option>
                        <option value="archived">В архиве</option>
                        <option value="rejected">Отклонено</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Bulk Actions Toolbar */}
                {selection.selectedIds.length > 0 && (
                  <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                    <BulkActionsToolbar
                      selectedIds={selection.selectedIds}
                      documents={filteredDocuments.map((d) => ({
                        id: d.id,
                        title: d.title,
                        status: d.status,
                      }))}
                      onClearSelection={selection.clearSelection}
                    />
                  </div>
                )}

                {/* Breadcrumbs */}
                {breadcrumbs.length > 0 && (
                  <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-4 py-2 text-sm">
                    <FolderOpen size={14} className="text-gray-500" />
                    <nav className="flex items-center gap-1">
                      <button
                        onClick={() => setSelectedFolderId(null)}
                        className="text-gray-600 hover:text-sky-600"
                      >
                        Все документы
                      </button>
                      {breadcrumbs.map((crumb, index) => (
                        <span key={index} className="flex items-center gap-1">
                          <span className="text-gray-400">/</span>
                          <span className={index === breadcrumbs.length - 1 ? "font-medium text-gray-900" : "text-gray-600"}>
                            {crumb}
                          </span>
                        </span>
                      ))}
                    </nav>
                  </div>
                )}

                {/* Documents List */}
                <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                  <div className="space-y-3">
                    {filteredDocuments.length === 0 ? (
                      <div className="rounded-xl bg-gray-50 p-8 text-center">
                        <FileText size={22} className="mx-auto mb-2 text-gray-400" />
                        <p className="text-sm text-gray-500">Документы не найдены</p>
                      </div>
                    ) : (
                      <>
                        {/* Select All */}
                        {filteredDocuments.length > 0 && (
                          <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
                            <input
                              type="checkbox"
                              checked={selection.isAllSelected}
                              onChange={selection.toggleAll}
                              className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                            />
                            <span className="text-sm text-gray-700">
                              Выбрать все ({filteredDocuments.length})
                            </span>
                          </div>
                        )}

                        {/* Document Cards */}
                        {filteredDocuments.map((doc) => {
                          const authorName = doc.created_by
                            ? `${doc.created_by.last_name} ${doc.created_by.first_name}`.trim()
                            : "Неизвестно";
                          const isSelected = selection.isSelected(doc.id);

                          return (
                            <article
                              key={doc.id}
                              className={`rounded-xl border p-4 transition ${
                                isSelected
                                  ? "border-sky-300 bg-sky-50"
                                  : "border-gray-100 bg-white hover:bg-gray-50"
                              }`}
                            >
                              <div className="flex items-start gap-3">
                                {/* Checkbox */}
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => selection.toggleDocument(doc.id)}
                                  className="mt-1 h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                                />

                                <div className="min-w-0 flex-1">
                                  <div className="mb-2 flex flex-wrap items-center gap-2">
                                    <p className="text-sm font-semibold text-gray-900">
                                      {doc.title}
                                    </p>
                                    <DocumentStatusBadge
                                      status={doc.status}
                                      statusCode={doc.status_code}
                                    />
                                    {/* Acknowledgement Badge */}
                                    {doc.acknowledgement_required && (
                                      doc.is_acknowledged ? (
                                        <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700 ring-1 ring-green-600/20">
                                          <CheckCircle size={12} />
                                          Ознакомлен
                                        </span>
                                      ) : (
                                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-600/20">
                                          <AlertCircle size={12} />
                                          Требуется ознакомление
                                        </span>
                                      )
                                    )}
                                  </div>

                                  <p className="mb-3 text-sm text-gray-700">
                                    {doc.description || "Описание не заполнено"}
                                  </p>

                                  {/* Workflow Buttons */}
                                  <div className="mb-3">
                                    <DocumentWorkflowButtons
                                      documentId={doc.id}
                                      currentStatus={doc.status_code}
                                      onStatusChange={loadDocuments}
                                    />
                                  </div>

                                  <div className="grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
                                    {doc.folder_path && (
                                      <p className="flex items-center gap-1 text-sky-600">
                                        <FolderOpen size={12} />
                                        {doc.folder_path}
                                      </p>
                                    )}
                                    <p>Автор: {authorName}</p>
                                    <p>Создано: {formatDate(doc.created_at)}</p>
                                    <p>Обновлено: {formatDate(doc.updated_at)}</p>
                                  </div>
                                </div>

                                <div className="flex shrink-0 flex-wrap gap-2">
                                  {doc.file_url && (
                                    <>
                                      {doc.file_name?.toLowerCase().endsWith(".pdf") ? (
                                        <button
                                          onClick={() =>
                                            setPdfViewerFile({
                                              url: doc.file_url!,
                                              name: doc.file_name || doc.title,
                                            })
                                          }
                                          className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700 ring-1 ring-sky-100 hover:bg-sky-100"
                                        >
                                          <Eye size={12} />
                                          PDF
                                        </button>
                                      ) : (
                                        <button
                                          onClick={() =>
                                            setPreviewFile({
                                              url: doc.file_url!,
                                              name: doc.file_name || doc.title,
                                            })
                                          }
                                          className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700 ring-1 ring-sky-100 hover:bg-sky-100"
                                        >
                                          <Eye size={12} />
                                          Просмотр
                                        </button>
                                      )}
                                    </>
                                  )}
                                  {/* Acknowledge Button - for documents requiring acknowledgement */}
                                  {doc.acknowledgement_required && !doc.is_acknowledged && (
                                    <button
                                      onClick={() => setSelectedDocument(doc)}
                                      className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-300 hover:bg-amber-200"
                                    >
                                      <CheckCircle size={12} />
                                      Ознакомиться
                                    </button>
                                  )}
                                  {/* Acknowledgements Report Button - for authors/admins */}
                                  {doc.acknowledgement_required && (
                                    <button
                                      onClick={() =>
                                        setShowAcknowledgementsReport({
                                          documentId: doc.id,
                                          documentTitle: doc.title,
                                        })
                                      }
                                      className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs text-blue-700 ring-1 ring-blue-200 hover:bg-blue-100"
                                      title="Посмотреть кто ознакомился"
                                    >
                                      Ведомость
                                    </button>
                                  )}
                                  <button
                                    onClick={() => setSelectedDocument(doc)}
                                    className="inline-flex items-center gap-1 rounded-full bg-gray-50 px-2.5 py-1 text-xs text-gray-700 ring-1 ring-gray-200 hover:bg-gray-100"
                                  >
                                    Детали
                                  </button>
                                </div>
                              </div>
                            </article>
                          );
                        })}
                      </>
                    )}
                  </div>
                </div>
              </>
              )}
            </>
          )}
        </div>
      </div>

      {/* Upload Modal */}
      <Modal
        isOpen={showUploadForm}
        onClose={() => setShowUploadForm(false)}
        title="Загрузить документ"
        size="lg"
        showFullscreenToggle
      >
        <DocumentUploadForm
          currentFolderId={selectedFolderId}
          onSuccess={() => {
            setShowUploadForm(false);
            loadDocuments();
          }}
          onCancel={() => setShowUploadForm(false)}
        />
      </Modal>

          {/* Document Details Modal */}
      <Modal
        isOpen={!!selectedDocument}
        onClose={() => setSelectedDocument(null)}
        title={selectedDocument?.title}
        size="lg"
        showFullscreenToggle
      >
        {selectedDocument && (
          <div className="space-y-6">
            {/* Status Badge */}
            <div>
              <DocumentStatusBadge
                status={selectedDocument.status}
                statusCode={selectedDocument.status_code}
              />
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-4">
              {/* Author */}
              <div className="flex items-start gap-3 rounded-lg bg-gray-50 p-3">
                <div className="rounded-full bg-sky-100 p-2">
                  <User size={16} className="text-sky-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-gray-500">Автор</p>
                  <p className="truncate text-sm font-medium text-gray-900">
                    {selectedDocument.uploaded_by
                      ? `${selectedDocument.uploaded_by.last_name} ${selectedDocument.uploaded_by.first_name}`
                      : selectedDocument.created_by
                      ? `${selectedDocument.created_by.last_name} ${selectedDocument.created_by.first_name}`
                      : "Не указан"}
                  </p>
                </div>
              </div>

              {/* Created Date */}
              <div className="flex items-start gap-3 rounded-lg bg-gray-50 p-3">
                <div className="rounded-full bg-green-100 p-2">
                  <Calendar size={16} className="text-green-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-gray-500">Дата создания</p>
                  <p className="text-sm font-medium text-gray-900">
                    {formatDate(selectedDocument.uploaded_at || selectedDocument.created_at)}
                  </p>
                </div>
              </div>

              {/* File Info */}
              {selectedDocument.file_name && (
                <div className="flex items-start gap-3 rounded-lg bg-gray-50 p-3">
                  <div className="rounded-full bg-purple-100 p-2">
                    <File size={16} className="text-purple-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-500">Файл</p>
                    <p className="truncate text-sm font-medium text-gray-900">
                      {selectedDocument.file_name}
                    </p>
                  </div>
                </div>
              )}

              {/* File Size */}
              {selectedDocument.file_size && (
                <div className="flex items-start gap-3 rounded-lg bg-gray-50 p-3">
                  <div className="rounded-full bg-orange-100 p-2">
                    <HardDrive size={16} className="text-orange-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-500">Размер</p>
                    <p className="text-sm font-medium text-gray-900">
                      {(selectedDocument.file_size / 1024 / 1024).toFixed(2)} МБ
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Folder Path */}
            {selectedDocument.folder_path && (
              <div className="rounded-lg border border-sky-200 bg-sky-50 p-3">
                <div className="flex items-center gap-2 text-sky-700">
                  <FolderOpen size={16} />
                  <span className="text-xs font-medium">Расположение</span>
                </div>
                <p className="mt-1 text-sm text-sky-900">{selectedDocument.folder_path}</p>
              </div>
            )}

            {/* Description */}
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
                <FileText size={16} />
                Описание
              </h3>
              <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-600">
                {selectedDocument.description || "Описание отсутствует"}
              </p>
            </div>

            {/* Recipients & Departments */}
            {(selectedDocument.sent_to_all ||
              (selectedDocument.recipients && selectedDocument.recipients.length > 0) ||
              (selectedDocument.departments && selectedDocument.departments.length > 0)) && (
              <div>
                <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
                  <Users size={16} />
                  Получатели
                </h3>
                <div className="space-y-2">
                  {selectedDocument.sent_to_all && (
                    <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700">
                      <CheckCircle size={14} />
                      <span className="font-medium">Отправлено всем сотрудникам</span>
                    </div>
                  )}
                  
                  {selectedDocument.departments && selectedDocument.departments.length > 0 && (
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="mb-1 flex items-center gap-2 text-xs font-medium text-gray-500">
                        <Building2 size={14} />
                        Отделы
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {selectedDocument.departments.map((dept) => (
                          <span
                            key={dept.id}
                            className="inline-flex items-center rounded-full bg-gray-200 px-2 py-0.5 text-xs text-gray-700"
                          >
                            {dept.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedDocument.recipients && selectedDocument.recipients.length > 0 && (
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="mb-1 flex items-center gap-2 text-xs font-medium text-gray-500">
                        <User size={14} />
                        Конкретные получатели ({selectedDocument.recipients.length})
                      </div>
                      <div className="max-h-32 space-y-1 overflow-y-auto">
                        {selectedDocument.recipients.slice(0, 10).map((recipient) => (
                          <div key={recipient.id} className="text-xs text-gray-700">
                            {recipient.last_name} {recipient.first_name}
                          </div>
                        ))}
                        {selectedDocument.recipients.length > 10 && (
                          <div className="text-xs text-gray-500">
                            ... и ещё {selectedDocument.recipients.length - 10}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Divider */}
            <div className="border-t border-gray-200" />

            {/* File Action */}
            {selectedDocument.file_url && (
              <div>
                <button
                  onClick={() =>
                    setPreviewFile({
                      url: selectedDocument.file_url!,
                      name: selectedDocument.file_name || selectedDocument.title,
                    })
                  }
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700"
                >
                  <Eye size={16} />
                  Открыть файл
                </button>
              </div>
            )}

            {/* Workflow Actions */}
            <div>
              <h3 className="mb-2 text-sm font-medium text-gray-700">Действия</h3>
              <DocumentWorkflowButtons
                documentId={selectedDocument.id}
                currentStatus={selectedDocument.status_code}
                onStatusChange={() => {
                  loadDocuments();
                  setSelectedDocument(null);
                }}
              />
            </div>

            {/* Acknowledgement */}
            {selectedDocument.acknowledgement_required && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-medium text-gray-700">
                    Подтверждение прочтения
                  </h3>
                  <button
                    onClick={() => {
                      setShowAcknowledgementsReport({
                        documentId: selectedDocument.id,
                        documentTitle: selectedDocument.title,
                      });
                      setSelectedDocument(null);
                    }}
                    className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 ring-1 ring-blue-200 hover:bg-blue-100"
                  >
                    Посмотреть ведомость
                  </button>
                </div>
                <DocumentAcknowledgement
                  document={selectedDocument}
                  onAcknowledge={() => {
                    loadDocuments();
                    // Refresh selected document
                    apiClient.getDocument(selectedDocument.id).then(setSelectedDocument);
                  }}
                />
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* File Preview Modal */}
      {previewFile && (
        <DocumentPreview
          fileUrl={previewFile.url}
          fileName={previewFile.name}
          onClose={() => setPreviewFile(null)}
        />
      )}

      {/* Enhanced PDF Viewer */}
      {pdfViewerFile && (
        <EnhancedPDFViewer
          fileUrl={pdfViewerFile.url}
          fileName={pdfViewerFile.name}
          onClose={() => setPdfViewerFile(null)}
        />
      )}

      {/* Create Folder Modal */}
      <Modal
        isOpen={showCreateFolder}
        onClose={() => setShowCreateFolder(false)}
        title="Создать папку"
        size="sm"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const formData = new FormData(e.currentTarget);
            const name = formData.get('name') as string;

            if (!name.trim()) {
              alert('Введите название папки');
              return;
            }

            try {
              await apiClient.createFolder({
                name: name.trim(),
                parent: selectedFolderId,
              });
              setShowCreateFolder(false);
              loadFolders();
            } catch (err) {
              console.error('Ошибка создания папки:', err);
              alert('Не удалось создать папку');
            }
          }}
          className="space-y-4"
        >
          <div>
            <label htmlFor="folderName" className="mb-1 block text-sm font-medium text-gray-700">
              Название папки
            </label>
            <input
              id="folderName"
              name="name"
              type="text"
              required
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              placeholder="Введите название..."
              autoFocus
            />
          </div>

          {selectedFolderId && (
            <div className="rounded-lg bg-sky-50 p-3">
              <p className="text-xs text-sky-700">
                <FolderOpen className="mr-1 inline" size={14} />
                Будет создана в выбранной папке
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowCreateFolder(false)}
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
            >
              Создать
            </button>
          </div>
        </form>
      </Modal>

      {/* Acknowledgements Report Modal */}
      {showAcknowledgementsReport && (
        <DocumentAcknowledgementsReport
          documentId={showAcknowledgementsReport.documentId}
          documentTitle={showAcknowledgementsReport.documentTitle}
          onClose={() => setShowAcknowledgementsReport(null)}
        />
      )}
    </AppShell>
  );
}
