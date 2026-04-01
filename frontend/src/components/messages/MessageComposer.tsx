"use client";

import type React from "react";
import { Paperclip, Send, Smile, X } from "lucide-react";

type ReplyTarget = {
  id: number;
  author: string;
  preview: string;
};

type MessageComposerProps = {
  canSendMessages: boolean;
  membershipRole?: string | null;
  editingMessageId: number | null;
  replyTo: ReplyTarget | null;
  attachedFiles: File[];
  messageText: string;
  sending: boolean;
  showEmojiPicker: boolean;
  allReactions: string[];
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  messageInputRef: React.RefObject<HTMLTextAreaElement | null>;
  onPickFiles: () => void;
  onFilesChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveFile: (index: number) => void;
  onToggleEmojiPicker: () => void;
  onSelectEmoji: (emoji: string) => void;
  onInputClick: () => void;
  onChangeMessage: (value: string) => void;
  onTyping: () => void;
  onSend: () => void;
  onCancelEdit: () => void;
  onCancelReply: () => void;
};

export default function MessageComposer({
  canSendMessages,
  membershipRole,
  editingMessageId,
  replyTo,
  attachedFiles,
  messageText,
  sending,
  showEmojiPicker,
  allReactions,
  fileInputRef,
  messageInputRef,
  onPickFiles,
  onFilesChange,
  onRemoveFile,
  onToggleEmojiPicker,
  onSelectEmoji,
  onInputClick,
  onChangeMessage,
  onTyping,
  onSend,
  onCancelEdit,
  onCancelReply,
}: MessageComposerProps) {
  return (
    <div className="shrink-0 border-t border-gray-100 bg-white pt-3">
      {editingMessageId ? (
        <div className="mb-2 flex items-start justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <div className="min-w-0">
            <p className="font-semibold">Режим редактирования</p>
            <p className="truncate">Измените текст сообщения и отправьте</p>
          </div>
          <button
            type="button"
            onClick={onCancelEdit}
            className="rounded-full p-0.5 text-amber-700 hover:bg-amber-100"
            aria-label="Отменить редактирование"
          >
            <X size={12} />
          </button>
        </div>
      ) : null}

      {replyTo ? (
        <div className="mb-2 flex items-start justify-between gap-2 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-xs text-sky-800">
          <div className="min-w-0">
            <p className="font-semibold">Ответ: {replyTo.author}</p>
            <p className="truncate">{replyTo.preview}</p>
          </div>
          <button
            type="button"
            onClick={onCancelReply}
            className="rounded-full p-0.5 text-sky-700 hover:bg-sky-100"
            aria-label="Отменить ответ"
          >
            <X size={12} />
          </button>
        </div>
      ) : null}

      {attachedFiles.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachedFiles.map((file, index) => (
            <span
              key={`${file.name}-${file.size}-${index}`}
              className="inline-flex max-w-full items-center gap-1 rounded-full bg-sky-50 px-3 py-1 text-xs text-sky-700 ring-1 ring-sky-100"
            >
              <span className="truncate max-w-[180px]">{file.name}</span>
              <button
                type="button"
                onClick={() => onRemoveFile(index)}
                className="rounded-full p-0.5 hover:bg-sky-100"
                aria-label="Удалить файл"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      {canSendMessages ? (
        <div className="flex items-start gap-2">
          <input
            ref={fileInputRef}
            multiple
            type="file"
            className="hidden"
            onChange={onFilesChange}
          />
          <button
            type="button"
            onClick={onPickFiles}
            disabled={Boolean(editingMessageId)}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 leading-none transition hover:bg-gray-50 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            title={editingMessageId ? "При редактировании вложения недоступны" : "Добавить файлы"}
          >
            <Paperclip size={15} />
          </button>

          <div className="relative w-full" data-composer-emoji="true">
            <button
              type="button"
              onClick={onToggleEmojiPicker}
              className="absolute right-2 top-1/2 z-10 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-sky-600"
              title="Смайлы"
            >
              <Smile size={14} />
            </button>

            {showEmojiPicker ? (
              <div className="absolute bottom-full right-0 z-20 mb-2 w-[260px] rounded-lg border border-gray-200 bg-white p-2 shadow-xl">
                <div className="grid max-h-48 grid-cols-8 gap-1 overflow-y-auto">
                  {allReactions.map((emoji) => (
                    <button
                      key={`composer-${emoji}`}
                      type="button"
                      onClick={() => onSelectEmoji(emoji)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-base hover:bg-sky-50"
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <textarea
              ref={messageInputRef}
              value={messageText}
              onChange={(event) => {
                onChangeMessage(event.target.value);
                onTyping();
              }}
              onClick={onInputClick}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSend();
                }
              }}
              rows={1}
              placeholder={editingMessageId ? "Редактируйте сообщение..." : "Введите сообщение..."}
              className="h-9 w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 pr-10 text-sm text-gray-900 outline-none ring-0 transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <button
            type="button"
            onClick={onSend}
            disabled={sending || (editingMessageId ? !messageText.trim() : (!messageText.trim() && attachedFiles.length === 0))}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-500 text-white leading-none transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            title={editingMessageId ? "Сохранить" : "Отправить"}
          >
            <Send size={15} />
          </button>
        </div>
      ) : (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-center text-sm text-amber-800">
          <p className="font-medium">У вас нет прав на отправку сообщений</p>
          <p className="mt-1 text-xs text-amber-700">
            {membershipRole === "guest"
              ? "Гости могут только просматривать сообщения и отправлять реакции"
              : "Обратитесь к администратору чата для получения прав"}
          </p>
        </div>
      )}
    </div>
  );
}