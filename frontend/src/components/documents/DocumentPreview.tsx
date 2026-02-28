"use client";

import { useState } from "react";
import { Document as PDFDocument, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface DocumentPreviewProps {
  fileUrl: string;
  fileName: string;
  onClose?: () => void;
}

export function DocumentPreview({ fileUrl, fileName, onClose }: DocumentPreviewProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isPDF = fileName.toLowerCase().endsWith('.pdf');

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setLoading(false);
  }

  function onDocumentLoadError(error: Error) {
    console.error('Error loading PDF:', error);
    setError('Не удалось загрузить PDF файл');
    setLoading(false);
  }

  const goToPrevPage = () => setPageNumber((prev) => Math.max(prev - 1, 1));
  const goToNextPage = () => setPageNumber((prev) => Math.min(prev + 1, numPages));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="relative flex h-full max-h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h3 className="truncate text-lg font-semibold text-gray-900">{fileName}</h3>
          <div className="flex items-center gap-2">
            <a
              href={fileUrl}
              download
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100"
              title="Скачать"
            >
              <Download size={20} />
            </a>
            {onClose && (
              <button
                onClick={onClose}
                className="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100"
                title="Закрыть"
              >
                <X size={20} />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {isPDF ? (
            <div className="flex flex-col items-center">
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
                </div>
              )}
              
              {error && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
                  {error}
                </div>
              )}

              <PDFDocument
                file={fileUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                loading={null}
              >
                <Page
                  pageNumber={pageNumber}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  className="shadow-lg"
                />
              </PDFDocument>
            </div>
          ) : (
            <div className="flex items-center justify-center rounded-xl bg-gray-50 p-12">
              <div className="text-center">
                <p className="mb-4 text-sm text-gray-600">
                  Предпросмотр недоступен для этого типа файла
                </p>
                <a
                  href={fileUrl}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
                >
                  <Download size={16} />
                  Скачать файл
                </a>
              </div>
            </div>
          )}
        </div>

        {/* PDF Navigation */}
        {isPDF && numPages > 0 && (
          <div className="flex items-center justify-between border-t border-gray-200 px-6 py-4">
            <button
              onClick={goToPrevPage}
              disabled={pageNumber <= 1}
              className="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft size={20} />
            </button>

            <span className="text-sm text-gray-600">
              Страница {pageNumber} из {numPages}
            </span>

            <button
              onClick={goToNextPage}
              disabled={pageNumber >= numPages}
              className="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
