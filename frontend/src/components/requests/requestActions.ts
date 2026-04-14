import type { Request } from "@/types/api";

export type RequestActionState = {
  canProcess: boolean;
  canCancel: boolean;
  canEdit: boolean;
  canDelete: boolean;
  canComment: boolean;
  hasSecondaryActions: boolean;
  isAuthor: boolean;
  statusKey: string;
};

export function getRequestActionState(
  request: Request,
  currentUserId: number | null | undefined,
  isFinal: (status?: string) => boolean,
): RequestActionState {
  const requestAuthor = request.employee || request.created_by;
  const statusKey = String(request.status || "").toLowerCase();
  const canProcess = Boolean(statusKey === "pending" && request.can_decide);
  const isAuthor = Boolean(requestAuthor?.id && currentUserId && requestAuthor.id === currentUserId);
  const canCancel = Boolean(isAuthor && !isFinal(statusKey));
  const canEdit = Boolean(isAuthor && !isFinal(statusKey));
  const canDelete = Boolean(isAuthor && !isFinal(statusKey));
  const canComment = statusKey !== "draft";

  return {
    canProcess,
    canCancel,
    canEdit,
    canDelete,
    canComment,
    hasSecondaryActions: canCancel || canEdit || canDelete,
    isAuthor,
    statusKey,
  };
}
