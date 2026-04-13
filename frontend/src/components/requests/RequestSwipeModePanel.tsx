import type { Request } from "@/types/api";
import { Zap } from "lucide-react";
import SwipeApprovalMode from "./SwipeApprovalMode";

type RequestSwipeModePanelProps = {
  actionError: string | null;
  onApprove: (id: number) => Promise<void>;
  onClose: () => void;
  onReject: (id: number) => Promise<void>;
  requests: Request[];
};

export function RequestSwipeModePanel({
  actionError,
  onApprove,
  onClose,
  onReject,
  requests,
}: RequestSwipeModePanelProps) {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-amber-500" />
          <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Быстрый разбор</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="app-action-secondary rounded-lg px-3 py-1.5 text-xs font-medium"
        >
          Обычный режим
        </button>
      </div>
      {actionError ? <p className="app-feedback-danger mb-3 rounded-lg px-3 py-2 text-sm">{actionError}</p> : null}
      <SwipeApprovalMode
        requests={requests}
        onApprove={onApprove}
        onReject={onReject}
        onClose={onClose}
      />
    </div>
  );
}
