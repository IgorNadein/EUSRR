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
        <div className="flex items-center justify-between border-b border-gray-200 px-3 sm:px-6 py-3 sm:py-4">
          <h3 className="truncate text-sm sm:text-lg font-semibold text-gray-900">{fileName}</h3>
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
          {fileType === 'pdf' ? (
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
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
                  <span className="ml-3 text-sm text-gray-600">Загрузка документа...</span>
                </div>
              )}
              
              {error && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
                  {error}
                  <div className="mt-2">
                    <a
                      href={fileUrl}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-red-700"
                    >
                      <Download size={14} />
                      Скачать файл
                    </a>
                  </div>
                </div>
              )}
              
              {!loading && !error && docxContent && (
                <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
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
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
                  <span className="ml-3 text-sm text-gray-600">Загрузка таблицы...</span>
                </div>
              )}
              
              {error && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
                  {error}
                  <div className="mt-2">
                    <a
                      href={fileUrl}
                      download
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-red-700"
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
                    <div className="mb-4 flex gap-2 overflow-x-auto border-b border-gray-200 pb-2">
                      {excelSheets.map((sheet, index) => (
                        <button
                          key={index}
                          onClick={() => setActiveSheet(index)}
                          className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition ${
                            activeSheet === index
                              ? 'bg-sky-100 text-sky-900'
                              : 'text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          <Table size={16} />
                          {sheet.name}
                        </button>
                      ))}
                    </div>
                  )}
                  
                  {/* Excel Table */}
                  <div className="flex-1 overflow-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                    <table className="w-full border-collapse text-sm">
                      <tbody>
                        {excelSheets[activeSheet]?.data.map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-b border-gray-200 hover:bg-gray-50">
                            {row.map((cell, cellIndex) => (
                              <td
                                key={cellIndex}
                                className="border-r border-gray-200 px-3 py-2 text-gray-900 last:border-r-0"
                              >
                                {cell !== null && cell !== undefined ? String(cell) : ''}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    
                    {excelSheets[activeSheet]?.data.length === 0 && (
                      <div className="flex items-center justify-center py-12 text-sm text-gray-500">
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
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
                  <span className="ml-3 text-sm text-gray-600">Загрузка файла...</span>
                </div>
              )}
              
              {error && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
                  {error}
                </div>
              )}
              
              {!loading && !error && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 shadow-sm">
                  <pre className="overflow-auto text-xs text-gray-900">
                    <code>{textContent}</code>
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center rounded-xl bg-gray-50 p-12">
              <div className="text-center">
                <FileText size={48} className="mx-auto mb-4 text-gray-400" />
                <p className="mb-2 text-sm font-medium text-gray-900">
                  Неизвестный тип файла
                </p>
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
        {fileType === 'pdf' && numPages > 0 && (
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
    </Modal>
  );
}
