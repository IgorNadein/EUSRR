"use client";

import Link from "next/link";

import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { displayUserName, userProfileLink } from "@/lib/shared";
import type { User } from "@/types/api";

type DepartmentPersonChipProps = {
  currentUserId?: number | null;
  person: User;
  subtitle?: string | null;
};

export function DepartmentPersonChip({
  currentUserId,
  person,
  subtitle,
}: DepartmentPersonChipProps) {
  const personName = displayUserName(person);
  const profileLink = userProfileLink(person, currentUserId);
  const fallback = (
    person.first_name?.[0] ||
    person.last_name?.[0] ||
    person.email?.[0] ||
    "?"
  ).toUpperCase();

  const content = (
    <>
      <RequestAvatar
        alt={personName}
        fallback={fallback}
        size="lg"
        src={person.avatar}
      />
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-[var(--foreground)]">
          {personName}
        </span>
        {subtitle ? (
          <span className="app-text-muted block truncate text-xs">{subtitle}</span>
        ) : null}
      </span>
    </>
  );

  const className =
    "app-badge inline-flex max-w-full items-center gap-2 rounded-full px-2.5 py-1.5";

  return profileLink ? (
    <Link href={profileLink} className={`${className} hover:bg-[var(--surface-tertiary)]`}>
      {content}
    </Link>
  ) : (
    <span className={className}>{content}</span>
  );
}
