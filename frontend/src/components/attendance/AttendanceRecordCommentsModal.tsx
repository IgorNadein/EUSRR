"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Camera, Loader2, MessageSquare, Send } from "lucide-react";

import { AttendanceRecordHeader } from "@/components/attendance/AttendanceRecordHeader";
import { CommentDeleteButton } from "@/components/shared/CommentControls";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { Modal } from "@/components/ui/Modal";
import { apiClient } from "@/lib/api";
import { displayUserName, formatDateTime } from "@/lib/shared";
import type { AttendanceRecordComment } from "@/lib/api/attendance";

export type AttendanceRecordCommentsPreview = {
  recordId: number;
  employeeName: string;
  date: string;
  statusLabel: string;
  displayText: string;
  detailLines?: string[];
  issues?: string[];
  isManuallyEdited?: boolean;
  commentsCount?: number;
};

type AttendanceRecordCommentsModalProps = {
  currentUserId?: number | null;
  isOpen: boolean;
  onClose: () => void;
  onCommentCountChange?: (recordId: number, count: number) => void;
  onOpenDayEvents?: (record: AttendanceRecordCommentsPreview) => void;
  record: AttendanceRecordCommentsPreview | null;
};

function getErrorMessage(error: unknown, fallback: string) {
  return String((error as Error)?.message || fallback);
}

function getAttendanceRecordComments(recordId: number) {
  const client = apiClient as typeof apiClient & {
    getAttendanceRecordComments?: (recordId: number) => Promise<AttendanceRecordComment[]>;
    request?: <T>(endpoint: string, options?: RequestInit) => Promise<T>;
  };

  if (typeof client.getAttendanceRecordComments === "function") {
    return client.getAttendanceRecordComments(recordId);
  }

  return client.request?.<AttendanceRecordComment[]>(
    `/api/v1/attendance/records/${recordId}/comments/`,
  ) ?? Promise.reject(new Error("Attendance comments API is unavailable"));
}

function addAttendanceRecordComment(recordId: number, text: string) {
  const client = apiClient as typeof apiClient & {
    addAttendanceRecordComment?: (
      recordId: number,
      text: string,
    ) => Promise<AttendanceRecordComment>;
    request?: <T>(endpoint: string, options?: RequestInit) => Promise<T>;
  };

  if (typeof client.addAttendanceRecordComment === "function") {
    return client.addAttendanceRecordComment(recordId, text);
  }

  return client.request?.<AttendanceRecordComment>(
    `/api/v1/attendance/records/${recordId}/comments/`,
    {
      method: "POST",
      body: JSON.stringify({ text }),
    },
  ) ?? Promise.reject(new Error("Attendance comments API is unavailable"));
}

function deleteAttendanceRecordComment(recordId: number, commentId: number) {
  const client = apiClient as typeof apiClient & {
    deleteAttendanceRecordComment?: (
      recordId: number,
      commentId: number,
    ) => Promise<void>;
    request?: <T>(endpoint: string, options?: RequestInit) => Promise<T>;
  };

  if (typeof client.deleteAttendanceRecordComment === "function") {
    return client.deleteAttendanceRecordComment(recordId, commentId);
  }

  return client.request?.<void>(
    `/api/v1/attendance/records/${recordId}/comments/${commentId}/`,
    { method: "DELETE" },
  ) ?? Promise.reject(new Error("Attendance comments API is unavailable"));
}

function commentAuthorName(comment: AttendanceRecordComment) {
  return displayUserName(comment.author) || comment.author?.email || "Сотрудник";
}

function commentFallback(comment: AttendanceRecordComment) {
  return (
    comment.author?.last_name?.[0] ||
    comment.author?.first_name?.[0] ||
    comment.author?.email?.[0] ||
    "К"
  ).toUpperCase();
}

