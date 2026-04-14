"use client";

import { memo } from "react";
import { CalendarCard } from "@/components/calendar/CalendarCard";
import { DesktopStickyRail } from "@/components/layout/DesktopStickyRail";
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
  pinnedDesktop?: boolean;
}

/**
 * Обертка для календаря в правом сайдбаре (десктоп)
 */
export const CalendarSidebar = memo(function CalendarSidebar(props: CalendarSidebarProps) {
  const { pinnedDesktop = true, ...calendarProps } = props;
  return (
    <DesktopStickyRail widthClass="w-72" pinned={pinnedDesktop}>
      <div className="space-y-4">
        <CalendarCard {...calendarProps} />
      </div>
    </DesktopStickyRail>
  );
});
