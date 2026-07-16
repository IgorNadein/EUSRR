"use client";

import { CalendarDays } from "lucide-react";
import { memo } from "react";
import { CalendarCard } from "@/components/calendar/CalendarCard";
import { type CalendarParticipantsTarget } from "@/lib/calendar/ui";
import type { CalendarEvent, CalendarEventDraft } from "@/services/calendarService";

interface CalendarSidebarProps {
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (event: CalendarEventDraft, date?: Date) => void;
  onOpenParticipantsModal: (calendar: CalendarParticipantsTarget) => void;
  eventsRefreshTrigger: number;
  setEventsRefreshTrigger: (value: number | ((prev: number) => number)) => void;
  setSidebarEvents: (events: CalendarEvent[]) => void;
  onCalendarChange: (calendarId: number | null) => void;
  fixedDesktop?: boolean;
  compact?: boolean;
  onExpand?: () => void;
}

/**
 * Обертка для календаря в правом сайдбаре (десктоп)
 */
export const CalendarSidebar = memo(function CalendarSidebar(props: CalendarSidebarProps) {
  const {
    fixedDesktop = false,
    compact = false,
    onExpand,
    ...calendarProps
  } = props;

  if (compact) {
    return (
      <aside className="hidden w-14 flex-shrink-0 transition-[width] duration-200 lg:block">
        <div
          className={`lg:w-14 ${
            fixedDesktop
              ? "lg:fixed lg:top-0 lg:bottom-0 lg:pt-[4.5rem] lg:pb-8"
              : "lg:sticky lg:top-8 lg:max-h-[calc(100dvh-7.5rem)] lg:pb-2"
          }`}
        >
          <div className="app-surface flex justify-center rounded-2xl p-2">
            <button
              type="button"
              onClick={onExpand}
              className="app-icon-button flex h-10 w-10 items-center justify-center rounded-lg"
              title="Развернуть календарь"
              aria-label="Развернуть календарь"
            >
              <CalendarDays size={18} />
            </button>
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block">
      <div
        className={`space-y-4 lg:overflow-y-auto ${
          fixedDesktop
            ? "lg:fixed lg:top-0 lg:bottom-0 lg:w-72 lg:pt-[4.5rem] lg:pb-8"
            : "lg:sticky lg:top-8 lg:max-h-[calc(100dvh-7.5rem)] lg:pb-2"
        }`}
      >
        <CalendarCard {...calendarProps} />
      </div>
    </aside>
  );
});
