import type { Message, MessageAttachment } from "@/types/api";
import { getMessageTimestamp } from "@/lib/messages/chatUtils";
import { getReplyToId } from "@/lib/messages/messageUtils";

const STORAGE_PREFIX = "eusrr_chat_pending_messages:v1";
const STORAGE_VERSION = 1;
const MAX_STORED_MESSAGES = 50;
const PENDING_TTL_MS = 7 * 24 * 60 * 60 * 1000;

type StoredPendingPayload = {
  version: typeof STORAGE_VERSION;
  saved_at: number;
  messages: Message[];
};

export function getPendingMessageStorageIdentity(chatId: number, userId: number): string {
  return `${userId}:${chatId}`;
}

function getStorageKey(chatId: number, userId: number): string {
  return `${STORAGE_PREFIX}:${getPendingMessageStorageIdentity(chatId, userId)}`;
}

function canUseLocalStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function sanitizeAttachment(attachment: MessageAttachment, index: number): MessageAttachment | null {
  if (!attachment || typeof attachment !== "object") return null;

  const fileName = typeof attachment.file_name === "string" ? attachment.file_name : "";
  if (!fileName.trim()) return null;

  return {
    id: typeof attachment.id === "number" ? attachment.id : -(Date.now() * 100 + index),
    file_name: fileName,
    file_type: typeof attachment.file_type === "string" ? attachment.file_type : undefined,
    file_url: typeof attachment.file_url === "string" ? attachment.file_url : "",
    file_size: typeof attachment.file_size === "number" ? attachment.file_size : undefined,
    mime_type: typeof attachment.mime_type === "string" ? attachment.mime_type : undefined,
    width: typeof attachment.width === "number" ? attachment.width : undefined,
    height: typeof attachment.height === "number" ? attachment.height : undefined,
    thumbnail: typeof attachment.thumbnail === "string" ? attachment.thumbnail : null,
    is_local: Boolean(attachment.is_local),
  };
}

function normalizeSendState(sendState: Message["send_state"]): Message["send_state"] {
  if (sendState === "pending" || sendState === "delayed" || sendState === "failed") {
    return sendState;
  }

  return "failed";
}

function sanitizePendingMessage(message: Message): Message | null {
  if (!message || typeof message !== "object") return null;

  const localId = typeof message.local_id === "string" && message.local_id.trim() ? message.local_id : null;
  if (!localId) return null;

  const timestamp = getMessageTimestamp(message) || Date.now();
  const attachments = (message.attachments || [])
    .map((attachment, index) => sanitizeAttachment(attachment, index))
    .filter((attachment): attachment is MessageAttachment => Boolean(attachment));
  const content = typeof message.content === "string" ? message.content : "";

  if (!content.trim() && attachments.length === 0) return null;

  return {
    id: typeof message.id === "number" && message.id < 0 ? message.id : -timestamp,
    chat: typeof message.chat === "number" ? message.chat : undefined,
    local_id: localId,
    author_id: typeof message.author_id === "number" ? message.author_id : undefined,
    author_name: typeof message.author_name === "string" ? message.author_name : undefined,
    avatar: typeof message.avatar === "string" ? message.avatar : undefined,
    content,
    is_read: false,
    send_state: normalizeSendState(message.send_state),
    is_optimistic: true,
    created_at: typeof message.created_at === "string" ? message.created_at : new Date(timestamp).toISOString(),
    created_ts: timestamp,
    has_attachments: attachments.length > 0,
    attachments,
    reply_to_id: getReplyToId(message) ?? undefined,
  };
}

function pruneStoredMessages(messages: Message[], now = Date.now()): Message[] {
  return messages
    .map(sanitizePendingMessage)
    .filter((message): message is Message => Boolean(message))
    .filter((message) => now - getMessageTimestamp(message) <= PENDING_TTL_MS)
    .slice(-MAX_STORED_MESSAGES);
}

export function loadStoredPendingMessages(chatId: number, userId: number): Message[] {
  if (!canUseLocalStorage()) return [];

  const key = getStorageKey(chatId, userId);

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];

    const payload = JSON.parse(raw) as Partial<StoredPendingPayload>;
    if (payload.version !== STORAGE_VERSION || !Array.isArray(payload.messages)) {
      window.localStorage.removeItem(key);
      return [];
    }

    const messages = pruneStoredMessages(payload.messages).map((message) => ({
      ...message,
      send_state: "failed" as const,
    }));

    if (messages.length === 0) {
      window.localStorage.removeItem(key);
    }

    return messages;
  } catch {
    window.localStorage.removeItem(key);
    return [];
  }
}

export function saveStoredPendingMessages(chatId: number, userId: number, messages: Message[]): void {
  if (!canUseLocalStorage()) return;

  const key = getStorageKey(chatId, userId);
  const storedMessages = pruneStoredMessages(messages);

  try {
    if (storedMessages.length === 0) {
      window.localStorage.removeItem(key);
      return;
    }

    const payload: StoredPendingPayload = {
      version: STORAGE_VERSION,
      saved_at: Date.now(),
      messages: storedMessages,
    };

    window.localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Quota/security errors should not break the chat UI.
  }
}

function getAttachmentSignature(message: Message): string {
  return (message.attachments || [])
    .map((attachment) => `${attachment.file_name}|${attachment.file_size ?? 0}|${attachment.mime_type ?? ""}`)
    .sort()
    .join("||");
}

function isConfirmedMatch(pending: Message, confirmed: Message): boolean {
  if (confirmed.id <= 0 || confirmed.is_optimistic) return false;
  if (pending.author_id && confirmed.author_id && pending.author_id !== confirmed.author_id) return false;
  if ((pending.content || "") !== (confirmed.content || "")) return false;
  if ((getReplyToId(pending) ?? null) !== (getReplyToId(confirmed) ?? null)) return false;
  if (getAttachmentSignature(pending) !== getAttachmentSignature(confirmed)) return false;

  const pendingTimestamp = getMessageTimestamp(pending);
  const confirmedTimestamp = getMessageTimestamp(confirmed);
  if (!pendingTimestamp || !confirmedTimestamp) return true;

  return Math.abs(pendingTimestamp - confirmedTimestamp) <= 10 * 60 * 1000;
}

export function reconcileStoredPendingMessages(pendingMessages: Message[], serverMessages: Message[]): Message[] {
  if (pendingMessages.length === 0 || serverMessages.length === 0) return pendingMessages;

  return pendingMessages.filter(
    (pending) => !serverMessages.some((serverMessage) => isConfirmedMatch(pending, serverMessage)),
  );
}
