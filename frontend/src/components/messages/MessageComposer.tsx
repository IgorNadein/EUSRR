"use client";

import { useLayoutEffect, useState } from "react";
import type React from "react";
import { Paperclip, Send, Smile, X } from "lucide-react";

const MIN_COMPOSER_HEIGHT = 40;
const MAX_COMPOSER_HEIGHT = 128;

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
  const [isExpanded, setIsExpanded] = useState(false);
  const canSend = editingMessageId ? messageText.trim().length > 0 : messageText.trim().length > 0 || attachedFiles.length > 0;

  useLayoutEffect(() => {
    const input = messageInputRef.current;
    if (!input) return;

    input.style.height = "0px";
    const nextHeight = Math.min(input.scrollHeight, MAX_COMPOSER_HEIGHT);
    const resolvedHeight = Math.max(nextHeight, MIN_COMPOSER_HEIGHT);

    input.style.height = `${resolvedHeight}px`;
    input.style.overflowY = input.scrollHeight > MAX_COMPOSER_HEIGHT ? "auto" : "hidden";
    setIsExpanded(resolvedHeight > MIN_COMPOSER_HEIGHT + 2);
  }, [messageText, messageInputRef]);

  return (
    <>
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
              className="inline-flex max-w-full items-center gap-1 rounded-full border border-sky-100 bg-white px-3 py-1 text-xs text-sky-700"
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
        <div className="flex items-end gap-2">
          <input
            ref={fileInputRef}
            multiple
            type="file"
            className="hidden"
            onChange={onFilesChange}
          />
          <div
            className={`relative min-w-0 flex-1 overflow-hidden border border-gray-200 bg-gray-50 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] transition focus-within:border-sky-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-sky-100 ${
              isExpanded ? "rounded-[1.5rem]" : "rounded-full"
            }`}
            data-composer-emoji="true"
          >
            <button
              type="button"
              onClick={onPickFiles}
              disabled={Boolean(editingMessageId)}
              className={`absolute left-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-full text-gray-400 transition hover:bg-white hover:text-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:opacity-50 ${
                isExpanded ? "bottom-2.5" : "top-1/2 -translate-y-1/2"
              }`}
              title={editingMessageId ? "При редактировании вложения недоступны" : "Добавить файлы"}
              aria-label={editingMessageId ? "При редактировании вложения недоступны" : "Добавить файлы"}
            >
              <Paperclip size={14} />
            </button>

            <button
              type="button"
              onClick={onToggleEmojiPicker}
              className={`absolute right-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-full text-gray-400 transition hover:bg-white hover:text-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-100 ${
                isExpanded ? "bottom-2.5" : "top-1/2 -translate-y-1/2"
              }`}
              title="Смайлы"
              aria-label="Открыть панель смайлов"
              aria-expanded={showEmojiPicker}
            >
              <Smile size={14} />
            </button>

            {showEmojiPicker ? (
              <div className="absolute bottom-full right-0 z-20 mb-2 w-[260px] rounded-xl border border-gray-200 bg-white p-2 shadow-lg ring-1 ring-slate-100">
                <div className="grid max-h-48 grid-cols-8 gap-1 overflow-y-auto">
                  {allReactions.map((emoji) => (
                    <button
                      key={`composer-${emoji}`}
                      type="button"
                      onClick={() => onSelectEmoji(emoji)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-base transition hover:bg-sky-50"
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
              aria-label={editingMessageId ? "Редактирование сообщения" : "Поле ввода сообщения"}
              className={`w-full resize-none bg-transparent py-2.5 pl-11 pr-12 text-sm leading-5 text-gray-800 outline-none placeholder:text-gray-400 ${
                isExpanded ? "rounded-[1.5rem]" : "rounded-full"
              }`}
            />
          </div>

          <button
            type="button"
            onClick={onSend}
            disabled={sending || !canSend}
            className="inline-flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-full bg-sky-500 text-white leading-none shadow-sm shadow-sky-200/70 transition hover:bg-sky-600 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:border disabled:border-gray-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:shadow-none disabled:opacity-100"
            title={editingMessageId ? "Сохранить" : "Отправить"}
            aria-label={editingMessageId ? "Сохранить сообщение" : "Отправить сообщение"}
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
    </>
  );
}