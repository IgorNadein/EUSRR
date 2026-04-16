"use client";

import { memo } from "react";
import { CalendarCard } from "@/components/calendar/CalendarCard";
import type { CalendarEvent } from "@/services/calendarService";

interface CalendarSidebarProps {
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (
    event: Partial<CalendarEvent> & { id?: number; calendar?: number | null },
    date?: Date,
  ) => void;
  onOpenParticipantsModal: (calendar: {
    id: number;
    name: string;
    user_role?: string;
    can_manage_participants?: boolean;
    type?: string | null;
    context_type?: string | null;
  }) => void;
  eventsRefreshTrigger: number;
  setEventsRefreshTrigger: (value: number | ((prev: number) => number)) => void;
  setSidebarEvents: (events: CalendarEvent[]) => void;
  onCalendarChange: (calendarId: number | null) => void;
  fixedDesktop?: boolean;
}

/**
 * Обертка для календаря в правом сайдбаре (десктоп)
 */
export const CalendarSidebar = memo(function CalendarSidebar(props: CalendarSidebarProps) {
  const { fixedDesktop = false, ...calendarProps } = props;
  return (
    <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block">
      <div
        className={`space-y-4 lg:overflow-y-auto ${
          fixedDesktop
            ? "lg:fixed lg:top-0 lg:bottom-0 lg:w-72 lg:pt-[5.5rem] lg:pb-8"
            : "lg:sticky lg:top-8 lg:max-h-[calc(100dvh-7.5rem)] lg:pb-2"
        }`}
      >
        <CalendarCard {...calendarProps} />
      </div>
    </aside>
  );
});
