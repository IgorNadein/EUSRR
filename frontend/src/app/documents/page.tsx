"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
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
} from "lucide-react";
import { DocumentUploadForm } from "@/components/documents/DocumentUploadForm";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { DocumentWorkflowButtons } from "@/components/documents/DocumentWorkflowButtons";
import { DocumentPreview } from "@/components/documents/DocumentPreview";
import { DocumentAcknowledgement } from "@/components/documents/DocumentAcknowledgement";
import { FolderTree, type FolderNode } from "@/components/documents/folders";
import { EnhancedPDFViewer } from "@/components/documents/viewer";
import { AdvancedSearch } from "@/components/documents/search";
import { BulkActionsToolbar, useDocumentSelection } from "@/components/documents/batch";
import { DocumentsDashboard } from "@/components/documents/dashboard";

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
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [previewFile, setPreviewFile] = useState<{ url: string; name: string } | null>(null);
  const [pdfViewerFile, setPdfViewerFile] = useState<{ url: string; name: string } | null>(null);
  
  // Sidebar
  const [showSidebar, setShowSidebar] = useState(true);
  
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
      const response = await apiClient.getDocuments(params);
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
      // TODO: Implement folders API endpoint
      // const response = await apiClient.getFolders();
      // setFolders(response.results || []);
      setFolders([]);
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
      <div className="flex h-full gap-4">
        {/* Sidebar */}
        {showSidebar && (
          <aside className="w-64 shrink-0 space-y-4">
            {/* Folders Section */}
            <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <FolderOpen size={16} />
                  Папки
                </h2>
              </div>
              <FolderTree
                folders={folders}
                selectedFolderId={selectedFolderId}
                onSelectFolder={setSelectedFolderId}
              />
            </section>

            {/* Quick Actions */}
            <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
              <h2 className="mb-3 text-sm font-semibold text-gray-900">Быстрое</h2>
              <div className="space-y-1">
                <button
                  onClick={() => setViewMode("documents")}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                    viewMode === "documents"
                      ? "bg-sky-100 text-sky-900"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <FileText size={16} />
                  Документы
                </button>
                <button
                  onClick={() => setViewMode("dashboard")}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                    viewMode === "dashboard"
                      ? "bg-sky-100 text-sky-900"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <LayoutDashboard size={16} />
                  Дашборд
                </button>
              </div>
            </section>
          </aside>
        )}

        {/* Main Content */}
        <div className="min-w-0 flex-1 space-y-4">
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
                <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-100">
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
                </section>
              )}

              {/* Documents View */}
              {viewMode === "documents" && (
                <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                  {/* Header */}
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setShowSidebar(!showSidebar)}
                        className="rounded-lg p-2 text-gray-600 hover:bg-gray-100"
                        title={showSidebar ? "Скрыть боковую панель" : "Показать боковую панель"}
                      >
                        <LayoutGrid size={20} />
                      </button>
                      <h1 className="text-xl font-semibold text-gray-900">
                        {selectedFolderId ? "Документы в папке" : "Все документы"}
                      </h1>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setShowAdvancedSearch(!showAdvancedSearch)}
                        className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
                      >
                        <SlidersHorizontal size={16} />
                        {showAdvancedSearch ? "Простой поиск" : "Расширенный"}
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

                  {/* Advanced Search */}
                  {showAdvancedSearch ? (
                    <div className="mb-4">
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
                    </div>
                  ) : (
                    /* Simple Filters */
                    <div className="mb-4 flex flex-col gap-3 sm:flex-row">
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

                  {/* Bulk Actions Toolbar */}
                  {selection.selectedIds.length > 0 && (
                    <div className="mb-4">
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
                  {/* Bulk Actions Toolbar */}
                  {selection.selectedIds.length > 0 && (
                    <div className="mb-4">
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

                  {/* Documents List */}
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
                                    <p>Автор: {authorName}</p>
                                    <p>Создано: {formatDate(doc.created_at)}</p>
                                    <p>Обновлено: {formatDate(doc.updated_at)}</p>
                                  </div>
                                </div>

                                <div className="flex shrink-0 gap-2">
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
                </section>
              )}
            </>
          )}
        </div>
      </div>

          {/* Upload Modal */}
          {showUploadForm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
              <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-900">Загрузить документ</h2>
                  <button
                    onClick={() => setShowUploadForm(false)}
                    className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  >
                    <X size={20} />
                  </button>
                </div>
                <DocumentUploadForm
                  onSuccess={() => {
                    setShowUploadForm(false);
                    loadDocuments();
                  }}
                  onCancel={() => setShowUploadForm(false)}
                />
              </div>
            </div>
          )}

          {/* Document Details Modal */}
          {selectedDocument && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
              <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-900">
                    {selectedDocument.title}
                  </h2>
                  <button
                    onClick={() => setSelectedDocument(null)}
                    className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  >
                    <X size={20} />
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <DocumentStatusBadge
                      status={selectedDocument.status}
                      statusCode={selectedDocument.status_code}
                    />
                  </div>

                  <div>
                    <h3 className="mb-1 text-sm font-medium text-gray-700">Описание</h3>
                    <p className="text-sm text-gray-600">
                      {selectedDocument.description || "Описание отсутствует"}
                    </p>
                  </div>

                  {selectedDocument.file_url && (
                    <div>
                      <button
                        onClick={() =>
                          setPreviewFile({
                            url: selectedDocument.file_url!,
                            name: selectedDocument.file_name || selectedDocument.title,
                          })
                        }
                        className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
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
                      <h3 className="mb-2 text-sm font-medium text-gray-700">
                        Подтверждение прочтения
                      </h3>
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
              </div>
            </div>
          )}

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
    </AppShell>
  );
}
