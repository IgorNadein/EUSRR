"use client";
/* eslint-disable react-hooks/refs -- All h.* values come from useState, not useRef. React compiler false positive. */

import { AppShell } from "../../components/AppShell";
import { RequestAttachmentPreviewModal } from "@/components/requests/RequestAttachmentPreviewModal";
import { RequestComposeModal } from "@/components/requests/RequestComposeModal";
import { RequestDetailModal } from "@/components/requests/RequestDetailModal";
import { RequestListControls } from "@/components/requests/RequestListControls";
import { RequestListItem } from "@/components/requests/RequestListItem";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FileSignature, Zap } from "lucide-react";
import dynamic from "next/dynamic";
import { useRequestsPage } from "@/hooks/useRequestsPage";

const SwipeApprovalMode = dynamic(() => import("@/components/requests/SwipeApprovalMode"), { ssr: false });

export default function RequestsPage() {
  return (
    <Suspense fallback={<RequestsPageFallback />}>
      <RequestsPageContent />
    </Suspense>
  );
}

function RequestsPageFallback() {
  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-6 text-center">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]"></div>
        <p className="app-text-muted mt-3 text-sm">Загрузка заявлений...</p>
      </section>
    </AppShell>
  );
}

function RequestsPageContent() {
  const { user } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const h = useRequestsPage(user?.id);
  const requestMenuRef = useRef<HTMLDivElement | null>(null);
  const openedLinkedRequestIdRef = useRef<number | null>(null);
  const loadingLinkedRequestIdRef = useRef<number | null>(null);
  const [requestMenuOpenId, setRequestMenuOpenId] = useState<number | null>(null);
  const linkedRequestId = Number(searchParams.get("request") || "");

  const pendingDecisionRequests = useMemo(
    () => h.requests.filter((request) => String(request.status || "").toLowerCase() === "pending" && request.can_decide),
    [h.requests],
  );
  const detailsRequestId = h.detailsRequest?.id;
  const requestList = h.requests;
  const setDetailsRequest = h.setDetailsRequest;

  const clearRequestParam = () => {
    if (!searchParams.get("request")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("request");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  };

  const closeDetailsRequest = () => {
    h.setDetailsRequest(null);
    clearRequestParam();
  };

  useEffect(() => {
    if (!linkedRequestId) {
      openedLinkedRequestIdRef.current = null;
      loadingLinkedRequestIdRef.current = null;
      return;
    }

    if (detailsRequestId === linkedRequestId) {
      openedLinkedRequestIdRef.current = linkedRequestId;
      loadingLinkedRequestIdRef.current = null;
      return;
    }

    if (openedLinkedRequestIdRef.current === linkedRequestId) {
      return;
    }

    const existing = requestList.find((item) => item.id === linkedRequestId);
    if (existing) {
      openedLinkedRequestIdRef.current = linkedRequestId;
      loadingLinkedRequestIdRef.current = null;
      setDetailsRequest(existing);
      return;
    }

    if (loadingLinkedRequestIdRef.current === linkedRequestId) {
      return;
    }

    loadingLinkedRequestIdRef.current = linkedRequestId;

    let cancelled = false;

    apiClient.getRequest(linkedRequestId)
      .then((request) => {
        if (!cancelled && openedLinkedRequestIdRef.current !== linkedRequestId) {
          openedLinkedRequestIdRef.current = linkedRequestId;
          loadingLinkedRequestIdRef.current = null;
          setDetailsRequest(request);
        }
      })
      .catch((error) => {
        loadingLinkedRequestIdRef.current = null;
        console.error("Ошибка deep-link заявления:", error);
      });

    return () => {
      cancelled = true;
    };
  }, [detailsRequestId, linkedRequestId, requestList, setDetailsRequest]);

  useEffect(() => {
    if (requestMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (requestMenuRef.current && !requestMenuRef.current.contains(event.target as Node)) {
        setRequestMenuOpenId(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setRequestMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [requestMenuOpenId]);

  return (
    <AppShell>
      {h.loading ? (
        <div className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка заявлений...</p>
        </div>
      ) : h.error ? (
        <div className="app-feedback-danger rounded-2xl p-6 text-center"><p className="text-sm">{h.error}</p></div>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          {h.swipeMode && pendingDecisionRequests.length > 0 ? (
            <div>
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2"><Zap size={14} className="text-amber-500" /><p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Быстрый разбор</p></div>
                <button type="button" onClick={() => h.setSwipeMode(false)} className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium">Обычный режим</button>
              </div>
              {h.actionError && <p className="app-feedback-danger mb-3 rounded-lg px-3 py-2 text-sm">{h.actionError}</p>}
              <SwipeApprovalMode requests={pendingDecisionRequests} onApprove={h.handleApprove} onReject={h.handleReject} onClose={() => h.setSwipeMode(false)} />
            </div>
          ) : (
          <>
          <RequestListControls
            actionError={h.actionError}
            actionSuccess={h.actionSuccess}
            createdFromFilter={h.createdFromFilter}
            createdToFilter={h.createdToFilter}
            employeeFilter={h.employeeFilter}
            employees={h.employees}
            filtersOpen={h.filtersOpen}
            onClearFilters={() => {
              h.setView("");
              h.setTypeFilter("");
              h.setStatusFilter("");
              h.setEmployeeFilter("");
              h.setCreatedFromFilter("");
              h.setCreatedToFilter("");
              h.setPeriodFromFilter("");
              h.setPeriodToFilter("");
            }}
            onOpenCreate={h.openCreate}
            onSetCreatedFromFilter={h.setCreatedFromFilter}
            onSetCreatedToFilter={h.setCreatedToFilter}
            onSetEmployeeFilter={h.setEmployeeFilter}
            onSetOrdering={h.setOrdering}
            onSetPeriodFromFilter={h.setPeriodFromFilter}
            onSetPeriodToFilter={h.setPeriodToFilter}
            onSetSearch={h.setSearch}
            onSetStatusFilter={h.setStatusFilter}
            onSetTypeFilter={h.setTypeFilter}
            onSetView={h.setView}
            onStartSwipeMode={() => h.setSwipeMode(true)}
            onToggleFilters={() => h.setFiltersOpen((value) => !value)}
            ordering={h.ordering}
            pendingDecisionCount={pendingDecisionRequests.length}
            periodFromFilter={h.periodFromFilter}
            periodToFilter={h.periodToFilter}
            search={h.search}
            statusFilter={h.statusFilter}
            typeFilter={h.typeFilter}
            view={h.view}
          />

          <div className="space-y-3">
            {h.requests.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-8 text-center"><FileSignature size={22} className="app-text-muted mx-auto mb-2" /><p className="app-text-muted text-sm">Заявления не найдены</p></div>
            ) : h.requests.map((item) => (
              <RequestListItem
                key={item.id}
                busyKey={h.busyKey}
                commentDraft={h.commentDrafts[item.id] || ""}
                comments={h.commentsMap[item.id] || []}
                commentsOpen={Boolean(h.expandedComments[item.id])}
                currentUserId={user?.id}
                departmentNameMap={h.departmentNameMap}
                isFinal={h.isFinal}
                isMenuOpen={requestMenuOpenId === item.id}
                menuRef={requestMenuOpenId === item.id ? requestMenuRef : null}
                onAddComment={h.handleAddComment}
                onApprove={h.handleApprove}
                onCancel={h.handleCancel}
                onDelete={h.handleDelete}
                onDeleteComment={h.handleDeleteComment}
                onEdit={h.openEdit}
                onOpenDetails={h.setDetailsRequest}
                onPreviewAttachment={h.setAttachmentPreview}
                onReject={h.handleReject}
                onSetCommentDraft={(requestId, value) => h.setCommentDrafts((prev) => ({ ...prev, [requestId]: value }))}
                onToggleComments={h.toggleComments}
                onToggleMenu={setRequestMenuOpenId}
                onToggleRow={h.toggleRow}
                request={item}
                rowOpen={Boolean(h.expandedRows[item.id])}
              />
            ))}
          </div>

          {h.nextPage && <div ref={h.loadMoreRef} className="mt-4 flex justify-center py-4">{h.loadingMore && <div className="app-text-muted flex items-center gap-2 text-sm"><div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" /><span>Загрузка...</span></div>}</div>}
          </>
          )}
        </section>
      )}

      <RequestDetailModal
        currentUserId={user?.id}
        departmentNameMap={h.departmentNameMap}
        onClose={closeDetailsRequest}
        onPreviewAttachment={h.setAttachmentPreview}
        request={h.detailsRequest}
      />

      {h.isModalOpen && (
        <RequestComposeModal
          actionError={h.actionError}
          busyKey={h.busyKey}
          currentUserId={user?.id}
          editingRequest={h.editingRequest}
          employees={h.employees}
          form={h.form}
          mode={h.modalMode}
          onClose={h.closeModal}
          onPreviewAttachment={h.setAttachmentPreview}
          onSubmit={h.handleCreateOrUpdate}
          setForm={h.setForm}
        />
      )}

      <RequestAttachmentPreviewModal
        preview={h.attachmentPreview}
        onClose={() => h.setAttachmentPreview(null)}
      />
    </AppShell>
  );
}
