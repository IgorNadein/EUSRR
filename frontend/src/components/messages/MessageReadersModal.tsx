"use client";

import { CheckCheck } from "lucide-react";

import { Modal } from "@/components/ui";
import type { MessageReader } from "@/types/api";

type MessageReadersModalProps = {
  isOpen: boolean;
  onClose: () => void;
  readers: MessageReader[];
};

export default function MessageReadersModal({ isOpen, onClose, readers }: MessageReadersModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Прочитали сообщение" size="sm">
      <div className="space-y-4">
        <div className="rounded-2xl border border-emerald-200/80 bg-emerald-50/80 p-4">
          <div className="flex items-center gap-2 text-emerald-900">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/90 ring-1 ring-emerald-100">
              <CheckCheck size={16} />
            </span>
            <div>
              <p className="text-sm font-semibold">Полный список прочитавших</p>
              <p className="text-xs text-emerald-800/80">
                {readers.length === 1 ? "1 сотрудник" : `${readers.length} сотрудников`}
              </p>
            </div>
          </div>
        </div>

        {readers.length > 0 ? (
          <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
            {readers.map((reader) => (
              <div
                key={`message-reader-${reader.id}`}
                className="rounded-2xl border border-gray-200 bg-white px-3 py-3 text-sm font-medium leading-5 text-gray-800 shadow-sm"
              >
                {reader.name}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-center text-sm text-gray-500">
            Пока никто не дочитал это сообщение.
          </div>
        )}
      </div>
    </Modal>
  );
}