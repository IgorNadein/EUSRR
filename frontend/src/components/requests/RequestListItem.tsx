import Link from "next/link";
import {
  defaultStatusMeta,
  requestTypeLabels,
  statusMeta,
  type RequestAttachmentPreview,
} from "@/hooks/useRequestsPage";
import { displayUserName, formatDate, formatDateTime, userProfileLink } from "@/lib/shared";
import type { Request, RequestComment, User } from "@/types/api";
import { Ban, ChevronDown, ChevronRight, MessageSquare, Paperclip, Pencil, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react";
import type { ReactNode, Ref } from "react";
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

type RequestMetaFieldProps = {
  label: string;
  value: ReactNode;
};

type RequestAudienceRowProps = {
  count?: number;
  currentUserId?: number | null;
  emptyText: string;
  label: string;
  people: User[];
};

function RequestMetaField({ label, value }: RequestMetaFieldProps) {
  return (
    <div className="space-y-1">
      <p className="app-text-muted text-[11px] font-medium uppercase tracking-wide">{label}</p>
      <div className="text-sm text-[var(--foreground)]">{value}</div>
    </div>
  );
}

function RequestAudienceRow({
  count,
  currentUserId,
  emptyText,
  label,
  people,
}: RequestAudienceRowProps) {
  return (
    <div className="space-y-2">
      <p className="app-text-muted text-[11px] font-medium uppercase tracking-wide">{label}</p>
      {people.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {people.slice(0, 2).map((person) => (
            <RequestUserBadge
              key={person.id}
              person={person}
              currentUserId={currentUserId}
            />
          ))}
          {people.length > 2 ? (
            <span className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
              +{people.length - 2}
            </span>
          ) : null}
        </div>
      ) : (
        <p className="app-text-muted text-sm">{count ? count : emptyText}</p>
      )}
    </div>
  );
}

