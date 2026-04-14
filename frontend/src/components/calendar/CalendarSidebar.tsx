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
  onOpenParticipantsModal: (calendar: { id: number; name: string; user_role?: string }) => void;
  eventsRefreshTrigger: number;
  setEventsRefreshTrigger: (value: number | ((prev: number) => number)) => void;
  setSidebarEvents: (events: CalendarEvent[]) => void;
  onCalendarChange: (calendarId: number | null) => void;
}

/**
 * Обертка для календаря в правом сайдбаре (десктоп)
 */
export const CalendarSidebar = memo(function CalendarSidebar(props: CalendarSidebarProps) {
  return (
    <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block">
      <div className="sticky top-8 space-y-4 lg:pb-2 max-h-[calc(100vh-7.5rem)] overflow-y-auto">
        <CalendarCard {...props} />
      </div>
    </aside>
  );
});
