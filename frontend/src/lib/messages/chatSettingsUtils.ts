import type { Chat, ChatMembership, User } from "@/types/api";
import { isDepartmentCommentsChat } from "@/lib/messages/chatUtils";

export type MemberSearchResult = Pick<User, "id" | "first_name" | "last_name" | "email" | "avatar"> & {
  name?: string;
};

export type ChatMemberRole = ChatMembership["role"] | null;

export function getChatTypeLabel(chat: Chat): string {
  const type = chat.chat_type || chat.type;
  switch (type) {
    case "global":
      return "Глобальный чат";
    case "channel":
      return "Канал";
    case "private":
    case "direct":
      return "Личный чат";
    case "group":
      return "Групповой чат";
    case "announcement":
      return "Канал объявлений";
    case "comments":
      return isDepartmentCommentsChat(chat) ? "Чат отдела" : "Комментарии";
    default:
      return "Диалог";
  }
}

export function getMemberRole(chat: Chat, userId: number): ChatMemberRole {
  if (chat.created_by === userId) return null;

  const membership = chat.memberships?.find((item) => item.user === userId);
  return membership?.role || "member";
}

export function getRoleLabel(role: ChatMemberRole): string {
  if (role === null) return "Владелец";

  switch (role) {
    case "admin":
      return "Админ";
    case "moderator":
      return "Модератор";
    case "member":
      return "Участник";
    case "guest":
      return "Гость";
    default:
      return "Участник";
  }
}

export function getRoleBadgeColor(role: ChatMemberRole): string {
  if (role === null) return "bg-purple-100 text-purple-700 ring-purple-200";

  switch (role) {
    case "admin":
      return "bg-red-100 text-red-700 ring-red-200";
    case "moderator":
      return "bg-blue-100 text-blue-700 ring-blue-200";
    case "member":
      return "bg-gray-100 text-gray-700 ring-gray-200";
    case "guest":
      return "bg-amber-100 text-amber-700 ring-amber-200";
    default:
      return "bg-gray-100 text-gray-700 ring-gray-200";
  }
}

export function getParticipantInitials(name?: string): string {
  return (
    (name || "?")
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0] || "")
      .join("")
      .toUpperCase() || "?"
  );
}
