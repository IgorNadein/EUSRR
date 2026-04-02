"use client";

import { ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import { X, ChevronDown } from "lucide-react";
import { useUser } from "@/contexts/UserContext";
import { CalendarCard } from "@/components/calendar/CalendarCard";
import type { CalendarEvent } from "@/services/calendarService";

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
        className={`absolute inset-0 bg-black/40 transition-opacity ${isOpen ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
        aria-label="Закрыть левое меню"
      />
      <div
        className={`absolute inset-y-0 left-0 w-full overflow-y-auto bg-white p-4 transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-gray-900">Меню</p>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
            aria-label="Закрыть меню"
          >
            <X size={20} className="text-gray-700" />
          </button>
        </div>

        {/* Профиль пользователя */}
        <div className="mb-6 rounded-xl bg-gradient-to-br from-sky-50 to-sky-100 ring-1 ring-sky-100 overflow-hidden">
          <button
            onClick={() => setIsProfileExpanded(!isProfileExpanded)}
            className="w-full flex items-center gap-3 p-4 hover:bg-sky-200/50 transition-colors"
          >
            <div className="h-12 w-12 overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white flex items-center justify-center flex-shrink-0">
              {user?.avatar ? (
                <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
              ) : (
                userInitials
              )}
            </div>
            <div className="min-w-0 flex-1 text-left">
              <p className="text-sm font-semibold text-gray-900">{userName}</p>
            </div>
            <ChevronDown
              size={20}
              className={`text-gray-700 transition-transform flex-shrink-0 ${isProfileExpanded ? "rotate-180" : ""}`}
            />
          </button>
          {isProfileExpanded && (
            <div className="border-t border-sky-200 p-2 space-y-2">
              <button
                className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-white text-gray-700"
                onClick={() => { onClose(); router.push("/profile"); }}
              >Мой профиль</button>
              <button
                className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-white text-gray-700"
                onClick={() => { onClose(); router.push("/settings"); }}
              >Настройки</button>
              <button
                className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-red-50 text-red-600"
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
  onOpenEventModal: (event: Partial<CalendarEvent> & { id?: number }, date?: Date) => void;
  onOpenParticipantsModal: (calendar: { id: number; name: string; user_role?: string }) => void;
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
        className={`absolute inset-0 bg-black/40 transition-opacity ${isOpen ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
        aria-label="Закрыть календарь"
      />
      <div
        className={`absolute inset-y-0 right-0 w-full overflow-y-auto bg-white p-4 transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-gray-900">Календарь</p>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
            aria-label="Закрыть календарь"
          >
            <X size={20} className="text-gray-700" />
          </button>
        </div>
        {isOpen && (
          <CalendarCard
            onOpenCalendarModal={onOpenCalendarModal}
            onOpenEventModal={onOpenEventModal}
            onOpenParticipantsModal={onOpenParticipantsModal}
            eventsRefreshTrigger={eventsRefreshTrigger}
            setEventsRefreshTrigger={setEventsRefreshTrigger}
            setSidebarEvents={setSidebarEvents}
            onCalendarChange={onCalendarChange}
          />
        )}
      </div>
    </div>
  );
}
