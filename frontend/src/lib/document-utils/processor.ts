/**
 * Main document processor
 * Интеллектуальная обработка документов перед загрузкой на сервер
 */

import { performOCR, isOCRSupported } from './ocr';
import { extractPDFText, generatePDFThumbnail, getPDFInfo } from './pdf';
import { extractDOCXText, isDOCXFile } from './docx';
import { compressImage, generateImageThumbnail, isImageFile } from './image';

export interface ProcessingResult {
  extractedText: string;
  thumbnail?: string;
  processedFile?: File | Blob;
  metadata: {
    originalSize: number;
    processedSize?: number;
    mimeType: string;
    hasText: boolean;
    processingTime: number;
    ocrApplied?: boolean;
    compressed?: boolean;
  };
}

export interface ProcessingProgress {
  stage: 'compressing' | 'ocr' | 'extracting_text' | 'generating_thumbnail' | 'complete';
  progress: number;
  message: string;
}

export interface ProcessDocumentOptions {
  enableOCR?: boolean;
  enableCompression?: boolean;
  enableTextExtraction?: boolean;
  enableThumbnail?: boolean;
  maxImageSizeMB?: number;
  onProgress?: (progress: ProcessingProgress) => void;
}

/**
 * Интеллектуально обрабатывает документ перед загрузкой
 * 
 * Автоматически определяет тип файла и выполняет:
 * - Сжатие изображений
 * - OCR для изображений
 * - Извлечение текста из PDF/DOCX
 * - Генерацию thumbnails
 * 
 * @param file - Файл для обработки
 * @param options - Опции обработки
 * @returns Результат обработки
 */
export async function processDocument(
  file: File,
  options: ProcessDocumentOptions = {}
): Promise<ProcessingResult> {
  const {
    enableOCR = true,
    enableCompression = true,
    enableTextExtraction = true,
    enableThumbnail = true,
    maxImageSizeMB = 10,
    onProgress
  } = options;

  const startTime = Date.now();
  let extractedText = '';
  let thumbnail: string | undefined;
  let processedFile: File | Blob | undefined;
  let ocrApplied = false;
  let compressed = false;

  try {
    // 1. Сжатие изображений
    if (enableCompression && isImageFile(file)) {
      onProgress?.({
        stage: 'compressing',
        progress: 10,
        message: 'Сжатие изображения...'
      });

      const sizeMB = file.size / (1024 * 1024);
      if (sizeMB > maxImageSizeMB) {
        processedFile = await compressImage(file, {
          maxSizeMB: maxImageSizeMB,
          quality: 0.85
        });
        compressed = true;
      }
    }

    const fileToProcess = processedFile || file;

    // 2. Извлечение текста
    if (enableTextExtraction) {
      onProgress?.({
        stage: 'extracting_text',
        progress: 30,
        message: 'Извлечение текста...'
      });

      // PDF
      if (file.type === 'application/pdf') {
        extractedText = await extractPDFText(file, (pdfProgress) => {
          onProgress?.({
            stage: 'extracting_text',
            progress: 30 + (pdfProgress.progress * 0.3),
            message: `Обработка страницы ${pdfProgress.currentPage} из ${pdfProgress.totalPages}...`
          });
        });
      }
      // DOCX
      else if (isDOCXFile(file)) {
        extractedText = await extractDOCXText(file);
      }
      // Images с OCR
      else if (enableOCR && isOCRSupported(file)) {
        onProgress?.({
          stage: 'ocr',
          progress: 40,
          message: 'Распознавание текста (OCR)...'
        });

        extractedText = await performOCR(file, {
          languages: ['rus', 'eng'],
          onProgress: (ocrProgress) => {
            onProgress?.({
              stage: 'ocr',
              progress: 40 + ocrProgress.progress * 0.4,
              message: `OCR: ${Math.round(ocrProgress.progress)}%`
            });
          }
        });
        ocrApplied = true;
      }
    }

    // 3. Генерация thumbnail
    if (enableThumbnail) {
      onProgress?.({
        stage: 'generating_thumbnail',
        progress: 85,
        message: 'Создание превью...'
      });

      if (file.type === 'application/pdf') {
        thumbnail = await generatePDFThumbnail(file, 0.5);
      } else if (isImageFile(file)) {
        thumbnail = await generateImageThumbnail(file, 200);
      }
    }

    onProgress?.({
      stage: 'complete',
      progress: 100,
      message: 'Обработка завершена'
    });

    const processingTime = Date.now() - startTime;

    return {
      extractedText,
      thumbnail,
      processedFile,
      metadata: {
        originalSize: file.size,
        processedSize: processedFile?.size,
        mimeType: file.type,
        hasText: extractedText.length > 0,
        processingTime,
        ocrApplied,
        compressed
      }
    };
  } catch (error) {
    console.error('[DocumentProcessor] Error:', error);
    throw error;
  }
}

/**
 * Быстрая проверка: нужна ли обработка этому файлу
 */
export function needsProcessing(file: File): boolean {
  return (
    file.type === 'application/pdf' ||
    isDOCXFile(file) ||
    isImageFile(file)
  );
}

/**
 * Оценивает время обработки в секундах
 */
export function estimateProcessingTime(file: File): number {
  const sizeMB = file.size / (1024 * 1024);

  if (file.type === 'application/pdf') {
    return Math.ceil(sizeMB * 2); // ~2 сек на MB
  } else if (isDOCXFile(file)) {
    return Math.ceil(sizeMB * 1); // ~1 сек на MB
  } else if (isImageFile(file)) {
    return Math.ceil(sizeMB * 3); // ~3 сек на MB (OCR)
  }

  return 1;
}