export function AttendanceRecordCommentsModal({
  currentUserId,
  isOpen,
  onClose,
  onCommentCountChange,
  onOpenDayEvents,
  record,
}: AttendanceRecordCommentsModalProps) {
  const [comments, setComments] = useState<AttendanceRecordComment[]>([]);
  const [commentsLoaded, setCommentsLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);
  const [composerExpanded, setComposerExpanded] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const commentsBottomRef = useRef<HTMLDivElement | null>(null);
  const onCommentCountChangeRef = useRef(onCommentCountChange);
  const activeRecordId = record?.recordId;

  useEffect(() => {
    onCommentCountChangeRef.current = onCommentCountChange;
  }, [onCommentCountChange]);

  const reset = useCallback(() => {
    setDraft("");
    setError(null);
    setActionId(null);
    setCommentsLoaded(false);
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    requestAnimationFrame(() => {
      commentsBottomRef.current?.scrollIntoView({
        behavior: smooth ? "smooth" : "auto",
        block: "end",
      });
    });
  }, []);

  const loadComments = useCallback(async (recordId: number) => {
    try {
      setLoading(true);
      setCommentsLoaded(false);
      setError(null);
      const nextComments = await getAttendanceRecordComments(recordId);
      setComments(nextComments);
      setCommentsLoaded(true);
      onCommentCountChangeRef.current?.(recordId, nextComments.length);
    } catch (loadError) {
      setComments([]);
      setError(getErrorMessage(loadError, "Не удалось загрузить комментарии"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isOpen || !activeRecordId) return;
    reset();
    void loadComments(activeRecordId);
  }, [activeRecordId, isOpen, loadComments, reset]);

  useEffect(() => {
    if (!isOpen || loading) return;
    scrollToBottom(false);
  }, [comments.length, isOpen, loading, scrollToBottom]);

  useLayoutEffect(() => {
    const input = inputRef.current;
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
    if (!record) return;
    const text = draft.trim();
    if (!text) {
      setError("Введите текст комментария");
      return;
    }
    try {
      setSending(true);
      setError(null);
      const saved = await addAttendanceRecordComment(record.recordId, text);
      const nextComments = [...comments, saved];
      setComments(nextComments);
      setCommentsLoaded(true);
      setDraft("");
      onCommentCountChange?.(record.recordId, nextComments.length);
      scrollToBottom();
    } catch (submitError) {
      setError(getErrorMessage(submitError, "Не удалось отправить комментарий"));
    } finally {
      setSending(false);
    }
  }, [comments, draft, onCommentCountChange, record, scrollToBottom]);

  const deleteComment = useCallback(
    async (comment: AttendanceRecordComment) => {
      if (!record) return;
      try {
        setActionId(comment.id);
        await deleteAttendanceRecordComment(record.recordId, comment.id);
        const nextComments = comments.filter((item) => item.id !== comment.id);
        setComments(nextComments);
        setCommentsLoaded(true);
        onCommentCountChange?.(record.recordId, nextComments.length);
      } catch (deleteError) {
        setError(getErrorMessage(deleteError, "Не удалось удалить комментарий"));
      } finally {
        setActionId(null);
      }
    },
    [comments, onCommentCountChange, record],
  );

  const displayedCommentsCount = commentsLoaded
    ? comments.length
    : record?.commentsCount ?? comments.length;

  function openDayEvents() {
    if (!record || !onOpenDayEvents) return;
    onClose();
    onOpenDayEvents({
      ...record,
      commentsCount: displayedCommentsCount,
    });
  }

  return (
    <Modal
      isOpen={isOpen && !!record}
      onClose={onClose}
      title="Комментарии к посещению"
      size="lg"
      noPadding
    >
      {record ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0 space-y-4 px-4 pb-4 sm:px-6">
            <AttendanceRecordHeader
              actions={onOpenDayEvents ? (
                <button
                  type="button"
                  onClick={openDayEvents}
                  className="app-action-ghost inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium"
                >
                  <Camera size={15} />
                  Подробности события
                </button>
              ) : null}
              record={{
                ...record,
                commentsCount: displayedCommentsCount,
              }}
            />

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
                  <Loader2 className="mx-auto animate-spin text-[var(--muted-foreground)]" size={22} />
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
                    Добавьте пояснение к записи посещения.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {comments.map((comment) => {
                    const authorName = commentAuthorName(comment);
                    const isOwnComment = Boolean(
                      comment.author?.id &&
                        currentUserId &&
                        comment.author.id === currentUserId,
                    );
                    return (
                      <article
                        key={comment.id}
                        className="app-surface-muted rounded-xl p-3"
                      >
                        <div className="flex items-start gap-3">
                          <RequestAvatar
                            alt={authorName}
                            fallback={commentFallback(comment)}
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
                                  {formatDateTime(comment.created_at)}
                                </p>
                              </div>
                              {isOwnComment ? (
                                <CommentDeleteButton
                                  disabled={actionId === comment.id}
                                  onClick={() => void deleteComment(comment)}
                                />
                              ) : null}
                            </div>
                            <p className="app-text-wrap mt-2 text-sm leading-6 text-[var(--foreground)]">
                              {comment.text}
                            </p>
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
            <div className="flex items-end gap-2">
              <div
                className={`app-input min-w-0 flex-1 overflow-hidden shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] ${
                  composerExpanded ? "rounded-[1.5rem]" : "h-10 rounded-full"
                }`}
              >
                <textarea
                  ref={inputRef}
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
                  className={`w-full resize-none bg-transparent px-4 py-2.5 text-sm leading-5 text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)] ${
                    composerExpanded ? "rounded-[1.5rem]" : "rounded-full"
                  }`}
                />
              </div>

              <button
                type="button"
                onClick={() => void submitComment()}
                disabled={sending || !draft.trim()}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sky-500 text-white leading-none shadow-sm transition hover:bg-sky-600 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:border disabled:border-[var(--border-subtle)] disabled:bg-[var(--surface-secondary)] disabled:text-[var(--muted-foreground)] disabled:shadow-none"
                title="Отправить комментарий"
                aria-label="Отправить комментарий"
              >
                {sending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
