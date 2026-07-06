import Link from "next/link";
import {
  defaultStatusMeta,
  requestTypeLabels,
  statusMeta,
  type RequestAttachmentPreview,
} from "@/hooks/useRequestsPage";
import { displayUserName, formatDate, userProfileLink } from "@/lib/shared";
import type { Request, RequestComment, User } from "@/types/api";
import {
  Ban,
  ChevronDown,
  ChevronRight,
  Link2,
  MessageSquare,
  Paperclip,
  Pencil,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import type { Ref } from "react";
import { CommentComposer, CommentDeleteButton } from "@/components/shared/CommentControls";
import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import { RequestAvatar } from "./RequestAvatar";
import { getRequestActionState } from "./requestActions";
import { RequestUserBadge } from "./RequestUserBadge";

type RequestListItemProps = {
  busyKey: string | null;
  commentDraft: string;
  comments: RequestComment[];
  commentsOpen: boolean;
  currentUserId?: number | null;
  departmentNameMap: Map<number, string>;
  isFinal: (status?: string) => boolean;
  isMenuOpen: boolean;
  menuRef?: Ref<HTMLDivElement> | null;
  onAddComment: (requestId: number) => void | Promise<void>;
  onApprove: (requestId: number) => void | Promise<void>;
  onCancel: (requestId: number) => void | Promise<void>;
  onDelete: (requestId: number) => void | Promise<void>;
  onDeleteComment: (requestId: number, commentId: number) => void | Promise<void>;
  onEdit: (request: Request) => void;
  onLinkTask: (request: Request) => void;
  onOpenDetails: (request: Request) => void;
  onPreviewAttachment: (preview: RequestAttachmentPreview) => void;
  onReject: (requestId: number) => void | Promise<void>;
  onSetCommentDraft: (requestId: number, value: string) => void;
  onToggleComments: (requestId: number) => void | Promise<void>;
  onToggleMenu: (requestId: number | null) => void;
  onToggleRow: (requestId: number) => void;
  request: Request;
  rowOpen: boolean;
};

function renderDecisionMaker(decisionMaker: User | undefined, currentUserId?: number | null) {
  if (!decisionMaker) return <span className="app-text-muted">—</span>;

  return <RequestUserBadge person={decisionMaker} currentUserId={currentUserId} />;
}

export function RequestListItem({
  busyKey,
  commentDraft,
  comments,
  commentsOpen,
  currentUserId,
  departmentNameMap,
  isFinal,
  isMenuOpen,
  menuRef = null,
  onAddComment,
  onApprove,
  onCancel,
  onDelete,
  onDeleteComment,
  onEdit,
  onLinkTask,
  onOpenDetails,
  onPreviewAttachment,
  onReject,
  onSetCommentDraft,
  onToggleComments,
  onToggleMenu,
  onToggleRow,
  request,
  rowOpen,
}: RequestListItemProps) {
  const requestAuthor = request.employee || request.created_by;
  const authorName = displayUserName(requestAuthor);
  const authorFallback = (requestAuthor?.first_name?.[0] || requestAuthor?.last_name?.[0] || "?").toUpperCase();
  const actionState = getRequestActionState(request, currentUserId, isFinal);
  const { canCancel, canComment, canDelete, canEdit, canProcess, hasSecondaryActions, statusKey } = actionState;
  const typeKey = String(request.type || request.request_type || "").toLowerCase();
  const status = statusMeta[statusKey] ?? defaultStatusMeta;
  const authorLink = requestAuthor ? userProfileLink(requestAuthor, currentUserId) : null;
  const typeLabel = requestTypeLabels[typeKey] || String(request.type || request.request_type || "Другое");
  const title = request.display_title || request.title || "Без заголовка";
  const departmentLabels = (request.departments || [])
    .map((id) => departmentNameMap.get(Number(id)) || `Отдел #${id}`)
    .join(", ");
  const recipients = request.recipients || [];
  const ccUsers = request.cc_users || [];
  const summary = request.comment || request.description;
  const attachmentUrl = request.attachment_url || request.attachment || "";
  const attachmentName = attachmentUrl
    ? decodeURIComponent(attachmentUrl.split("/").pop() || "Вложение")
    : "";
  const commentCount = request.comments_count ?? comments.length;
  const decisionMaker = request.approver || request.assigned_to;
  const linkedTasks = request.linked_tasks || [];
  const hasMenuActions = hasSecondaryActions || Boolean(onLinkTask);

  return (
    <article
      className={`app-surface-muted rounded-xl transition hover:border-[var(--border-strong)] ${isMenuOpen ? "relative z-20 overflow-visible" : "overflow-hidden"}`}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex shrink-0 flex-col items-center gap-3 pt-0.5">
            <button
              type="button"
              onClick={() => onToggleRow(request.id)}
              className="app-action-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg transition"
            >
              <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
            </button>
            <button
              type="button"
              title={canComment ? `Комментарии (${commentCount})` : "Комментарии для черновика недоступны"}
              onClick={() => canComment && void onToggleComments(request.id)}
              disabled={!canComment}
              className="app-action-secondary relative inline-flex h-8 w-8 items-center justify-center rounded-lg disabled:cursor-not-allowed disabled:opacity-50"
            >
              <MessageSquare size={15} />
              {commentCount > 0 ? (
                <span className="app-counter absolute -right-1.5 -top-1.5 flex h-4 min-w-4 px-1 text-[10px] font-bold">
                  {commentCount}
                </span>
              ) : null}
            </button>
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex items-center gap-2">
                  {authorLink ? (
                    <Link href={authorLink} className="group flex min-w-0 items-center gap-2">
                      <RequestAvatar
                        alt={authorName}
                        fallback={authorFallback}
                        size="lg"
                        src={requestAuthor?.avatar}
                      />
                      <span className="truncate text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--accent-primary-strong)]">
                        {authorName}
                      </span>
                    </Link>
                  ) : (
                    <div className="flex min-w-0 items-center gap-2">
                      <RequestAvatar
                        alt={authorName}
                        fallback={authorFallback}
                        size="lg"
                      />
                      <span className="truncate text-sm font-medium text-[var(--foreground)]">{authorName}</span>
                    </div>
                  )}
                </div>

                <button type="button" onClick={() => onOpenDetails(request)} className="block w-full text-left">
                  <h3
                    className={`${rowOpen ? "app-text-wrap line-clamp-3" : "truncate"} text-sm font-semibold text-[var(--foreground)] transition hover:text-[var(--accent-primary-strong)]`}
                  >
                    <span className="app-text-muted">{typeLabel}:</span>{" "}
                    <span className="text-[var(--foreground)]">{title}</span>
                  </h3>
                </button>

                <div className="app-text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span>
                    Период: {request.date_from ? formatDate(request.date_from) : "—"}
                    {request.date_to ? ` — ${formatDate(request.date_to)}` : ""}
                  </span>
                </div>
              </div>

              <div className="shrink-0">
                <div ref={isMenuOpen ? menuRef : null} className="flex items-center justify-end gap-2">
                  <span className={`app-status-pill ${status.className}`}>
                    {status.label}
                  </span>
                  {hasMenuActions ? (
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => onToggleMenu(isMenuOpen ? null : request.id)}
                        className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-lg"
                        title="Действия с заявлением"
                        aria-label="Действия с заявлением"
                        aria-expanded={isMenuOpen}
                        aria-haspopup="menu"
                      >
                        <ChevronRight
                          size={15}
                          className={`transition-transform duration-200 ${isMenuOpen ? "rotate-90" : ""}`}
                        />
                      </button>
                      {isMenuOpen ? (
                        <div className="app-menu absolute right-0 top-full z-20 mt-2 w-44 rounded-xl py-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              onToggleMenu(null);
                              onLinkTask(request);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                            <Link2 size={14} />
                            Связать с задачей
                          </button>
                          {canCancel ? (
                            <button
                              type="button"
                              disabled={busyKey === `cancel-${request.id}`}
                              onClick={() => {
                                onToggleMenu(null);
                                void onCancel(request.id);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                            >
                              <Ban size={14} />
                              Отменить
                            </button>
                          ) : null}
                          {canEdit ? (
                            <button
                              type="button"
                              onClick={() => {
                                onToggleMenu(null);
                                onEdit(request);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                            >
                              <Pencil size={14} />
                              Редактировать
                            </button>
                          ) : null}
                          {canDelete ? (
                            <button
                              type="button"
                              disabled={busyKey === `delete-${request.id}`}
                              onClick={() => {
                                onToggleMenu(null);
                                void onDelete(request.id);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                            >
                              <Trash2 size={14} />
                              Удалить
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            {summary ? (
              <p
                className={`${rowOpen ? "app-text-wrap line-clamp-10" : "app-text-wrap line-clamp-3"} mt-3 text-sm text-[var(--foreground)]`}
              >
                {summary}
              </p>
            ) : null}

            {linkedTasks.length > 0 ? (
              <div className={`${summary ? "mt-3" : "mt-2"} flex flex-wrap gap-1.5`}>
                {linkedTasks.slice(0, 3).map((task) => (
                  <TaskLinkPill
                    key={task.link_id || task.id}
                    task={task}
                    maxTitleClassName="max-w-44"
                  />
                ))}
                {linkedTasks.length > 3 ? (
                  <span className="app-badge rounded-full px-2 py-1 text-[11px] font-medium">
                    +{linkedTasks.length - 3}
                  </span>
                ) : null}
              </div>
            ) : null}

            {canProcess ? (
              <div className={`${summary || linkedTasks.length > 0 ? "mt-3" : "mt-2"} flex flex-wrap items-center gap-1.5`}>
                <span className="ml-auto inline-flex items-center gap-2">
                  <button
                    type="button"
                    title="Одобрить"
                    onClick={() => void onApprove(request.id)}
                    disabled={busyKey === `approve-${request.id}`}
                    className="app-action-approve inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"
                  >
                    <ThumbsUp size={18} className="text-emerald-500" />
                  </button>
                  <button
                    type="button"
                    title="Отклонить"
                    onClick={() => void onReject(request.id)}
                    disabled={busyKey === `reject-${request.id}`}
                    className="app-action-reject inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"
                  >
                    <ThumbsDown size={18} />
                  </button>
                </span>
              </div>
            ) : null}
          </div>
        </div>

        {(rowOpen || commentsOpen) ? (
          <div className="app-surface-elevated mt-4 rounded-xl p-4">
            {commentsOpen ? (
              <div className={rowOpen ? "app-surface rounded-xl p-3" : "app-surface rounded-xl p-3"}>
                <div className="space-y-2">
                  {comments.length === 0 ? (
                    <p className="app-text-muted text-xs">Комментариев пока нет</p>
                  ) : (
                    comments.map((comment) => (
                      <div
                        key={comment.id}
                        className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]"
                      >
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="font-medium">{displayUserName(comment.author)}</span>
                          <div className="flex items-center gap-2">
                            <span className="app-text-muted">{formatDate(comment.created_at)}</span>
                            {Boolean(comment.author?.id && currentUserId === comment.author.id) ? (
                              <CommentDeleteButton
                                onClick={() => onDeleteComment(request.id, comment.id)}
                              />
                            ) : null}
                          </div>
                        </div>
                        <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
                      </div>
                    ))
                  )}
                </div>
                <div className="mt-2">
                  <CommentComposer
                    value={commentDraft}
                    onChange={(value) => onSetCommentDraft(request.id, value)}
                    onSubmit={() => onAddComment(request.id)}
                    disabled={busyKey === `comment-${request.id}`}
                  />
                </div>
              </div>
            ) : null}

            {rowOpen ? (
              <div className={`${commentsOpen ? "mt-3" : ""} space-y-3 text-xs`}>
                <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                  <div>
                    <span className="app-text-muted">Создано:</span>{" "}
                    <span className="font-medium text-[var(--foreground)]">
                      {formatDate(request.created_at) || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="app-text-muted">Обновлено:</span>{" "}
                    <span className="font-medium text-[var(--foreground)]">
                      {formatDate(request.updated_at) || "—"}
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="grid grid-cols-[104px_minmax(0,1fr)] items-start gap-2">
                    <span className="app-text-muted pt-1">Принял решение:</span>
                    <div className="min-w-0">
                      {renderDecisionMaker(decisionMaker, currentUserId)}
                    </div>
                  </div>

                  <div className="grid grid-cols-[104px_minmax(0,1fr)] items-start gap-2">
                    <span className="app-text-muted pt-1">Получатели:</span>
                    <div className="flex min-w-0 flex-wrap gap-1.5">
                      {recipients.slice(0, 2).map((recipient) => (
                        <RequestUserBadge
                          key={recipient.id}
                          person={recipient}
                          currentUserId={currentUserId}
                        />
                      ))}
                      {recipients.length === 0 ? (
                        <span className="app-text-muted pt-1">{request.recipient_count ?? 0}</span>
                      ) : null}
                      {recipients.length > 2 ? (
                        <span className="app-badge px-2 py-1 text-xs font-medium">
                          +{recipients.length - 2}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="grid grid-cols-[104px_minmax(0,1fr)] items-start gap-2">
                    <span className="app-text-muted pt-1">В копии:</span>
                    <div className="flex min-w-0 flex-wrap gap-1.5">
                      {ccUsers.slice(0, 2).map((ccUser) => (
                        <RequestUserBadge
                          key={ccUser.id}
                          person={ccUser}
                          currentUserId={currentUserId}
                        />
                      ))}
                      {ccUsers.length === 0 ? <span className="app-text-muted pt-1">—</span> : null}
                      {ccUsers.length > 2 ? (
                        <span className="app-badge px-2 py-1 text-xs font-medium">
                          +{ccUsers.length - 2}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {departmentLabels ? (
                    <div className="grid grid-cols-[104px_minmax(0,1fr)] items-start gap-2">
                      <span className="app-text-muted pt-1">Отделы:</span>
                      <span className="pt-1 font-medium text-[var(--foreground)]">{departmentLabels}</span>
                    </div>
                  ) : null}

                  {attachmentUrl ? (
                    <div className="grid grid-cols-[104px_minmax(0,1fr)] items-start gap-2">
                      <span className="app-text-muted pt-1">Вложение:</span>
                      <button
                        type="button"
                        onClick={() => onPreviewAttachment({ url: attachmentUrl, name: attachmentName })}
                        className="app-badge app-badge-accent inline-flex min-w-0 max-w-full items-center gap-1.5 px-2.5 py-1 text-xs font-medium"
                      >
                        <Paperclip size={13} className="shrink-0" />
                        <span className="truncate">{attachmentName}</span>
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
