"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Document } from "@/types/api";
import { toast } from "sonner";
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
  CheckSquare,
  AlertCircle,
  Calendar,
  User,
  Users,
  Download,
  ChevronDown,
  ChevronRight,
  Pencil,
  Trash2,
  ScrollText,
  Loader2,
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

const DOCUMENT_PREVIEW_EXTENSIONS = new Set([
  "pdf",
  "jpg",
  "jpeg",
  "png",
  "gif",
  "webp",
  "svg",
  "bmp",
  "ico",
  "avif",
  "docx",
  "xls",
  "xlsx",
  "xlsm",
  "xlsb",
  "ods",
  "csv",
  "tsv",
  "txt",
  "text",
  "md",
  "markdown",
  "json",
  "xml",
  "html",
  "htm",
  "css",
  "scss",
  "sass",
  "less",
  "js",
  "jsx",
  "ts",
  "tsx",
  "mjs",
  "cjs",
  "yml",
  "yaml",
  "ini",
  "conf",
  "cfg",
  "log",
  "sql",
  "py",
  "java",
  "c",
  "cpp",
  "h",
  "hpp",
  "cs",
  "go",
  "rs",
  "php",
  "rb",
  "kt",
  "kts",
  "swift",
  "sh",
  "bash",
  "zsh",
  "ps1",
  "bat",
  "cmd",
  "properties",
  "env",
  "rtf",
  "mp4",
  "webm",
  "ogg",
  "ogv",
  "mov",
  "m4v",
  "mp3",
  "wav",
  "oga",
  "m4a",
  "aac",
  "flac",
]);
const DOCUMENT_PREVIEW_FILE_NAMES = new Set(["dockerfile", "makefile", "readme", "license", ".gitignore", ".env"]);

function getDocumentFileExtension(fileName?: string | null): string {
  const cleanName = (fileName || "").toLowerCase().split("?")[0].split("#")[0];
  return cleanName.match(/\.([^.]+)$/)?.[1] || "";
}

function canPreviewDocument(fileName?: string | null): boolean {
  const lowerName = (fileName || "").toLowerCase();
  const extension = getDocumentFileExtension(fileName);
  return DOCUMENT_PREVIEW_EXTENSIONS.has(extension) || DOCUMENT_PREVIEW_FILE_NAMES.has(lowerName);
}

function formatFileSize(value?: number): string {
  if (!value || value <= 0) return "";
  if (value < 1024) return `${value} Б`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} КБ`;
  return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} МБ`;
}

type DocumentTagOption = { id: number; name: string };
type PaginatedResponse<T> = { results: T[]; next?: string | null };
type DocumentSection = "folders" | "regulations";
const DOCUMENTS_PAGE_SIZE = 10000;

function isPaginatedResponse<T>(value: unknown): value is PaginatedResponse<T> {
  if (typeof value !== "object" || value === null) return false;
  return Array.isArray((value as { results?: unknown }).results);
}

