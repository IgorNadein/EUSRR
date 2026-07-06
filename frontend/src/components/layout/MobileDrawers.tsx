"use client";

import { ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import { X, ChevronDown } from "lucide-react";
import { useUser } from "@/contexts/UserContext";
import { CalendarCard } from "@/components/calendar/CalendarCard";
import { type CalendarParticipantsTarget } from "@/lib/calendar/ui";
import type { CalendarEvent, CalendarEventDraft } from "@/services/calendarService";

/* ────────────── Left Navigation Drawer (mobile) ────────────── */

interface LeftNavDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode; // LeftNavContent rendered by parent
}

export function MobileLeftDrawer({ isOpen, onClose, children }: LeftNavDrawerProps) {
  const router = useRouter();
  const { user, logout } = useUser();
  const [isProfileExpanded, setIsProfileExpanded] = useState(false);

  const userInitials = user
    ? `${user.last_name?.[0] || ""}${user.first_name?.[0] || ""}`
    : "Г";
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : "Гость";

  return (
    <div className={`fixed inset-0 z-[100] lg:hidden ${isOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
      <button
        type="button"
        className={`app-overlay absolute inset-0 transition-opacity ${isOpen ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
        aria-label="Закрыть левое меню"
      />
      <div
        className={`app-surface-elevated absolute inset-y-0 left-0 w-full overflow-y-auto p-4 transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-[var(--foreground)]">Меню</p>
          <button
            type="button"
            onClick={onClose}
            className="app-icon-button flex h-10 w-10 items-center justify-center rounded-full"
            aria-label="Закрыть меню"
          >
            <X size={20} />
          </button>
        </div>

        {/* Профиль пользователя */}
        <div className="app-selected mb-6 overflow-hidden rounded-xl">
          <button
            onClick={() => setIsProfileExpanded(!isProfileExpanded)}
            className="flex w-full items-center gap-3 p-4 transition-colors hover:bg-[var(--accent-soft)]"
          >
            <div className="app-avatar-fallback flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-full text-sm font-semibold">
              {user?.avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
              ) : (
                userInitials
              )}
            </div>
            <div className="min-w-0 flex-1 text-left">
              <p className="text-sm font-semibold text-[var(--foreground)]">{userName}</p>
            </div>
            <ChevronDown
              size={20}
              className={`app-text-muted flex-shrink-0 transition-transform ${isProfileExpanded ? "rotate-180" : ""}`}
            />
          </button>
          {isProfileExpanded && (
            <div className="space-y-2 border-t border-[color:color-mix(in_srgb,var(--accent-primary)_18%,var(--border-subtle))] p-2">
              <button
                className="app-action-ghost w-full rounded-lg px-3 py-2 text-left text-sm transition"
                onClick={() => { onClose(); router.push("/profile"); }}
              >Мой профиль</button>
              <button
                className="app-action-ghost w-full rounded-lg px-3 py-2 text-left text-sm transition"
                onClick={() => { onClose(); router.push("/settings"); }}
              >Настройки</button>
              <button
                className="app-menu-danger-item w-full rounded-lg px-3 py-2 text-left text-sm transition"
                onClick={() => { onClose(); logout(); }}
              >Выйти</button>
            </div>
          )}
        </div>

        {children}
      </div>
    </div>
  );
}

/* ────────────── Calendar Drawer (mobile) ────────────── */

interface CalendarDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (event: CalendarEventDraft, date?: Date) => void;
  onOpenParticipantsModal: (calendar: CalendarParticipantsTarget) => void;
  eventsRefreshTrigger: number;
  setEventsRefreshTrigger: (value: number | ((prev: number) => number)) => void;
  setSidebarEvents: (events: CalendarEvent[]) => void;
  onCalendarChange: (calendarId: number | null) => void;
}

export function MobileCalendarDrawer({
  isOpen,
  onClose,
  onOpenCalendarModal,
  onOpenEventModal,
  onOpenParticipantsModal,
  eventsRefreshTrigger,
  setEventsRefreshTrigger,
  setSidebarEvents,
  onCalendarChange,
}: CalendarDrawerProps) {
  return (
    <div className={`fixed inset-0 z-[100] lg:hidden ${isOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
      <button
        type="button"
        className={`app-overlay absolute inset-0 transition-opacity ${isOpen ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
        aria-label="Закрыть календарь"
      />
      <div
        className={`app-surface-elevated absolute inset-y-0 right-0 w-full overflow-y-auto p-4 transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-[var(--foreground)]">Календарь</p>
          <button
            type="button"
            onClick={onClose}
            className="app-icon-button flex h-10 w-10 items-center justify-center rounded-full"
            aria-label="Закрыть календарь"
          >
            <X size={20} />
          </button>
        </div>
        {isOpen && (
          <div className="space-y-4 pb-4">
            <CalendarCard
              onOpenCalendarModal={onOpenCalendarModal}
              onOpenEventModal={onOpenEventModal}
              onOpenParticipantsModal={onOpenParticipantsModal}
              eventsRefreshTrigger={eventsRefreshTrigger}
              setEventsRefreshTrigger={setEventsRefreshTrigger}
              setSidebarEvents={setSidebarEvents}
              onCalendarChange={onCalendarChange}
            />
          </div>
        )}
      </div>
    </div>
  );
}
