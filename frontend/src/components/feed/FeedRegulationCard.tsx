"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  ChevronRight,
  Download,
  Eye,
  FileText,
  FolderOpen,
  Link2,
  Loader2,
  MessageSquare,
  Pencil,
  ScrollText,
  Trash2,
  Users,
} from "lucide-react";

import { ExpandableFeedText } from "@/components/feed/ExpandableFeedText";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import { canPreviewDocument } from "@/lib/document-preview";
import { userProfileLink } from "@/lib/shared";
import type { Document } from "@/types/api";

type FeedRegulationCardProps = {
  currentUserId?: number | null;
  document: Document;
  isAcknowledging?: boolean;
  onAcknowledge: (document: Document) => void;
  onDelete: (document: Document) => void;
  onEdit: (document: Document) => void;
  onLinkTask: (document: Document) => void;
  onMove: (document: Document) => void;
  onOpen: (document: Document) => void;
  onOpenAcknowledgements: (document: Document) => void;
  onOpenComments: (document: Document) => void;
  onPreview: (document: Document) => void;
};

function formatTimeAgo(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 60_000) return "только что";
  const diffHours = Math.floor(diffMs / 3_600_000);
  if (diffHours < 24) return `${diffHours} ч. назад`;
  return `${Math.floor(diffHours / 24)} дн. назад`;
}

function uploaderName(document: Document) {
  const uploader = document.uploaded_by || document.created_by;
  const name = `${uploader?.last_name || ""} ${uploader?.first_name || ""}`.trim();
  return name || uploader?.email || "Сотрудник";
}

