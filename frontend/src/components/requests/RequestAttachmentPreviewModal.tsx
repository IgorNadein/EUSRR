import Image from "next/image";
import { Modal } from "@/components/ui";
import type { RequestAttachmentPreview } from "@/hooks/useRequestsPage";
import { resolveMediaUrl } from "@/lib/url";
import { FileSignature } from "lucide-react";

type RequestAttachmentPreviewModalProps = {
  onClose: () => void;
  preview: RequestAttachmentPreview | null;
};

export function RequestAttachmentPreviewModal({
  onClose,
  preview,
}: RequestAttachmentPreviewModalProps) {
  if (!preview) return null;

  const extension = preview.url.split(".").pop()?.toLowerCase() || "";
  const previewUrl = resolveMediaUrl(preview.url);

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={preview.name}
      size="lg"
      footer={(
        <a
          href={previewUrl}
          download
          className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium"
        >
          Скачать
        </a>
      )}
    >
      <div className="flex-1 overflow-auto">
        {["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"].includes(extension) ? (
          <div className="relative mx-auto h-[70vh] overflow-hidden rounded-lg bg-[var(--surface-secondary)]">
            <Image
              src={previewUrl}
              alt={preview.name}
              fill
              unoptimized
              sizes="(max-width: 1024px) 100vw, 960px"
              className="object-contain"
            />
          </div>
        ) : ["mp4", "webm", "ogg", "mov"].includes(extension) ? (
          <video src={previewUrl} controls className="mx-auto max-h-[70vh] rounded-lg" />
        ) : ["mp3", "wav", "aac"].includes(extension) ? (
          <audio src={previewUrl} controls className="mx-auto mt-8" />
        ) : (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <FileSignature size={40} className="app-text-muted" />
            <p className="app-text-muted text-sm">{preview.name}</p>
            <a
              href={previewUrl}
              download
              className="app-action-primary rounded-lg px-4 py-2 text-sm font-medium"
            >
              Скачать файл
            </a>
          </div>
        )}
      </div>
    </Modal>
  );
}
