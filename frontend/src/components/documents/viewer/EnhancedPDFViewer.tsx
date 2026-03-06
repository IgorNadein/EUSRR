"use client";

import { useState, useCallback, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  ChevronLeft,
  ChevronRight,
  Maximize,
  Printer,
  Search,
  X,
  Sidebar,
} from "lucide-react";

// Настройка worker для react-pdf - используем worker из node_modules
if (typeof window !== 'undefined' && !pdfjs.GlobalWorkerOptions.workerSrc) {
  pdfjs.GlobalWorkerOptions.workerSrc = `/pdf.worker.min.mjs`;
}

type FitMode = "width" | "page" | "custom";

interface EnhancedPDFViewerProps {
  fileUrl: string;
  fileName?: string;
  onClose?: () => void;
}

export function EnhancedPDFViewer({ fileUrl, fileName, onClose }: EnhancedPDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [rotation, setRotation] = useState(0);
  const [fitMode, setFitMode] = useState<FitMode>("width");
  const [showSidebar, setShowSidebar] = useState(true);
  const [showSearch, setShowSearch] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [containerWidth, setContainerWidth] = useState(800);

  // Обработка успешной загрузки документа
  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setCurrentPage(1);
  }, []);

  // Навигация по страницам
  const goToPage = useCallback(
    (page: number) => {
      if (page >= 1 && page <= numPages) {
        setCurrentPage(page);
      }
    },
    [numPages]
  );

  const nextPage = useCallback(() => {
    goToPage(currentPage + 1);
  }, [currentPage, goToPage]);

  const previousPage = useCallback(() => {
    goToPage(currentPage - 1);
  }, [currentPage, goToPage]);

  // Управление масштабом
  const zoomIn = useCallback(() => {
    setScale((prev) => Math.min(prev + 0.25, 3.0));
    setFitMode("custom");
  }, []);

  const zoomOut = useCallback(() => {
    setScale((prev) => Math.max(prev - 0.25, 0.5));
    setFitMode("custom");
  }, []);

  const fitToWidth = useCallback(() => {
    setFitMode("width");
  }, []);

  const fitToPage = useCallback(() => {
    setFitMode("page");
  }, []);

  // Поворот
  const rotateClockwise = useCallback(() => {
    setRotation((prev) => (prev + 90) % 360);
  }, []);

  // Печать
  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  // Горячие клавиши
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Игнорировать, если фокус в поле ввода
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case "ArrowLeft":
          previousPage();
          break;
        case "ArrowRight":
          nextPage();
          break;
        case "+":
        case "=":
          zoomIn();
          break;
        case "-":
          zoomOut();
          break;
        case "r":
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            rotateClockwise();
          }
          break;
        case "f":
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            setShowSearch((prev) => !prev);
          }
          break;
        case "p":
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handlePrint();
          }
          break;
        case "Escape":
          setShowSearch(false);
          if (onClose) onClose();
          break;
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [currentPage, nextPage, previousPage, zoomIn, zoomOut, rotateClockwise, handlePrint, onClose]);

  // Вычисление ширины для режима fitToWidth
  const getPageWidth = useCallback(() => {
    if (fitMode === "width") {
      return containerWidth - 40; // С учетом padding
    }
    return undefined;
  }, [fitMode, containerWidth]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-gray-900">
      {/* Шапка */}
      <div className="flex items-center justify-between border-b border-gray-700 bg-gray-800 px-2 sm:px-4 py-2 sm:py-3 text-white">
        <div className="flex items-center gap-2 sm:gap-4">
          <button
            onClick={() => setShowSidebar((prev) => !prev)}
            className="rounded p-1.5 sm:p-2 hover:bg-gray-700"
            title="Боковая панель"
          >
            <Sidebar size={18} className="sm:w-5 sm:h-5" />
          </button>
          <span className="text-xs sm:text-sm font-medium truncate max-w-[150px] sm:max-w-none">{fileName || "Документ"}</span>
        </div>

        {/* Поиск */}
        {showSearch && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Поиск в документе..."
              className="rounded border border-gray-600 bg-gray-700 px-3 py-1 text-sm text-white focus:border-sky-500 focus:outline-none"
              autoFocus
            />
            <button
              onClick={() => setShowSearch(false)}
              className="rounded p-1 hover:bg-gray-700"
            >
              <X size={16} />
            </button>
          </div>
        )}

        <button
          onClick={onClose}
          className="rounded p-2 hover:bg-gray-700"
          title="Закрыть (Esc)"
        >
          <X size={20} />
        </button>
      </div>

      {/* Панель инструментов */}
      <div className="flex items-center justify-between border-b border-gray-700 bg-gray-800 px-4 py-2 text-white">
        {/* Навигация */}
        <div className="flex items-center gap-2">
          <button
            onClick={previousPage}
            disabled={currentPage <= 1}
            className="rounded p-2 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="Предыдущая страница (←)"
          >
            <ChevronLeft size={20} />
          </button>
          <span className="text-sm">
            <input
              type="number"
              value={currentPage}
              onChange={(e) => goToPage(Number(e.target.value))}
              className="w-12 rounded border border-gray-600 bg-gray-700 px-1 text-center text-sm"
              min={1}
              max={numPages}
            />{" "}
            / {numPages}
          </span>
          <button
            onClick={nextPage}
            disabled={currentPage >= numPages}
            className="rounded p-2 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="Следующая страница (→)"
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Масштаб */}
        <div className="flex items-center gap-2">
          <button
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="rounded p-2 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="Уменьшить (-)"
          >
            <ZoomOut size={20} />
          </button>
          <span className="text-sm">{Math.round(scale * 100)}%</span>
          <button
            onClick={zoomIn}
            disabled={scale >= 3.0}
            className="rounded p-2 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            title="Увеличить (+)"
          >
            <ZoomIn size={20} />
          </button>
          <button
            onClick={fitToWidth}
            className={`rounded px-3 py-1 text-xs hover:bg-gray-700 ${
              fitMode === "width" ? "bg-gray-700" : ""
            }`}
            title="По ширине"
          >
            По ширине
          </button>
          <button
            onClick={fitToPage}
            className={`rounded px-3 py-1 text-xs hover:bg-gray-700 ${
              fitMode === "page" ? "bg-gray-700" : ""
            }`}
            title="Вся страница"
          >
            Вся страница
          </button>
        </div>

        {/* Дополнительные инструменты */}
        <div className="flex items-center gap-2">
          <button
            onClick={rotateClockwise}
            className="rounded p-2 hover:bg-gray-700"
            title="Повернуть (Ctrl+R)"
          >
            <RotateCw size={20} />
          </button>
          <button
            onClick={() => setShowSearch((prev) => !prev)}
            className="rounded p-2 hover:bg-gray-700"
            title="Поиск (Ctrl+F)"
          >
            <Search size={20} />
          </button>
          <button
            onClick={handlePrint}
            className="rounded p-2 hover:bg-gray-700"
            title="Печать (Ctrl+P)"
          >
            <Printer size={20} />
          </button>
        </div>
      </div>

      {/* Основная область */}
      <div className="flex flex-1 overflow-hidden">
        {/* Боковая панель с миниатюрами */}
        {showSidebar && (
          <div className="w-48 overflow-y-auto border-r border-gray-700 bg-gray-800 p-2">
            <div className="space-y-2">
              {Array.from(new Array(numPages), (_, index) => (
                <button
                  key={`thumb_${index + 1}`}
                  onClick={() => goToPage(index + 1)}
                  className={`w-full rounded border-2 p-1 transition ${
                    currentPage === index + 1
                      ? "border-sky-500 bg-gray-700"
                      : "border-transparent hover:border-gray-600"
                  }`}
                >
                  <Document file={fileUrl} loading="">
                    <Page
                      pageNumber={index + 1}
                      width={160}
                      renderAnnotationLayer={false}
                      renderTextLayer={false}
                    />
                  </Document>
                  <p className="mt-1 text-center text-xs text-gray-400">{index + 1}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Область просмотра */}
        <div
          className="flex-1 overflow-auto bg-gray-900 p-4"
          ref={(el) => {
            if (el) {
              setContainerWidth(el.clientWidth);
            }
          }}
        >
          <div className="flex justify-center">
            <Document
              file={fileUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              loading={
                <div className="flex h-96 items-center justify-center text-white">
                  Загрузка документа...
                </div>
              }
              error={
                <div className="flex h-96 items-center justify-center text-red-400">
                  Ошибка загрузки документа
                </div>
              }
            >
              <Page
                pageNumber={currentPage}
                scale={fitMode === "custom" ? scale : undefined}
                width={getPageWidth()}
                rotate={rotation}
                renderAnnotationLayer={true}
                renderTextLayer={true}
              />
            </Document>
          </div>
        </div>
      </div>
    </div>
  );
}
