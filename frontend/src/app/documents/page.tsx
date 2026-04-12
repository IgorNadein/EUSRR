"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { Suspense, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Document } from "@/types/api";
import {
  Search,
  FileText,
  Plus,
  Eye,
  X,
  FolderOpen,
  Tags,
  Filter,
  CheckCircle,
  AlertCircle,
  Calendar,
  User,
  Users,
  Download,
  ChevronDown,
} from "lucide-react";
import { DocumentAcknowledgementsReport } from "@/components/documents/DocumentAcknowledgementsReport";
import { DocumentMetadataEditor } from "@/components/documents/DocumentMetadataEditor";
import { DocumentDetailModal } from "@/components/documents/DocumentDetailModal";
import { FolderTree, type FolderNode } from "@/components/documents/folders";
import { BulkActionsToolbar, useDocumentSelection } from "@/components/documents/batch";
import { TagManagementModal } from "@/components/documents/tags";
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

function formatFileSize(value?: number): string {
  if (!value || value <= 0) return "";
  if (value < 1024) return `${value} Б`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} КБ`;
  return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} МБ`;
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<DocumentsPageFallback />}>
      <DocumentsPageContent />
    </Suspense>
  );
}

function DocumentsPageFallback() {
  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-6 text-center">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
        <p className="app-text-muted mt-3 text-sm">Загрузка документов...</p>
      </section>
    </AppShell>
  );
}

function DocumentsPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // State
  const [documents, setDocuments] = useState<Document[]>([]);
  const [folders, setFolders] = useState<FolderNode[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [availableTags, setAvailableTags] = useState<Array<{ id: number; name: string }>>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modals
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [showTagManagement, setShowTagManagement] = useState(false);
  const [showAcknowledgementsReport, setShowAcknowledgementsReport] = useState<{
    documentId: number;
    documentTitle: string;
  } | null>(null);
  const [showMetadataEditor, setShowMetadataEditor] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [previewFile, setPreviewFile] = useState<{ url: string; name: string } | null>(null);
  const [pdfViewerFile, setPdfViewerFile] = useState<{ url: string; name: string } | null>(null);
  
  // Folder dropdown
  const [showFolderDropdown, setShowFolderDropdown] = useState(false);
  
  // Bulk selection
  const selection = useDocumentSelection(documents);
  const linkedDocumentId = Number(searchParams.get("document") || "");

  const clearDocumentParam = () => {
    if (!searchParams.get("document")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("document");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  };

  const closeSelectedDocument = () => {
    setSelectedDocument(null);
    clearDocumentParam();
  };

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const params: any = {};
      if (selectedFolderId !== null) {
        params.folder_id = selectedFolderId;
      }
      console.log("📁 Загрузка документов с параметрами:", params);
      const response = await apiClient.getDocuments(params);
      console.log("📄 Получено документов:", response.results?.length || 0);
      setDocuments(response.results || response || []);
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

  const loadTags = async () => {
    try {
      const response = await apiClient.getDocumentTags();
      setAvailableTags(response.results || response || []);
    } catch (err) {
      console.error("Ошибка загрузки тегов:", err);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [selectedFolderId]);

  useEffect(() => {
    loadFolders();
    loadTags();
  }, []);

  useEffect(() => {
    if (!linkedDocumentId || selectedDocument?.id === linkedDocumentId) return;

    let cancelled = false;

    apiClient.getDocument(linkedDocumentId)
      .then((document) => {
        if (!cancelled) {
          setSelectedDocument(document);
        }
      })
      .catch((error) => {
        console.error("Ошибка deep-link документа:", error);
      });

    return () => {
      cancelled = true;
    };
  }, [linkedDocumentId, selectedDocument?.id]);

  const filteredDocuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    
    // Filter documents
    let filtered = documents.filter((doc) => {
      // Text search
      if (q) {
        const title = doc.title.toLowerCase();
        const description = (doc.description || "").toLowerCase();
        const author = doc.created_by
          ? `${doc.created_by.last_name} ${doc.created_by.first_name}`.toLowerCase()
          : "";
        if (!title.includes(q) && !description.includes(q) && !author.includes(q)) {
          return false;
        }
      }

      // Tag filter
      if (selectedTags.length > 0) {
        const docTags = (doc.tags || []).map((t: any) => t.id);
        const hasTag = selectedTags.some(tagId => docTags.includes(tagId));
        if (!hasTag) return false;
      }

      // Date from filter
      if (dateFrom) {
        const docDate = new Date(doc.created_at);
        const fromDate = new Date(dateFrom);
        if (docDate < fromDate) return false;
      }

      // Date to filter
      if (dateTo) {
        const docDate = new Date(doc.created_at);
        const toDate = new Date(dateTo);
        toDate.setHours(23, 59, 59, 999); // Include the entire day
        if (docDate > toDate) return false;
      }

      return true;
    });

    // Sort documents
    filtered.sort((a, b) => {
      let compareValue = 0;
      
      if (sortBy === "date") {
        const aTime = new Date(a.created_at).getTime() || 0;
        const bTime = new Date(b.created_at).getTime() || 0;
        compareValue = bTime - aTime;
      } else if (sortBy === "title") {
        compareValue = a.title.localeCompare(b.title, 'ru');
      }

      return sortOrder === "desc" ? compareValue : -compareValue;
    });

    return filtered;
  }, [documents, search, selectedTags, dateFrom, dateTo, sortBy, sortOrder]);

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

  const activeFilterCount = selectedTags.length + (dateFrom ? 1 : 0) + (dateTo ? 1 : 0);

  return (
    <AppShell>
      <div className="space-y-4">
        {/* Top Bar */}
        <div className="app-surface rounded-2xl p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Документы</p>
            <button
              onClick={() => setShowUploadForm(true)}
              className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium"
            >
              <Plus size={14} /> Загрузить документ
            </button>
          </div>

          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search
                size={16}
                className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по документам"
                className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${
                showFilters || activeFilterCount > 0
                  ? 'app-selected app-accent-text border-[color:var(--accent-primary)]'
                  : 'app-surface-muted app-text-muted hover:bg-[var(--surface-elevated)]'
              }`}
              title="Фильтры"
            >
              <Filter size={16} />
              {activeFilterCount > 0 && (
                <span className="app-counter absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            <div className="relative">
              <button
                onClick={() => setShowFolderDropdown(!showFolderDropdown)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  selectedFolderId
                    ? 'app-pill-active'
                    : 'app-pill'
                }`}
              >
                <FolderOpen size={14} />
                <span className="max-w-[220px] truncate">
                  {selectedFolder ? selectedFolder.name : 'Все папки'}
                </span>
                {selectedFolderId ? (
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFolderId(null);
                    }}
                    className={`rounded-full p-0.5 ${selectedFolderId ? 'hover:bg-sky-500' : 'hover:bg-gray-300'}`}
                    title="Сбросить фильтр"
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.stopPropagation();
                        setSelectedFolderId(null);
                      }
                    }}
                  >
                    <X size={12} />
                  </span>
                ) : (
                  <ChevronDown size={12} className="opacity-70" />
                )}
              </button>
              {showFolderDropdown && (
                <div className="app-menu absolute left-0 top-full z-10 mt-2 w-72 rounded-lg">
                  <div className="app-divider border-b p-2">
                    <button
                      onClick={() => {
                        setShowCreateFolder(true);
                        setShowFolderDropdown(false);
                      }}
                      className="app-link-accent flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition hover:bg-[color:var(--accent-soft)]"
                    >
                      <Plus size={16} />
                      Создать папку
                    </button>
                  </div>
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

          {/* Active Filters Tags */}
          {(selectedTags.length > 0 || dateFrom || dateTo) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedTags.map(tagId => {
                const tag = availableTags.find(t => t.id === tagId);
                return tag ? (
                  <span
                    key={tagId}
                    className="app-selected app-accent-text inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs"
                  >
                    <Tags size={12} />
                    {tag.name}
                    <button
                      onClick={() => setSelectedTags(prev => prev.filter(id => id !== tagId))}
                      className="transition hover:opacity-80"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ) : null;
              })}
              {dateFrom && (
                <span className="app-badge-accent inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs">
                  <Calendar size={12} />
                  С: {new Date(dateFrom).toLocaleDateString('ru')}
                  <button
                    onClick={() => setDateFrom('')}
                    className="transition hover:opacity-80"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}
              {dateTo && (
                <span className="app-badge-accent inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs">
                  <Calendar size={12} />
                  До: {new Date(dateTo).toLocaleDateString('ru')}
                  <button
                    onClick={() => setDateTo('')}
                    className="transition hover:opacity-80"
                  >
                    <X size={12} />
                  </button>
                </span>
              )}
              <button
                onClick={() => {
                  setSelectedTags([]);
                  setDateFrom('');
                  setDateTo('');
                }}
                className="app-badge inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs hover:bg-[var(--surface-tertiary)]"
              >
                Сбросить все
              </button>
            </div>
          )}

          {/* Filters Panel */}
          {showFilters && (
            <div className="app-surface-muted mb-3 flex flex-col gap-4 rounded-xl p-3">
              {/* Tags Filter */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-sm font-medium text-[var(--foreground)]">Теги</label>
                  <button
                    type="button"
                    onClick={() => setShowTagManagement(true)}
                    className="app-link-accent text-xs hover:underline"
                  >
                    Управление
                  </button>
                </div>
                {availableTags.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                    {availableTags.map(tag => (
                      <label
                        key={tag.id}
                        className="app-surface flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:border-[color:var(--accent-primary)] hover:bg-[color:var(--accent-soft)]"
                      >
                        <input
                          type="checkbox"
                          checked={selectedTags.includes(tag.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedTags(prev => [...prev, tag.id]);
                            } else {
                              setSelectedTags(prev => prev.filter(id => id !== tag.id));
                            }
                          }}
                          className="h-4 w-4 rounded accent-[var(--accent-primary)]"
                        />
                        <span className="truncate">{tag.name}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="app-text-muted text-sm italic">Нет доступных тегов</p>
                )}
              </div>

              {/* Date Range */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                    Дата создания (с)
                  </label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                    Дата создания (до)
                  </label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>

              {/* Sorting */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                    Сортировать по
                  </label>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as "date" | "title")}
                    className="app-select w-full rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="date">Дата создания</option>
                    <option value="title">Название</option>
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                    Порядок
                  </label>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}
                    className="app-select w-full rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="desc">По убыванию</option>
                    <option value="asc">По возрастанию</option>
                  </select>
                </div>
              </div>

              {activeFilterCount > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedTags([]);
                    setDateFrom('');
                    setDateTo('');
                  }}
                  className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium"
                >
                  Очистить фильтры
                </button>
              )}
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="space-y-4">
          {loading ? (
            <div className="app-surface rounded-2xl p-8 text-center">
              <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
              <p className="app-text-muted text-sm">Загрузка документов...</p>
            </div>
          ) : error ? (
            <div className="app-feedback-danger rounded-2xl p-6 text-center">
              <p className="text-sm">{error}</p>
            </div>
          ) : (
            <>
                {/* Bulk Actions Toolbar */}
                {selection.selectedIds.length > 0 && (
                  <div className="app-surface rounded-2xl p-4">
                    <BulkActionsToolbar
                      selectedIds={selection.selectedIds}
                      documents={filteredDocuments.map((d) => ({
                        id: d.id,
                        title: d.title,
                      }))}
                      onClearSelection={selection.clearSelection}
                    />
                  </div>
                )}

                {/* Breadcrumbs */}
                {breadcrumbs.length > 0 && (
                  <div className="app-surface-muted flex items-center gap-2 rounded-lg px-4 py-2 text-sm">
                    <FolderOpen size={14} className="app-text-muted" />
                    <nav className="flex items-center gap-1">
                      <button
                        onClick={() => setSelectedFolderId(null)}
                        className="app-link-accent"
                      >
                        Все документы
                      </button>
                      {breadcrumbs.map((crumb, index) => (
                        <span key={index} className="flex items-center gap-1">
                          <span className="app-text-muted">/</span>
                          <span className={index === breadcrumbs.length - 1 ? "font-medium text-[var(--foreground)]" : "app-text-muted"}>
                            {crumb}
                          </span>
                        </span>
                      ))}
                    </nav>
                  </div>
                )}

                {/* Documents List */}
                <div className="app-surface rounded-2xl p-4">
                  <div className="space-y-3">
                    {filteredDocuments.length === 0 ? (
                      <div className="app-surface-muted rounded-xl p-8 text-center">
                        <FileText size={22} className="app-text-muted mx-auto mb-2" />
                        <p className="app-text-muted text-sm">Документы не найдены</p>
                      </div>
                    ) : (
                      <>
                        {/* Select All */}
                        {filteredDocuments.length > 0 && (
                          <div className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2">
                            <input
                              type="checkbox"
                              checked={selection.isAllSelected}
                              onChange={selection.toggleAll}
                              className="h-4 w-4 rounded accent-[var(--accent-primary)]"
                            />
                            <span className="text-sm text-[var(--foreground)]">
                              Выбрать все ({filteredDocuments.length})
                            </span>
                          </div>
                        )}

                        {/* Document Cards */}
                        {filteredDocuments.map((doc) => {
                          const authorName = doc.created_by
                            ? `${doc.created_by.last_name || ''} ${doc.created_by.first_name || ''}`.trim()
                            : null;
                          const createdDate = formatDate(doc.created_at);
                          const isSelected = selection.isSelected(doc.id);
                          const fileSize = formatFileSize(doc.file_size);
                          const recipientsCount = doc.recipients?.length || 0;
                          const departmentsCount = doc.departments?.length || 0;
                          const hasPreview = Boolean(doc.file_url && doc.file_name?.toLowerCase().endsWith(".pdf"));

                          // DEBUG: Проверка данных документа
                          if (!authorName || !createdDate) {
                            console.log('⚠️ Документ без метаданных:', {
                              id: doc.id,
                              title: doc.title,
                              created_by: doc.created_by,
                              created_at: doc.created_at,
                              authorName,
                              createdDate
                            });
                          }

                          return (
                            <article
                              key={doc.id}
                              className={`overflow-hidden rounded-xl transition ${
                                isSelected
                                  ? "app-selected shadow-[var(--shadow-card)]"
                                  : "app-surface-muted hover:border-[var(--border-strong)]"
                              }`}
                            >
                              <div className="p-4">
                                <div className="flex items-start gap-3">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => selection.toggleDocument(doc.id)}
                                    className="mt-1 h-4 w-4 rounded accent-[var(--accent-primary)]"
                                  />

                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="min-w-0 flex-1">
                                        <div className="mb-2 flex flex-wrap items-center gap-1.5">
                                          {doc.folder_path && (
                                            <span className="app-badge inline-flex max-w-full items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium">
                                              <FolderOpen size={12} className="shrink-0" />
                                              <span className="truncate">{doc.folder_path}</span>
                                            </span>
                                          )}
                                          {doc.tags?.slice(0, 3).map((tag) => (
                                            <span
                                              key={tag.id}
                                              className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium"
                                              style={{
                                                backgroundColor: tag.color
                                                  ? `color-mix(in srgb, ${tag.color} 12%, var(--surface-primary))`
                                                  : "var(--surface-secondary)",
                                                color: tag.color || "var(--muted-foreground)",
                                                borderColor: tag.color
                                                  ? `color-mix(in srgb, ${tag.color} 28%, var(--border-subtle))`
                                                  : "var(--border-subtle)",
                                              }}
                                            >
                                              <Tags size={10} />
                                              {tag.name}
                                            </span>
                                          ))}
                                          {doc.tags && doc.tags.length > 3 && (
                                            <span className="app-badge px-2 py-0.5 text-[11px] font-medium">
                                              +{doc.tags.length - 3} тег.
                                            </span>
                                          )}
                                        </div>

                                        <button
                                          type="button"
                                          onClick={() => setSelectedDocument(doc)}
                                          className="block w-full text-left"
                                        >
                                          <h3
                                            className="truncate text-base font-semibold text-[var(--foreground)] transition hover:text-[var(--accent-primary-strong)]"
                                            title={doc.title}
                                          >
                                            {doc.title}
                                          </h3>
                                        </button>

                                        <div className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                          {authorName && (
                                            <span className="inline-flex items-center gap-1.5">
                                              <User size={13} />
                                              {authorName}
                                            </span>
                                          )}
                                          {createdDate && (
                                            <span className="inline-flex items-center gap-1.5">
                                              <Calendar size={13} />
                                              {createdDate}
                                            </span>
                                          )}
                                          {fileSize && (
                                            <span className="inline-flex items-center gap-1.5">
                                              <FileText size={13} />
                                              {fileSize}
                                            </span>
                                          )}
                                        </div>
                                      </div>

                                      <div className="shrink-0 text-right">
                                        {doc.acknowledgement_required ? (
                                          doc.is_acknowledged ? (
                                            <span className="app-feedback-success inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
                                              Ознакомлен
                                            </span>
                                          ) : (
                                            <span className="app-feedback-warning inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium">
                                              <AlertCircle size={11} />
                                              Требует ознакомления
                                            </span>
                                          )
                                        ) : (
                                          <span className="app-badge px-2.5 py-1 text-xs font-medium">
                                            Документ
                                          </span>
                                        )}
                                      </div>
                                    </div>

                                    {(doc.sent_to_all || recipientsCount > 0 || departmentsCount > 0) && (
                                      <div className="mt-3 flex flex-wrap items-center gap-1.5">
                                        {doc.sent_to_all && (
                                          <span className="app-selected-soft inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
                                            <Users size={12} />
                                            Для всей компании
                                          </span>
                                        )}
                                        {recipientsCount > 0 && (
                                          <span className="app-badge inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium">
                                            <Users size={12} />
                                            {recipientsCount} получ.
                                          </span>
                                        )}
                                        {departmentsCount > 0 && (
                                          <span className="app-badge inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium">
                                            {departmentsCount} отдел.
                                          </span>
                                        )}
                                      </div>
                                    )}

                                    {doc.description && (
                                      <p className="app-text-wrap mt-3 line-clamp-3 text-sm leading-relaxed text-[var(--foreground)]">
                                        {doc.description}
                                      </p>
                                    )}

                                    <div className={`${doc.description ? "mt-3" : "mt-2"} flex flex-wrap items-center gap-1.5`}>
                                      <button
                                        onClick={() => setSelectedDocument(doc)}
                                        className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
                                        title="Подробная информация"
                                      >
                                        <FileText size={14} className="shrink-0" />
                                        <span className="truncate">Детали</span>
                                      </button>

                                      {hasPreview && (
                                        <button
                                          onClick={() =>
                                            setPdfViewerFile({
                                              url: doc.file_url!,
                                              name: doc.file_name || doc.title,
                                            })
                                          }
                                          className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
                                          title="Открыть PDF"
                                        >
                                          <Eye size={14} className="shrink-0" />
                                          <span className="truncate">PDF</span>
                                        </button>
                                      )}

                                      {doc.file_url && (
                                        <a
                                          href={doc.file_url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
                                          title="Скачать документ"
                                        >
                                          <Download size={14} className="shrink-0" />
                                          <span className="truncate">Скачать</span>
                                        </a>
                                      )}

                                      {doc.acknowledgement_required && (
                                        <button
                                          onClick={() =>
                                            setShowAcknowledgementsReport({
                                              documentId: doc.id,
                                              documentTitle: doc.title,
                                            })
                                          }
                                          className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
                                          title="Посмотреть ведомость ознакомления"
                                        >
                                          <Users size={14} className="shrink-0" />
                                          <span className="truncate">Ведомость</span>
                                        </button>
                                      )}

                                      {doc.acknowledgement_required && !doc.is_acknowledged && (
                                        <button
                                          onClick={() => setSelectedDocument(doc)}
                                          className="app-action-primary ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
                                          title="Ознакомиться с документом"
                                        >
                                          <CheckCircle size={14} className="shrink-0" />
                                          <span className="truncate">Ознакомиться</span>
                                        </button>
                                      )}
                                    </div>
                                  </div>
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
        </div>
      </div>

      {/* Upload Modal */}
      <Modal
        isOpen={showUploadForm}
        onClose={() => setShowUploadForm(false)}
        title="Загрузить документ"
        size="lg"
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
      <DocumentDetailModal
        document={selectedDocument}
        isOpen={!!selectedDocument}
        onClose={closeSelectedDocument}
        onUpdate={() => {
          loadDocuments();
          if (selectedDocument) {
            apiClient.getDocument(selectedDocument.id).then(setSelectedDocument);
          }
        }}
        onEditMetadata={() => {
          setShowMetadataEditor(true);
        }}
        onViewReport={() => {
          if (selectedDocument) {
            setShowAcknowledgementsReport({
              documentId: selectedDocument.id,
              documentTitle: selectedDocument.title,
            });
            setSelectedDocument(null);
          }
        }}
        onNavigateToRelated={(docId) => {
          apiClient.getDocument(docId).then(setSelectedDocument);
        }}
      />

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
            <label htmlFor="folderName" className="mb-1 block text-sm font-medium text-[var(--foreground)]">
              Название папки
            </label>
            <input
              id="folderName"
              name="name"
              type="text"
              required
              className="app-input w-full rounded-lg px-3 py-2 text-sm"
              placeholder="Введите название..."
              autoFocus
            />
          </div>

          {selectedFolderId && (
            <div className="app-selected rounded-lg p-3">
              <p className="app-accent-text text-xs">
                <FolderOpen className="mr-1 inline" size={14} />
                Будет создана в выбранной папке
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowCreateFolder(false)}
              className="app-action-secondary flex-1 rounded-lg px-4 py-2 text-sm font-medium"
            >
              Отмена
            </button>
            <button
              type="submit"
              className="app-action-primary flex-1 rounded-lg px-4 py-2 text-sm font-medium"
            >
              Создать
            </button>
          </div>
        </form>
      </Modal>

      <TagManagementModal
        isOpen={showTagManagement}
        onClose={() => setShowTagManagement(false)}
        onTagsUpdated={loadTags}
      />

      {/* Document Metadata Editor */}
      {selectedDocument && (
        <DocumentMetadataEditor
          isOpen={showMetadataEditor}
          onClose={() => setShowMetadataEditor(false)}
          document={selectedDocument}
          onUpdate={() => {
            loadDocuments();
            // Refresh selected document
            apiClient.getDocument(selectedDocument.id).then(setSelectedDocument);
          }}
        />
      )}
    </AppShell>
  );
}
