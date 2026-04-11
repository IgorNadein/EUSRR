"use client";

import { useState, useEffect } from "react";
import { Document as PDFDocument, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, Download, X, FileText, Table } from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Modal } from "@/components/ui";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface DocumentPreviewProps {
  fileUrl: string;
  fileName: string;
  onClose?: () => void;
}

interface ExcelSheet {
  name: string;
  data: any[][];
}

function getFileType(fileName: string): 'pdf' | 'image' | 'word' | 'excel' | 'text' | 'unknown' {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  
  if (ext === 'pdf') return 'pdf';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) return 'image';
  if (['doc', 'docx'].includes(ext)) return 'word';
  if (['xls', 'xlsx'].includes(ext)) return 'excel';
  if (['txt', 'csv', 'json', 'xml', 'html', 'css', 'js', 'ts', 'md'].includes(ext)) return 'text';
  
  return 'unknown';
}

export function DocumentPreview({ fileUrl, fileName, onClose }: DocumentPreviewProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docxContent, setDocxContent] = useState<string>('');
  const [excelSheets, setExcelSheets] = useState<ExcelSheet[]>([]);
  const [activeSheet, setActiveSheet] = useState<number>(0);
  const [textContent, setTextContent] = useState<string>('');

  const fileType = getFileType(fileName);
  
  // Конвертируем DOCX в HTML на клиенте
  useEffect(() => {
    if (fileType === 'word' && fileName.toLowerCase().endsWith('.docx')) {
      setLoading(true);
      
      fetch(fileUrl, {
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
      })
        .then(response => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.arrayBuffer();
        })
        .then(async (arrayBuffer) => {
          try {
            const mammoth = (await import('mammoth')).default;
            const result = await mammoth.convertToHtml({ arrayBuffer });
            setDocxContent(result.value);
            setLoading(false);
          } catch (err) {
            console.error('Ошибка конвертации DOCX:', err);
            setError('Не удалось загрузить документ');
            setLoading(false);
          }
        })
        .catch(err => {
          console.error('Ошибка загрузки файла:', err);
          setError('Не удалось загрузить файл');
          setLoading(false);
        });
    }
  }, [fileUrl, fileName, fileType]);
  
  // Парсим Excel файлы локально
  useEffect(() => {
    if (fileType === 'excel') {
      setLoading(true);
      
      fetch(fileUrl, {
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
      })
        .then(response => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.arrayBuffer();
        })
        .then(async (arrayBuffer) => {
          try {
            const XLSX = (await import('xlsx')).default;
            const workbook = XLSX.read(arrayBuffer, { type: 'array' });
            
            const sheets: ExcelSheet[] = workbook.SheetNames.map(sheetName => {
              const worksheet = workbook.Sheets[sheetName];
              const data = XLSX.utils.sheet_to_json(worksheet, { header: 1 }) as any[][];
              return {
                name: sheetName,
                data
              };
            });
            
            setExcelSheets(sheets);
            setLoading(false);
          } catch (err) {
            console.error('Ошибка парсинга Excel:', err);
            setError('Не удалось загрузить таблицу');
            setLoading(false);
          }
        })
        .catch(err => {
          console.error('Ошибка загрузки файла:', err);
          setError('Не удалось загрузить файл');
          setLoading(false);
        });
    }
  }, [fileUrl, fileName, fileType]);
  
  // Загружаем текстовые файлы
  useEffect(() => {
    if (fileType === 'text') {
      setLoading(true);
      
      fetch(fileUrl, {
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
      })
        .then(response => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.text();
        })
        .then(text => {
          setTextContent(text);
          setLoading(false);
        })
        .catch(err => {
          console.error('Ошибка загрузки текстового файла:', err);
          setError('Не удалось загрузить файл');
          setLoading(false);
        });
    }
  }, [fileUrl, fileName, fileType]);

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
    <Modal isOpen onClose={onClose ?? (() => {})} noHeader noPadding size="xl">
        {/* Header */}
        <div className="app-divider flex items-center justify-between border-b px-3 py-3 sm:px-6 sm:py-4">
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

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {fileType === 'pdf' ? (
            <div className="flex flex-col items-center">
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
                </div>
              )}
              
              {error && (
                <div className="app-feedback-danger rounded-lg p-4 text-sm">
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
          ) : fileType === 'image' ? (
            <div className="flex items-center justify-center">
              <img 
                src={fileUrl} 
                alt={fileName}
                className="max-h-full max-w-full rounded-lg shadow-lg"
                onLoad={() => setLoading(false)}
                onError={() => setError('Не удалось загрузить изображение')}
              />
            </div>
          ) : fileType === 'word' ? (
            <div className="h-full">
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
                  <span className="app-text-muted ml-3 text-sm">Загрузка документа...</span>
                </div>
              )}
              
              {error && (
                <div className="app-feedback-danger rounded-lg p-4 text-sm">
                  {error}
                  <div className="mt-2">
                    <a
                      href={fileUrl}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="app-action-danger inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium"
                    >
                      <Download size={14} />
                      Скачать файл
                    </a>
                  </div>
                </div>
              )}
              
              {!loading && !error && docxContent && (
                <div className="app-surface rounded-lg p-8">
                  <div 
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: docxContent }}
                  />
                </div>
              )}
            </div>
          ) : fileType === 'excel' ? (
            <div className="h-full">
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
                  <span className="app-text-muted ml-3 text-sm">Загрузка таблицы...</span>
                </div>
              )}
              
              {error && (
                <div className="app-feedback-danger rounded-lg p-4 text-sm">
                  {error}
                  <div className="mt-2">
                    <a
                      href={fileUrl}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="app-action-danger inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium"
                    >
                      <Download size={14} />
                      Скачать файл
                    </a>
                  </div>
                </div>
              )}
              
              {!loading && !error && excelSheets.length > 0 && (
                <div className="flex h-full flex-col">
                  {/* Sheet Tabs */}
                  {excelSheets.length > 1 && (
                    <div className="app-divider mb-4 flex gap-2 overflow-x-auto border-b pb-2">
                      {excelSheets.map((sheet, index) => (
                        <button
                          key={index}
                          onClick={() => setActiveSheet(index)}
                          className={`flex items-center gap-2 whitespace-nowrap px-4 py-2 text-sm ${
                            activeSheet === index
                              ? 'app-pill-active'
                              : 'app-pill'
                          }`}
                        >
                          <Table size={16} />
                          {sheet.name}
                        </button>
                      ))}
                    </div>
                  )}
                  
                  {/* Excel Table */}
                  <div className="app-surface-elevated flex-1 overflow-auto rounded-lg">
                    <table className="w-full border-collapse text-sm">
                      <tbody>
                        {excelSheets[activeSheet]?.data.map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-b border-[var(--border-subtle)] hover:bg-[var(--surface-secondary)]">
                            {row.map((cell, cellIndex) => (
                              <td
                                key={cellIndex}
                                className="border-r border-[var(--border-subtle)] px-3 py-2 text-[var(--foreground)] last:border-r-0"
                              >
                                {cell !== null && cell !== undefined ? String(cell) : ''}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    
                    {excelSheets[activeSheet]?.data.length === 0 && (
                      <div className="app-text-muted flex items-center justify-center py-12 text-sm">
                        Лист пуст
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : fileType === 'text' ? (
            <div className="h-full">
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
                  <span className="app-text-muted ml-3 text-sm">Загрузка файла...</span>
                </div>
              )}
              
              {error && (
                <div className="app-feedback-danger rounded-lg p-4 text-sm">
                  {error}
                </div>
              )}
              
              {!loading && !error && (
                <div className="app-surface-muted rounded-lg p-4">
                  <pre className="overflow-auto text-xs text-[var(--foreground)]">
                    <code>{textContent}</code>
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="app-surface-muted flex items-center justify-center rounded-xl p-12">
              <div className="text-center">
                <FileText size={48} className="app-text-muted mx-auto mb-4" />
                <p className="mb-2 text-sm font-medium text-[var(--foreground)]">
                  Неизвестный тип файла
                </p>
                <p className="app-text-muted mb-4 text-sm">
                  Предпросмотр недоступен для этого типа файла
                </p>
                <a
                  href={fileUrl}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
                >
                  <Download size={16} />
                  Скачать файл
                </a>
              </div>
            </div>
          )}
        </div>

        {/* PDF Navigation */}
        {fileType === 'pdf' && numPages > 0 && (
          <div className="app-divider flex items-center justify-between border-t px-6 py-4">
            <button
              onClick={goToPrevPage}
              disabled={pageNumber <= 1}
              className="app-action-secondary rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft size={20} />
            </button>

            <span className="app-text-muted text-sm">
              Страница {pageNumber} из {numPages}
            </span>

            <button
              onClick={goToNextPage}
              disabled={pageNumber >= numPages}
              className="app-action-secondary rounded-lg p-2 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        )}
    </Modal>
  );
}
