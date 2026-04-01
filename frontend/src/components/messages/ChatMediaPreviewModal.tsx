"use client";

import Image from "next/image";
import { X } from "lucide-react";

import type { MediaPreview } from "@/components/messages/ChatMessageItem";

type ChatMediaPreviewModalProps = {
  preview: MediaPreview;
  onClose: () => void;
};

export default function ChatMediaPreviewModal({ preview, onClose }: ChatMediaPreviewModalProps) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4" onClick={onClose}>
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
        aria-label="Закрыть предпросмотр"
      >
        <X size={18} />
      </button>

      <div className="max-h-full max-w-[92vw]" onClick={(event) => event.stopPropagation()}>
        {preview.type === "image" ? (
          <Image
            src={preview.src}
            alt={preview.name}
            width={1600}
            height={1200}
            unoptimized
            className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain"
          />
        ) : (
          <video controls autoPlay className="max-h-[88vh] max-w-[92vw] rounded-lg bg-black" src={preview.src} />
        )}
      </div>
    </div>
  );
}