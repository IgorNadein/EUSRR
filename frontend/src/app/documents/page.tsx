"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import type { Document, DocumentStatus } from "@/types/api";
import { Search, FileText, Plus, Eye, X } from "lucide-react";
import { DocumentUploadForm } from "@/components/documents/DocumentUploadForm";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { DocumentWorkflowButtons } from "@/components/documents/DocumentWorkflowButtons";
import { DocumentPreview } from "@/components/documents/DocumentPreview";
import { DocumentAcknowledgement } from "@/components/documents/DocumentAcknowledgement";

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

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [previewFile, setPreviewFile] = useState<{ url: string; name: string } | null>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {};
      if (statusFilter !== "all") {
        params.status = statusFilter;
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

  useEffect(() => {
    loadDocuments();
  }, [statusFilter]);

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

  return (
    <AppShell>
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
          <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            {/* Header */}
            <div className="mb-4 flex items-center justify-between gap-3">
              <h1 className="text-xl font-semibold text-gray-900">Документы</h1>
              <button
                onClick={() => setShowUploadForm(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
              >
                <Plus size={16} />
                Загрузить документ
              </button>
            </div>

            {/* Filters */}
            <div className="mb-4 flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск по документам"
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as DocumentStatus | "all")}
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

            {/* Documents List */}
            <div className="space-y-3">
              {filteredDocuments.length === 0 ? (
                <div className="rounded-xl bg-gray-50 p-8 text-center">
                  <FileText size={22} className="mx-auto mb-2 text-gray-400" />
                  <p className="text-sm text-gray-500">Документы не найдены</p>
                </div>
              ) : (
                filteredDocuments.map((doc) => {
                  const authorName = doc.created_by
                    ? `${doc.created_by.last_name} ${doc.created_by.first_name}`.trim()
                    : "Неизвестно";

                  return (
                    <article
                      key={doc.id}
                      className="rounded-xl border border-gray-100 bg-white p-4 transition hover:bg-gray-50"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-gray-900">{doc.title}</p>
                            <DocumentStatusBadge
                              status={doc.status}
                              statusCode={doc.status_code}
                            />
                          </div>
                        </div>

                        <div className="flex shrink-0 gap-2">
                          {doc.file_url && (
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
                          <button
                            onClick={() => setSelectedDocument(doc)}
                            className="inline-flex items-center gap-1 rounded-full bg-gray-50 px-2.5 py-1 text-xs text-gray-700 ring-1 ring-gray-200 hover:bg-gray-100"
                          >
                            Детали
                          </button>
                        </div>
                      </div>

                      <p className="mt-3 text-sm text-gray-700">
                        {doc.description || "Описание не заполнено"}
                      </p>

                      {doc.tags && doc.tags.length > 0 && (
                       div className="mt-3">
                        <DocumentWorkflowButtons
                          documentId={doc.id}
                          currentStatus={doc.status_code}
                          onStatusChange={loadDocuments}
                        />
                      </div>

                      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
                        <p>Автор: {authorName}</p>
                        <p>Создано: {formatDate(doc.created_at)}</p>
                        <p>Обновлено: {formatDate(doc.updated_at)}</p>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </section>

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

                  <div>
                    <h3 className="mb-1 text-sm font-medium text-gray-700">Тип</h3>
                    <p className="text-sm text-gray-600">{selectedDocument.document_type}</p>
                  </div>

                  {selectedDocument.file_url && (
                    <div>
                      <button
                        onClick={() =>
                          setPreviewFile({
                            url: selectedDocument.file_url!,
                            name: selectedDocument.file_name || selectedDocument.title,
                          })
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
        </>
      )}
    </AppShell>
  );
}
