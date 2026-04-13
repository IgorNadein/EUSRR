import Link from "next/link";
import { displayUserName, userProfileLink } from "@/lib/shared";
import type { User } from "@/types/api";
import { RequestAvatar } from "./RequestAvatar";

type RequestUserBadgeProps = {
  currentUserId?: number | null;
  large?: boolean;
  person: User;
};

export function RequestUserBadge({
  currentUserId,
  large = false,
  person,
}: RequestUserBadgeProps) {
  const personLink = userProfileLink(person, currentUserId);
  const personName = displayUserName(person);
  const fallback = (person.first_name?.[0] || person.last_name?.[0] || "?").toUpperCase();
  const chip = (
    <>
      <RequestAvatar
        alt={personName}
        fallback={fallback}
        size={large ? "md" : "sm"}
        src={person.avatar}
      />
      <span className="break-words">{personName}</span>
    </>
  );

  const className = `app-badge inline-flex max-w-full items-center gap-2 rounded-full ${large ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs"} font-medium`;

  return personLink
    ? <Link href={personLink} className={`${className} hover:bg-[var(--surface-tertiary)]`}>{chip}</Link>
    : <span className={className}>{chip}</span>;
}
