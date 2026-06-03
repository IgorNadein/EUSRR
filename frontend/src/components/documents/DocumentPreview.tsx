"use client";

import { useEffect, useMemo, useState } from "react";
import { Document as PDFDocument, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, Download, FileAudio, FileText, FileVideo, Table, X } from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Modal } from "@/components/ui";

if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
}

interface DocumentPreviewProps {
  fileUrl: string;
  fileName: string;
  onClose?: () => void;
}

interface DocumentPreviewPaneProps {
  fileUrl: string;
  fileName: string;
  className?: string;
}

interface ExcelSheet {
  name: string;
  rows: unknown[][];
}

type PreviewType = "pdf" | "image" | "word" | "spreadsheet" | "text" | "video" | "audio" | "unsupported";

const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico", "avif"]);
const WORD_EXTENSIONS = new Set(["docx"]);
const SPREADSHEET_EXTENSIONS = new Set(["xls", "xlsx", "xlsm", "xlsb", "ods", "csv", "tsv"]);
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv", "mov", "m4v"]);
const AUDIO_EXTENSIONS = new Set(["mp3", "wav", "ogg", "oga", "m4a", "aac", "flac", "webm"]);
const TEXT_EXTENSIONS = new Set([
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
]);
const TEXT_FILE_NAMES = new Set(["dockerfile", "makefile", "readme", "license", ".gitignore", ".env"]);

function getFileExtension(fileName: string): string {
  const cleanName = fileName.toLowerCase().split("?")[0].split("#")[0];
  const match = cleanName.match(/\.([^.]+)$/);
  return match?.[1] || "";
}

function getPreviewType(fileName: string): PreviewType {
  const lowerName = fileName.toLowerCase();
  const extension = getFileExtension(fileName);

  if (extension === "pdf") return "pdf";
  if (IMAGE_EXTENSIONS.has(extension)) return "image";
  if (WORD_EXTENSIONS.has(extension)) return "word";
  if (SPREADSHEET_EXTENSIONS.has(extension)) return "spreadsheet";
  if (VIDEO_EXTENSIONS.has(extension)) return "video";
  if (AUDIO_EXTENSIONS.has(extension)) return "audio";
  if (TEXT_EXTENSIONS.has(extension) || TEXT_FILE_NAMES.has(lowerName)) return "text";

  return "unsupported";
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchFile(fileUrl: string): Promise<ArrayBuffer> {
  const response = await fetch(fileUrl, {
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.arrayBuffer();
}

function decodeText(buffer: ArrayBuffer, extension: string): string {
  const decoded = new TextDecoder("utf-8").decode(buffer);
  if (extension === "json") {
    try {
      return JSON.stringify(JSON.parse(decoded), null, 2);
    } catch {
      return decoded;
    }
  }
  return decoded;
}

function sanitizeDocxHtml(html: string): string {
  if (typeof window === "undefined") return html;

  const parsed = new DOMParser().parseFromString(html, "text/html");
  parsed.querySelectorAll("script, iframe, object, embed, link, meta, style").forEach((node) => node.remove());
  parsed.querySelectorAll("*").forEach((node) => {
    Array.from(node.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith("on") || name === "style" || value.startsWith("javascript:")) {
        node.removeAttribute(attribute.name);
      }
    });
  });

  return parsed.body.innerHTML;
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex h-full min-h-[240px] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
      <span className="app-text-muted ml-3 text-sm">{label}</span>
    </div>
  );
}

function ErrorState({ message, fileUrl }: { message: string; fileUrl: string }) {
  return (
    <div className="flex h-full min-h-[240px] items-center justify-center p-6">
      <div className="app-feedback-danger max-w-md rounded-lg p-4 text-sm">
        <p>{message}</p>
        <a
          href={fileUrl}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="app-action-danger mt-3 inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium"
        >
          <Download size={14} />
          Скачать файл
        </a>
      </div>
    </div>
  );
}

