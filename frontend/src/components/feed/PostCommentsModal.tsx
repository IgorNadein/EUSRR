"use client";

import Image from "next/image";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ImageIcon, MessageSquare, Paperclip, Pencil, Send, Smile, X } from "lucide-react";
import { toast } from "sonner";

import { extractDepartmentApiErrorMessage } from "@/components/departments/api-error";
import { CommentDeleteButton } from "@/components/shared/CommentControls";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { Modal } from "@/components/ui/Modal";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import type { Comment, PaginatedResponse, Post } from "@/types/api";

type PostCommentsModalProps = {
  canDeleteComment?: (comment: Comment) => boolean;
  canEditComment?: (comment: Comment) => boolean;
  currentUserId?: number | null;
  isOpen: boolean;
  onClose: () => void;
  onCommentCountChange?: (postId: number, delta: number) => void;
  post: Post | null;
};

const ALL_REACTIONS = [
  "👍","❤️","😂","🔥","👏","🎉","😊","😉","😁","🤝",
  "🙏","😮","😢","😡","💯","✅","👀","🤔","😍","😎",
  "🤩","🥳","😴","🫡","👌","💪","🙌","🧠","💡","🚀",
  "🎯","⭐","✨","💩","🫶","🤗","😅","🤯","🥲","🫠",
];

function formatAuthorName(comment: Comment) {
  const firstName = comment.author?.first_name || "";
  const lastName = comment.author?.last_name || "";
  const fullName = `${lastName} ${firstName}`.trim();
  return fullName || comment.author?.email || "Сотрудник";
}

function formatCommentFallback(comment: Comment) {
  return (
    comment.author?.last_name?.[0] ||
    comment.author?.first_name?.[0] ||
    comment.author?.email?.[0] ||
    "К"
  ).toUpperCase();
}

