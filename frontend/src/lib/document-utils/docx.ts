/**
 * DOCX text extraction using mammoth.js
 */

import mammoth from 'mammoth';

/**
 * Извлекает текст из DOCX файла
 * 
 * @param file - DOCX файл
 * @returns Извлеченный текст
 */
export async function extractDOCXText(file: File): Promise<string> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    
    if (result.messages.length > 0) {
      console.warn('[DOCX] Warnings:', result.messages);
    }
    
    return result.value;
  } catch (error) {
    console.error('[DOCX] Extraction error:', error);
    throw new Error('Ошибка извлечения текста из DOCX');
  }
}

/**
 * Извлекает HTML из DOCX файла (для rich preview)
 * 
 * @param file - DOCX файл
 * @returns HTML строка
 */
export async function extractDOCXHTML(file: File): Promise<string> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.convertToHtml({ arrayBuffer });
    
    return result.value;
  } catch (error) {
    console.error('[DOCX] HTML extraction error:', error);
    throw new Error('Ошибка конвертации DOCX в HTML');
  }
}

/**
 * Проверяет, является ли файл DOCX
 */
export function isDOCXFile(file: File): boolean {
  return (
    file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    file.name.toLowerCase().endsWith('.docx')
  );
}
