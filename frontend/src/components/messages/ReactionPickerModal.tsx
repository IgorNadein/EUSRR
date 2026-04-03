"use client";

import dynamic from "next/dynamic";
import { EmojiStyle, SuggestionMode, Theme } from "emoji-picker-react";

import { Modal } from "@/components/ui";
import emojiDataRu from "emoji-picker-react/dist/data/emojis-ru.js";

const EmojiPicker = dynamic(() => import("emoji-picker-react"), { ssr: false });

type ReactionPickerModalProps = {
  onClose: () => void;
  onSelect: (emoji: string) => void;
};

export default function ReactionPickerModal({ onClose, onSelect }: ReactionPickerModalProps) {
  return (
    <Modal isOpen onClose={onClose} title="Выберите реакцию" size="sm" className="reaction-picker-modal">
      <div className="space-y-4" data-reaction-picker="true">
        <p className="text-sm text-gray-500">Быстрый способ отреагировать на сообщение без текста.</p>

        <div className="overflow-hidden rounded-xl border border-gray-100 bg-white">
          <EmojiPicker
            emojiData={emojiDataRu}
            onEmojiClick={(emoji) => onSelect(emoji.emoji)}
            searchPlaceholder="Поиск смайликов"
            theme={Theme.LIGHT}
            emojiStyle={EmojiStyle.NATIVE}
            suggestedEmojisMode={SuggestionMode.FREQUENT}
            lazyLoadEmojis
            previewConfig={{ showPreview: false }}
            width="100%"
            height={420}
          />
        </div>
      </div>
    </Modal>
  );
}