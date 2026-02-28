/**
 * Client-side OCR using Tesseract.js
 * Извлекает текст из изображений прямо в браузере
 */

import Tesseract from 'tesseract.js';

export interface OCRProgress {
  status: string;
  progress: number;
}

export interface OCROptions {
  languages?: string[];
  onProgress?: (progress: OCRProgress) => void;
}

/**
 * Выполняет OCR для изображения
 * 
 * @param file - Файл изображения
 * @param options - Опции OCR
 * @returns Извлеченный текст
 */
export async function performOCR(
  file: File,
  options: OCROptions = {}
): Promise<string> {
  const {
    languages = ['rus', 'eng'], // Русский + английский по умолчанию
    onProgress
  } = options;

  try {
    const worker = await Tesseract.createWorker({
      logger: (m) => {
        if (onProgress) {
          onProgress({
            status: m.status,
            progress: m.progress * 100
          });
        }
      }
    });

    // Загружаем языки
    await worker.loadLanguage(languages.join('+'));
    await worker.initialize(languages.join('+'));

    // Распознаем текст
    const { data } = await worker.recognize(file);
    
    await worker.terminate();

    return data.text;
  } catch (error) {
    console.error('[OCR] Error:', error);
    throw new Error('Ошибка распознавания текста');
  }
}

/**
 * Проверяет, поддерживается ли OCR для данного файла
 */
export function isOCRSupported(file: File): boolean {
  const supportedTypes = [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/bmp',
    'image/tiff'
  ];
  
  return supportedTypes.includes(file.type);
}

/**
 * Оценивает время OCR в секундах (приблизительно)
 */
export function estimateOCRTime(file: File): number {
  // Приблизительно 2-5 секунд на MB
  const sizeMB = file.size / (1024 * 1024);
  return Math.ceil(sizeMB * 3);
}
