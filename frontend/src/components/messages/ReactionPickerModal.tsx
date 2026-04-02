"use client";

import { X } from "lucide-react";

type ReactionPickerModalProps = {
  allReactions: string[];
  onClose: () => void;
  onSelect: (emoji: string) => void;
};

export default function ReactionPickerModal({ allReactions, onClose, onSelect }: ReactionPickerModalProps) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-2 sm:p-4" data-reaction-picker="true">
      <div className="w-full max-w-[95vw] rounded-xl bg-white p-4 shadow-xl sm:max-w-md sm:rounded-2xl sm:p-6">
        <div className="mb-3 flex items-center justify-between sm:mb-4">
          <h3 className="text-base font-semibold text-gray-900 sm:text-lg">Выберите реакцию</h3>
          <button type="button" onClick={onClose} className="rounded-full p-1 hover:bg-gray-100" aria-label="Закрыть">
            <X size={18} className="text-gray-600 sm:h-5 sm:w-5" />
          </button>
        </div>
        <div className="grid max-h-[60vh] grid-cols-6 gap-1.5 overflow-y-auto sm:max-h-[55vh] sm:grid-cols-8 sm:gap-2">
          {allReactions.map((emoji) => (
            <button
              key={`picker-${emoji}`}
              type="button"
              onClick={() => onSelect(emoji)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md text-lg hover:bg-sky-50"
            >
              {emoji}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}