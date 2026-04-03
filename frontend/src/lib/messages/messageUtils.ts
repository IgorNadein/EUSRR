import type { Message, MessageAttachment, MessageReplyPreview } from "@/types/api";

type ReplyPreviewSource = Message | MessageReplyPreview;

function isReplyPreviewSource(value: unknown): value is ReplyPreviewSource {
  return Boolean(
    value && typeof value === "object" && typeof (value as { id?: unknown }).id === "number"
  );
}

export function getMessageInitials(message: Message): string {
  const name = (message.author_name || "").trim();
  if (!name) return "С";

  const parts = name.split(" ").filter(Boolean);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }

  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

export function getMessageDate(message: Message): Date | null {
  if (message.created_at) {
    const date = new Date(message.created_at);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  if (message.created_ts) {
    const date = new Date(message.created_ts);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  return null;
}

export function formatDayDivider(date: Date): string {
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export function messageTime(message: Message): string {
  const date = getMessageDate(message);
  if (!date) return "";

  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }

  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatFileSize(size?: number): string {
  if (!size || size <= 0) return "";

  const kilobytes = size / 1024;
  if (kilobytes < 1024) return `${Math.round(kilobytes)} КБ`;

  const megabytes = kilobytes / 1024;
  return `${megabytes.toFixed(1)} МБ`;
}

export function isImageAttachment(attachment: MessageAttachment): boolean {
  const mime = (attachment.mime_type || "").toLowerCase();
  const type = (attachment.file_type || "").toLowerCase();
  const name = (attachment.file_name || "").toLowerCase();
  const byExt = /\.(png|jpe?g|gif|webp|bmp|svg|avif)$/i.test(name);
  return mime.startsWith("image/") || type === "image" || byExt;
}

export function isVideoAttachment(attachment: MessageAttachment): boolean {
  const mime = (attachment.mime_type || "").toLowerCase();
  const type = (attachment.file_type || "").toLowerCase();
  const name = (attachment.file_name || "").toLowerCase();
  const byExt = /\.(mp4|webm|mov|m4v|avi|mkv|3gp|mpeg|mpg)$/i.test(name);
  return mime.startsWith("video/") || type === "video" || byExt;
}

export function isAudioAttachment(attachment: MessageAttachment): boolean {
  const mime = (attachment.mime_type || "").toLowerCase();
  const type = (attachment.file_type || "").toLowerCase();
  return mime.startsWith("audio/") || type === "audio";
}

export function getMessagePreviewText(message: Message): string {
  if (message.content?.trim()) return message.content.trim();
  if (message.attachments?.length) return "[Вложение]";
  return "[Сообщение]";
}

export function getReplyPreview(message: Message, loadedReply?: Message | null): ReplyPreviewSource | null {
  if (loadedReply) {
    return loadedReply;
  }

  if (isReplyPreviewSource(message.reply_to)) {
    return message.reply_to;
  }

  if (isReplyPreviewSource(message.reply_to_message)) {
    return message.reply_to_message;
  }

  return null;
}

export function isReplyPreviewDeleted(preview: ReplyPreviewSource | null | undefined): boolean {
  return Boolean(preview?.is_deleted);
}

export function getReplyPreviewText(preview: ReplyPreviewSource): string {
  if (preview.is_deleted) return "Сообщение удалено";
  if (preview.content?.trim()) return preview.content.trim();
  if ("attachments" in preview && Array.isArray(preview.attachments) && preview.attachments.length > 0) {
    return "[Вложение]";
  }
  if (preview.has_attachments) return "[Вложение]";
  return "[Сообщение]";
}

export function getReplyToId(message: Message): number | null {
  if (typeof message.reply_to_id === "number") return message.reply_to_id;
  if (typeof message.reply_to === "number") return message.reply_to;
  if (isReplyPreviewSource(message.reply_to)) {
    return message.reply_to.id;
  }
  if (isReplyPreviewSource(message.reply_to_message)) {
    return message.reply_to_message.id;
  }
  return null;
}