function formatDate(value?: string) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function PostCommentsModal({
  canDeleteComment,
  canEditComment,
  currentUserId,
  isOpen,
  onClose,
  onCommentCountChange,
  post,
}: PostCommentsModalProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [draftImage, setDraftImage] = useState<File | null>(null);
  const [draftAttachment, setDraftAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editingCommentText, setEditingCommentText] = useState("");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);

  const attachmentRef = useRef<HTMLInputElement | null>(null);
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const commentsBottomRef = useRef<HTMLDivElement | null>(null);
  const [composerExpanded, setComposerExpanded] = useState(false);

  const postPreview = useMemo(() => {
    if (!post) return "";
    return (post.body || post.content || "").trim();
  }, [post]);

  const resetComposer = useCallback(() => {
    setDraft("");
    setDraftImage(null);
    setDraftAttachment(null);
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingCommentId(null);
    setEditingCommentText("");
  }, []);

  const scrollCommentsToBottom = useCallback((smooth = true) => {
    requestAnimationFrame(() => {
      commentsBottomRef.current?.scrollIntoView({
        behavior: smooth ? "smooth" : "auto",
        block: "end",
      });
    });
  }, []);

  const loadComments = useCallback(async () => {
    if (!post) return;

    try {
      setLoading(true);
      setError(null);
      const response = (await apiClient.getComments({
        post: post.id,
      })) as PaginatedResponse<Comment> | Comment[];
      const items = Array.isArray(response)
        ? response
        : Array.isArray(response?.results)
          ? response.results
          : [];
      setComments(items);
    } catch (loadError) {
      console.error("Не удалось загрузить комментарии публикации:", loadError);
      setError(
        extractDepartmentApiErrorMessage(
          loadError,
          "Не удалось загрузить комментарии",
        ),
      );
      setComments([]);
    } finally {
      setLoading(false);
    }
  }, [post]);

  useEffect(() => {
    if (!isOpen || !post) return;
    resetComposer();
    cancelEdit();
    setShowEmojiPicker(false);
    void loadComments();
  }, [cancelEdit, isOpen, loadComments, post, resetComposer]);

  useEffect(() => {
    if (!isOpen || loading) return;
    scrollCommentsToBottom(false);
  }, [comments.length, isOpen, loading, scrollCommentsToBottom]);

  useLayoutEffect(() => {
    const input = composerInputRef.current;
    if (!input) return;

    const minHeight = 38;
    const maxHeight = 128;

    input.style.height = "0px";
    const nextHeight = Math.min(input.scrollHeight, maxHeight);
    const resolvedHeight = Math.max(nextHeight, minHeight);

    input.style.height = `${resolvedHeight}px`;
    input.style.overflowY = input.scrollHeight > maxHeight ? "auto" : "hidden";
    setComposerExpanded(resolvedHeight > minHeight + 2);
  }, [draft]);

  const submitComment = useCallback(async () => {
    if (!post) return;

    const text = draft.trim();
    if (!text && !draftImage && !draftAttachment) {
      setError("Добавь текст, изображение или вложение");
      return;
    }

    try {
      setSending(true);
      setError(null);
      const created = (await apiClient.createComment(
        post.id,
        text || " ",
        draftImage || undefined,
        draftAttachment || undefined,
      )) as Comment;
      setComments((previous) => [...previous, created]);
      resetComposer();
      onCommentCountChange?.(post.id, 1);
      scrollCommentsToBottom();
    } catch (submitError) {
      console.error("Не удалось отправить комментарий:", submitError);
      setError(
        extractDepartmentApiErrorMessage(
          submitError,
          "Не удалось отправить комментарий",
        ),
      );
    } finally {
      setSending(false);
    }
  }, [
    draft,
    draftAttachment,
    draftImage,
    onCommentCountChange,
    post,
    resetComposer,
    scrollCommentsToBottom,
  ]);

  const beginEdit = useCallback((comment: Comment) => {
    setEditingCommentId(comment.id);
    setEditingCommentText((comment.text || comment.content || "").trim());
    if (error) setError(null);
  }, [error]);

  const saveEditedComment = useCallback(
    async (commentId: number) => {
      const text = editingCommentText.trim();
      if (!text) return;

      try {
        setActionId(commentId);
        setError(null);
        const updated = (await apiClient.updateComment(commentId, text)) as Comment;
        setComments((previous) =>
          previous.map((item) =>
            item.id === commentId ? { ...item, ...updated } : item,
          ),
        );
        cancelEdit();
      } catch (saveError) {
        console.error("Не удалось обновить комментарий:", saveError);
        setError(
          extractDepartmentApiErrorMessage(
            saveError,
            "Не удалось сохранить комментарий",
          ),
        );
      } finally {
        setActionId(null);
      }
    },
    [cancelEdit, editingCommentText],
  );

  const deleteComment = useCallback(
    async (comment: Comment) => {
      if (!post) return;

      try {
        setActionId(comment.id);
        await apiClient.deleteComment(comment.id);
        setComments((previous) =>
          previous.filter((item) => item.id !== comment.id),
        );
        onCommentCountChange?.(post.id, -1);
        if (editingCommentId === comment.id) {
          cancelEdit();
        }
      } catch (deleteError) {
        console.error("Не удалось удалить комментарий:", deleteError);
        toast.error(
          extractDepartmentApiErrorMessage(
            deleteError,
            "Не удалось удалить комментарий",
          ),
        );
      } finally {
        setActionId(null);
      }
    },
    [cancelEdit, editingCommentId, onCommentCountChange, post],
  );

  return (
    <Modal
      isOpen={isOpen && !!post}
      onClose={onClose}
      title="Комментарии"
      size="lg"
      noPadding
    >
      {post ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0 space-y-4 px-4 pb-4 sm:px-6">
            <section className="app-surface-muted rounded-xl p-4">
              <p className="app-card-caption">Публикация</p>
              <div className="mt-2 space-y-2">
                <h3 className="app-text-wrap text-base font-semibold text-[var(--foreground)]">
                  {post.title || "Без заголовка"}
                </h3>
                {postPreview ? (
                  <p className="app-text-wrap app-text-muted line-clamp-3 text-sm leading-6">
                    {postPreview}
                  </p>
                ) : null}
                <div className="app-text-muted flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                  <span>{formatDate(post.created_at)}</span>
                  <span>
                    Комментариев: {Math.max(comments.length, post.comments_count || 0)}
                  </span>
                </div>
              </div>
            </section>

            {error ? (
              <div className="app-feedback-danger rounded-xl p-3 text-sm">
                {error}
              </div>
            ) : null}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 sm:px-6">
            <section className="app-surface rounded-xl p-4">
              <div className="mb-3 flex items-center gap-2">
                <MessageSquare size={16} className="app-text-muted" />
                <p className="app-card-caption">Обсуждение</p>
              </div>

              {loading ? (
                <div className="py-8 text-center">
                  <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
                  <p className="app-text-muted mt-3 text-sm">
                    Загрузка комментариев...
                  </p>
                </div>
              ) : comments.length === 0 ? (
                <div className="app-surface-muted rounded-xl px-4 py-8 text-center">
                  <p className="text-sm font-medium text-[var(--foreground)]">
                    Комментариев пока нет
                  </p>
                  <p className="app-text-muted mt-2 text-sm">
                    Начни обсуждение первым.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {comments.map((comment) => {
                    const authorName = formatAuthorName(comment);
                    const commentText = (comment.text || comment.content || "").trim();
                    const isOwnComment = Boolean(
                      comment.author?.id &&
                        currentUserId &&
                        comment.author.id === currentUserId,
                    );
                    const allowEdit = canEditComment
                      ? canEditComment(comment)
                      : isOwnComment;
                    const allowDelete = canDeleteComment
                      ? canDeleteComment(comment)
                      : isOwnComment;

                    return (
                      <article
                        key={comment.id}
                        className="app-surface-muted rounded-xl p-3"
                      >
                        <div className="flex items-start gap-3">
                          <RequestAvatar
                            alt={authorName}
                            fallback={formatCommentFallback(comment)}
                            size="lg"
                            src={comment.author?.avatar}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-[var(--foreground)]">
                                  {authorName}
                                </p>
                                <p className="app-text-muted mt-0.5 text-xs">
                                  {formatDate(comment.created_at)}
                                </p>
                              </div>
                              {(allowEdit || allowDelete) ? (
                                <div className="flex items-center gap-1">
                                  {allowEdit ? (
                                    <button
                                      type="button"
                                      onClick={() => beginEdit(comment)}
                                      className="app-action-secondary inline-flex h-7 w-7 items-center justify-center rounded-lg"
                                      title="Редактировать комментарий"
                                      aria-label="Редактировать комментарий"
                                    >
                                      <Pencil size={14} />
                                    </button>
                                  ) : null}
                                  {allowDelete ? (
                                    <CommentDeleteButton
                                      disabled={actionId === comment.id}
                                      onClick={() => void deleteComment(comment)}
                                    />
                                  ) : null}
                                </div>
                              ) : null}
                            </div>

                            {editingCommentId === comment.id ? (
                              <div className="mt-3 space-y-2">
                                <textarea
                                  value={editingCommentText}
                                  onChange={(event) =>
                                    setEditingCommentText(event.target.value)
                                  }
                                  className="app-input min-h-24 w-full rounded-lg p-3 text-sm resize-none"
                                />
                                <div className="flex flex-wrap items-center justify-end gap-2">
                                  <button
                                    type="button"
                                    onClick={cancelEdit}
                                    className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium"
                                    disabled={actionId === comment.id}
                                  >
                                    Отмена
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void saveEditedComment(comment.id)}
                                    className="app-action-primary rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                                    disabled={
                                      actionId === comment.id ||
                                      !editingCommentText.trim()
                                    }
                                  >
                                    Сохранить
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                {commentText ? (
                                  <p className="app-text-wrap mt-2 text-sm leading-6 text-[var(--foreground)]">
                                    {commentText}
                                  </p>
                                ) : null}

                                {comment.image ? (
                                  <div className="mt-3 overflow-hidden rounded-xl">
                                    <Image
                                      src={resolveMediaUrl(comment.image)}
                                      alt="Изображение комментария"
                                      width={1200}
                                      height={720}
                                      className="max-h-64 w-full object-cover"
                                      unoptimized
                                    />
                                  </div>
                                ) : null}

                                {comment.attachment ? (
                                  <div className="mt-3">
                                    <a
                                      href={resolveMediaUrl(comment.attachment)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
                                    >
                                      <Paperclip size={14} />
                                      Открыть вложение
                                    </a>
                                  </div>
                                ) : null}
                              </>
                            )}
                          </div>
                        </div>
                      </article>
                    );
                  })}
                  <div ref={commentsBottomRef} />
                </div>
              )}
            </section>
          </div>

          <div className="app-surface-elevated shrink-0 border-t border-[var(--border-primary)] px-4 py-4 sm:px-6">
            <div className="space-y-3">
              {(draftImage || draftAttachment) ? (
                <div className="flex flex-wrap gap-2">
                  {draftImage ? (
                    <div className="app-badge app-badge-accent inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs">
                      <ImageIcon size={12} />
                      <span className="max-w-[14rem] truncate">{draftImage.name}</span>
                      <button
                        type="button"
                        onClick={() => setDraftImage(null)}
                        className="app-accent-text hover:text-[var(--accent-primary)]"
                        aria-label="Убрать изображение"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ) : null}
                  {draftAttachment ? (
                    <div className="app-badge inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs">
                      <Paperclip size={12} />
                      <span className="max-w-[14rem] truncate">
                        {draftAttachment.name}
                      </span>
                      <button
                        type="button"
                        onClick={() => setDraftAttachment(null)}
                        className="app-text-muted hover:text-[var(--foreground)]"
                        aria-label="Убрать вложение"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              <input
                ref={attachmentRef}
                type="file"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0] || null;
                  if (file?.type?.startsWith("image/")) {
                    setDraftImage(file);
                  } else {
                    setDraftAttachment(file);
                  }
                  event.target.value = "";
                  if (error) setError(null);
                }}
              />

              <div className="flex items-end gap-2">
                <div
                  className={`app-input relative min-w-0 flex-1 ${showEmojiPicker ? "overflow-visible" : "overflow-hidden"} shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] ${
                    composerExpanded ? "rounded-[1.5rem]" : "h-10 rounded-full"
                  }`}
                  data-composer-emoji="true"
                >
                  <button
                    type="button"
                    onClick={() => attachmentRef.current?.click()}
                    className={`app-icon-button absolute left-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-full ${
                      composerExpanded ? "bottom-2.5" : "top-1/2 -translate-y-1/2"
                    }`}
                    title="Прикрепить файл"
                    aria-label="Прикрепить файл"
                  >
                    <Paperclip size={14} />
                  </button>

                  <button
                    type="button"
                    onClick={() => setShowEmojiPicker((value) => !value)}
                    className={`app-icon-button absolute right-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-full ${
                      composerExpanded ? "bottom-2.5" : "top-1/2 -translate-y-1/2"
                    }`}
                    title="Смайлы"
                    aria-label="Открыть панель смайлов"
                    aria-expanded={showEmojiPicker}
                  >
                    <Smile size={14} />
                  </button>

                  {showEmojiPicker ? (
                    <div className="app-menu absolute bottom-full right-0 z-20 mb-2 w-[260px] rounded-xl p-2">
                      <div className="grid max-h-48 grid-cols-8 gap-1 overflow-y-auto">
                        {ALL_REACTIONS.map((emoji) => (
                          <button
                            key={`comment-composer-${emoji}`}
                            type="button"
                            onClick={() => {
                              setDraft((value) => `${value}${emoji}`);
                              setShowEmojiPicker(false);
                              if (error) setError(null);
                            }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-base transition hover:bg-sky-500/10"
                          >
                            {emoji}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <textarea
                    ref={composerInputRef}
                    value={draft}
                    onChange={(event) => {
                      setDraft(event.target.value);
                      if (error) setError(null);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void submitComment();
                      }
                    }}
                    rows={1}
                    placeholder="Введите комментарий..."
                    aria-label="Поле ввода комментария"
                    className={`w-full resize-none bg-transparent py-2.5 pl-11 pr-11 text-sm leading-5 text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)] ${
                      composerExpanded ? "rounded-[1.5rem]" : "rounded-full"
                    }`}
                  />
                </div>

                <button
                  type="button"
                  onClick={() => void submitComment()}
                  disabled={sending || (!draft.trim() && !draftImage && !draftAttachment)}
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sky-500 text-white leading-none shadow-sm shadow-sky-200/70 transition hover:bg-sky-600 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:border disabled:border-gray-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:shadow-none disabled:opacity-100"
                  title="Отправить комментарий"
                  aria-label="Отправить комментарий"
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
