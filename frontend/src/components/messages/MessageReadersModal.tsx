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
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <CheckCheck size={16} className="text-gray-400" />
          <p>{readers.length === 1 ? "Сообщение прочитал 1 сотрудник" : `Сообщение прочитали ${readers.length} сотрудников`}</p>
        </div>

        {readers.length > 0 ? (
          <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
            {readers.map((reader) => (
              <div
                key={`message-reader-${reader.id}`}
                className="rounded-xl border border-gray-200 bg-white px-3 py-3 text-sm font-medium leading-5 text-gray-800"
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