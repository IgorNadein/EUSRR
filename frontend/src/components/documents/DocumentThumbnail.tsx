'use client';

import { Document } from '@/types/api';
import { apiClient } from '@/lib/api';

interface DocumentThumbnailProps {
  document: Document;
  size?: 'small' | 'medium' | 'large' | 'original';
  className?: string;
}

export default function DocumentThumbnail({
  document,
  size = 'medium',
  className = '',
}: DocumentThumbnailProps) {
  const thumbnailUrl = apiClient.getDocumentThumbnail(document.id, size);

  const isImage = document.file_name?.match(/\.(jpg|jpeg|png|gif|webp)$/i);

  if (!isImage) {
    // Для не-изображений показываем иконку файла
    const getFileIcon = (fileName?: string) => {
      if (!fileName) return 'bi-file-earmark';
      if (fileName.match(/\.pdf$/i)) return 'bi-file-earmark-pdf';
      if (fileName.match(/\.(doc|docx)$/i)) return 'bi-file-earmark-word';
      if (fileName.match(/\.(xls|xlsx)$/i)) return 'bi-file-earmark-excel';
      if (fileName.match(/\.(zip|rar|7z)$/i)) return 'bi-file-earmark-zip';
      return 'bi-file-earmark';
    };

    return (
      <div
        className={`d-flex align-items-center justify-content-center bg-light rounded ${className}`}
        style={{
          width: size === 'small' ? '60px' : size === 'medium' ? '120px' : '200px',
          height: size === 'small' ? '60px' : size === 'medium' ? '120px' : '200px',
        }}
      >
        <i
          className={`bi ${getFileIcon(document.file_name)} text-secondary`}
          style={{
            fontSize: size === 'small' ? '24px' : size === 'medium' ? '48px' : '72px',
          }}
        ></i>
      </div>
    );
  }

  return (
    <img
      src={thumbnailUrl}
      alt={document.title}
      className={`img-thumbnail ${className}`}
      style={{
        maxWidth: size === 'small' ? '60px' : size === 'medium' ? '120px' : '200px',
        maxHeight: size === 'small' ? '60px' : size === 'medium' ? '120px' : '200px',
        objectFit: 'cover',
      }}
      loading="lazy"
    />
  );
}
