"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, Clock3, ImageOff, Loader2 } from "lucide-react";

import { Modal } from "@/components/ui/Modal";
import { apiClient } from "@/lib/api";
import type { AttendanceDayEvent } from "@/lib/api/attendance";

export type AttendanceDayEventsPreview = {
  recordId: number;
  employeeName: string;
  date: string;
  statusLabel: string;
  displayText: string;
  detailLines?: string[];
  issues?: string[];
  isManuallyEdited?: boolean;
};

type AttendanceDayEventsModalProps = {
  isOpen: boolean;
  onClose: () => void;
  record: AttendanceDayEventsPreview | null;
};

function getErrorMessage(error: unknown, fallback: string) {
  return String((error as Error)?.message || fallback);
}

function revokePhotoUrls(urls: Record<string, string>) {
  Object.values(urls).forEach((url) => URL.revokeObjectURL(url));
}

export function AttendanceDayEventsModal({
  isOpen,
  onClose,
  record,
}: AttendanceDayEventsModalProps) {
  const [events, setEvents] = useState<AttendanceDayEvent[]>([]);
  const [photoUrls, setPhotoUrls] = useState<Record<string, string>>({});
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [loadingPhotos, setLoadingPhotos] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const photoUrlsRef = useRef<Record<string, string>>({});

  useEffect(() => {
    photoUrlsRef.current = photoUrls;
  }, [photoUrls]);

  useEffect(() => {
    if (!isOpen || !record?.recordId) return;
    let cancelled = false;
    const recordId = record.recordId;

    async function loadEvents() {
      revokePhotoUrls(photoUrlsRef.current);
      setEvents([]);
      setPhotoUrls({});
      setError(null);
      setLoadingEvents(true);
      setLoadingPhotos(false);

      try {
        const nextEvents = await apiClient.getAttendanceRecordDayEvents(recordId);
        if (cancelled) return;
        setEvents(nextEvents);

        const eventsWithPhotos = nextEvents.filter(
          (event) => event.has_photo && event.photo_url,
        );
        if (eventsWithPhotos.length === 0) return;

        setLoadingPhotos(true);
        const loadedEntries = await Promise.all(
          eventsWithPhotos.map(async (event) => {
            const blob = await apiClient.getAttendanceDayEventPhoto(event.photo_url as string);
            return [event.event_key, URL.createObjectURL(blob)] as const;
          }),
        );
        if (cancelled) {
          loadedEntries.forEach(([, url]) => URL.revokeObjectURL(url));
          return;
        }
        setPhotoUrls(Object.fromEntries(loadedEntries));
      } catch (loadError) {
        if (!cancelled) {
          setError(getErrorMessage(loadError, "Не удалось загрузить события дня"));
        }
      } finally {
        if (!cancelled) {
          setLoadingEvents(false);
          setLoadingPhotos(false);
        }
      }
    }

    void loadEvents();

    return () => {
      cancelled = true;
    };
  }, [isOpen, record?.recordId]);

  useEffect(() => (
    () => {
      revokePhotoUrls(photoUrlsRef.current);
    }
  ), []);

  const close = () => {
    revokePhotoUrls(photoUrlsRef.current);
    setPhotoUrls({});
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen && !!record}
      onClose={close}
      title="События посещения"
      size="xl"
    >
      {record ? (
        <div className="space-y-4">
          <section className="app-surface-muted rounded-xl p-4">
            <p className="app-card-caption">Запись посещения</p>
            <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="app-text-wrap text-base font-semibold text-[var(--foreground)]">
                  {record.employeeName}
                </h3>
                <p className="app-text-muted mt-1 text-sm">
                  {record.date} · {record.displayText || "Нет записи"}
                </p>
              </div>
              <span className="app-status-pill bg-[var(--surface-primary)] text-[var(--foreground)]">
                {record.statusLabel}
              </span>
            </div>
            {record.detailLines?.length ? (
              <div className="mt-3 grid gap-1 text-xs text-[var(--muted-foreground)] sm:grid-cols-2">
                {record.detailLines.slice(0, 8).map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            ) : null}
            {record.issues?.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {record.issues.map((issue) => (
                  <span key={issue} className="app-status-pill bg-amber-500/15 text-amber-300">
                    {issue}
                  </span>
                ))}
              </div>
            ) : null}
            {record.isManuallyEdited ? (
              <div className="mt-3 inline-flex rounded-lg border border-violet-400/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-200">
                Ручная корректировка EUSRR
              </div>
            ) : null}
          </section>

          <section className="app-surface rounded-xl p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Camera size={16} className="app-text-muted" />
                <p className="app-card-caption">События LogStorm за день</p>
              </div>
              {loadingPhotos ? (
                <span className="app-text-muted inline-flex items-center gap-2 text-xs">
                  <Loader2 size={14} className="animate-spin" />
                  Загрузка фото
                </span>
              ) : null}
            </div>

            {error ? (
              <div className="app-feedback-danger rounded-xl p-3 text-sm">
                {error}
              </div>
            ) : loadingEvents ? (
              <div className="py-10 text-center">
                <Loader2 className="mx-auto animate-spin text-[var(--muted-foreground)]" size={22} />
                <p className="app-text-muted mt-3 text-sm">Загрузка событий...</p>
              </div>
            ) : events.length === 0 ? (
              <div className="app-surface-muted rounded-xl px-4 py-8 text-center">
                <p className="text-sm font-medium text-[var(--foreground)]">
                  Событий за день нет
                </p>
                <p className="app-text-muted mt-2 text-sm">
                  LogStorm не вернул проходы для этой даты.
                </p>
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {events.map((event) => {
                  const photoUrl = photoUrls[event.event_key];
                  return (
                    <article
                      key={event.event_key}
                      className="app-surface-muted overflow-hidden rounded-xl"
                    >
                      <div className="aspect-video bg-[var(--surface-primary)]">
                        {photoUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={photoUrl}
                            alt={`${event.caption}, ${event.time_label}`}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full flex-col items-center justify-center gap-2 text-[var(--muted-foreground)]">
                            <ImageOff size={24} />
                            <span className="text-xs">Фото не сохранено</span>
                          </div>
                        )}
                      </div>
                      <div className="space-y-2 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-semibold text-[var(--foreground)]">
                            {event.caption}
                          </p>
                          <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--foreground)]">
                            <Clock3 size={13} />
                            {event.time_label}
                          </span>
                        </div>
                        <p className="app-text-muted text-xs">
                          {event.device_name || event.device || "Устройство"} · #{event.serial_no}
                        </p>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </Modal>
  );
}
