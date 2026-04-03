'use client';

import { useCallback, useState } from 'react';
import Cropper from 'react-easy-crop';
import type { Area, Point } from 'react-easy-crop';
import { Modal } from "@/components/ui";

interface AvatarCropperProps {
  onCropComplete: (croppedImage: string) => void;
  onCancel: () => void;
  initialImage: string;
}

export default function AvatarCropper({ onCropComplete, onCancel, initialImage }: AvatarCropperProps) {
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  
  // Фиксированный размер области обрезки 3:4 (240x320px)
  const cropSize = { width: 240, height: 320 };

  const onCropAreaChange = useCallback((croppedArea: Area, croppedAreaPixels: Area) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const createCroppedImage = useCallback(async () => {
    if (!croppedAreaPixels) return;

    const image = new Image();
    image.src = initialImage;

    await new Promise((resolve) => {
      image.onload = resolve;
    });

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Устанавливаем размер canvas равным обрезанной области
    canvas.width = croppedAreaPixels.width;
    canvas.height = croppedAreaPixels.height;

    // Рисуем обрезанное изображение
    ctx.drawImage(
      image,
      croppedAreaPixels.x,
      croppedAreaPixels.y,
      croppedAreaPixels.width,
      croppedAreaPixels.height,
      0,
      0,
      croppedAreaPixels.width,
      croppedAreaPixels.height
    );

    // Конвертируем в base64
    const croppedBase64 = canvas.toDataURL('image/jpeg', 0.9);
    onCropComplete(croppedBase64);
  }, [croppedAreaPixels, initialImage, onCropComplete]);

  return (
    <Modal isOpen onClose={onCancel} noHeader noPadding size="lg">
        {/* Заголовок */}
        <div className="border-b border-gray-200 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">
            Настройка фото профиля
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            Разместите лицо в центре овала. Фото будет использоваться для распознавания.
          </p>
        </div>

        {/* Область кадрирования */}
        <div className="relative h-96 bg-gray-100">
          <Cropper
            image={initialImage}
            crop={crop}
            zoom={zoom}
            aspect={3 / 4}
            cropSize={cropSize}
            cropShape="rect"
            showGrid={false}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={onCropAreaChange}
            objectFit="contain"
            restrictPosition={false}
          />

          {/* Направляющие рамки */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <svg 
              width={cropSize.width} 
              height={cropSize.height}
              viewBox="0 0 240 320"
            >
              {/* Овал для головы (70% ширины, верхняя часть) */}
              <ellipse
                cx="120"
                cy="100"
                rx="84"
                ry="100"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="4"
                strokeDasharray="8,8"
                opacity="0.5"
              />
              
              {/* Шея */}
              <path
                d="M 90 180 L 85 220 L 155 220 L 150 180"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="4"
                strokeDasharray="8,8"
                opacity="0.5"
              />
              
              {/* Плечи */}
              <path
                d="M 85 220 Q 50 240 30 280 L 30 320 M 155 220 Q 190 240 210 280 L 210 320"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="4"
                strokeDasharray="8,8"
                opacity="0.5"
              />
            </svg>
          </div>
        </div>

        {/* Контролы масштабирования */}
        <div className="border-t border-gray-200 px-6 py-4">
          <div className="flex items-center gap-4">
            <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
            <input
              type="range"
              min={1}
              max={3}
              step={0.1}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className="flex-1"
            />
            <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
            </svg>
          </div>
          <p className="mt-2 text-center text-xs text-gray-500">
            Используйте ползунок для масштабирования
          </p>
        </div>

        {/* Кнопки действий */}
        <div className="border-t border-gray-200 px-6 py-4">
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 rounded-lg border border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={createCroppedImage}
              className="flex-1 rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-300"
            >
              Применить
            </button>
          </div>
        </div>
    </Modal>
  );
}
