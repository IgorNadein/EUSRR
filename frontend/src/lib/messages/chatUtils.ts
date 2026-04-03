import type { Chat, Message } from "@/types/api";

export type ChatIdentity = {
  first_name?: string;
  last_name?: string;
  patronymic?: string;
  email?: string;
} | null | undefined;

export function getUserFullName(lastName?: string, firstName?: string): string {
  return `${lastName || ""} ${firstName || ""}`.trim();
}

function normalizeName(value?: string | null): string {
  return (value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function isLikelyCurrentUserName(candidate: string, user?: ChatIdentity): boolean {
  if (!user) return false;

  const normalizedCandidate = normalizeName(candidate);
  if (!normalizedCandidate) return false;

  const firstName = normalizeName(user.first_name);
  const lastName = normalizeName(user.last_name);
  const patronymic = normalizeName(user.patronymic);
  const email = normalizeName(user.email);

  if (email && normalizedCandidate === email) return true;

  const variants = new Set<string>([
    normalizeName(`${lastName} ${firstName}`),
    normalizeName(`${firstName} ${lastName}`),
    normalizeName(`${lastName} ${firstName} ${patronymic}`),
    normalizeName(`${firstName} ${patronymic} ${lastName}`),
    normalizeName(`${firstName} ${patronymic}`),
  ]);

  if (variants.has(normalizedCandidate)) return true;

  return Boolean(firstName && lastName && normalizedCandidate.includes(firstName) && normalizedCandidate.includes(lastName));
}

export function getInterlocutorFromParticipants(chat: Chat, currentUserId?: number) {
  const participants = (chat.participants || []).filter(
    (participant): participant is Exclude<typeof participant, number> =>
      typeof participant === "object" && participant !== null
  );
  return participants.find((participant) => participant.id !== currentUserId);
}

export function getInterlocutorFromParticipantDetails(chat: Chat, currentUserId?: number) {
  return (chat.participant_details || []).find((participant) => participant.id !== currentUserId);
}

export function getInterlocutorNameFromParticipantNames(chat: Chat, currentUser?: ChatIdentity): string {
  const names = (chat.participant_names || []).map((name) => (name || "").trim()).filter(Boolean);
  if (!names.length) return "";

  const otherParticipant = names.find((name) => !isLikelyCurrentUserName(name, currentUser));
  return otherParticipant || names[0] || "";
}

export function getChatTitle(chat: Chat, currentUserId?: number, currentUser?: ChatIdentity): string {
  const chatKind = chat.chat_type || chat.type;
  const rawName = (chat.name || "").trim();

  if (chatKind === "direct" || chatKind === "private" || !rawName || rawName.toLowerCase() === "диалог") {
    if (chat.interlocutor?.name?.trim()) {
      return chat.interlocutor.name.trim();
    }

    const detailsOther = getInterlocutorFromParticipantDetails(chat, currentUserId);
    if (detailsOther?.name?.trim()) {
      return detailsOther.name.trim();
    }

    const otherParticipant = getInterlocutorFromParticipants(chat, currentUserId);
    if (otherParticipant) {
      const participantName = getUserFullName(otherParticipant.last_name, otherParticipant.first_name);
      if (participantName) return participantName;
      if (otherParticipant.email) return otherParticipant.email;
    }

    const namesFallback = getInterlocutorNameFromParticipantNames(chat, currentUser);
    if (namesFallback) return namesFallback;
  }

  return rawName || "Диалог";
}

export function getChatAvatar(chat: Chat, currentUserId?: number): string {
  const chatKind = chat.chat_type || chat.type;
  if (chatKind === "direct" || chatKind === "private" || (chat.name || "").trim().toLowerCase() === "диалог") {
    if (chat.interlocutor?.avatar) return chat.interlocutor.avatar;

    const detailsOther = getInterlocutorFromParticipantDetails(chat, currentUserId);
    if (detailsOther?.avatar) return detailsOther.avatar;

    const otherParticipant = getInterlocutorFromParticipants(chat, currentUserId);
    if (otherParticipant?.avatar) return otherParticipant.avatar;
  }

  return chat.avatar || "";
}

export function getChatInitials(chat: Chat, currentUserId?: number, currentUser?: ChatIdentity): string {
  return (
    getChatTitle(chat, currentUserId, currentUser)
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() || "")
      .join("") || "Ч"
  );
}

export function uniqueMessagesById(items: Message[]): Message[] {
  const map = new Map<number, Message>();
  items.forEach((message) => {
    map.set(message.id, message);
  });
  return Array.from(map.values());
}

export function getMessageTimestamp(message: Message): number {
  if (typeof message.created_ts === "number") {
    return message.created_ts;
  }

  if (message.created_at) {
    const value = new Date(message.created_at).getTime();
    if (!Number.isNaN(value)) {
      return value;
    }
  }

  return 0;
}

export function mergeDisplayMessages(serverMessages: Message[], pendingMessages: Message[]): Message[] {
  const combined = [...serverMessages, ...pendingMessages].map((message, index) => ({ message, index }));

  combined.sort((left, right) => {
    const timestampDiff = getMessageTimestamp(left.message) - getMessageTimestamp(right.message);
    if (timestampDiff !== 0) {
      return timestampDiff;
    }

    if (left.message.is_optimistic !== right.message.is_optimistic) {
      return left.message.is_optimistic ? 1 : -1;
    }

    return left.index - right.index;
  });

  return combined.map(({ message }) => message);
}