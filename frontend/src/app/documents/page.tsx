"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import type { Document } from "@/types/api";
import {
  Search,
  FileText,
  Plus,
  Eye,
  X,
  FolderOpen,
  Tags,
  LayoutGrid,
  CheckSquare,
  SlidersHorizontal,
  CheckCircle,
  AlertCircle,
  Calendar,
  User,
  Users,
  Building2,
  Download,
  Edit,
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

export default function DocumentsPage() {
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

  return (
    <AppShell>
      <div className="space-y-4">
        {/* Top Bar */}
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            {/* Left Section: Navigation */}
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
              {/* Folder Filter */}
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
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFolderId(null);
                      }}
                      className="rounded p-0.5 hover:bg-sky-200 cursor-pointer"
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
                      <X size={14} />
                    </span>
                  )}
                </button>
                {showFolderDropdown && (
                  <div className="absolute left-0 top-full z-10 mt-2 w-72 rounded-lg border border-gray-200 bg-white shadow-lg">
                    <div className="border-b border-gray-100 p-2">
                      <button
                        onClick={() => {
                          setShowCreateFolder(true);
                          setShowFolderDropdown(false);
                        }}
                        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-sky-600 transition hover:bg-sky-50"
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

            {/* Right Section: Actions */}
            <div className="flex shrink-0">
              <button
                onClick={() => setShowUploadForm(true)}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
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
              {/* Search & Filters */}
                  <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                    {/* Search Bar */}
                    <div className="flex gap-2">
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
                      <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition ${
                          showFilters || selectedTags.length > 0 || dateFrom || dateTo
                            ? 'border-sky-500 bg-sky-50 text-sky-700'
                            : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                        title="Фильтры"
                      >
                        <SlidersHorizontal size={16} />
                        {(selectedTags.length > 0 || dateFrom || dateTo) && (
                          <span className="rounded-full bg-sky-600 px-1.5 py-0.5 text-xs text-white">
                            {selectedTags.length + (dateFrom ? 1 : 0) + (dateTo ? 1 : 0)}
                          </span>
                        )}
                      </button>
                    </div>

                    {/* Active Filters Tags */}
                    {(selectedTags.length > 0 || dateFrom || dateTo) && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedTags.map(tagId => {
                          const tag = availableTags.find(t => t.id === tagId);
                          return tag ? (
                            <span
                              key={tagId}
                              className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-3 py-1 text-xs text-sky-700"
                            >
                              <Tags size={12} />
                              {tag.name}
                              <button
                                onClick={() => setSelectedTags(prev => prev.filter(id => id !== tagId))}
                                className="hover:text-sky-900"
                              >
                                <X size={12} />
                              </button>
                            </span>
                          ) : null;
                        })}
                        {dateFrom && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-3 py-1 text-xs text-purple-700">
                            <Calendar size={12} />
                            С: {new Date(dateFrom).toLocaleDateString('ru')}
                            <button
                              onClick={() => setDateFrom('')}
                              className="hover:text-purple-900"
                            >
                              <X size={12} />
                            </button>
                          </span>
                        )}
                        {dateTo && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-3 py-1 text-xs text-purple-700">
                            <Calendar size={12} />
                            До: {new Date(dateTo).toLocaleDateString('ru')}
                            <button
                              onClick={() => setDateTo('')}
                              className="hover:text-purple-900"
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
                          className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600 hover:bg-gray-200"
                        >
                          Сбросить все
                        </button>
                      </div>
                    )}

                    {/* Filters Panel */}
                    {showFilters && (
                      <div className="mt-4 space-y-4 border-t pt-4">
                        {/* Tags Filter */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-gray-700">Теги</label>
                            <button
                              onClick={() => setShowTagManagement(true)}
                              className="text-xs text-blue-600 hover:text-blue-700 hover:underline"
                            >
                              Управление
                            </button>
                          </div>
                          {availableTags.length > 0 ? (
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                              {availableTags.map(tag => (
                                <label
                                  key={tag.id}
                                  className="flex cursor-pointer items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm transition hover:border-sky-300 hover:bg-sky-50"
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
                                    className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-2 focus:ring-sky-100"
                                  />
                                  <span className="truncate">{tag.name}</span>
                                </label>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-gray-500 italic">Нет доступных тегов</p>
                          )}
                        </div>

                        {/* Date Range */}
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-gray-700">
                              Дата создания (с)
                            </label>
                            <input
                              type="date"
                              value={dateFrom}
                              onChange={(e) => setDateFrom(e.target.value)}
                              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                            />
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-gray-700">
                              Дата создания (до)
                            </label>
                            <input
                              type="date"
                              value={dateTo}
                              onChange={(e) => setDateTo(e.target.value)}
                              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                            />
                          </div>
                        </div>

                        {/* Sorting */}
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-gray-700">
                              Сортировать по
                            </label>
                            <select
                              value={sortBy}
                              onChange={(e) => setSortBy(e.target.value as "date" | "title")}
                              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                            >
                              <option value="date">Дата создания</option>
                              <option value="title">Название</option>
                            </select>
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-gray-700">
                              Порядок
                            </label>
                            <select
                              value={sortOrder}
                              onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}
                              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                            >
                              <option value="desc">По убыванию</option>
                              <option value="asc">По возрастанию</option>
                            </select>
                          </div>
                        </div>
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
                            ? `${doc.created_by.last_name || ''} ${doc.created_by.first_name || ''}`.trim()
                            : null;
                          const createdDate = formatDate(doc.created_at);
                          const isSelected = selection.isSelected(doc.id);

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
                              className={`group rounded-xl border transition-all ${
                                isSelected
                                  ? "border-sky-300 bg-sky-50/50 shadow-sm"
                                  : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-md"
                              }`}
                            >
                              {/* Header - Checkbox + View Actions */}
                              <div className="flex items-start gap-3 border-b border-gray-100 bg-gray-50/50 px-4 py-3">
                                {/* Checkbox */}
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => selection.toggleDocument(doc.id)}
                                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                                />

                                {/* Spacer */}
                                <div className="flex-1"></div>

                                {/* View/Info Actions - Right Side with wrapping */}
                                <div className="flex flex-wrap items-center gap-1.5">
                                  {/* PDF Button - only for PDF files */}
                                  {doc.file_url && doc.file_name?.toLowerCase().endsWith(".pdf") && (
                                    <button
                                      onClick={() =>
                                        setPdfViewerFile({
                                          url: doc.file_url!,
                                          name: doc.file_name || doc.title,
                                        })
                                      }
                                      className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-700"
                                      title="Открыть PDF"
                                    >
                                      <Eye size={14} className="shrink-0" />
                                      <span className="truncate">PDF</span>
                                    </button>
                                  )}
                                  
                                  {/* Details Button */}
                                  <button
                                    onClick={() => setSelectedDocument(doc)}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
                                    title="Подробная информация"
                                  >
                                    <FileText size={14} className="shrink-0" />
                                    <span className="truncate">Детали</span>
                                  </button>
                                  
                                  {/* Acknowledgements Report */}
                                  {doc.acknowledgement_required && (
                                    <button
                                      onClick={() =>
                                        setShowAcknowledgementsReport({
                                          documentId: doc.id,
                                          documentTitle: doc.title,
                                        })
                                      }
                                      className="inline-flex items-center gap-1.5 rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition hover:bg-blue-100"
                                      title="Посмотреть кто ознакомился"
                                    >
                                      <Users size={14} className="shrink-0" />
                                      <span className="truncate">Ведомость</span>
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Body */}
                              <div className="px-4 py-3">
                                {/* Title - с обрезкой */}
                                <h3 className="mb-2 truncate text-base font-semibold text-gray-900" title={doc.title}>
                                  {doc.title}
                                </h3>

                                {/* Tags - отображаем теги документа */}
                                {doc.tags && doc.tags.length > 0 && (
                                  <div className="mb-2 flex flex-wrap items-center gap-1.5">
                                    {doc.tags.map((tag) => (
                                      <span
                                        key={tag.id}
                                        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset"
                                        style={{
                                          backgroundColor: tag.color ? `${tag.color}15` : '#f3f4f6',
                                          color: tag.color || '#6b7280',
                                          borderColor: tag.color ? `${tag.color}40` : '#e5e7eb',
                                        }}
                                      >
                                        <Tags size={10} />
                                        {tag.name}
                                      </span>
                                    ))}
                                  </div>
                                )}

                                {/* Metadata - показываем только если есть хотя бы одно значение */}
                                {(authorName || createdDate || doc.folder_path) && (
                                  <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-gray-600">
                                    {authorName && (
                                      <>
                                        <span className="inline-flex items-center gap-1.5">
                                          <User size={13} className="text-gray-400" />
                                          {authorName}
                                        </span>
                                        {(createdDate || doc.folder_path) && <span className="text-gray-300">•</span>}
                                      </>
                                    )}
                                    {createdDate && (
                                      <>
                                        <span className="inline-flex items-center gap-1.5">
                                          <Calendar size={13} className="text-gray-400" />
                                          {createdDate}
                                        </span>
                                        {doc.folder_path && <span className="text-gray-300">•</span>}
                                      </>
                                    )}
                                    {doc.folder_path && (
                                      <span className="inline-flex items-center gap-1.5">
                                        <FolderOpen size={13} className="text-sky-500" />
                                        <span className="text-sky-600">{doc.folder_path}</span>
                                      </span>
                                    )}
                                  </div>
                                )}

                                {/* Status Badges */}
                                <div className="mb-3 flex flex-wrap items-center gap-2">
                                  {doc.acknowledgement_required && (
                                    doc.is_acknowledged ? (
                                      <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-600/20">
                                        <CheckCircle size={10} />
                                        Ознакомлен
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-amber-600/20">
                                        <AlertCircle size={10} />
                                        Требуется ознакомление
                                      </span>
                                    )
                                  )}
                                </div>

                                {/* Description */}
                                {doc.description && (
                                  <p className="text-sm leading-relaxed text-gray-600">
                                    {doc.description}
                                  </p>
                                )}
                              </div>

                              {/* Footer - Workflow Actions */}
                              <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3">
                                <div className="flex flex-wrap items-center gap-2">
                                  {/* Acknowledgement Action */}
                                  {doc.acknowledgement_required && !doc.is_acknowledged && (
                                    <button
                                      onClick={() => setSelectedDocument(doc)}
                                      className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-amber-600"
                                      title="Ознакомиться с документом"
                                    >
                                      <CheckCircle size={14} className="shrink-0" />
                                      <span className="truncate">Ознакомиться</span>
                                    </button>
                                  )}
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
        onClose={() => setSelectedDocument(null)}
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

      {/* Tag Management Modal */}
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
