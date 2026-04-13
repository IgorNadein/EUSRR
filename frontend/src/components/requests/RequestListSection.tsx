import type { RequestAttachmentPreview } from "@/hooks/useRequestsPage";
import type { Request, RequestComment } from "@/types/api";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { FileSignature } from "lucide-react";
import { RequestListItem } from "./RequestListItem";

type RequestListSectionProps = {
  busyKey: string | null;
  commentDrafts: Record<number, string>;
  commentsMap: Record<number, RequestComment[]>;
  currentUserId?: number | null;
  departmentNameMap: Map<number, string>;
  expandedComments: Record<number, boolean>;
  expandedRows: Record<number, boolean>;
  handleAddComment: (requestId: number) => void | Promise<void>;
  handleApprove: (requestId: number) => void | Promise<void>;
  handleCancel: (requestId: number) => void | Promise<void>;
  handleDelete: (requestId: number) => void | Promise<void>;
  handleDeleteComment: (requestId: number, commentId: number) => void | Promise<void>;
  handleReject: (requestId: number) => void | Promise<void>;
  isFinal: (status?: string) => boolean;
  loadMoreRef: RefObject<HTMLDivElement | null>;
  loadingMore: boolean;
  nextPage: number | null;
  openEdit: (request: Request) => void;
  requestMenuOpenId: number | null;
  requestMenuRef: RefObject<HTMLDivElement | null>;
  requests: Request[];
  setAttachmentPreview: (preview: RequestAttachmentPreview | null) => void;
  setCommentDrafts: Dispatch<SetStateAction<Record<number, string>>>;
  setDetailsRequest: (request: Request | null) => void;
  setRequestMenuOpenId: (requestId: number | null) => void;
  toggleComments: (requestId: number) => void | Promise<void>;
  toggleRow: (requestId: number) => void;
};

export function RequestListSection({
  busyKey,
  commentDrafts,
  commentsMap,
  currentUserId,
  departmentNameMap,
  expandedComments,
  expandedRows,
  handleAddComment,
  handleApprove,
  handleCancel,
  handleDelete,
  handleDeleteComment,
  handleReject,
  isFinal,
  loadMoreRef,
  loadingMore,
  nextPage,
  openEdit,
  requestMenuOpenId,
  requestMenuRef,
  requests,
  setAttachmentPreview,
  setCommentDrafts,
  setDetailsRequest,
  setRequestMenuOpenId,
  toggleComments,
  toggleRow,
}: RequestListSectionProps) {
  return (
    <>
      <div className="space-y-3">
        {requests.length === 0 ? (
          <div className="app-surface-muted rounded-xl p-8 text-center">
            <FileSignature size={22} className="app-text-muted mx-auto mb-2" />
            <p className="app-text-muted text-sm">Заявления не найдены</p>
          </div>
        ) : requests.map((request) => (
          <RequestListItem
            key={request.id}
            busyKey={busyKey}
            commentDraft={commentDrafts[request.id] || ""}
            comments={commentsMap[request.id] || []}
            commentsOpen={Boolean(expandedComments[request.id])}
            currentUserId={currentUserId}
            departmentNameMap={departmentNameMap}
            isFinal={isFinal}
            isMenuOpen={requestMenuOpenId === request.id}
            menuRef={requestMenuOpenId === request.id ? requestMenuRef : null}
            onAddComment={handleAddComment}
            onApprove={handleApprove}
            onCancel={handleCancel}
            onDelete={handleDelete}
            onDeleteComment={handleDeleteComment}
            onEdit={openEdit}
            onOpenDetails={setDetailsRequest}
            onPreviewAttachment={setAttachmentPreview}
            onReject={handleReject}
            onSetCommentDraft={(requestId, value) => setCommentDrafts((prev) => ({ ...prev, [requestId]: value }))}
            onToggleComments={toggleComments}
            onToggleMenu={setRequestMenuOpenId}
            onToggleRow={toggleRow}
            request={request}
            rowOpen={Boolean(expandedRows[request.id])}
          />
        ))}
      </div>

      {nextPage ? (
        <div ref={loadMoreRef} className="mt-4 flex justify-center py-4">
          {loadingMore ? (
            <div className="app-text-muted flex items-center gap-2 text-sm">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
              <span>Загрузка...</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
