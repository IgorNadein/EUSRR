import type { Calendar } from "@/types/api";

type SearchParamsLike = {
  get(name: string): string | null;
};

export interface LinkedCalendarState {
  linkedCalendarId: number | null;
  linkedCalendarName: string;
  linkedCalendarType: string | null;
  linkedContextType: string | null;
}

export interface CalendarParticipantsTarget {
  id: number;
  name: string;
  can_manage_participants?: boolean;
  type?: string | null;
  context_type?: string | null;
}

function parsePositiveInt(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function readLinkedCalendarState(
  searchParams: SearchParamsLike,
): LinkedCalendarState {
  return {
    linkedCalendarId: parsePositiveInt(searchParams.get("calendar")),
    linkedCalendarName: searchParams.get("calendarName") || "",
    linkedCalendarType: searchParams.get("calendarType"),
    linkedContextType: searchParams.get("contextType"),
  };
}

export function resolveSelectedCalendar(
  calendars: Calendar[],
  selectedCalendarId: number | null,
  linkedState: LinkedCalendarState,
): Calendar | null {
  const calendar =
    selectedCalendarId === null
      ? null
      : calendars.find((item) => item.id === selectedCalendarId) || null;

  if (calendar) {
    return calendar;
  }

  if (selectedCalendarId && linkedState.linkedCalendarName) {
    return {
      id: selectedCalendarId,
      name: linkedState.linkedCalendarName,
      slug: `linked-calendar-${selectedCalendarId}`,
      type: linkedState.linkedCalendarType || undefined,
      context_type: linkedState.linkedContextType || undefined,
      can_create_events: true,
      can_edit_calendar: false,
      can_manage_participants: false,
    };
  }

  return null;
}

export function buildCalendarOptions(
  calendars: Calendar[],
  selectedCalendar: Calendar | null,
): Calendar[] {
  if (!selectedCalendar) {
    return calendars;
  }

  return calendars.some((item) => item.id === selectedCalendar.id)
    ? calendars
    : [...calendars, selectedCalendar];
}

export function isDepartmentCalendar(
  calendar: Pick<Calendar, "type" | "context_type"> | null | undefined,
): boolean {
  return Boolean(
    calendar &&
      (calendar.type === "department" ||
        calendar.context_type === "department"),
  );
}

export function canOpenParticipantsModal(
  calendar:
    | Pick<Calendar, "can_manage_participants" | "type" | "context_type">
    | null
    | undefined,
): boolean {
  return Boolean(
    calendar &&
      (calendar.can_manage_participants || isDepartmentCalendar(calendar)),
  );
}

export function toParticipantsTarget(
  calendar: Calendar,
): CalendarParticipantsTarget {
  return {
    id: calendar.id,
    name: calendar.name,
    can_manage_participants: calendar.can_manage_participants,
    type: calendar.type,
    context_type: calendar.context_type,
  };
}
