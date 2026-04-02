/**
 * Shared user display helpers used across list pages.
 */
import type { User } from "@/types/api";

export function displayUserName(
  person?: User | number | null,
  fallbackName?: string | null,
  fallbackEmail?: string | null,
): string {
  if (fallbackName) return fallbackName;
  if (!person) return fallbackEmail || "—";
  if (typeof person === "number") return fallbackEmail || `Пользователь #${person}`;
  const full = `${person.last_name || ""} ${person.first_name || ""}`.trim();
  return (
    full ||
    (person as unknown as Record<string, string>)?.full_name ||
    (person as unknown as Record<string, string>)?.display_name ||
    person.email ||
    fallbackEmail ||
    "Пользователь"
  );
}

export function userProfileLink(
  person: User | null | undefined,
  currentUserId: number | null | undefined,
): string {
  if (!person?.id) return "";
  if (currentUserId && person.id === currentUserId) return "/profile";
  return `/users/${person.id}`;
}