function renderDecisionMaker(decisionMaker: User | undefined, currentUserId?: number | null) {
  if (!decisionMaker) {
    return <span className="app-text-muted">-</span>;
  }

  const decisionMakerLink = userProfileLink(decisionMaker, currentUserId);
  const decisionMakerName = displayUserName(decisionMaker);

  return decisionMakerLink ? (
    <Link href={decisionMakerLink} className="app-link-accent font-medium">
      {decisionMakerName}
    </Link>
  ) : (
    <span className="font-medium text-[var(--foreground)]">{decisionMakerName}</span>
  );
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
  const authorLink = requestAuthor ? userProfileLink(requestAuthor, currentUserId) : null;
  const statusKey = String(request.status || "").toLowerCase();
  const status = statusMeta[statusKey] ?? defaultStatusMeta;
  const typeKey = String(request.type || request.request_type || "").toLowerCase();
  const typeLabel = requestTypeLabels[typeKey] || String(request.type || request.request_type || "Другое");
  const title = request.display_title || request.title || "Без заголовка";
  const canProcess = Boolean(statusKey === "pending" && request.can_decide);
  const isAuthor = Boolean(requestAuthor?.id && currentUserId && requestAuthor.id === currentUserId);
  const canCancel = Boolean(isAuthor && !isFinal(statusKey));
  const canEdit = Boolean(isAuthor && !isFinal(statusKey));
  const canDelete = Boolean(isAuthor && !isFinal(statusKey));
  const hasSecondaryActions = canCancel || canEdit || canDelete;
  const canComment = statusKey !== "draft";
  const summary = request.comment || request.description;
  const commentCount = request.comments_count ?? comments.length;
  const trimmedCommentDraft = commentDraft.trim();
  const recipients = request.recipients || [];
  const ccUsers = request.cc_users || [];
  const decisionMaker = request.approver || request.assigned_to;
  const departmentLabels = (request.departments || [])
    .map((id) => departmentNameMap.get(Number(id)) || `Отдел #${id}`)
    .join(", ");
  const attachmentUrl = request.attachment_url || request.attachment || "";
  const attachmentName = attachmentUrl
    ? decodeURIComponent(attachmentUrl.split("/").pop() || "Вложение")
    : "";
  const hasExpandedPanels = rowOpen || commentsOpen;

  return (
    <article
      className={`app-surface-muted rounded-xl border border-transparent transition hover:border-[var(--border-strong)] ${isMenuOpen ? "relative z-20 overflow-visible" : "overflow-hidden"}`}
    >
      <div className="p-4 sm:p-5">
        <div className="flex items-start gap-4">
          <div className="app-surface flex shrink-0 flex-col items-center gap-2 rounded-xl p-1.5">
            <button
              type="button"
              onClick={() => onToggleRow(request.id)}
              className={`inline-flex h-8 w-8 items-center justify-center rounded-lg transition ${rowOpen ? "app-selected app-accent-text" : "app-action-secondary"}`}
              title={rowOpen ? "Скрыть подробности" : "Показать подробности"}
              aria-expanded={rowOpen}
              aria-label={rowOpen ? "Скрыть подробности" : "Показать подробности"}
            >
              <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
            </button>
            <button
              type="button"
              title={canComment ? `Комментарии (${commentCount})` : "Комментарии для черновика недоступны"}
              onClick={() => canComment && void onToggleComments(request.id)}
              disabled={!canComment}
              className={`relative inline-flex h-8 w-8 items-center justify-center rounded-lg transition disabled:cursor-not-allowed disabled:opacity-50 ${commentsOpen ? "app-selected app-accent-text" : "app-action-secondary"}`}
            >
              <MessageSquare size={15} />
              {commentCount > 0 ? (
                <span className="app-counter absolute -right-1.5 -top-1.5 flex h-4 min-w-4 px-1 text-[10px] font-bold">
                  {commentCount}
                </span>
              ) : null}
            </button>
          </div>

          <div className="min-w-0 flex-1 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  {authorLink ? (
                    <Link href={authorLink} className="group flex min-w-0 items-center gap-2">
                      {requestAuthor?.avatar ? (
                        <img
                          src={requestAuthor.avatar}
                          alt={authorName}
                          className="app-avatar-frame h-8 w-8 shrink-0 rounded-full object-cover"
                        />
                      ) : (
                        <span className="app-avatar-fallback flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold">
                          {(requestAuthor?.first_name?.[0] || requestAuthor?.last_name?.[0] || "?").toUpperCase()}
                        </span>
                      )}
                      <span className="truncate text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--accent-primary-strong)]">
                        {authorName}
                      </span>
                    </Link>
                  ) : (
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="app-badge flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold">?</span>
                      <span className="truncate text-sm font-medium text-[var(--foreground)]">{authorName}</span>
                    </div>
                  )}
                  <span className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
                    {typeLabel}
                  </span>
                </div>

                <div className="space-y-2">
                  <button type="button" onClick={() => onOpenDetails(request)} className="block w-full text-left">
                    <h3 className={`${rowOpen ? "app-text-wrap line-clamp-3" : "truncate"} text-sm font-semibold text-[var(--foreground)] transition hover:text-[var(--accent-primary-strong)]`}>
                      {title}
                    </h3>
                  </button>

                  <div className="app-text-muted flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                    <span>
                      Период: {request.date_from ? formatDate(request.date_from) : "-"}
                      {request.date_to ? ` - ${formatDate(request.date_to)}` : ""}
                    </span>
                    <span>Создано: {formatDate(request.created_at) || "-"}</span>
                    {departmentLabels ? <span>Отделы: {departmentLabels}</span> : null}
                  </div>
                </div>

                {summary ? (
                  <p className={`${rowOpen ? "app-text-wrap line-clamp-10" : "app-text-wrap line-clamp-3"} text-sm leading-relaxed text-[var(--foreground)]`}>
                    {summary}
                  </p>
                ) : null}
              </div>

              <div className="flex shrink-0 flex-col items-end gap-2">
                <div ref={isMenuOpen ? menuRef : null} className="flex items-center justify-end gap-2">
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs ring-1 ${status.className}`}>
                    {status.label}
                  </span>
                  {hasSecondaryActions ? (
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

                {canProcess ? (
                  <div className="app-surface flex items-center gap-1 rounded-xl p-1">
                    <button
                      type="button"
                      title="Одобрить"
                      onClick={() => void onApprove(request.id)}
                      disabled={busyKey === `approve-${request.id}`}
                      className="app-feedback-success inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"
                    >
                      <ThumbsUp size={18} />
                    </button>
                    <button
                      type="button"
                      title="Отклонить"
                      onClick={() => void onReject(request.id)}
                      disabled={busyKey === `reject-${request.id}`}
                      className="app-action-danger inline-flex items-center justify-center rounded-lg p-2 disabled:opacity-60"
                    >
                      <ThumbsDown size={18} />
                    </button>
                  </div>
                ) : null}
              </div>
            </div>

            {hasExpandedPanels ? (
              <div className="space-y-3 border-t border-[var(--border-subtle)] pt-4">
                {rowOpen ? (
                  <section className="app-surface-elevated rounded-xl p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Подробности</p>
                      {attachmentUrl ? (
                        <button
                          type="button"
                          onClick={() => onPreviewAttachment({ url: attachmentUrl, name: attachmentName })}
                          className="app-action-secondary inline-flex min-w-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium"
                        >
                          <Paperclip size={13} className="shrink-0" />
                          <span className="truncate">{attachmentName}</span>
                        </button>
                      ) : null}
                    </div>

                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                      <div className="app-surface rounded-xl p-3">
                        <div className="space-y-3">
                          <RequestMetaField
                            label="Принял решение"
                            value={renderDecisionMaker(decisionMaker, currentUserId)}
                          />
                          <RequestMetaField
                            label="Создано"
                            value={formatDateTime(request.created_at) || "-"}
                          />
                          <RequestMetaField
                            label="Обновлено"
                            value={formatDateTime(request.updated_at) || "-"}
                          />
                          <RequestMetaField
                            label="Отделы"
                            value={departmentLabels || <span className="app-text-muted">-</span>}
                          />
                        </div>
                      </div>

                      <div className="app-surface rounded-xl p-3">
                        <div className="space-y-3">
                          <RequestAudienceRow
                            label="Получатели"
                            people={recipients}
                            count={request.recipient_count}
                            currentUserId={currentUserId}
                            emptyText="-"
                          />
                          <RequestAudienceRow
                            label="В копии"
                            people={ccUsers}
                            currentUserId={currentUserId}
                            emptyText="-"
                          />
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}

                {commentsOpen ? (
                  <section className="app-surface-elevated rounded-xl p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Комментарии</p>
                      <span className="app-badge inline-flex rounded-full px-2.5 py-1 text-xs font-medium">
                        {commentCount}
                      </span>
                    </div>

                    <div className="space-y-2">
                      {comments.length === 0 ? (
                        <p className="app-text-muted text-sm">Комментариев пока нет</p>
                      ) : comments.map((comment) => (
                        <div key={comment.id} className="app-surface rounded-xl px-3 py-3 text-sm text-[var(--foreground)]">
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <span className="font-medium">{displayUserName(comment.author)}</span>
                            <div className="flex items-center gap-2">
                              <span className="app-text-muted text-xs">{formatDateTime(comment.created_at) || "-"}</span>
                              {Boolean(comment.author?.id && currentUserId === comment.author.id) ? (
                                <button
                                  type="button"
                                  onClick={() => void onDeleteComment(request.id, comment.id)}
                                  disabled={busyKey === `comment-delete-${comment.id}`}
                                  className="app-action-danger inline-flex rounded-lg px-2 py-1 text-xs font-medium disabled:opacity-60"
                                >
                                  Удалить
                                </button>
                              ) : null}
                            </div>
                          </div>
                          <p className="app-text-wrap leading-relaxed text-[var(--foreground)]">{comment.text}</p>
                        </div>
                      ))}
                    </div>

                    <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                      <input
                        value={commentDraft}
                        onChange={(event) => onSetCommentDraft(request.id, event.target.value)}
                        placeholder="Добавить комментарий"
                        className="app-input flex-1 rounded-lg px-3 py-2.5 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => void onAddComment(request.id)}
                        disabled={busyKey === `comment-${request.id}` || !trimmedCommentDraft}
                        className="app-action-primary rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-60"
                      >
                        Отправить
                      </button>
                    </div>
                  </section>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
