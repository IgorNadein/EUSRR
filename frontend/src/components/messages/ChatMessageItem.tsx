"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCheck,
  ChevronRight,
  Clock3,
  FileText,
  Image as ImageIcon,
  Loader2,
  PlayCircle,
  RotateCcw,
} from "lucide-react";

import { RequestAvatar } from "@/components/requests/RequestAvatar";
import MessageActionsMenu from "@/components/messages/MessageActionsMenu";
import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import { resolveMediaUrl } from "@/lib/url";
import {
  formatFileSize,
  getReplyPreview,
  getReplyPreviewStatusLabel,
  getReplyPreviewText,
  getReplyToId,
  getMessageDate,
  getMessageInitials,
  isReplyPreviewDeleted,
  isAudioAttachment,
  isImageAttachment,
  isVideoAttachment,
  messageTime,
} from "@/lib/messages/messageUtils";
import type { Message } from "@/types/api";

export type MediaPreview = {
  type: "image" | "video";
  src: string;
  name: string;
};

function MediaTypeBadge({ type }: { type: "image" | "video" }) {
  const isVideo = type === "video";
  const Icon = isVideo ? PlayCircle : ImageIcon;

  return (
    <span className="absolute left-2 top-2 z-10 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
      <Icon size={12} />
      {isVideo ? "Видео" : "Фото"}
    </span>
  );
}

type ChatMessageItemProps = {
  message: Message;
  currentUserId?: number;
  repliedMessage?: Message | null;
  isHighlighted?: boolean;
  isActionsOpen: boolean;
  canManage: boolean;
  canReply: boolean;
  brokenMedia: Record<number, boolean>;
  useOriginalImage: Record<number, boolean>;
  onToggleActions: (messageId: number) => void;
  onJumpToReply: (messageId: number) => void;
  onOpenMediaPreview: (preview: MediaPreview) => void;
  onAttachmentLoad: (attachmentId: number) => void;
  onAttachmentError: (attachmentId: number) => void;
  onUseOriginalImage: (attachmentId: number) => void;
  onReact: (message: Message, emoji: string) => void;
  hasMyReaction: (message: Message, emoji: string) => boolean;
  recentReactions: string[];
  onQuickReact: (message: Message, emoji: string) => void;
  onOpenReactionPicker: (message: Message) => void;
  onShowAllReaders?: (message: Message) => void;
  onLinkToTask?: (message: Message) => void;
  onRetry?: (message: Message) => void;
  isRetrying?: boolean;
  retryDisabled?: boolean;
  onReply: (message: Message) => void;
  onEdit: (message: Message) => void;
  onDelete: (message: Message) => void;
};

function getMessageAuthorLabel(message: Message): string {
  return message.author_name || message.author?.last_name || message.sender?.last_name || "Сотрудник";
}

function formatReactionInitials(name: string): string {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return `${parts[0].slice(0, 1)}${parts[1].slice(0, 1)}`.toUpperCase();
}

function MessageDeliveryStatus({ sendState, isRead }: { sendState?: Message["send_state"]; isRead: boolean }) {
  if (sendState === "pending") {
    return (
      <span className="inline-flex items-center text-sky-100" title="Отправляется" aria-label="Отправляется">
        <Loader2 size={13} strokeWidth={2.2} className="animate-spin" />
      </span>
    );
  }

  if (sendState === "delayed") {
    return (
      <span className="inline-flex items-center text-sky-100" title="Сервер отвечает медленно" aria-label="Сервер отвечает медленно">
        <Clock3 size={13} strokeWidth={2.2} />
      </span>
    );
  }

  if (sendState === "failed") {
    return (
      <span className="inline-flex items-center text-rose-200" title="Не отправлено" aria-label="Не отправлено">
        <AlertCircle size={13} strokeWidth={2.2} />
      </span>
    );
  }

  const Icon = isRead ? CheckCheck : Check;

  return (
    <span
      className={`inline-flex items-center ${isRead ? "text-white" : "text-sky-100"}`}
      title={isRead ? "Прочитано" : "Отправлено"}
      aria-label={isRead ? "Прочитано" : "Отправлено"}
    >
      <Icon size={13} strokeWidth={2.2} />
    </span>
  );
}

