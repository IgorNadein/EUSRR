/**
 * Client-side PDF utilities
 * Извлечение текста, операции с PDF (split, merge, rotate)
 */

import * as pdfjsLib from 'pdfjs-dist';
import { PDFDocument, degrees } from 'pdf-lib';

// Настройка worker для PDF.js
pdfjsLib.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

export interface PDFTextExtractionProgress {
  currentPage: number;
  totalPages: number;
  progress: number;
}

/**
 * Извлекает текст из PDF файла
 * 
 * @param file - PDF файл
 * @param onProgress - Callback прогресса
 * @returns Извлеченный текст
 */
export async function extractPDFText(
  file: File,
  onProgress?: (progress: PDFTextExtractionProgress) => void
): Promise<string> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    const totalPages = pdf.numPages;
    
    let fullText = '';

    for (let i = 1; i <= totalPages; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();
      const pageText = textContent.items
        .map((item: any) => item.str)
        .join(' ');
      
      fullText += pageText + '\n\n';

      if (onProgress) {
        onProgress({
          currentPage: i,
          totalPages,
          progress: (i / totalPages) * 100
        });
      }
    }

    return fullText.trim();
  } catch (error) {
    console.error('[PDF] Text extraction error:', error);
    throw new Error('Ошибка извлечения текста из PDF');
  }
}

/**
 * Генерирует thumbnail первой страницы PDF
 * 
 * @param file - PDF файл
 * @param scale - Масштаб (по умолчанию 0.5)
 * @returns Data URL изображения
 */
export async function generatePDFThumbnail(
  file: File,
  scale: number = 0.5
): Promise<string> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    const page = await pdf.getPage(1);

    const viewport = page.getViewport({ scale });
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d')!;

    canvas.width = viewport.width;
    canvas.height = viewport.height;

    await page.render({
      canvasContext: context,
      viewport
    }).promise;

    return canvas.toDataURL('image/jpeg', 0.7);
  } catch (error) {
    console.error('[PDF] Thumbnail generation error:', error);
    throw new Error('Ошибка создания превью PDF');
  }
}

/**
 * Разделяет PDF файл на отдельные страницы
 * 
 * @param file - PDF файл
 * @param pageNumbers - Номера страниц для извлечения (1-based)
 * @returns Новый PDF как Uint8Array
 */
export async function splitPDF(
  file: File,
  pageNumbers: number[]
): Promise<Uint8Array> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdfDoc = await PDFDocument.load(arrayBuffer);
    const newPdf = await PDFDocument.create();

    for (const pageNum of pageNumbers) {
      const [page] = await newPdf.copyPages(pdfDoc, [pageNum - 1]);
      newPdf.addPage(page);
    }

    return await newPdf.save();
  } catch (error) {
    console.error('[PDF] Split error:', error);
    throw new Error('Ошибка разделения PDF');
  }
}

/**
 * Объединяет несколько PDF файлов
 * 
 * @param files - Массив PDF файлов
 * @returns Объединенный PDF как Uint8Array
 */
export async function mergePDFs(files: File[]): Promise<Uint8Array> {
  try {
    const mergedPdf = await PDFDocument.create();

    for (const file of files) {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await PDFDocument.load(arrayBuffer);
      const pages = await mergedPdf.copyPages(pdf, pdf.getPageIndices());
      pages.forEach(page => mergedPdf.addPage(page));
    }

    return await mergedPdf.save();
  } catch (error) {
    console.error('[PDF] Merge error:', error);
    throw new Error('Ошибка объединения PDF');
  }
}

/**
 * Поворачивает все страницы PDF
 * 
 * @param file - PDF файл
 * @param rotation - Угол поворота (90, 180, 270)
 * @returns Повернутый PDF как Uint8Array
 */
export async function rotatePDF(
  file: File,
  rotation: 90 | 180 | 270
): Promise<Uint8Array> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdfDoc = await PDFDocument.load(arrayBuffer);
    
    const pages = pdfDoc.getPages();
    pages.forEach(page => {
      page.setRotation(degrees(rotation));
    });

    return await pdfDoc.save();
  } catch (error) {
    console.error('[PDF] Rotate error:', error);
    throw new Error('Ошибка поворота PDF');
  }
}

/**
 * Получает информацию о PDF файле
 */
export async function getPDFInfo(file: File): Promise<{
  numPages: number;
  title?: string;
  author?: string;
  creationDate?: Date;
}> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    const metadata = await pdf.getMetadata();

    return {
      numPages: pdf.numPages,
      title: metadata.info?.Title,
      author: metadata.info?.Author,
      creationDate: metadata.info?.CreationDate
        ? new Date(metadata.info.CreationDate)
        : undefined
    };
  } catch (error) {
    console.error('[PDF] Info error:', error);
    throw new Error('Ошибка получения информации о PDF');
  }
}