export function FeedRegulationCard({
  currentUserId,
  document,
  isAcknowledging = false,
  onAcknowledge,
  onDelete,
  onEdit,
  onLinkTask,
  onMove,
  onOpen,
  onOpenAcknowledgements,
  onOpenComments,
  onPreview,
}: FeedRegulationCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const uploader = document.uploaded_by || document.created_by;
  const name = uploaderName(document);
  const initials = `${uploader?.last_name?.[0] || ""}${uploader?.first_name?.[0] || ""}`.toUpperCase() || "Р";
  const linkedTasks = document.linked_tasks || [];
  const uploadedAt = document.uploaded_at || document.created_at;
  const acknowledgementRequiredForUser =
    document.acknowledgement_required_for_user ?? document.acknowledgement_required;
  const acknowledgedCount = document.acknowledged_count || 0;
  const acknowledgementTotal = document.acknowledgement_total || 0;
  const commentsCount = document.comments_count || 0;
  const hasPreview = Boolean(
    document.file_url && canPreviewDocument(document.file_name || document.title),
  );

  useEffect(() => {
    if (!menuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };

    window.document.addEventListener("mousedown", handlePointerDown);
    window.document.addEventListener("keydown", handleEscape);
    return () => {
      window.document.removeEventListener("mousedown", handlePointerDown);
      window.document.removeEventListener("keydown", handleEscape);
    };
  }, [menuOpen]);

  return (
    <article
      className="app-surface rounded-2xl p-5"
      style={{ borderColor: "var(--regulation-border)" }}
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <RequestAvatar
            alt={name}
            fallback={initials}
            size="lg"
            src={uploader?.avatar}
          />
          <div className="min-w-0">
            {uploader ? (
              <Link
                href={userProfileLink(uploader, currentUserId)}
                className="block truncate text-sm font-semibold text-[var(--foreground)] transition hover:text-[var(--accent-primary-strong)]"
              >
                {name}
              </Link>
            ) : (
              <p className="truncate text-sm font-semibold text-[var(--foreground)]">{name}</p>
            )}
            <div className="app-text-muted flex flex-wrap items-center gap-1.5 text-xs">
              <span>{formatTimeAgo(uploadedAt)}</span>
              <span className="app-selected app-accent-text inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium">
                <ScrollText size={11} />
                Регламент
              </span>
            </div>
          </div>
        </div>

        <div ref={menuRef} className="relative shrink-0">
          <button
            type="button"
            onClick={() => setMenuOpen((current) => !current)}
            className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
            title="Действия с регламентом"
            aria-label={`Действия с регламентом ${document.title}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
          >
            <ChevronRight
              size={15}
              className={`transition-transform duration-200 ${menuOpen ? "rotate-90" : ""}`}
            />
          </button>

          {menuOpen ? (
            <div className="app-menu absolute right-0 top-full z-30 mt-2 w-56 rounded-xl py-1.5" role="menu">
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onOpen(document);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
              >
                <FileText size={14} />
                Детали
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onEdit(document);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
              >
                <Pencil size={14} />
                Редактировать
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onMove(document);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
              >
                <FolderOpen size={14} />
                Переместить
              </button>
              {hasPreview ? (
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onPreview(document);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                >
                  <Eye size={14} />
                  Предпросмотр
                </button>
              ) : null}
              {document.file_url ? (
                <a
                  href={document.file_url}
                  download={document.file_name || document.title}
                  onClick={() => setMenuOpen(false)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                >
                  <Download size={14} />
                  Скачать
                </a>
              ) : null}
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onOpenComments(document);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
              >
                <MessageSquare size={14} />
                Комментарии ({commentsCount})
              </button>
              {document.acknowledgement_required ? (
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onOpenAcknowledgements(document);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                >
                  <Users size={14} />
                  Ведомость ({acknowledgedCount}/{acknowledgementTotal})
                </button>
              ) : null}
              {acknowledgementRequiredForUser && !document.is_acknowledged ? (
                <button
                  type="button"
                  disabled={isAcknowledging}
                  onClick={() => {
                    setMenuOpen(false);
                    onAcknowledge(document);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                >
                  {isAcknowledging ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Ознакомился(лась)
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onLinkTask(document);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
              >
                <Link2 size={14} />
                Связать с задачей
              </button>
              <div className="my-1 border-t border-[var(--border-subtle)]" />
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onDelete(document);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
              >
                <Trash2 size={14} />
                Удалить
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <button
        type="button"
        onClick={() => onOpen(document)}
        className="block w-full text-left"
      >
        <h3 className="app-text-wrap text-base font-semibold text-[var(--foreground)]">
          {document.title}
        </h3>
      </button>
      {document.description ? (
        <ExpandableFeedText text={document.description} className="mt-1" />
      ) : null}

      <div className="app-text-muted mt-3 flex flex-wrap items-center gap-2 text-xs">
        {document.sent_to_all ? (
          <span className="app-badge inline-flex items-center gap-1 rounded-full px-2 py-1">
            <Users size={11} /> Для всей компании
          </span>
        ) : null}
        {(document.departments || []).slice(0, 3).map((department) => (
          <span key={department.id} className="app-badge rounded-full px-2 py-1">
            {department.name}
          </span>
        ))}
        {acknowledgementRequiredForUser ? (
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 ${document.is_acknowledged ? "app-feedback-success" : "app-feedback-warning"}`}>
            <CheckCircle2 size={11} />
            {document.is_acknowledged ? "Ознакомлен" : "Требует ознакомления"}
          </span>
        ) : null}
      </div>

      <footer className="app-text-muted mt-4 flex flex-wrap items-center gap-3 text-sm">
        <div className="flex flex-wrap items-center gap-1">
          {acknowledgementRequiredForUser && !document.is_acknowledged ? (
            <button
              type="button"
              onClick={() => onAcknowledge(document)}
              disabled={isAcknowledging}
              className="app-action-ghost inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60"
              title="Ознакомился(лась)"
              aria-label="Ознакомился(лась)"
            >
              {isAcknowledging ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              <span>{isAcknowledging ? "Подтверждение..." : "Ознакомился(лась)"}</span>
            </button>
          ) : null}
          {document.file_url ? (
            <a
              href={document.file_url}
              download={document.file_name || document.title}
              className="app-action-ghost inline-flex h-9 w-9 items-center justify-center rounded-lg"
              title="Скачать"
              aria-label="Скачать регламент"
            >
              <Download size={16} />
            </a>
          ) : null}
        </div>

        {linkedTasks.length > 0 ? (
          <div className="flex max-w-full flex-wrap gap-1.5">
            {linkedTasks.slice(0, 3).map((task) => (
              <TaskLinkPill
                key={task.link_id || task.id}
                task={task}
                maxTitleClassName="max-w-40"
              />
            ))}
            {linkedTasks.length > 3 ? (
              <span className="app-badge rounded-full px-2 py-0.5 text-[11px] font-medium">
                +{linkedTasks.length - 3}
              </span>
            ) : null}
          </div>
        ) : null}

        <div className="ml-auto flex flex-wrap items-center justify-end gap-1">
          <button
            type="button"
            onClick={() => onOpenComments(document)}
            className="app-action-ghost inline-flex h-9 items-center justify-center gap-1.5 rounded-lg px-2"
            title="Комментарии"
            aria-label={`Комментарии: ${commentsCount}`}
          >
            <MessageSquare size={16} className="app-text-muted" />
            <span>{commentsCount}</span>
          </button>
          {document.acknowledgement_required ? (
            <button
              type="button"
              onClick={() => onOpenAcknowledgements(document)}
              className="app-action-ghost inline-flex h-9 items-center justify-center gap-1.5 rounded-lg px-2"
              title="Ведомость ознакомлений"
              aria-label={`Ведомость ознакомлений: ${acknowledgedCount} из ${acknowledgementTotal}`}
            >
              <Users size={16} />
              <span>{acknowledgedCount}/{acknowledgementTotal}</span>
            </button>
          ) : null}
        </div>
      </footer>
    </article>
  );
}