async function loadAllPaginated<T>(
  fetchPage: (page: number) => Promise<unknown>
): Promise<T[]> {
  const items: T[] = [];
  let page = 1;

  while (true) {
    const response = await fetchPage(page);

    if (Array.isArray(response)) {
      return response as T[];
    }

    if (!isPaginatedResponse<T>(response)) {
      return items;
    }

    items.push(...response.results);

    if (!response.next || response.results.length === 0) {
      return items;
    }

    page += 1;
  }
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
  const [activeSection, setActiveSection] = useState<DocumentSection>("regulations");
  const [search, setSearch] = useState("");
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [availableTags, setAvailableTags] = useState<DocumentTagOption[]>([]);
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
  const [metadataDocument, setMetadataDocument] = useState<Document | null>(null);
  const [previewFile, setPreviewFile] = useState<{ url: string; name: string } | null>(null);
  const [pdfViewerFile, setPdfViewerFile] = useState<{ url: string; name: string } | null>(null);
  
  // Folder dropdown
  const [showFolderDropdown, setShowFolderDropdown] = useState(false);
  const [folderMenuOpenId, setFolderMenuOpenId] = useState<number | null>(null);
  const [documentMenuOpenId, setDocumentMenuOpenId] = useState<number | null>(null);
  const folderMenuRef = useRef<HTMLDivElement | null>(null);
  const documentMenuRef = useRef<HTMLDivElement | null>(null);
  const [createFolderParentId, setCreateFolderParentId] = useState<number | null>(null);
  const [editingFolder, setEditingFolder] = useState<FolderNode | null>(null);
  const [downloadingFolderId, setDownloadingFolderId] = useState<number | null>(null);
  const [acknowledgingDocumentId, setAcknowledgingDocumentId] = useState<number | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  
  // Bulk selection
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

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params: { folder_id?: number; is_regulation?: boolean } = {};
      if (activeSection === "regulations") {
        params.is_regulation = true;
      } else if (selectedFolderId !== null) {
        params.folder_id = selectedFolderId;
      }
      console.log("📁 Загрузка документов с параметрами:", params);
      const loadedDocuments = await loadAllPaginated<Document>((page) =>
        apiClient.getDocuments({
          ...params,
          page,
          page_size: DOCUMENTS_PAGE_SIZE,
        })
      );
      console.log("📄 Получено документов:", loadedDocuments.length);
      setDocuments(loadedDocuments);
    } catch (err) {
      console.error("Ошибка загрузки документов:", err);
      setError("Не удалось загрузить документы");
    } finally {
      setLoading(false);
    }
  }, [activeSection, selectedFolderId]);

  const loadFolders = async () => {
    try {
      const loadedFolders = await loadAllPaginated<FolderNode>((page) =>
        apiClient.getFolders({ page, page_size: DOCUMENTS_PAGE_SIZE })
      );
      setFolders(loadedFolders);
    } catch (err) {
      console.error("Ошибка загрузки папок:", err);
    }
  };

  const loadTags = async () => {
    try {
      const loadedTags = await loadAllPaginated<DocumentTagOption>((page) =>
        apiClient.getDocumentTags({ page, page_size: DOCUMENTS_PAGE_SIZE })
      );
      setAvailableTags(loadedTags);
    } catch (err) {
      console.error("Ошибка загрузки тегов:", err);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    loadFolders();
    loadTags();
  }, []);

  useEffect(() => {
    if (folderMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (folderMenuRef.current && !folderMenuRef.current.contains(event.target as Node)) {
        setFolderMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [folderMenuOpenId]);

  useEffect(() => {
    if (documentMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (documentMenuRef.current && !documentMenuRef.current.contains(event.target as Node)) {
        setDocumentMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [documentMenuOpenId]);

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
    const filtered = documents.filter((doc) => {
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
        const docTags = (doc.tags || []).map((tag) => tag.id);
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

  const selection = useDocumentSelection(filteredDocuments);

  // Find selected folder and build breadcrumb path
  const selectedFolder = useMemo(() => {
    if (activeSection !== "folders" || !selectedFolderId) return null;

    return folders.find((folder) => folder.id === selectedFolderId) || null;
  }, [activeSection, selectedFolderId, folders]);

  const breadcrumbs = useMemo(() => {
    if (!selectedFolder) return [];

    const foldersById = new Map(folders.map((folder) => [folder.id, folder]));
    const chain: FolderNode[] = [];
    const visitedIds = new Set<number>();
    let current: FolderNode | null = selectedFolder;

    while (current && !visitedIds.has(current.id)) {
      chain.push(current);
      visitedIds.add(current.id);
      current = current.parent_id !== null
        ? foldersById.get(current.parent_id) || null
        : null;
    }

    return chain.reverse();
  }, [selectedFolder, folders]);

  const childFolderCounts = useMemo(() => {
    const counts = new Map<number, number>();

    folders.forEach((folder) => {
      if (folder.parent_id !== null) {
        counts.set(folder.parent_id, (counts.get(folder.parent_id) || 0) + 1);
      }
    });

    return counts;
  }, [folders]);

  const visibleFolders = useMemo(() => {
    if (activeSection === "regulations") return [];

    const q = search.trim().toLowerCase();

    return folders
      .filter((folder) => folder.parent_id === selectedFolderId)
      .filter((folder) => {
        if (!q) return true;
        return (
          folder.name.toLowerCase().includes(q) ||
          folder.path.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  }, [activeSection, folders, search, selectedFolderId]);

  const createFolderParent = useMemo(() => {
    if (createFolderParentId === null) return null;
    return folders.find((folder) => folder.id === createFolderParentId) || null;
  }, [createFolderParentId, folders]);

  const bulkFolderOptions = useMemo(
    () => [
      { id: "__root__", name: "Без папки" },
      ...folders.map((folder) => ({
        id: String(folder.id),
        name: folder.path || folder.name,
      })),
    ],
    [folders]
  );

  const bulkTagOptions = useMemo(
    () => availableTags.map((tag) => ({
      id: String(tag.id),
      name: tag.name,
    })),
    [availableTags]
  );

  const activeFilterCount = selectedTags.length + (dateFrom ? 1 : 0) + (dateTo ? 1 : 0);

  const openCreateFolderModal = (parentId: number | null) => {
    setCreateFolderParentId(parentId);
    setShowCreateFolder(true);
  };

  const closeCreateFolderModal = () => {
    setShowCreateFolder(false);
    setCreateFolderParentId(null);
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const handleBulkMoveDocuments = async (folderId: string, documentIds: number[]) => {
    const targetFolderId = folderId === "__root__" ? null : Number(folderId);
    if (folderId !== "__root__" && Number.isNaN(targetFolderId)) return;

    for (const documentId of documentIds) {
      await apiClient.updateDocument(documentId, { folder: targetFolderId });
    }
    loadDocuments();
    loadFolders();
  };

  const handleBulkAddTags = async (tagIds: string[], documentIds: number[]) => {
    const parsedTagIds = tagIds
      .map((tagId) => Number(tagId))
      .filter((tagId) => !Number.isNaN(tagId));

    if (parsedTagIds.length === 0) return;

    for (const documentId of documentIds) {
      const documentItem = documents.find((doc) => doc.id === documentId);
      const currentTagIds = (documentItem?.tags || []).map((tag) => tag.id);
      const nextTagIds = Array.from(new Set([...currentTagIds, ...parsedTagIds]));

      await apiClient.updateDocument(documentId, { tag_ids: nextTagIds });
    }
    loadDocuments();
  };

  const handleBulkDownloadDocuments = async (documentIds: number[]) => {
    const { blob, filename } = await apiClient.downloadDocumentsArchive(documentIds);
    downloadBlob(blob, filename || "documents.zip");
  };

  const handleBulkDeleteDocuments = async (documentIds: number[]) => {
    for (const documentId of documentIds) {
      await apiClient.deleteDocument(documentId);
    }

    if (selectedDocument && documentIds.includes(selectedDocument.id)) {
      closeSelectedDocument();
    } else if (linkedDocumentId && documentIds.includes(linkedDocumentId)) {
      clearDocumentParam();
    }

    loadDocuments();
    loadFolders();
  };

  const disableSelectionMode = () => {
    selection.clearSelection();
    setSelectionMode(false);
  };

  const selectDocumentFromMenu = (documentId: number) => {
    if (!selection.isSelected(documentId)) {
      selection.toggleDocument(documentId);
    }
    setSelectionMode(true);
    setDocumentMenuOpenId(null);
  };

  const unselectDocumentFromMenu = (documentId: number) => {
    if (selection.isSelected(documentId)) {
      selection.toggleDocument(documentId);
    }
    if (selection.selectedIds.length <= 1) {
      setSelectionMode(false);
    }
    setDocumentMenuOpenId(null);
  };

  const toggleDocumentSelectionFromCheckbox = (documentId: number) => {
    const isLastSelectedDocument = selection.isSelected(documentId) && selection.selectedIds.length <= 1;
    selection.toggleDocument(documentId);

    if (isLastSelectedDocument) {
      setSelectionMode(false);
    } else {
      setSelectionMode(true);
    }
  };

  const openDocumentDetailsFromMenu = (documentItem: Document) => {
    setSelectedDocument(documentItem);
    setDocumentMenuOpenId(null);
  };

  const openDocumentMetadataFromMenu = (documentItem: Document) => {
    setMetadataDocument(documentItem);
    setShowMetadataEditor(true);
    setDocumentMenuOpenId(null);
  };

  const openDocumentReportFromMenu = (documentItem: Document) => {
    setShowAcknowledgementsReport({
      documentId: documentItem.id,
      documentTitle: documentItem.title,
    });
    setDocumentMenuOpenId(null);
  };

  const openDocumentPreviewFromMenu = (documentItem: Document) => {
    if (!documentItem.file_url) return;
    const previewFile = {
      url: documentItem.file_url,
      name: documentItem.file_name || documentItem.title,
    };
    if (getDocumentFileExtension(documentItem.file_name) === "pdf") {
      setPdfViewerFile(previewFile);
    } else {
      setPreviewFile(previewFile);
    }
    setDocumentMenuOpenId(null);
  };

  const deleteDocumentFromMenu = async (documentItem: Document) => {
    setDocumentMenuOpenId(null);

    if (!window.confirm(`Удалить документ "${documentItem.title}"?`)) return;

    try {
      await apiClient.deleteDocument(documentItem.id);

      if (selectedDocument?.id === documentItem.id) {
        closeSelectedDocument();
      } else if (linkedDocumentId === documentItem.id) {
        clearDocumentParam();
      }

      if (selection.isSelected(documentItem.id)) {
        selection.toggleDocument(documentItem.id);
        if (selection.selectedIds.length <= 1) {
          setSelectionMode(false);
        }
      }

      loadDocuments();
      loadFolders();
    } catch (err) {
      console.error("Ошибка удаления документа:", err);
      alert("Не удалось удалить документ");
    }
  };

  const handleAcknowledgeDocument = async (documentItem: Document) => {
    setAcknowledgingDocumentId(documentItem.id);
    setDocumentMenuOpenId(null);

    try {
      await apiClient.acknowledgeDocument(documentItem.id);
      setDocuments((currentDocuments) =>
        currentDocuments.map((doc) =>
          doc.id === documentItem.id ? { ...doc, is_acknowledged: true } : doc
        )
      );
      if (selectedDocument?.id === documentItem.id) {
        setSelectedDocument({ ...selectedDocument, is_acknowledged: true });
      }
      toast.success("Ознакомление подтверждено");
      loadDocuments();
    } catch (err) {
      console.error("Ошибка подтверждения ознакомления:", err);
      toast.error("Не удалось подтвердить ознакомление");
    } finally {
      setAcknowledgingDocumentId(null);
    }
  };

  const downloadFolderArchive = async (folder: FolderNode) => {
    setDownloadingFolderId(folder.id);

    try {
      const { blob, filename } = await apiClient.downloadFolderArchive(folder.id);
      downloadBlob(blob, filename || `${folder.name}.zip`);
    } catch (err) {
      console.error("Ошибка выгрузки архива папки:", err);
      alert("Не удалось выгрузить архив папки");
    } finally {
      setDownloadingFolderId(null);
    }
  };

  const deleteFolder = async (folder: FolderNode) => {
    const nestedFolderCount = childFolderCounts.get(folder.id) || 0;
    const directDocumentCount = folder.document_count || 0;
    const details = [
      directDocumentCount > 0 ? `${directDocumentCount} док.` : null,
      nestedFolderCount > 0 ? `${nestedFolderCount} подпап.` : null,
    ].filter(Boolean).join(", ");
    const message = details
      ? `Удалить папку "${folder.name}" (${details})? Будут удалены все подпапки, документы внутри них и связанные документы.`
      : `Удалить папку "${folder.name}"? Будут удалены все подпапки, документы внутри них и связанные документы.`;

    if (!window.confirm(message)) return;

    try {
      await apiClient.deleteFolder(folder.id);
      setFolderMenuOpenId(null);
      if (selectedFolderId === folder.id) {
        setSelectedFolderId(folder.parent_id);
      }
      loadFolders();
      loadDocuments();
    } catch (err) {
      console.error("Ошибка удаления папки:", err);
      alert("Не удалось удалить папку");
    }
  };

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
              <div
                className={`inline-flex items-center overflow-hidden rounded-full text-xs font-medium transition ${
                  activeSection === "folders" && selectedFolderId
                    ? 'app-pill-active'
                    : 'app-pill'
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    setActiveSection("folders");
                    setShowFolderDropdown(false);
                  }}
                  className="inline-flex min-w-0 items-center gap-1.5 py-1.5 pl-3 pr-1.5 transition hover:opacity-85"
                >
                  <FolderOpen size={14} className="shrink-0" />
                  <span className="max-w-[220px] truncate">
                    {selectedFolder ? selectedFolder.name : 'Все папки'}
                  </span>
                </button>
                {activeSection === "folders" && selectedFolderId ? (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFolderId(null);
                      setActiveSection("folders");
                    }}
                    className="flex h-7 w-6 shrink-0 items-center justify-center transition hover:bg-sky-500"
                    title="Сбросить фильтр"
                    aria-label="Сбросить фильтр папки"
                  >
                    <X size={12} />
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => {
                    setActiveSection("folders");
                    setShowFolderDropdown((prev) => !prev);
                  }}
                  className="flex h-7 w-7 shrink-0 items-center justify-center transition hover:bg-[var(--surface-tertiary)]"
                  title="Показать папки"
                  aria-label="Показать список папок"
                  aria-expanded={showFolderDropdown}
                  aria-haspopup="menu"
                >
                  <ChevronDown
                    size={12}
                    className={`opacity-70 transition-transform ${showFolderDropdown ? "rotate-180" : ""}`}
                  />
                </button>
              </div>
              {showFolderDropdown && (
                <div className="app-menu absolute left-0 top-full z-10 mt-2 w-72 rounded-lg">
                  <div className="app-divider border-b p-2">
                    <button
                      onClick={() => {
                        openCreateFolderModal(selectedFolderId);
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
                        setActiveSection("folders");
                        setSelectedFolderId(id);
                        setShowFolderDropdown(false);
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                setActiveSection("regulations");
                setSelectedFolderId(null);
                setShowFolderDropdown(false);
              }}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                activeSection === "regulations" ? "app-pill-active" : "app-pill"
              }`}
            >
              <ScrollText size={14} />
              Регламенты
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
                {selectionMode && selection.selectedIds.length > 0 && (
                  <div className="app-surface rounded-2xl p-4">
                    <BulkActionsToolbar
                      selectedIds={selection.selectedIds}
                      availableFolders={bulkFolderOptions}
                      availableTags={bulkTagOptions}
                      onMove={handleBulkMoveDocuments}
                      onAddTags={handleBulkAddTags}
                      onDownload={handleBulkDownloadDocuments}
                      onDelete={handleBulkDeleteDocuments}
                      onClearSelection={disableSelectionMode}
                    />
                  </div>
                )}

                {/* Breadcrumbs */}
                {breadcrumbs.length > 0 && (
                  <div className="app-surface-muted flex items-center gap-2 rounded-lg px-4 py-2 text-sm">
                    <FolderOpen size={14} className="app-text-muted" />
                    <nav className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          setActiveSection("folders");
                          setSelectedFolderId(null);
                        }}
                        className="app-link-accent"
                      >
                        Все документы
                      </button>
                      {breadcrumbs.map((crumb, index) => {
                        const isLast = index === breadcrumbs.length - 1;

                        return (
                          <span key={crumb.id} className="flex items-center gap-1">
                            <span className="app-text-muted">/</span>
                            {isLast ? (
                              <span className="font-medium text-[var(--foreground)]">
                                {crumb.name}
                              </span>
                            ) : (
                              <button
                                type="button"
                                onClick={() => {
                                  setActiveSection("folders");
                                  setSelectedFolderId(crumb.id);
                                }}
                                className="app-link-accent"
                              >
                                {crumb.name}
                              </button>
                            )}
                          </span>
                        );
                      })}
                    </nav>
                  </div>
                )}

                {/* Documents List */}
                <div className="app-surface rounded-2xl p-4">
                  <div className="space-y-3">
                    {visibleFolders.length === 0 && filteredDocuments.length === 0 ? (
                      <div className="app-surface-muted rounded-xl p-8 text-center">
                        {activeSection === "regulations" ? (
                          <ScrollText size={22} className="app-text-muted mx-auto mb-2" />
                        ) : (
                          <FileText size={22} className="app-text-muted mx-auto mb-2" />
                        )}
                        <p className="app-text-muted text-sm">
                          {activeSection === "regulations" ? "Регламенты не найдены" : "Документы не найдены"}
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between gap-2">
                          <p className="app-text-muted text-xs">
                            {activeSection === "regulations"
                              ? `${filteredDocuments.length} регл.`
                              : (
                                  <>
                                    {visibleFolders.length > 0 ? `${visibleFolders.length} пап.` : ""}
                                    {visibleFolders.length > 0 && filteredDocuments.length > 0 ? " · " : ""}
                                    {filteredDocuments.length > 0 ? `${filteredDocuments.length} док.` : ""}
                                  </>
                                )}
                          </p>
                        </div>

                        {/* Folder Cards */}
                        {visibleFolders.map((folder) => {
                          const nestedFolderCount = childFolderCounts.get(folder.id) || 0;
                          const directDocumentCount = folder.document_count || 0;
                          const isFolderMenuOpen = folderMenuOpenId === folder.id;
                          const isDownloadingArchive = downloadingFolderId === folder.id;

                          return (
                            <article
                              key={`folder-${folder.id}`}
                              className="app-surface-muted flex w-full items-center gap-3 rounded-xl p-4 text-left transition hover:border-[var(--accent-primary)] hover:bg-[color:var(--accent-soft)]"
                            >
                              <button
                                type="button"
                                onClick={() => setSelectedFolderId(folder.id)}
                                className="flex min-w-0 flex-1 items-center gap-3 text-left"
                              >
                                <span className="app-selected app-accent-text flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
                                  <FolderOpen size={20} />
                                </span>
                                <span className="min-w-0 flex-1">
                                  <span className="block truncate text-base font-semibold text-[var(--foreground)]">
                                    {folder.name}
                                  </span>
                                  <span className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                    {folder.path && (
                                      <span className="truncate">{folder.path}</span>
                                    )}
                                    <span>{directDocumentCount} док.</span>
                                    {nestedFolderCount > 0 && (
                                      <span>{nestedFolderCount} подпап.</span>
                                    )}
                                  </span>
                                </span>
                              </button>
                              <div
                                ref={isFolderMenuOpen ? folderMenuRef : null}
                                className="relative shrink-0"
                              >
                                <button
                                  type="button"
                                  onClick={() => setFolderMenuOpenId((prev) => (prev === folder.id ? null : folder.id))}
                                  className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                                  title="Действия с папкой"
                                  aria-label={`Действия с папкой ${folder.name}`}
                                  aria-expanded={isFolderMenuOpen}
                                  aria-haspopup="menu"
                                >
                                  <ChevronRight
                                    size={15}
                                    className={`transition-transform duration-200 ${isFolderMenuOpen ? "rotate-90" : ""}`}
                                  />
                                </button>

                                {isFolderMenuOpen ? (
                                  <div className="app-menu absolute right-0 top-full z-20 mt-2 w-52 rounded-xl py-1.5">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setFolderMenuOpenId(null);
                                        setSelectedFolderId(folder.id);
                                      }}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                    >
                                      <FolderOpen size={14} />
                                      Открыть
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setFolderMenuOpenId(null);
                                        openCreateFolderModal(folder.id);
                                      }}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                    >
                                      <Plus size={14} />
                                      Создать подпапку
                                    </button>
                                    <button
                                      type="button"
                                      disabled={isDownloadingArchive}
                                      onClick={() => {
                                        setFolderMenuOpenId(null);
                                        void downloadFolderArchive(folder);
                                      }}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                                    >
                                      <Download size={14} />
                                      {isDownloadingArchive ? "Готовим архив..." : "Выгрузить архив"}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setFolderMenuOpenId(null);
                                        setEditingFolder(folder);
                                      }}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                    >
                                      <Pencil size={14} />
                                      Переименовать
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => void deleteFolder(folder)}
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                                    >
                                      <Trash2 size={14} />
                                      Удалить
                                    </button>
                                  </div>
                                ) : null}
                              </div>
                            </article>
                          );
                        })}

                        {/* Document Cards */}
                        {filteredDocuments.map((doc) => {
                          const authorName = doc.created_by
                            ? `${doc.created_by.last_name || ''} ${doc.created_by.first_name || ''}`.trim()
                            : null;
                          const createdDate = formatDate(doc.created_at);
                          const isDocumentSelected = selection.isSelected(doc.id);
                          const isSelected = selectionMode && isDocumentSelected;
                          const isDocumentMenuOpen = documentMenuOpenId === doc.id;
                          const fileSize = formatFileSize(doc.file_size);
                          const recipientsCount = doc.recipients?.length || 0;
                          const departmentsCount = doc.departments?.length || 0;
                          const hasPreview = Boolean(doc.file_url && canPreviewDocument(doc.file_name || doc.title));
                          const isAcknowledging = acknowledgingDocumentId === doc.id;

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
                              className={`rounded-xl transition ${
                                isSelected
                                  ? "app-selected shadow-[var(--shadow-card)]"
                                  : "app-surface-muted hover:border-[var(--border-strong)]"
                              }`}
                            >
                              <div className="p-4">
                                <div className="flex items-start gap-3">
                                  {selectionMode && (
                                    <input
                                      type="checkbox"
                                      checked={isDocumentSelected}
                                      onChange={() => toggleDocumentSelectionFromCheckbox(doc.id)}
                                      className="mt-1 h-4 w-4 shrink-0 rounded accent-[var(--accent-primary)]"
                                      aria-label={`Выбрать документ ${doc.title}`}
                                    />
                                  )}

                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="min-w-0 flex-1">
                                        <div className="mb-2 flex flex-wrap items-center gap-1.5">
                                          {doc.is_regulation && (
                                            <span className="app-selected app-accent-text inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium">
                                              <ScrollText size={12} className="shrink-0" />
                                              Регламент
                                            </span>
                                          )}
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

                                      <div className="flex shrink-0 items-start gap-2">
                                        <div className="text-right">
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
                                              {doc.is_regulation ? "Регламент" : "Документ"}
                                            </span>
                                          )}
                                        </div>

                                        <div
                                          ref={isDocumentMenuOpen ? documentMenuRef : null}
                                          className="relative"
                                        >
                                          <button
                                            type="button"
                                            onClick={() => setDocumentMenuOpenId((prev) => (prev === doc.id ? null : doc.id))}
                                            className={`flex h-8 w-8 items-center justify-center rounded-md transition ${
                                              isSelected
                                                ? "app-selected app-accent-text"
                                                : "app-action-ghost"
                                            }`}
                                            title="Действия с документом"
                                            aria-label={`Действия с документом ${doc.title}`}
                                            aria-expanded={isDocumentMenuOpen}
                                            aria-haspopup="menu"
                                          >
                                            <ChevronRight
                                              size={15}
                                              className={`transition-transform duration-200 ${isDocumentMenuOpen ? "rotate-90" : ""}`}
                                            />
                                          </button>

                                          {isDocumentMenuOpen ? (
                                            <div className="app-menu absolute right-0 top-full z-20 mt-2 w-56 rounded-xl py-1.5">
                                              <button
                                                type="button"
                                                onClick={() => openDocumentDetailsFromMenu(doc)}
                                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                              >
                                                <FileText size={14} />
                                                Детали
                                              </button>

                                              <button
                                                type="button"
                                                onClick={() => openDocumentMetadataFromMenu(doc)}
                                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                              >
                                                <Pencil size={14} />
                                                Редактировать
                                              </button>

                                              <button
                                                type="button"
                                                onClick={() => openDocumentMetadataFromMenu(doc)}
                                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                              >
                                                <FolderOpen size={14} />
                                                Переместить
                                              </button>

                                              {hasPreview && (
                                                <button
                                                  type="button"
                                                  onClick={() => openDocumentPreviewFromMenu(doc)}
                                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                                >
                                                  <Eye size={14} />
                                                  Предпросмотр
                                                </button>
                                              )}

                                              {doc.file_url && (
                                                <a
                                                  href={doc.file_url}
                                                  download={doc.file_name || doc.title}
                                                  onClick={() => setDocumentMenuOpenId(null)}
                                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                                >
                                                  <Download size={14} />
                                                  Скачать
                                                </a>
                                              )}

                                              {doc.acknowledgement_required && (
                                                <button
                                                  type="button"
                                                  onClick={() => openDocumentReportFromMenu(doc)}
                                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                                >
                                                  <Users size={14} />
                                                  Ведомость
                                                </button>
                                              )}

                                              {doc.acknowledgement_required && !doc.is_acknowledged && (
                                                <button
                                                  type="button"
                                                  onClick={() => void handleAcknowledgeDocument(doc)}
                                                  disabled={isAcknowledging}
                                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                                >
                                                  {isAcknowledging ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                                                  {isAcknowledging ? "Подтверждение..." : "Ознакомиться"}
                                                </button>
                                              )}

                                              <div className="my-1 border-t border-[var(--border-subtle)]" />

                                              {isDocumentSelected ? (
                                                <button
                                                  type="button"
                                                  onClick={() => unselectDocumentFromMenu(doc.id)}
                                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                                >
                                                  <X size={14} />
                                                  Снять выбор
                                                </button>
                                              ) : (
                                                <button
                                                  type="button"
                                                  onClick={() => selectDocumentFromMenu(doc.id)}
                                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                                                >
                                                  <CheckSquare size={14} />
                                                  Выбрать
                                                </button>
                                              )}

                                              <button
                                                type="button"
                                                onClick={() => void deleteDocumentFromMenu(doc)}
                                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                                              >
                                                <Trash2 size={14} />
                                                Удалить
                                              </button>
                                            </div>
                                          ) : null}
                                        </div>
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

                                    <div className="mt-3 flex flex-wrap items-center justify-end gap-1.5">
                                      {doc.acknowledgement_required && !doc.is_acknowledged ? (
                                        <button
                                          type="button"
                                          onClick={() => void handleAcknowledgeDocument(doc)}
                                          disabled={isAcknowledging}
                                          title="Подтвердить ознакомление"
                                          className="app-action-approve inline-flex h-9 items-center justify-center gap-1.5 rounded-lg px-3 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                          {isAcknowledging ? (
                                            <Loader2 size={14} className="animate-spin" />
                                          ) : (
                                            <CheckCircle size={14} />
                                          )}
                                          <span>{isAcknowledging ? "Подтверждение..." : "Ознакомиться"}</span>
                                        </button>
                                      ) : null}

                                      {hasPreview ? (
                                        <button
                                          type="button"
                                          onClick={() => openDocumentPreviewFromMenu(doc)}
                                          title="Предпросмотр"
                                          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
                                        >
                                          <Eye size={15} />
                                        </button>
                                      ) : null}

                                      {doc.file_url ? (
                                        <a
                                          href={doc.file_url}
                                          download={doc.file_name || doc.title}
                                          title="Скачать"
                                          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
                                        >
                                          <Download size={15} />
                                        </a>
                                      ) : null}

                                      {doc.acknowledgement_required ? (
                                        <button
                                          type="button"
                                          onClick={() => openDocumentReportFromMenu(doc)}
                                          title="Ведомость ознакомления"
                                          className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
                                        >
                                          <Users size={15} />
                                        </button>
                                      ) : null}

                                      <button
                                        type="button"
                                        onClick={() => setSelectedDocument(doc)}
                                        title="Детали"
                                        className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
                                      >
                                        <FileText size={15} />
                                      </button>

                                      <button
                                        type="button"
                                        onClick={() => {
                                          setMetadataDocument(doc);
                                          setShowMetadataEditor(true);
                                        }}
                                        title="Редактировать"
                                        className="app-action-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
                                      >
                                        <Pencil size={15} />
                                      </button>
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
            loadFolders();
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
          loadFolders();
          if (selectedDocument) {
            apiClient.getDocument(selectedDocument.id).then(setSelectedDocument);
          }
        }}
        onEditMetadata={() => {
          if (selectedDocument) {
            setMetadataDocument(selectedDocument);
            setShowMetadataEditor(true);
          }
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
        onClose={closeCreateFolderModal}
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
                parent: createFolderParentId,
              });
              closeCreateFolderModal();
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

          {createFolderParent && (
            <div className="app-selected rounded-lg p-3">
              <p className="app-accent-text text-xs">
                <FolderOpen className="mr-1 inline" size={14} />
                Будет создана в папке «{createFolderParent.name}»
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={closeCreateFolderModal}
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

      <Modal
        isOpen={!!editingFolder}
        onClose={() => setEditingFolder(null)}
        title="Переименовать папку"
        size="sm"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!editingFolder) return;

            const formData = new FormData(e.currentTarget);
            const name = formData.get('name') as string;

            if (!name.trim()) {
              alert('Введите название папки');
              return;
            }

            try {
              await apiClient.updateFolder(editingFolder.id, { name: name.trim() });
              setEditingFolder(null);
              loadFolders();
            } catch (err) {
              console.error('Ошибка переименования папки:', err);
              alert('Не удалось переименовать папку');
            }
          }}
          className="space-y-4"
        >
          <div>
            <label htmlFor="editFolderName" className="mb-1 block text-sm font-medium text-[var(--foreground)]">
              Название папки
            </label>
            <input
              id="editFolderName"
              name="name"
              type="text"
              required
              defaultValue={editingFolder?.name || ""}
              className="app-input w-full rounded-lg px-3 py-2 text-sm"
              placeholder="Введите название..."
              autoFocus
            />
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setEditingFolder(null)}
              className="app-action-secondary flex-1 rounded-lg px-4 py-2 text-sm font-medium"
            >
              Отмена
            </button>
            <button
              type="submit"
              className="app-action-primary flex-1 rounded-lg px-4 py-2 text-sm font-medium"
            >
              Сохранить
            </button>
          </div>
        </form>
      </Modal>

      <TagManagementModal
        isOpen={showTagManagement}
        onClose={() => setShowTagManagement(false)}
        onTagsUpdated={loadTags}
      />

      {showAcknowledgementsReport && (
        <DocumentAcknowledgementsReport
          documentId={showAcknowledgementsReport.documentId}
          documentTitle={showAcknowledgementsReport.documentTitle}
          onClose={() => setShowAcknowledgementsReport(null)}
        />
      )}

      {/* Document Metadata Editor */}
      {metadataDocument && (
        <DocumentMetadataEditor
          isOpen={showMetadataEditor}
          onClose={() => {
            setShowMetadataEditor(false);
            setMetadataDocument(null);
          }}
          document={metadataDocument}
          onUpdate={() => {
            loadDocuments();
            loadFolders();
            if (selectedDocument?.id === metadataDocument.id) {
              apiClient.getDocument(metadataDocument.id).then(setSelectedDocument);
            }
          }}
        />
      )}
    </AppShell>
  );
}