export default function ChatMessageItem({
  message,
  currentUserId,
  repliedMessage,
  isHighlighted = false,
  isActionsOpen,
  canManage,
  canReply,
  brokenMedia,
  useOriginalImage,
  onToggleActions,
  onJumpToReply,
  onOpenMediaPreview,
  onAttachmentLoad,
  onAttachmentError,
  onUseOriginalImage,
  onReact,
  hasMyReaction,
  recentReactions,
  onQuickReact,
  onOpenReactionPicker,
  onShowAllReaders,
  onLinkToTask,
  onRetry,
  isRetrying = false,
  retryDisabled = false,
  onReply,
  onEdit,
  onDelete,
}: ChatMessageItemProps) {
  const [reactionPopoverEmoji, setReactionPopoverEmoji] = useState<string | null>(null);
  const currentDate = getMessageDate(message);
  const replyPreviewMessage = getReplyPreview(message, repliedMessage);
  const replyToId = getReplyToId(message);
  const canJumpToReply = Boolean(replyToId && !isReplyPreviewDeleted(replyPreviewMessage));
  const replyStatusLabel = getReplyPreviewStatusLabel(replyPreviewMessage);
  const isMine = Boolean(
    currentUserId &&
      (message.author_id === currentUserId || message.author?.id === currentUserId || message.sender?.id === currentUserId)
  );
  const hasActions = canReply || canManage;
  const isRead = Boolean(message.is_read);
  const sendState = message.send_state;
  const linkedTasks = message.linked_tasks || [];
  const reactionUsers = useMemo(() => {
    const summary = message.reactions_summary || {};
    return Object.fromEntries(
      Object.entries(summary).map(([emoji, meta]) => {
        const names = Array.isArray(meta.user_names) ? meta.user_names : [];
        const userIds = Array.isArray(meta.users) ? meta.users : [];
        return [
          emoji,
          Array.isArray(meta.user_details) && meta.user_details.length > 0
            ? meta.user_details.map((person, index) => ({
                id: person.id ?? userIds[index] ?? `${emoji}-${index}-${person.name}`,
                name: person.name,
                avatar: person.avatar || null,
              }))
            : names.map((name, index) => ({
                id: userIds[index] ?? `${emoji}-${index}-${name}`,
                name,
                avatar: null,
              })),
        ];
      }),
    ) as Record<string, Array<{ id: number | string; name: string; avatar: string | null }>>;
  }, [message.reactions_summary]);

  return (
    <div data-message-id={message.id} data-message-date={currentDate?.toISOString() || ""} className="mb-3 last:mb-0">
      <div className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
        {!isMine ? (
          <div className="relative mr-2 mt-1 h-8 w-8 shrink-0">
            <div className="app-avatar-fallback flex h-8 w-8 items-center justify-center overflow-hidden rounded-full text-[10px] font-semibold">
              {message.avatar || message.author?.avatar ? (
                <Image
                  src={resolveMediaUrl(message.avatar || message.author?.avatar || "")}
                  alt={message.author_name || "Автор"}
                  width={32}
                  height={32}
                  unoptimized
                  className="h-full w-full object-cover"
                />
              ) : (
                getMessageInitials(message)
              )}
            </div>
          </div>
        ) : null}

        <div className={`flex min-w-0 items-start gap-1 ${isMine ? "max-w-[88%] flex-row-reverse" : "max-w-[calc(100%-2.5rem)]"}`}>
          <div className={`relative min-w-0 rounded-2xl px-3 py-2 pr-9 transition-shadow duration-300 ${isMine ? "bg-sky-500 text-white" : "app-surface-elevated text-[var(--foreground)]"} ${isHighlighted ? (isMine ? "shadow-[0_0_0_3px_rgba(125,211,252,0.45)]" : "ring-2 ring-sky-300 shadow-[0_0_0_4px_rgba(186,230,253,0.28)]") : ""}`}>
            {hasActions ? (
              <div className="absolute right-1 top-1 z-20">
                <button
                  type="button"
                  data-actions-trigger="true"
                  onClick={() => onToggleActions(message.id)}
                  className={`inline-flex h-6 w-6 items-center justify-center rounded-full border border-transparent bg-transparent text-[var(--muted-foreground)] transition hover:text-sky-600 ${
                    isActionsOpen ? "rotate-90" : ""
                  }`}
                  title="Действия"
                  aria-label="Действия сообщения"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            ) : null}

            {!isMine ? <p className="app-text-muted mb-1 text-[11px] font-medium">{getMessageAuthorLabel(message)}</p> : null}

            {replyToId ? (
              canJumpToReply ? (
                <button
                  type="button"
                  onClick={() => onJumpToReply(replyToId)}
                  className={[
                    "group mb-2 block w-full rounded-xl border-l-2 px-2.5 py-1.5 text-left text-xs transition focus-visible:outline-none",
                    isMine
                      ? "border-sky-200 bg-sky-400/30 text-sky-50 hover:bg-sky-400/40 focus-visible:bg-sky-400/40 focus-visible:ring-2 focus-visible:ring-white/35"
                      : "border-[var(--border-strong)] bg-[var(--surface-secondary)] text-[var(--muted-foreground)] hover:bg-[var(--surface-tertiary)] focus-visible:bg-[var(--surface-tertiary)] focus-visible:ring-2 focus-visible:ring-sky-200",
                  ].join(" ")}
                  title="Перейти к исходному сообщению"
                  aria-label={`Перейти к сообщению ${replyPreviewMessage?.author_name || `#${replyToId}`}`}
                >
                  <p className="font-medium opacity-90 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                    {replyPreviewMessage?.author_name || "Ответ на сообщение"}
                  </p>
                  <p className="truncate opacity-90 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                    {replyPreviewMessage ? getReplyPreviewText(replyPreviewMessage) : `Сообщение #${replyToId}`}
                  </p>
                </button>
              ) : (
                <div
                  className={[
                    "mb-2 block w-full rounded-xl border-l-2 px-2.5 py-1.5 text-left text-xs opacity-95",
                    isMine
                      ? "border-sky-200/80 bg-sky-400/20 text-sky-50/95"
                      : "border-[var(--border-strong)] bg-[var(--surface-secondary)] text-[var(--muted-foreground)]",
                  ].join(" ")}
                  title="Исходное сообщение удалено"
                  aria-label={`Исходное сообщение удалено${replyPreviewMessage?.author_name ? `, автор ${replyPreviewMessage.author_name}` : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="min-w-0 truncate font-medium">
                      {replyPreviewMessage?.author_name || "Ответ на сообщение"}
                    </p>
                    {replyStatusLabel ? (
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${isMine ? "bg-white/18 text-white/90" : "bg-[var(--surface-tertiary)] text-[var(--muted-foreground)]"}`}>
                        {replyStatusLabel}
                      </span>
                    ) : null}
                  </div>
                  <p className="truncate opacity-90">
                    {replyPreviewMessage ? getReplyPreviewText(replyPreviewMessage) : "Сообщение удалено"}
                  </p>
                </div>
              )
            ) : null}

            {message.is_deleted ? (
              <p className={`italic text-sm ${isMine ? "text-sky-100" : "app-text-muted"}`}>Сообщение удалено</p>
            ) : message.content ? (
              <p className="whitespace-pre-wrap break-words text-sm leading-5">{message.content}</p>
            ) : null}

            {message.attachments && message.attachments.length > 0 ? (
              <div className="mt-2 space-y-2">
                {message.attachments.map((attachment) => {
                  if (attachment.is_local) {
                    return (
                      <div
                        key={attachment.id}
                        className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${isMine ? "bg-sky-400/25 text-sky-50" : "app-surface-muted text-[var(--foreground)]"}`}
                      >
                        <FileText size={16} className="shrink-0" />
                        <span className="min-w-0 flex-1 truncate">{attachment.file_name}</span>
                        <span className={`shrink-0 text-xs ${isMine ? "text-sky-100" : "app-text-muted"}`}>{formatFileSize(attachment.file_size)}</span>
                      </div>
                    );
                  }

                  const fileUrl = resolveMediaUrl(attachment.file_url);

                  if (isImageAttachment(attachment)) {
                    if (brokenMedia[attachment.id]) {
                      return (
                        <a
                          key={attachment.id}
                          href={fileUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                        >
                          <FileText size={16} className="shrink-0" />
                          <span className="min-w-0 flex-1 truncate">Предпросмотр недоступен — открыть файл</span>
                        </a>
                      );
                    }

                    const hasThumbnail = Boolean(attachment.thumbnail);
                    const imageSrc = useOriginalImage[attachment.id]
                      ? fileUrl
                      : resolveMediaUrl(attachment.thumbnail || attachment.file_url);

                    return (
                      <button
                        key={attachment.id}
                        type="button"
                        onClick={() => onOpenMediaPreview({ type: "image", src: fileUrl, name: attachment.file_name })}
                        className="relative block w-full overflow-hidden rounded-lg"
                      >
                        <MediaTypeBadge type="image" />
                        <Image
                          src={imageSrc}
                          alt={attachment.file_name}
                          width={attachment.width || 1280}
                          height={attachment.height || 720}
                          unoptimized
                          className="max-h-64 w-full rounded-lg object-cover"
                          onError={() => {
                            if (hasThumbnail && !useOriginalImage[attachment.id]) {
                              onUseOriginalImage(attachment.id);
                              return;
                            }
                            onAttachmentError(attachment.id);
                          }}
                          onLoad={() => onAttachmentLoad(attachment.id)}
                          sizes="(max-width: 768px) 100vw, 512px"
                        />
                      </button>
                    );
                  }

                  if (isVideoAttachment(attachment)) {
                    if (brokenMedia[attachment.id]) {
                      return (
                        <a
                          key={attachment.id}
                          href={fileUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                        >
                          <FileText size={16} className="shrink-0" />
                          <span className="min-w-0 flex-1 truncate">Видео не поддерживается в браузере — открыть файл</span>
                        </a>
                      );
                    }

                    return (
                      <button
                        key={attachment.id}
                        type="button"
                        onClick={() => onOpenMediaPreview({ type: "video", src: fileUrl, name: attachment.file_name })}
                        className="relative block w-full overflow-hidden rounded-lg"
                      >
                        <MediaTypeBadge type="video" />
                        <video
                          preload="metadata"
                          playsInline
                          muted
                          src={fileUrl}
                          width={attachment.width || undefined}
                          height={attachment.height || undefined}
                          className="max-h-64 w-full rounded-lg bg-black"
                          onError={() => onAttachmentError(attachment.id)}
                          onLoadedData={() => onAttachmentLoad(attachment.id)}
                        />
                        <span className="pointer-events-none absolute inset-0 flex items-center justify-center">
                          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-black/45 text-white backdrop-blur-sm">
                            <PlayCircle size={26} fill="currentColor" strokeWidth={1.8} />
                          </span>
                        </span>
                      </button>
                    );
                  }

                  if (isAudioAttachment(attachment)) {
                    if (brokenMedia[attachment.id]) {
                      return (
                        <a
                          key={attachment.id}
                          href={fileUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                        >
                          <FileText size={16} className="shrink-0" />
                          <span className="min-w-0 flex-1 truncate">Аудио не поддерживается — открыть файл</span>
                        </a>
                      );
                    }

                    return (
                      <audio
                        key={attachment.id}
                        controls
                        preload="metadata"
                        className="w-full"
                        onError={() => onAttachmentError(attachment.id)}
                        onCanPlay={() => onAttachmentLoad(attachment.id)}
                      >
                        <source src={fileUrl} type={attachment.mime_type || "audio/mpeg"} />
                      </audio>
                    );
                  }

                  return (
                    <a
                      key={attachment.id}
                      href={fileUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="app-surface-muted flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-sky-700 hover:bg-[var(--surface-elevated)]"
                    >
                      <FileText size={16} className="shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{attachment.file_name}</span>
                      <span className="app-text-muted shrink-0 text-xs">{formatFileSize(attachment.file_size)}</span>
                    </a>
                  );
                })}
              </div>
            ) : null}

            {linkedTasks.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {linkedTasks.slice(0, 2).map((task) => (
                  <TaskLinkPill
                    key={task.link_id}
                    task={task}
                    tone={isMine ? "onAccent" : "default"}
                  />
                ))}
                {linkedTasks.length > 2 ? (
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      isMine ? "bg-white/18 text-white" : "app-pill"
                    }`}
                  >
                    +{linkedTasks.length - 2}
                  </span>
                ) : null}
              </div>
            ) : null}

            <div className={`mt-1 flex items-center ${isMine ? "justify-end gap-1.5" : "justify-end"}`}>
              {isMine && sendState === "failed" && onRetry ? (
                <button
                  type="button"
                  onClick={() => onRetry(message)}
                  disabled={isRetrying || retryDisabled}
                  className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/15 text-white transition hover:bg-white/25 focus:outline-none focus:ring-2 focus:ring-white/35 disabled:cursor-not-allowed disabled:opacity-45"
                  title={retryDisabled ? "Вложения нужно выбрать заново" : isRetrying ? "Отправляется" : "Переотправить"}
                  aria-label={retryDisabled ? "Нельзя переотправить: вложения нужно выбрать заново" : "Переотправить сообщение"}
                >
                  <RotateCcw size={12} className={isRetrying ? "animate-spin" : ""} />
                </button>
              ) : null}
              <p className={`text-right text-[11px] ${isMine ? "text-sky-100" : "app-text-muted"}`}>{messageTime(message)}</p>
              {isMine ? <MessageDeliveryStatus sendState={sendState} isRead={isRead} /> : null}
            </div>

            {Object.keys(message.reactions_summary || {}).length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(message.reactions_summary || {}).map(([emoji, meta]) => {
                  const mine = hasMyReaction(message, emoji);
                  const reactedUsers = reactionUsers[emoji] || [];
                  const showReactionPopover = reactionPopoverEmoji === emoji && reactedUsers.length > 0;
                  return (
                    <div
                      key={`${message.id}-${emoji}`}
                      className="relative"
                      onMouseEnter={() => setReactionPopoverEmoji(emoji)}
                      onMouseLeave={() => setReactionPopoverEmoji((current) => (current === emoji ? null : current))}
                    >
                      <button
                        type="button"
                        onClick={() => onReact(message, emoji)}
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs transition ${
                          mine ? "bg-sky-100 text-sky-700 ring-1 ring-sky-300" : "app-surface-muted text-[var(--foreground)] ring-1 ring-[var(--border-subtle)] hover:bg-[var(--surface-elevated)]"
                        }`}
                        title="Реакция"
                      >
                        <span>{emoji}</span>
                        <span>{meta.count}</span>
                      </button>
                      {showReactionPopover ? (
                        <div className={`app-menu absolute top-full z-20 mt-1 w-56 rounded-xl p-2 ${isMine ? "right-0" : "left-0"}`}>
                          <p className="app-text-muted px-1 pb-1 text-xs font-semibold">Отреагировали</p>
                          <div className="max-h-56 space-y-1 overflow-y-auto">
                            {reactedUsers.map((person) => (
                              <div key={person.id} className="flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-[var(--surface-secondary)]">
                                <RequestAvatar
                                  alt={person.name}
                                  fallback={formatReactionInitials(person.name)}
                                  size="sm"
                                  src={person.avatar || undefined}
                                />
                                <p className="truncate text-xs text-[var(--foreground)]">{person.name}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : null}

            {isActionsOpen ? (
              <MessageActionsMenu
                currentUserId={currentUserId}
                message={message}
                canReply={canReply}
                canManage={canManage}
                isMine={isMine}
                recentReactions={recentReactions}
                onQuickReact={(emoji) => onQuickReact(message, emoji)}
                onOpenReactionPicker={() => onOpenReactionPicker(message)}
                onShowAllReaders={onShowAllReaders ? () => onShowAllReaders(message) : undefined}
                onLinkToTask={onLinkToTask ? () => onLinkToTask(message) : undefined}
                onReply={() => onReply(message)}
                onEdit={() => onEdit(message)}
                onDelete={() => onDelete(message)}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