function UnsupportedState({ fileUrl, fileName }: { fileUrl: string; fileName: string }) {
  const extension = getFileExtension(fileName);
  return (
    <div className="app-surface-muted flex h-full min-h-[240px] items-center justify-center p-8">
      <div className="text-center">
        <FileText size={56} className="app-text-muted mx-auto mb-4" />
        <p className="text-sm font-medium text-[var(--foreground)]">{fileName}</p>
        {extension && <p className="app-text-muted mt-1 text-xs uppercase">{extension} файл</p>}
        <p className="app-text-muted mt-3 max-w-sm text-xs">
          Для этого формата нет встроенного предпросмотра. Файл можно скачать и открыть локально.
        </p>
        <a
          href={fileUrl}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="app-action-primary mt-4 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
        >
          <Download size={16} />
          Скачать файл
        </a>
      </div>
    </div>
  );
}

export function DocumentPreviewPane({ fileUrl, fileName, className = "" }: DocumentPreviewPaneProps) {
  const previewType = getPreviewType(fileName);
  const extension = getFileExtension(fileName);
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [loading, setLoading] = useState(previewType !== "unsupported");
  const [error, setError] = useState<string | null>(null);
  const [docxContent, setDocxContent] = useState("");
  const [excelSheets, setExcelSheets] = useState<ExcelSheet[]>([]);
  const [activeSheet, setActiveSheet] = useState(0);
  const [textContent, setTextContent] = useState("");

  const pdfSource = useMemo(() => ({
    url: fileUrl,
    httpHeaders: getAuthHeaders(),
    withCredentials: true,
  }), [fileUrl]);

  useEffect(() => {
    let cancelled = false;

    setNumPages(0);
    setPageNumber(1);
    setError(null);
    setDocxContent("");
    setExcelSheets([]);
    setActiveSheet(0);
    setTextContent("");
    setLoading(["pdf", "image", "word", "spreadsheet", "text"].includes(previewType));

    async function loadDocx() {
      try {
        const arrayBuffer = await fetchFile(fileUrl);
        const mammoth = (await import("mammoth")).default;
        const result = await mammoth.convertToHtml({ arrayBuffer });
        if (!cancelled) {
          setDocxContent(sanitizeDocxHtml(result.value));
          setLoading(false);
        }
      } catch (loadError) {
        console.error("DOCX preview error:", loadError);
        if (!cancelled) {
          setError("Не удалось открыть DOCX для предпросмотра");
          setLoading(false);
        }
      }
    }

    async function loadSpreadsheet() {
      try {
        const arrayBuffer = await fetchFile(fileUrl);
        const XLSX = await import("xlsx");
        const workbook = XLSX.read(arrayBuffer, { type: "array" });
        const sheets = workbook.SheetNames.map((sheetName) => {
          const worksheet = workbook.Sheets[sheetName];
          const rows = XLSX.utils.sheet_to_json<unknown[]>(worksheet, {
            header: 1,
            defval: "",
            blankrows: false,
          }) as unknown[][];
          return { name: sheetName, rows };
        });
        if (!cancelled) {
          setExcelSheets(sheets);
          setLoading(false);
        }
      } catch (loadError) {
        console.error("Spreadsheet preview error:", loadError);
        if (!cancelled) {
          setError("Не удалось открыть таблицу для предпросмотра");
          setLoading(false);
        }
      }
    }

    async function loadText() {
      try {
        const arrayBuffer = await fetchFile(fileUrl);
        if (!cancelled) {
          setTextContent(decodeText(arrayBuffer, extension));
          setLoading(false);
        }
      } catch (loadError) {
        console.error("Text preview error:", loadError);
        if (!cancelled) {
          setError("Не удалось открыть текстовый файл");
          setLoading(false);
        }
      }
    }

    if (previewType === "word") {
      void loadDocx();
    } else if (previewType === "spreadsheet") {
      void loadSpreadsheet();
    } else if (previewType === "text") {
      void loadText();
    } else if (previewType === "video" || previewType === "audio" || previewType === "unsupported") {
      setLoading(false);
    }

    return () => {
      cancelled = true;
    };
  }, [extension, fileUrl, previewType]);

  const goToPrevPage = () => setPageNumber((prev) => Math.max(prev - 1, 1));
  const goToNextPage = () => setPageNumber((prev) => Math.min(prev + 1, numPages));

  return (
    <div className={`flex h-full min-h-0 flex-col bg-[var(--surface-secondary)] ${className}`}>
      {previewType === "pdf" && (
        <>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            {loading && <LoadingState label="Загрузка PDF..." />}
            {error && <ErrorState message={error} fileUrl={fileUrl} />}
            <div className="flex justify-center">
              <PDFDocument
                file={pdfSource}
                onLoadSuccess={({ numPages: loadedPages }) => {
                  setNumPages(loadedPages);
                  setLoading(false);
                }}
                onLoadError={(loadError) => {
                  console.error("PDF preview error:", loadError);
                  setError("Не удалось загрузить PDF файл");
                  setLoading(false);
                }}
                loading={null}
              >
                <Page
                  pageNumber={pageNumber}
                  renderAnnotationLayer
                  renderTextLayer
                  className="overflow-hidden rounded-lg shadow-lg"
                />
              </PDFDocument>
            </div>
          </div>
          {numPages > 0 && (
            <div className="app-divider flex shrink-0 items-center justify-between border-t px-4 py-3">
              <button
                onClick={goToPrevPage}
                disabled={pageNumber <= 1}
                className="app-action-secondary rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
                title="Предыдущая страница"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="app-text-muted text-sm">
                Страница {pageNumber} из {numPages}
              </span>
              <button
                onClick={goToNextPage}
                disabled={pageNumber >= numPages}
                className="app-action-secondary rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
                title="Следующая страница"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          )}
        </>
      )}

      {previewType === "image" && (
        <div className="flex h-full min-h-0 items-center justify-center overflow-auto p-4">
          {loading && <LoadingState label="Загрузка изображения..." />}
          {error && <ErrorState message={error} fileUrl={fileUrl} />}
          <img
            src={fileUrl}
            alt={fileName}
            className={`max-h-full max-w-full rounded-lg object-contain shadow-lg ${loading || error ? "hidden" : ""}`}
            onLoad={() => setLoading(false)}
            onError={() => {
              setError("Не удалось загрузить изображение");
              setLoading(false);
            }}
          />
        </div>
      )}

      {previewType === "word" && (
        <div className="h-full min-h-0 overflow-auto p-4 sm:p-6">
          {loading && <LoadingState label="Загрузка DOCX..." />}
          {error && <ErrorState message={error} fileUrl={fileUrl} />}
          {!loading && !error && (
            <article className="mx-auto min-h-full max-w-4xl rounded-lg bg-white p-6 text-sm leading-relaxed text-slate-900 shadow-lg sm:p-8">
              {docxContent ? (
                <div
                  className="max-w-none [&_a]:text-sky-700 [&_img]:max-w-full [&_li]:my-1 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:my-3 [&_strong]:font-semibold [&_table]:my-4 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-slate-300 [&_td]:p-2 [&_th]:border [&_th]:border-slate-300 [&_th]:bg-slate-100 [&_th]:p-2 [&_ul]:list-disc [&_ul]:pl-6"
                  dangerouslySetInnerHTML={{ __html: docxContent }}
                />
              ) : (
                <p className="text-slate-500">В документе нет текстового содержимого для предпросмотра.</p>
              )}
            </article>
          )}
        </div>
      )}

      {previewType === "spreadsheet" && (
        <div className="flex h-full min-h-0 flex-col p-4">
          {loading && <LoadingState label="Загрузка таблицы..." />}
          {error && <ErrorState message={error} fileUrl={fileUrl} />}
          {!loading && !error && (
            <>
              {excelSheets.length > 1 && (
                <div className="app-divider mb-3 flex shrink-0 gap-2 overflow-x-auto border-b pb-2">
                  {excelSheets.map((sheet, index) => (
                    <button
                      key={sheet.name}
                      onClick={() => setActiveSheet(index)}
                      className={`inline-flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm ${
                        activeSheet === index ? "app-pill-active" : "app-pill"
                      }`}
                    >
                      <Table size={16} />
                      {sheet.name}
                    </button>
                  ))}
                </div>
              )}
              <div className="app-surface-elevated min-h-0 flex-1 overflow-auto rounded-lg">
                {excelSheets[activeSheet]?.rows.length ? (
                  <table className="w-full border-collapse text-sm">
                    <tbody>
                      {excelSheets[activeSheet].rows.map((row, rowIndex) => (
                        <tr key={rowIndex} className="border-b border-[var(--border-subtle)]">
                          {row.map((cell, cellIndex) => (
                            <td
                              key={cellIndex}
                              className="max-w-[360px] border-r border-[var(--border-subtle)] px-3 py-2 text-[var(--foreground)] last:border-r-0"
                            >
                              <span className="block whitespace-pre-wrap break-words">
                                {cell === null || cell === undefined ? "" : String(cell)}
                              </span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="app-text-muted flex h-full min-h-[220px] items-center justify-center text-sm">
                    Таблица пуста
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {previewType === "text" && (
        <div className="h-full min-h-0 overflow-auto p-4">
          {loading && <LoadingState label="Загрузка файла..." />}
          {error && <ErrorState message={error} fileUrl={fileUrl} />}
          {!loading && !error && (
            <pre className="app-surface-elevated min-h-full overflow-auto rounded-lg p-4 text-xs leading-relaxed text-[var(--foreground)]">
              <code>{textContent}</code>
            </pre>
          )}
        </div>
      )}

      {previewType === "video" && (
        <div className="flex h-full min-h-[240px] items-center justify-center p-4">
          <div className="w-full max-w-5xl">
            <div className="mb-3 flex items-center gap-2 text-sm text-[var(--foreground)]">
              <FileVideo size={18} className="app-text-muted" />
              {fileName}
            </div>
            <video src={fileUrl} controls className="max-h-[70vh] w-full rounded-lg bg-black" />
          </div>
        </div>
      )}

      {previewType === "audio" && (
        <div className="flex h-full min-h-[240px] items-center justify-center p-8">
          <div className="app-surface-elevated w-full max-w-xl rounded-xl p-6">
            <div className="mb-4 flex items-center gap-3">
              <FileAudio size={28} className="app-text-muted" />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-[var(--foreground)]">{fileName}</p>
                <p className="app-text-muted text-xs">Аудиофайл</p>
              </div>
            </div>
            <audio src={fileUrl} controls className="w-full" />
          </div>
        </div>
      )}

      {previewType === "unsupported" && <UnsupportedState fileUrl={fileUrl} fileName={fileName} />}
    </div>
  );
}

export function DocumentPreview({ fileUrl, fileName, onClose }: DocumentPreviewProps) {
  return (
    <Modal isOpen onClose={onClose ?? (() => {})} noHeader noPadding size="xl" className="h-[90vh]">
      <div className="app-divider flex shrink-0 items-center justify-between border-b px-3 py-3 sm:px-6 sm:py-4">
        <h3 className="truncate text-sm font-semibold text-[var(--foreground)] sm:text-lg">{fileName}</h3>
        <div className="flex items-center gap-2">
          <a
            href={fileUrl}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="app-action-secondary rounded-lg p-2"
            title="Скачать"
          >
            <Download size={20} />
          </a>
          {onClose && (
            <button
              onClick={onClose}
              className="app-action-secondary rounded-lg p-2"
              title="Закрыть"
            >
              <X size={20} />
            </button>
          )}
        </div>
      </div>
      <DocumentPreviewPane fileUrl={fileUrl} fileName={fileName} className="flex-1" />
    </Modal>
  );
}
