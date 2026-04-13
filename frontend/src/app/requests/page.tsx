"use client";

import { AppShell } from "../../components/AppShell";
import { RequestAttachmentPreviewModal } from "@/components/requests/RequestAttachmentPreviewModal";
import { RequestComposeModal } from "@/components/requests/RequestComposeModal";
import { RequestDetailModal } from "@/components/requests/RequestDetailModal";
import { RequestListControls } from "@/components/requests/RequestListControls";
import { RequestListSection } from "@/components/requests/RequestListSection";
import { RequestSwipeModePanel } from "@/components/requests/RequestSwipeModePanel";
import { useUser } from "@/contexts/UserContext";
import { Suspense } from "react";
import { useRequestsPage } from "@/hooks/useRequestsPage";
import { useRequestsPageScreen } from "@/hooks/useRequestsPageScreen";

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
  const h = useRequestsPage(user?.id);
  const screen = useRequestsPageScreen({
    detailsRequestId: h.detailsRequest?.id,
    requests: h.requests,
    setDetailsRequest: h.setDetailsRequest,
  });

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
          {h.swipeMode && h.pendingDecisionRequests.length > 0 ? (
            <RequestSwipeModePanel
              actionError={h.actionError}
              onApprove={h.handleApprove}
              onClose={() => h.setSwipeMode(false)}
              onReject={h.handleReject}
              requests={h.pendingDecisionRequests}
            />
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
            onClearFilters={h.clearFilters}
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
            pendingDecisionCount={h.pendingDecisionRequests.length}
            periodFromFilter={h.periodFromFilter}
            periodToFilter={h.periodToFilter}
            search={h.search}
            statusFilter={h.statusFilter}
            typeFilter={h.typeFilter}
            view={h.view}
          />
          <RequestListSection
            busyKey={h.busyKey}
            commentDrafts={h.commentDrafts}
            commentsMap={h.commentsMap}
            currentUserId={user?.id}
            departmentNameMap={h.departmentNameMap}
            expandedComments={h.expandedComments}
            expandedRows={h.expandedRows}
            handleAddComment={h.handleAddComment}
            handleApprove={h.handleApprove}
            handleCancel={h.handleCancel}
            handleDelete={h.handleDelete}
            handleDeleteComment={h.handleDeleteComment}
            handleReject={h.handleReject}
            isFinal={h.isFinal}
            loadMoreRef={h.loadMoreRef}
            loadingMore={h.loadingMore}
            nextPage={h.nextPage}
            openEdit={h.openEdit}
            requestMenuOpenId={screen.requestMenuOpenId}
            requestMenuRef={screen.requestMenuRef}
            requests={h.requests}
            setAttachmentPreview={h.setAttachmentPreview}
            onSetCommentDraft={h.setCommentDraft}
            setDetailsRequest={h.setDetailsRequest}
            setRequestMenuOpenId={screen.setRequestMenuOpenId}
            toggleComments={h.toggleComments}
            toggleRow={h.toggleRow}
          />
          </>
          )}
        </section>
      )}

      <RequestDetailModal
        currentUserId={user?.id}
        departmentNameMap={h.departmentNameMap}
        onClose={screen.closeDetailsRequest}
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
