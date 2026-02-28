/**
 * Document Utils
 * Утилиты для client-side обработки документов
 * 
 * Возможности:
 * - OCR (Tesseract.js) - rus + eng
 * - PDF text extraction & operations (pdf-lib + pdf.js)
 * - DOCX text extraction (mammoth.js)
 * - Image compression & processing (Canvas API)
 * - Intelligent document processor
 */

// Main processor
export {
  processDocument,
  needsProcessing,
  estimateProcessingTime,
  type ProcessingResult,
  type ProcessingProgress,
  type ProcessDocumentOptions
} from './processor';

// OCR
export {
  performOCR,
  isOCRSupported,
  estimateOCRTime,
  type OCRProgress,
  type OCROptions
} from './ocr';

// PDF
export {
  extractPDFText,
  generatePDFThumbnail,
  splitPDF,
  mergePDFs,
  rotatePDF,
  getPDFInfo,
  type PDFTextExtractionProgress
} from './pdf';

// DOCX
export {
  extractDOCXText,
  extractDOCXHTML,
  isDOCXFile
} from './docx';

// Image
export {
  compressImage,
  cropImage,
  rotateImage,
  generateImageThumbnail,
  isImageFile,
  getImageDimensions,
  type ImageCompressOptions,
  type CropArea
} from './image';
