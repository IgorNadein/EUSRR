"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Request, User } from "@/types/api";
import { Check, ChevronUp, Flame, ThumbsDown, ThumbsUp, Undo2, X } from "lucide-react";

/* ── helpers ── */

const statusMeta: Record<string, { label: string; cls: string }> = {
  draft: { label: "Черновик", cls: "bg-slate-100 text-slate-700" },
  pending: { label: "На рассмотрении", cls: "bg-amber-50 text-amber-700" },
  approved: { label: "Одобрено", cls: "bg-emerald-50 text-emerald-700" },
  rejected: { label: "Отклонено", cls: "bg-rose-50 text-rose-700" },
  cancelled: { label: "Отменено", cls: "bg-gray-100 text-gray-600" },
  in_progress: { label: "В работе", cls: "bg-sky-50 text-sky-700" },
  completed: { label: "Завершено", cls: "bg-violet-50 text-violet-700" },
};

const typeLabels: Record<string, string> = {
  vacation: "Отпуск",
  sick_leave: "Больничный",
  day_off: "Отгул",
  transfer: "Перевод",
  dismissal: "Увольнение",
  other: "Другое",
};

function fmt(d?: string | null) {
  if (!d) return "—";
  const dt = new Date(d);
  return Number.isNaN(dt.getTime()) ? "—" : dt.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function userName(p?: User | null) {
  if (!p) return "—";
  const full = `${p.last_name || ""} ${p.first_name || ""}`.trim();
  return full || (p as any)?.full_name || p.email || "Пользователь";
}

/* ── types ── */

type SwipeAction = "approved" | "rejected" | "skipped";

type HistoryEntry = {
  request: Request;
  action: SwipeAction;
};

interface Props {
  /** Only pending requests the current user can process */
  requests: Request[];
  onApprove: (id: number) => Promise<void>;
  onReject: (id: number) => Promise<void>;
  onClose: () => void;
}

/* ── thresholds ── */
const SWIPE_THRESHOLD = 80; // px

export default function SwipeApprovalMode({ requests, onApprove, onReject, onClose }: Props) {
  const [queue, setQueue] = useState<Request[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [stats, setStats] = useState({ approved: 0, rejected: 0, skipped: 0 });
  const [busy, setBusy] = useState(false);
  const [undoToast, setUndoToast] = useState<HistoryEntry | null>(null);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  // swipe state
  const [dragX, setDragX] = useState(0);
  const [dragY, setDragY] = useState(0);
  const [dragging, setDragging] = useState(false);
  const startPos = useRef({ x: 0, y: 0 });
  const cardRef = useRef<HTMLDivElement>(null);
  const [flyOut, setFlyOut] = useState<"left" | "right" | "up" | null>(null);

  // init queue
  useEffect(() => {
    setQueue(requests.filter((r) => String(r.status).toLowerCase() === "pending"));
  }, [requests]);

  const current = queue[0] || null;

  /* ── perform action ── */

  const performAction = useCallback(
    async (action: SwipeAction) => {
      if (!current || busy) return;
      setBusy(true);
      const entry: HistoryEntry = { request: current, action };

      try {
        if (action === "approved") await onApprove(current.id);
        else if (action === "rejected") await onReject(current.id);
        // skipped = no API call

        setHistory((h) => [entry, ...h]);
        setStats((s) => ({ ...s, [action]: s[action] + 1 }));
        setQueue((q) => q.slice(1));

        // show undo toast
        if (undoTimer.current) clearTimeout(undoTimer.current);
        setUndoToast(entry);
        undoTimer.current = setTimeout(() => setUndoToast(null), 4000);
      } catch {
        // error is handled by parent (actionError state)
      } finally {
        setBusy(false);
        setDragX(0);
        setDragY(0);
        setFlyOut(null);
      }
    },
    [current, busy, onApprove, onReject]
  );

  /* ── undo ── */

  const handleUndo = useCallback(() => {
    if (!undoToast) return;
    const entry = undoToast;
    setUndoToast(null);
    if (undoTimer.current) clearTimeout(undoTimer.current);
    // put back at front of queue
    setQueue((q) => [entry.request, ...q]);
    setStats((s) => ({ ...s, [entry.action]: Math.max(0, s[entry.action] - 1) }));
    setHistory((h) => h.slice(1));
    // Note: for approved/rejected the API call already happened — undo is visual only.
    // A full undo would require a "revert" API endpoint.
  }, [undoToast]);

  /* ── touch / mouse drag ── */

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (busy || detailOpen) return;
      startPos.current = { x: e.clientX, y: e.clientY };
      setDragging(true);
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    },
    [busy, detailOpen]
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      setDragX(e.clientX - startPos.current.x);
      setDragY(e.clientY - startPos.current.y);
    },
    [dragging]
  );

  const onPointerUp = useCallback(() => {
    if (!dragging) return;
    setDragging(false);

    if (dragX > SWIPE_THRESHOLD) {
      setFlyOut("right");
      setTimeout(() => performAction("approved"), 250);
    } else if (dragX < -SWIPE_THRESHOLD) {
      setFlyOut("left");
      setTimeout(() => performAction("rejected"), 250);
    } else if (dragY < -SWIPE_THRESHOLD) {
      setFlyOut("up");
      setTimeout(() => performAction("skipped"), 250);
    } else {
      setDragX(0);
      setDragY(0);
    }
  }, [dragging, dragX, dragY, performAction]);

  /* ── keyboard ── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") performAction("approved");
      else if (e.key === "ArrowLeft") performAction("rejected");
      else if (e.key === "ArrowUp") performAction("skipped");
      else if (e.key === "z" && (e.ctrlKey || e.metaKey)) handleUndo();
      else if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [performAction, handleUndo, onClose]);

  /* ── derived ── */
  const swipeIntent: SwipeAction | null =
    dragX > SWIPE_THRESHOLD / 2
      ? "approved"
      : dragX < -SWIPE_THRESHOLD / 2
        ? "rejected"
        : dragY < -SWIPE_THRESHOLD / 2
          ? "skipped"
          : null;

  const total = stats.approved + stats.rejected + stats.skipped;
  const remaining = queue.length;

  /* ── render helpers ── */

  const renderCard = (req: Request) => {
    const st = String(req.status).toLowerCase();
    const sMeta = statusMeta[st] ?? { label: st, cls: "app-badge" };
    const typeKey = String(req.type || req.request_type || "").toLowerCase();
    const typeLabel = typeLabels[typeKey] || typeKey || "Другое";
    const author = req.employee || req.created_by;
    const summaryText = req.comment || req.description;

    return (
      <>
        {/* header */}
        <div className="mb-3 flex items-center justify-between">
          <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${sMeta.cls}`}>
            {sMeta.label}
          </span>
          <span className="app-text-muted text-xs">#{req.id}</span>
        </div>

        {/* author */}
        <div className="mb-3 flex items-center gap-2">
          {author?.avatar ? (
            <img src={author.avatar} alt="" className="app-avatar-frame h-10 w-10 rounded-full object-cover" />
          ) : (
            <span className="app-avatar-fallback flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold">
              {(author?.first_name?.[0] || author?.last_name?.[0] || "?").toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--foreground)]">{userName(author)}</p>
            <p className="app-text-muted text-xs">Автор заявления</p>
          </div>
        </div>

        {/* title */}
        <h3 className="app-text-wrap mb-2 text-base font-bold text-[var(--foreground)]">
          <span className="app-text-muted">{typeLabel}:</span> {req.display_title || req.title || "Без заголовка"}
        </h3>

        {/* period */}
        <div className="app-text-muted mb-3 flex flex-wrap items-center gap-3 text-xs">
          <span>Период: {fmt(req.date_from)} — {fmt(req.date_to)}</span>
          <span>Создано: {fmt(req.created_at)}</span>
        </div>

        {/* description */}
        {summaryText && (
          <div className={`app-text-wrap app-surface-muted rounded-lg p-3 text-sm leading-relaxed text-[var(--foreground)] ${detailOpen ? "" : "line-clamp-3"}`}>
            {summaryText}
          </div>
        )}

        {summaryText && summaryText.length > 100 && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setDetailOpen(!detailOpen); }}
            className="app-link-accent mt-1 text-xs font-medium"
          >
            {detailOpen ? "Свернуть" : "Подробнее..."}
          </button>
        )}
      </>
    );
  };

  /* ── empty state ── */
  if (!current && total === 0) {
    return (
      <div className="app-surface flex flex-col items-center justify-center rounded-2xl p-8 text-center">
        <Check size={40} className="mb-3 text-emerald-400" />
        <h3 className="text-lg font-bold text-[var(--foreground)]">Нет заявлений на рассмотрение</h3>
        <p className="app-text-muted mt-1 text-sm">Все заявления обработаны или отсутствуют</p>
        <button type="button" onClick={onClose} className="app-action-secondary mt-4 rounded-lg px-4 py-2 text-sm font-medium">
          Вернуться к списку
        </button>
      </div>
    );
  }

  /* ── all done ── */
  if (!current && total > 0) {
    return (
      <div className="app-surface flex flex-col items-center justify-center rounded-2xl p-8 text-center">
        <Flame size={40} className="mb-3 text-amber-400" />
        <h3 className="text-lg font-bold text-[var(--foreground)]">Все разобрано!</h3>
        <div className="mt-3 flex items-center gap-4 text-sm">
          <span className="font-semibold text-emerald-600">✓ {stats.approved}</span>
          <span className="font-semibold text-rose-600">✗ {stats.rejected}</span>
          <span className="app-text-muted">↑ {stats.skipped} пропущено</span>
        </div>
        <button type="button" onClick={onClose} className="app-action-secondary mt-4 rounded-lg px-4 py-2 text-sm font-medium">
          Вернуться к списку
        </button>
      </div>
    );
  }

  /* ── card transform ── */
  const translateX = flyOut === "right" ? 400 : flyOut === "left" ? -400 : dragX;
  const translateY = flyOut === "up" ? -400 : Math.min(0, dragY);
  const rotate = translateX * 0.06;
  const opacity = flyOut ? 0 : 1;
  const transition = dragging ? "none" : "transform 0.3s ease, opacity 0.3s ease";

  return (
    <div className="relative flex flex-col items-center">
      {/* stats bar */}
      <div className="app-surface-muted mb-4 flex w-full items-center justify-between rounded-xl px-4 py-2.5 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-emerald-600">✓ {stats.approved}</span>
          <span className="font-semibold text-rose-600">✗ {stats.rejected}</span>
          <span className="app-text-muted">↑ {stats.skipped}</span>
        </div>
        <span className="app-text-muted">Осталось: <span className="font-semibold text-[var(--foreground)]">{remaining}</span></span>
      </div>

      {/* swipe hint overlays on card */}
      <div className="relative w-full max-w-md">
        {/* background hint labels */}
        <div className="pointer-events-none absolute inset-0 z-0 flex items-center justify-between px-6">
          <div className={`flex flex-col items-center transition-opacity ${swipeIntent === "rejected" ? "opacity-100" : "opacity-0"}`}>
            <div className="rounded-full bg-rose-100 p-3"><ThumbsDown size={28} className="text-rose-600" /></div>
            <span className="mt-1 text-xs font-bold text-rose-600">Отклонить</span>
          </div>
          <div className={`flex flex-col items-center transition-opacity ${swipeIntent === "approved" ? "opacity-100" : "opacity-0"}`}>
            <div className="rounded-full bg-emerald-100 p-3"><ThumbsUp size={28} className="text-emerald-600" /></div>
            <span className="mt-1 text-xs font-bold text-emerald-600">Одобрить</span>
          </div>
        </div>
        <div className={`pointer-events-none absolute inset-x-0 top-0 z-0 flex justify-center transition-opacity ${swipeIntent === "skipped" ? "opacity-100" : "opacity-0"}`}>
          <div className="flex flex-col items-center pt-4">
            <div className="app-surface-muted rounded-full p-3"><ChevronUp size={28} className="app-text-muted" /></div>
            <span className="app-text-muted mt-1 text-xs font-bold">Пропустить</span>
          </div>
        </div>

        {/* the draggable card */}
        <div
          ref={cardRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          style={{
            transform: `translate(${translateX}px, ${translateY}px) rotate(${rotate}deg)`,
            opacity,
            transition,
            touchAction: "none",
          }}
          className="app-surface relative z-10 cursor-grab select-none rounded-2xl p-5 active:cursor-grabbing"
        >
          {current && renderCard(current)}

          {/* coloured border glow for intent */}
          {swipeIntent === "approved" && (
            <div className="pointer-events-none absolute inset-0 rounded-2xl ring-4 ring-emerald-300/50" />
          )}
          {swipeIntent === "rejected" && (
            <div className="pointer-events-none absolute inset-0 rounded-2xl ring-4 ring-rose-300/50" />
          )}
          {swipeIntent === "skipped" && (
            <div className="pointer-events-none absolute inset-0 rounded-2xl ring-4 ring-slate-300/40" />
          )}
        </div>

        {/* next card peek */}
        {queue[1] && (
          <div className="app-surface-muted absolute inset-x-2 top-2 -z-10 rounded-2xl p-5 opacity-60">
            <div className="h-4 w-24 rounded bg-[var(--surface-tertiary)]" />
            <div className="mt-2 h-3 w-40 rounded bg-[var(--surface-tertiary)]" />
          </div>
        )}
      </div>

      {/* action buttons */}
      <div className="mt-5 flex items-center gap-4">
        <button
          type="button"
          onClick={() => { setFlyOut("left"); setTimeout(() => performAction("rejected"), 250); }}
          disabled={busy}
          className="app-feedback-danger flex h-14 w-14 items-center justify-center rounded-full transition hover:shadow-md active:scale-95 disabled:opacity-50"
          title="Отклонить (←)"
        >
          <ThumbsDown size={22} />
        </button>

        <button
          type="button"
          onClick={() => { setFlyOut("up"); setTimeout(() => performAction("skipped"), 250); }}
          disabled={busy}
          className="app-action-secondary app-text-muted flex h-11 w-11 items-center justify-center rounded-full transition hover:shadow-md active:scale-95 disabled:opacity-50"
          title="Пропустить (↑)"
        >
          <ChevronUp size={20} />
        </button>

        <button
          type="button"
          onClick={() => { setFlyOut("right"); setTimeout(() => performAction("approved"), 250); }}
          disabled={busy}
          className="app-feedback-success flex h-14 w-14 items-center justify-center rounded-full transition hover:shadow-md active:scale-95 disabled:opacity-50"
          title="Одобрить (→)"
        >
          <ThumbsUp size={22} />
        </button>
      </div>

      {/* hint */}
      <p className="app-text-muted mt-3 text-center text-[11px]">
        Свайп ← отклонить · → одобрить · ↑ пропустить
      </p>

      {/* undo toast */}
      {undoToast && (
        <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-xl bg-gray-900 px-4 py-3 text-sm text-white shadow-lg">
          <span>
            {undoToast.action === "approved" ? "Одобрено" : undoToast.action === "rejected" ? "Отклонено" : "Пропущено"}:{" "}
            <span className="font-medium">{undoToast.request.display_title || undoToast.request.title || "—"}</span>
          </span>
          <button type="button" onClick={handleUndo} className="inline-flex items-center gap-1 rounded-lg bg-white/20 px-2.5 py-1 text-xs font-medium hover:bg-white/30">
            <Undo2 size={13} /> Отменить
          </button>
        </div>
      )}
    </div>
  );
}
