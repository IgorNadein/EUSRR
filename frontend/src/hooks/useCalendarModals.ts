"use client";

import { useState, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { DEFAULT_EVENT_COLOR } from "@/lib/calendar-event-colors";
import type { CalendarEvent } from "@/services/calendarService";

export interface CalendarModalsState {
  showCalendarModal: boolean;
  showEventModal: boolean;
  showParticipantsModal: boolean;
  showDayEventsModal: boolean;
  showEventDetailsModal: boolean;
  editingCalendar: { id?: number; name: string } | null;
  editingEvent: CalendarEvent | null;
  participantsCalendar: { id: number; name: string; user_role?: string } | null;
  selectedDateForModal: Date | null;
  viewingEvent: CalendarEvent | null;
  sidebarEvents: CalendarEvent[];
  currentSelectedCalendarId: number | null;
  eventsRefreshTrigger: number;
}

export function useCalendarModals() {
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [showEventModal, setShowEventModal] = useState(false);
  const [showParticipantsModal, setShowParticipantsModal] = useState(false);
  const [showDayEventsModal, setShowDayEventsModal] = useState(false);
  const [showEventDetailsModal, setShowEventDetailsModal] = useState(false);

  const [editingCalendar, setEditingCalendar] = useState<{ id?: number; name: string } | null>(null);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [participantsCalendar, setParticipantsCalendar] = useState<{ id: number; name: string; user_role?: string } | null>(null);
  const [selectedDateForModal, setSelectedDateForModal] = useState<Date | null>(null);
  const [viewingEvent, setViewingEvent] = useState<CalendarEvent | null>(null);
  const [sidebarEvents, setSidebarEvents] = useState<CalendarEvent[]>([]);
  const [currentSelectedCalendarId, setCurrentSelectedCalendarId] = useState<number | null>(null);
  const [eventsRefreshTrigger, setEventsRefreshTrigger] = useState(0);

  const handleSetSidebarEvents = useCallback((events: CalendarEvent[]) => {
    setSidebarEvents(events);
  }, []);

  const handleCalendarChange = useCallback((calendarId: number | null) => {
    setCurrentSelectedCalendarId(calendarId);
  }, []);

  const handleSetEventsRefreshTrigger = useCallback((value: number | ((prev: number) => number)) => {
    setEventsRefreshTrigger(value);
  }, []);

  const handleOpenCalendarModal = useCallback((calendar?: { id?: number; name: string }) => {
    setEditingCalendar(calendar || { name: "" });
    setShowCalendarModal(true);
  }, []);

  const handleOpenEventModal = useCallback((event: Partial<CalendarEvent> & { id?: number }, date?: Date) => {
    if (date && !event.id) {
      setSelectedDateForModal(date);
      setShowDayEventsModal(true);
    } else if (event.id) {
      setViewingEvent(event as CalendarEvent);
      setShowEventDetailsModal(true);
    } else {
      setEditingEvent(event as CalendarEvent);
      setShowEventModal(true);
    }
  }, []);

  const handleCreateEventFromDay = useCallback(() => {
    if (!currentSelectedCalendarId) {
      alert("Сначала выберите календарь");
      return;
    }
    if (!selectedDateForModal) return;

    const startDate = new Date(selectedDateForModal);
    startDate.setHours(10, 0, 0, 0);
    const endDate = new Date(selectedDateForModal);
    endDate.setHours(11, 0, 0, 0);

    setEditingEvent({
      title: "",
      description: "",
      start: startDate.toISOString(),
      end: endDate.toISOString(),
      calendar: currentSelectedCalendarId,
      color_event: DEFAULT_EVENT_COLOR,
    } as CalendarEvent);

    setShowDayEventsModal(false);
    setShowEventModal(true);
  }, [currentSelectedCalendarId, selectedDateForModal]);

  const handleEditFromDetails = useCallback(() => {
    setEditingEvent(viewingEvent);
    setShowEventDetailsModal(false);
    setShowEventModal(true);
  }, [viewingEvent]);

  const handleEventClickFromDay = useCallback(async (event: CalendarEvent & { is_recurring?: boolean; event_id?: number }) => {
    setShowDayEventsModal(false);

    if (event.is_recurring && event.event_id) {
      try {
        const fullEvent = await apiClient.getEvent(event.event_id);
        setViewingEvent({
          ...fullEvent,
          start: event.start,
          end: event.end,
        });
        setShowEventDetailsModal(true);
      } catch (err) {
        console.error("Ошибка загрузки события:", err);
      }
    } else {
      setViewingEvent(event);
      setShowEventDetailsModal(true);
    }
  }, []);

  const handleEventSaved = useCallback(() => {
    setEventsRefreshTrigger(prev => prev + 1);
  }, []);

  const handleOpenParticipantsModal = useCallback((calendar: { id: number; name: string; user_role?: string }) => {
    setParticipantsCalendar(calendar);
    setShowParticipantsModal(true);
  }, []);

  const handleDeleteEvent = useCallback(async () => {
    if (!viewingEvent?.id) return;
    if (!confirm("Удалить это событие?")) return;

    try {
      await apiClient.deleteEvent(viewingEvent.id);
      setShowEventDetailsModal(false);
      setViewingEvent(null);
      setEventsRefreshTrigger(prev => prev + 1);
    } catch (err) {
      console.error("Ошибка удаления события:", err);
      alert("Не удалось удалить событие");
    }
  }, [viewingEvent]);

  const closeCalendarModal = useCallback(() => {
    setShowCalendarModal(false);
    setEditingCalendar(null);
  }, []);

  const closeParticipantsModal = useCallback(() => {
    setShowParticipantsModal(false);
    setParticipantsCalendar(null);
  }, []);

  const closeEventModal = useCallback(() => {
    setShowEventModal(false);
    setEditingEvent(null);
  }, []);

  const closeDayEventsModal = useCallback(() => {
    setShowDayEventsModal(false);
    setSelectedDateForModal(null);
  }, []);

  const closeEventDetailsModal = useCallback(() => {
    setShowEventDetailsModal(false);
    setViewingEvent(null);
  }, []);

  return {
    // State for CalendarSidebar/CalendarCard props
    eventsRefreshTrigger,
    handleSetEventsRefreshTrigger,
    handleSetSidebarEvents,
    handleCalendarChange,

    // Handlers for opening modals
    handleOpenCalendarModal,
    handleOpenEventModal,
    handleOpenParticipantsModal,

    // Modal state and close handlers
    showCalendarModal,
    editingCalendar,
    closeCalendarModal,

    showParticipantsModal,
    participantsCalendar,
    closeParticipantsModal,

    showEventModal,
    editingEvent,
    closeEventModal,
    handleEventSaved,

    showDayEventsModal,
    selectedDateForModal,
    closeDayEventsModal,
    sidebarEvents,
    handleEventClickFromDay,
    handleCreateEventFromDay,

    showEventDetailsModal,
    viewingEvent,
    closeEventDetailsModal,
    handleEditFromDetails,
    handleDeleteEvent,
  };
}
