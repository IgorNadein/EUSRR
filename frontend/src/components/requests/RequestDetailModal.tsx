import { Modal } from "@/components/ui";
import {
  defaultStatusMeta,
  requestTypeLabels,
  statusMeta,
  type RequestAttachmentPreview,
} from "@/hooks/useRequestsPage";
import { formatDate, formatDateTime } from "@/lib/shared";
import type { Request } from "@/types/api";
import { Ban, Paperclip, Pencil, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react";
import { getRequestActionState } from "./requestActions";
import { RequestUserBadge } from "./RequestUserBadge";

type RequestDetailModalProps = {
  actionError?: string | null;
  busyKey: string | null;
  currentUserId?: number | null;
  departmentNameMap: Map<number, string>;
  isFinal: (status?: string) => boolean;
  onApprove: (requestId: number) => void | Promise<void>;
  onCancel: (requestId: number) => void | Promise<void>;
  onClose: () => void;
  onDelete: (requestId: number) => void | Promise<void>;
  onEdit: (request: Request) => void;
  onPreviewAttachment: (preview: RequestAttachmentPreview) => void;
  onReject: (requestId: number) => void | Promise<void>;
  request: Request | null;
};

export function RequestDetailModal({
  actionError,
  busyKey,
  currentUserId,
  departmentNameMap,
  isFinal,
  onApprove,
  onCancel,
  onClose,
  onDelete,
  onEdit,
  onPreviewAttachment,
  onReject,
  request,
}: RequestDetailModalProps) {
  if (!request) return null;

  const author = request.employee || request.created_by;
  const approver = request.approver || request.assigned_to;
  const actionState = getRequestActionState(request, currentUserId, isFinal);
  const { canCancel, canDelete, canEdit, canProcess } = actionState;
  const status = statusMeta[String(request.status || "").toLowerCase()] ?? defaultStatusMeta;
  const typeLabel = requestTypeLabels[String(request.type || request.request_type || "").toLowerCase()]
    || String(request.type || request.request_type || "Другое");
  const attachmentUrl = request.attachment_url || request.attachment || "";
  const attachmentName = attachmentUrl
    ? decodeURIComponent(attachmentUrl.split("/").pop() || "Вложение")
    : "";

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Полная информация по заявлению"
      size="lg"
      footer={(
        <div className="space-y-3">
          {actionError ? (
            <div className="app-feedback-danger rounded-xl px-3 py-2 text-sm">
              {actionError}
            </div>
          ) : null}
          {(canProcess || canCancel || canEdit || canDelete) ? (
            <div className="flex flex-wrap items-center justify-end gap-2">
              {canProcess ? (
                <>
                  <button
                    type="button"
                    onClick={() => void onApprove(request.id)}
                    disabled={busyKey === `approve-${request.id}`}
                    className="app-feedback-success inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-60"
                  >
                    <ThumbsUp size={16} />
                    Одобрить
                  </button>
                  <button
                    type="button"
                    onClick={() => void onReject(request.id)}
                    disabled={busyKey === `reject-${request.id}`}
                    className="app-action-danger inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-60"
                  >
                    <ThumbsDown size={16} />
                    Отклонить
                  </button>
                </>
              ) : null}
              {canCancel ? (
                <button
                  type="button"
                  onClick={() => void onCancel(request.id)}
                  disabled={busyKey === `cancel-${request.id}`}
                  className="app-action-secondary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-60"
                >
                  <Ban size={16} />
                  Отменить
                </button>
              ) : null}
              {canEdit ? (
                <button
                  type="button"
                  onClick={() => onEdit(request)}
                  className="app-action-secondary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium"
                >
                  <Pencil size={16} />
                  Редактировать
                </button>
              ) : null}
              {canDelete ? (
                <button
                  type="button"
                  onClick={() => void onDelete(request.id)}
                  disabled={busyKey === `delete-${request.id}`}
                  className="app-action-danger inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-60"
                >
                  <Trash2 size={16} />
                  Удалить
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    >
      <div className="space-y-5 text-sm text-[var(--foreground)]">
        <div className="app-surface-muted rounded-xl p-4">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="app-badge app-badge-accent px-2.5 py-1 text-xs font-medium">
                {typeLabel}
              </span>
              <span className={`app-status-pill ${status.className}`}>
                {status.label}
              </span>
            </div>
            <h2 className="app-text-wrap text-lg font-semibold text-[var(--foreground)]">
              {request.display_title || request.title || "Без заголовка"}
            </h2>
            {(request.comment || request.description) ? (
              <div className="app-text-wrap mt-3 whitespace-pre-wrap text-sm leading-relaxed text-[var(--foreground)]">
                {request.comment || request.description}
              </div>
            ) : (
              <p className="app-text-muted mt-3 text-sm">Описание отсутствует</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="app-surface rounded-xl p-4">
            <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Даты</p>
            <div className="mt-3 space-y-2">
              <div>
                <p className="app-text-muted text-xs">Период</p>
                <p className="mt-1 text-sm text-[var(--foreground)]">
                  {request.date_from ? formatDate(request.date_from) : "—"}
                  {request.date_to ? ` — ${formatDate(request.date_to)}` : ""}
                </p>
              </div>
              <div>
                <p className="app-text-muted text-xs">Создано</p>
                <p className="mt-1 text-sm text-[var(--foreground)]">
                  {formatDateTime(request.created_at) || "—"}
                </p>
              </div>
              <div>
                <p className="app-text-muted text-xs">Обновлено</p>
                <p className="mt-1 text-sm text-[var(--foreground)]">
                  {formatDateTime(request.updated_at) || "—"}
                </p>
              </div>
            </div>
          </div>

          <div className="app-surface rounded-xl p-4">
            <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Участники</p>
            <div className="mt-3 space-y-3">
              <div>
                <p className="app-text-muted text-xs">Автор</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {author ? (
                    <RequestUserBadge person={author} currentUserId={currentUserId} large />
                  ) : (
                    <span className="app-text-muted text-sm">—</span>
                  )}
                </div>
              </div>
              <div>
                <p className="app-text-muted text-xs">Принял решение</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {approver ? (
                    <RequestUserBadge person={approver} currentUserId={currentUserId} large />
                  ) : (
                    <span className="app-text-muted text-sm">—</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="app-surface rounded-xl p-4">
          <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Отделы</p>
          {(request.departments || []).length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {(request.departments || []).map((id) => (
                <span key={id} className="app-badge px-3 py-1.5 text-sm font-medium">
                  {departmentNameMap.get(Number(id)) || `Отдел #${id}`}
                </span>
              ))}
            </div>
          ) : (
            <p className="app-text-muted mt-3 text-sm">Отделы не указаны</p>
          )}
        </div>

        <div className="app-surface rounded-xl p-4">
          <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Получатели</p>
          {(request.recipients || []).length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {(request.recipients || []).map((recipient) => (
                <RequestUserBadge
                  key={recipient.id}
                  person={recipient}
                  currentUserId={currentUserId}
                  large
                />
              ))}
            </div>
          ) : (
            <p className="app-text-muted mt-3 text-sm">Получатели не указаны</p>
          )}
        </div>

        <div className="app-surface rounded-xl p-4">
          <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">В копии</p>
          {(request.cc_users || []).length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {(request.cc_users || []).map((ccUser) => (
                <RequestUserBadge
                  key={ccUser.id}
                  person={ccUser}
                  currentUserId={currentUserId}
                  large
                />
              ))}
            </div>
          ) : (
            <p className="app-text-muted mt-3 text-sm">Копия не указана</p>
          )}
        </div>

        <div className="app-surface rounded-xl p-4">
          <p className="app-text-muted text-xs font-semibold uppercase tracking-wide">Вложение</p>
          {attachmentUrl ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => onPreviewAttachment({ url: attachmentUrl, name: attachmentName })}
                className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium"
              >
                <Paperclip size={15} />
                <span className="app-text-wrap">{attachmentName}</span>
              </button>
              <a
                href={attachmentUrl}
                target="_blank"
                rel="noreferrer"
                className="app-link-accent text-sm font-medium hover:underline"
              >
                Открыть в новой вкладке
              </a>
            </div>
          ) : (
            <p className="app-text-muted mt-3 text-sm">Вложение отсутствует</p>
          )}
        </div>
      </div>
    </Modal>
  );
}
