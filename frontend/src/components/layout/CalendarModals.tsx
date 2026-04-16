"use client";

import { CalendarModal } from "@/components/CalendarModal";
import CalendarParticipantsModal from "@/components/CalendarParticipantsModal";
import { EventModal } from "@/components/EventModal";
import { ViewDayEventsModal } from "@/components/ViewDayEventsModal";
import { ViewEventDetailsModal } from "@/components/ViewEventDetailsModal";
import type { useCalendarModals } from "@/hooks/useCalendarModals";

type CalendarModalsProps = ReturnType<typeof useCalendarModals>;

export function CalendarModals(props: CalendarModalsProps) {
  return (
    <>
      <CalendarModal
        isOpen={props.showCalendarModal}
        onClose={props.closeCalendarModal}
        calendar={props.editingCalendar}
      />

      {props.participantsCalendar && (
        <CalendarParticipantsModal
          isOpen={props.showParticipantsModal}
          onClose={props.closeParticipantsModal}
          calendarId={props.participantsCalendar.id}
          calendarName={props.participantsCalendar.name}
          canManageParticipants={props.participantsCalendar.can_manage_participants}
          calendarType={props.participantsCalendar.type}
          contextType={props.participantsCalendar.context_type}
        />
      )}

      <EventModal
        isOpen={props.showEventModal}
        onClose={props.closeEventModal}
        event={props.editingEvent}
        onSave={props.handleEventSaved}
        showParticipants={true}
      />

      <ViewDayEventsModal
        isOpen={props.showDayEventsModal}
        onClose={props.closeDayEventsModal}
        date={props.selectedDateForModal}
        events={props.sidebarEvents}
        onEventClick={props.handleEventClickFromDay}
        onCreateEvent={props.handleCreateEventFromDay}
      />

      <ViewEventDetailsModal
        isOpen={props.showEventDetailsModal}
        onClose={props.closeEventDetailsModal}
        event={props.viewingEvent}
        onEdit={props.handleEditFromDetails}
        onDelete={props.handleDeleteEvent}
        showParticipants={true}
      />
    </>
  );
}
