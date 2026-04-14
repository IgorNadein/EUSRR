"use client";

import Image from "next/image";
import type { ReactNode } from "react";
import { Heart, MessageSquare, Paperclip, Pin } from "lucide-react";

import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { resolveMediaUrl } from "@/lib/url";
import type { Post } from "@/types/api";

type FeedPostCardProps = {
  post: Post;
  authorSubtitle: ReactNode;
  attachmentButtonClassName?: string;
  commentsButtonClassName?: string;
  footerAction?: ReactNode;
  headerActions?: ReactNode;
  imageSrc?: string;
  isLikeActive?: boolean;
  likeButtonClassName?: string;
  likeDisabled?: boolean;
  likesPopover?: ReactNode;
  likesWrapperProps?: {
    onMouseEnter?: () => void;
    onMouseLeave?: () => void;
  };
  onLikeToggle?: (post: Post) => void;
  onOpenComments: (post: Post) => void;
  pinMarkerTitle?: string;
  pinnedStyle?: "inline" | "badge" | "none";
};

function formatAuthorName(post: Post) {
  const firstName = post.author?.first_name || "";
  const lastName = post.author?.last_name || "";
  const fullName = `${lastName} ${firstName}`.trim();
  return fullName || post.author?.email || "Сотрудник";
}

function formatAuthorFallback(post: Post) {
  return (
    post.author?.last_name?.[0] ||
    post.author?.first_name?.[0] ||
    post.author?.email?.[0] ||
    "П"
  ).toUpperCase();
}

export function FeedPostCard({
  post,
  authorSubtitle,
  attachmentButtonClassName,
  commentsButtonClassName = "app-action-ghost flex items-center gap-2 rounded-lg px-3 py-2",
  footerAction,
  headerActions,
  imageSrc,
  isLikeActive = false,
  likeButtonClassName,
  likeDisabled = false,
  likesPopover,
  likesWrapperProps,
  onLikeToggle,
  onOpenComments,
  pinMarkerTitle = "Закрепленная публикация",
  pinnedStyle = "inline",
}: FeedPostCardProps) {
  const authorName = formatAuthorName(post);
  const authorFallback = formatAuthorFallback(post);
  const postText = (post.body || post.content || "").trim();
  const resolvedImageSrc = resolveMediaUrl(imageSrc || post.image);
  const attachmentHref = resolveMediaUrl(post.attachment || post.attachment_url);
  const resolvedLikeButtonClassName =
    likeButtonClassName ||
    `flex items-center gap-2 rounded-lg px-3 py-2 transition ${
      isLikeActive
        ? "app-action-ghost text-[var(--accent-primary)]"
        : "app-action-ghost"
    }`;

  return (
    <article id={`post-${post.id}`} className="app-surface rounded-2xl p-5">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <RequestAvatar
            alt={authorName}
            fallback={authorFallback}
            size="lg"
            src={post.author?.avatar}
          />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--foreground)]">
              {authorName}
            </p>
            <div className="app-text-muted flex items-center gap-1.5 text-xs">
              {authorSubtitle}
              {pinnedStyle === "inline" && post.pinned ? (
                <span
                  className="app-accent-text inline-flex items-center justify-center"
                  title={pinMarkerTitle}
                  aria-label={pinMarkerTitle}
                >
                  <Pin size={12} className="shrink-0 fill-current" />
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-start gap-2">
          {pinnedStyle === "badge" && post.pinned ? (
            <span className="app-badge inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
              <Pin size={12} className="app-accent-text fill-current" />
              Закреплено
            </span>
          ) : null}
          {headerActions}
        </div>
      </header>

      {post.title ? (
        <h3 className="app-text-wrap mb-1 text-base font-semibold text-[var(--foreground)]">
          {post.title}
        </h3>
      ) : null}

      {postText ? (
        <p className="app-text-wrap whitespace-pre-line text-sm leading-6 text-[var(--foreground)]">
          {postText}
        </p>
      ) : null}

      {resolvedImageSrc ? (
        <div className="mt-3 overflow-hidden rounded-xl">
          <Image
            src={resolvedImageSrc}
            alt={post.title || "Публикация"}
            width={1200}
            height={720}
            className="max-h-72 w-full object-cover"
            unoptimized
          />
        </div>
      ) : null}

      <div className="app-text-muted mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        <div className="flex items-center gap-4 text-sm">
          <div className="relative" {...likesWrapperProps}>
            {onLikeToggle ? (
              <button
                type="button"
                disabled={likeDisabled}
                onClick={() => onLikeToggle(post)}
                className={resolvedLikeButtonClassName}
              >
                <Heart
                  size={16}
                  className={
                    isLikeActive
                      ? "fill-[var(--accent-primary)] text-[var(--accent-primary)]"
                      : "app-text-muted"
                  }
                />
                {post.likes_count || 0}
              </button>
            ) : (
              <span className="inline-flex items-center gap-2">
                <Heart size={16} />
                {post.likes_count || 0}
              </span>
            )}
            {likesPopover}
          </div>

          <button
            type="button"
            onClick={() => onOpenComments(post)}
            className={commentsButtonClassName}
          >
            <MessageSquare size={16} className="app-text-muted" />
            {post.comments_count || 0}
          </button>

          {attachmentHref ? (
            <a
              href={attachmentHref}
              target="_blank"
              rel="noopener noreferrer"
              className={
                attachmentButtonClassName ||
                "app-action-ghost inline-flex items-center gap-2 rounded-lg px-3 py-2"
              }
            >
              <Paperclip size={16} className="app-text-muted" />
              Вложение
            </a>
          ) : null}
        </div>

        {footerAction}
      </div>
    </article>
  );
}
