"use client";

import Image from "next/image";
import { CheckCheck } from "lucide-react";

import { Modal } from "@/components/ui";
import { resolveMediaUrl } from "@/lib/url";
import type { MessageReader } from "@/types/api";

type MessageReadersModalProps = {
  isOpen: boolean;
  onClose: () => void;
  readers: MessageReader[];
};

function getReaderInitials(name: string): string {
  const parts = name
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return "П";
  }

  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("") || "П";
}

export default function MessageReadersModal({ isOpen, onClose, readers }: MessageReadersModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Прочитали сообщение" size="sm">
      <div className="space-y-4">
        <div className="app-text-muted flex items-center gap-2 text-sm">
          <CheckCheck size={16} />
          <p>{readers.length === 1 ? "Сообщение прочитал 1 сотрудник" : `Сообщение прочитали ${readers.length} сотрудников`}</p>
        </div>

        {readers.length > 0 ? (
          <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
            {readers.map((reader) => (
              <div
                key={`message-reader-${reader.id}`}
                className="app-surface flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium leading-5"
              >
                <div className="app-avatar-fallback flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full text-xs font-semibold">
                  {reader.avatar ? (
                    <Image
                      src={resolveMediaUrl(reader.avatar)}
                      alt={reader.name}
                      width={40}
                      height={40}
                      unoptimized
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <span>{getReaderInitials(reader.name)}</span>
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[var(--foreground)]">{reader.name}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="app-surface-muted app-text-muted rounded-2xl border border-dashed px-4 py-6 text-center text-sm">
            Пока никто не дочитал это сообщение.
          </div>
        )}
      </div>
    </Modal>
  );
}
