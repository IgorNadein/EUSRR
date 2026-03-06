/**
 * Client-side image processing utilities
 * Compression, resize, crop, rotate
 */

export interface ImageCompressOptions {
  maxSizeMB?: number;
  maxWidthOrHeight?: number;
  quality?: number;
}

export interface CropArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Сжимает изображение перед загрузкой
 * 
 * @param file - Файл изображения
 * @param options - Опции сжатия
 * @returns Сжатое изображение как Blob
 */
export async function compressImage(
  file: File,
  options: ImageCompressOptions = {}
): Promise<Blob> {
  const {
    maxSizeMB = 10,
    maxWidthOrHeight = 2048,
    quality = 0.85
  } = options;

  try {
    const img = await createImageBitmap(file);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;

    // Вычисляем новые размеры с сохранением пропорций
    let width = img.width;
    let height = img.height;

    if (width > maxWidthOrHeight || height > maxWidthOrHeight) {
      const ratio = Math.min(
        maxWidthOrHeight / width,
        maxWidthOrHeight / height
      );
      width = Math.floor(width * ratio);
      height = Math.floor(height * ratio);
    }

    canvas.width = width;
    canvas.height = height;

    // Рисуем изображение
    ctx.drawImage(img, 0, 0, width, height);

    // Конвертируем в Blob
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            // Проверяем размер
            const sizeMB = blob.size / (1024 * 1024);
            if (sizeMB > maxSizeMB) {
              // Если еще слишком большой, рекурсивно сжимаем с меньшим quality
              const newQuality = quality * 0.8;
              if (newQuality < 0.1) {
                reject(new Error('Не удалось сжать изображение до требуемого размера'));
              } else {
                compressImage(file, { ...options, quality: newQuality })
                  .then(resolve)
                  .catch(reject);
              }
            } else {
              resolve(blob);
            }
          } else {
            reject(new Error('Ошибка создания Blob'));
          }
        },
        'image/jpeg',
        quality
      );
    });
  } catch (error) {
    console.error('[Image] Compression error:', error);
    throw new Error('Ошибка сжатия изображения');
  }
}

/**
 * Обрезает изображение
 * 
 * @param file - Файл изображения
 * @param area - Область обрезки
 * @returns Обрезанное изображение как Blob
 */
export async function cropImage(
  file: File,
  area: CropArea
): Promise<Blob> {
  try {
    const img = await createImageBitmap(file);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;

    canvas.width = area.width;
    canvas.height = area.height;

    ctx.drawImage(
      img,
      area.x,
      area.y,
      area.width,
      area.height,
      0,
      0,
      area.width,
      area.height
    );

    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error('Ошибка создания Blob'));
          }
        },
        file.type,
        0.95
      );
    });
  } catch (error) {
    console.error('[Image] Crop error:', error);
    throw new Error('Ошибка обрезки изображения');
  }
}

/**
 * Поворачивает изображение
 * 
 * @param file - Файл изображения
 * @param degrees - Угол поворота (90, 180, 270, -90)
 * @returns Повернутое изображение как Blob
 */
export async function rotateImage(
  file: File,
  degrees: number
): Promise<Blob> {
  try {
    const img = await createImageBitmap(file);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;

    // Для 90 и 270 градусов меняем размеры canvas
    if (degrees === 90 || degrees === -90 || degrees === 270) {
      canvas.width = img.height;
      canvas.height = img.width;
    } else {
      canvas.width = img.width;
      canvas.height = img.height;
    }

    // Поворачиваем
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((degrees * Math.PI) / 180);
    ctx.drawImage(img, -img.width / 2, -img.height / 2);

    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error('Ошибка создания Blob'));
          }
        },
        file.type,
        0.95
      );
    });
  } catch (error) {
    console.error('[Image] Rotate error:', error);
    throw new Error('Ошибка поворота изображения');
  }
}

/**
 * Генерирует thumbnail изображения
 * 
 * @param file - Файл изображения
 * @param maxSize - Максимальный размер (ширина или высота)
 * @returns Data URL thumbnail
 */
export async function generateImageThumbnail(
  file: File,
  maxSize: number = 200
): Promise<string> {
  try {
    const img = await createImageBitmap(file);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;

    const ratio = Math.min(maxSize / img.width, maxSize / img.height);
    const width = Math.floor(img.width * ratio);
    const height = Math.floor(img.height * ratio);

    canvas.width = width;
    canvas.height = height;
    ctx.drawImage(img, 0, 0, width, height);

    return canvas.toDataURL('image/jpeg', 0.7);
  } catch (error) {
    console.error('[Image] Thumbnail error:', error);
    throw new Error('Ошибка создания thumbnail');
  }
}

/**
 * Проверяет, является ли файл изображением
 */
export function isImageFile(file: File): boolean {
  return file.type.startsWith('image/');
}

/**
 * Получает размеры изображения
 */
export async function getImageDimensions(
  file: File
): Promise<{ width: number; height: number }> {
  const img = await createImageBitmap(file);
  return {
    width: img.width,
    height: img.height
  };
}
