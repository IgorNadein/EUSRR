"use client";

import { useState, useEffect, useRef } from "react";
import { X, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Modal } from "@/components/ui";

// Нормализация byweekday в массив чисел
function normalizeByweekday(byweekday: any): number[] {
  if (!byweekday) return [];
  if (Array.isArray(byweekday)) return byweekday;
  if (typeof byweekday === 'string') {
    return byweekday.split(',').map(d => parseInt(d.trim(), 10)).filter(n => !isNaN(n));
  }
  if (typeof byweekday === 'number') return [byweekday];
  return [];
}

interface EventModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: any | null;
  onSave: () => void;
  showParticipants?: boolean;
}

export function EventModal({
  isOpen,
  onClose,
  event,
  onSave,
  showParticipants = false,
}: EventModalProps) {
  const [editingEvent, setEditingEvent] = useState<any>(null);
  const [eventParticipants, setEventParticipants] = useState<any[]>([]);
  const [eventParticipantsLoading, setEventParticipantsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [ruleDetails, setRuleDetails] = useState<any>(null);
  const [showAddParticipants, setShowAddParticipants] = useState(false);
  const [availableEmployees, setAvailableEmployees] = useState<any[]>([]);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [addingParticipants, setAddingParticipants] = useState(false);
  const [pendingParticipantIds, setPendingParticipantIds] = useState<number[]>([]);

  // Ref для отслеживания, был ли уже выполнен авто-выбор дня (чтобы не перезаписывать выбор пользователя)
  const autoWeekdaySetRef = useRef(false);

  // Сброс флага при открытии/закрытии модала
  useEffect(() => {
    if (!isOpen) {
      autoWeekdaySetRef.current = false;
    }
  }, [isOpen]);

  // Автоматический выбор дня начала при включении WEEKLY (как в Apple Calendar)
  useEffect(() => {
    // Если уже устанавливали автоматически - не трогаем выбор пользователя
    if (autoWeekdaySetRef.current) {
      return;
    }

    if (editingEvent?.frequency === 'WEEKLY' && editingEvent?.start) {
      const startDate = new Date(editingEvent.start);
      const startDay = startDate.getDay();
      // Конвертируем: JS (0=Вс, 1=Пн...) -> наш формат (0=Пн, 6=Вс)
      const dayIndex = startDay === 0 ? 6 : startDay - 1;

      // Если дни недели еще не выбраны - добавляем день начала
      const normalizedByweekday = normalizeByweekday(editingEvent.byweekday);
      if (normalizedByweekday.length === 0) {
        setEditingEvent((prev: any) => ({
          ...prev,
          byweekday: [dayIndex]
        }));
        autoWeekdaySetRef.current = true;
      } else {
        // Дни уже выбраны (например, при редактировании события)
        autoWeekdaySetRef.current = true;
      }
    }
  }, [editingEvent?.frequency, editingEvent?.start]);

  useEffect(() => {
    if (isOpen && event) {
      // Инициализируем все boolean поля дефолтными значениями
      // Определяем repeatMode: 'count' | 'forever'
      let repeatMode = 'count';
      if (event.count) {
        repeatMode = 'count';
      } else if (!event.end_recurring_period && event.isRecurring) {
        repeatMode = 'forever';
      }

      setEditingEvent({
        ...event,
        isRecurring: event.isRecurring ?? false,
        repeatMode,
      });

      // Загружаем участников для существующего события
      if (event.id && showParticipants) {
        loadEventParticipants(event.id);
      } else {
        setEventParticipants([]);
      }

      // Загружаем правило для повторяющегося события
      if (event.id && event.rule) {
        loadRule(event.rule);
      } else {
        setRuleDetails(null);
      }
    } else if (!isOpen) {
      // Сбрасываем временные состояния при закрытии модала
      setShowAddParticipants(false);
      setSelectedEmployeeIds([]);
      setPendingParticipantIds([]);
      setSearchQuery('');
      setAvailableEmployees([]);
      setRuleDetails(null);
    }
  }, [isOpen, event, showParticipants]);

  // Конвертирует Date в формат datetime-local (локальное время)
  const toLocalDateTimeString = (date: Date | string): string => {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  // Вычисляет дату первого вхождения еженедельного события
  const getFirstOccurrenceDate = (): string | null => {
    const normalizedByweekday = normalizeByweekday(editingEvent?.byweekday);
    if (editingEvent?.frequency !== 'WEEKLY' || !editingEvent?.start || normalizedByweekday.length === 0) {
      return null;
    }

    const startDate = new Date(editingEvent.start);
    const startDay = startDate.getDay();
    const startDayIndex = startDay === 0 ? 6 : startDay - 1;

    // Если день начала выбран - первое вхождение это сам день начала
    if (normalizedByweekday.includes(startDayIndex)) {
      return null; // Не показываем подсказку
    }

    // Ищем ближайший выбранный день недели
    const sortedDays = [...normalizedByweekday].sort((a, b) => a - b);
    let daysToAdd = 0;

    // Ищем день после startDayIndex
    const nextDay = sortedDays.find(d => d > startDayIndex);
    if (nextDay !== undefined) {
      daysToAdd = nextDay - startDayIndex;
    } else {
      // Если все дни до текущего - берем первый день следующей недели
      daysToAdd = 7 - startDayIndex + sortedDays[0];
    }

    const firstOccurrence = new Date(startDate);
    firstOccurrence.setDate(firstOccurrence.getDate() + daysToAdd);

    return firstOccurrence.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      weekday: 'short'
    });
  };

  const loadEventParticipants = async (eventId: number) => {
    setEventParticipantsLoading(true);
    try {
      const data = await apiClient.getEventParticipants(eventId);
      setEventParticipants(data.results || data || []);
    } catch (error) {
      console.error('Failed to load event participants:', error);
    } finally {
      setEventParticipantsLoading(false);
    }
  };

  const loadRule = async (ruleId: number) => {
    try {
      const rule = await apiClient.getRule(ruleId);
      setRuleDetails(rule);

      // Заполняем поля редактирования параметрами из загруженного правила
      setEditingEvent((prev: any) => {
        // Определяем repeatMode на основе параметров правила
        let repeatMode: 'count' | 'forever' = 'count';
        if (rule.params?.count) {
          repeatMode = 'count';
        } else if (!prev.end_recurring_period) {
          repeatMode = 'forever';
        }

        return {
          ...prev,
          isRecurring: true,
          frequency: rule.frequency,
          interval: rule.params?.interval || 1,
          byweekday: normalizeByweekday(rule.params?.byweekday),
          count: rule.params?.count || undefined,
          repeatMode,
        };
      });
    } catch (error) {
      console.error('Failed to load rule:', error);
    }
  };

  const loadAvailableEmployees = async () => {
    setLoadingEmployees(true);
    try {
      const data = await apiClient.getEmployees({ limit: 200 });
      setAvailableEmployees(data.results || []);
    } catch (error) {
      console.error('Failed to load employees:', error);
    } finally {
      setLoadingEmployees(false);
    }
  };

  const handleRemoveParticipant = async (relationId: number) => {
    if (!confirm('Удалить участника из события?')) return;

    try {
      await apiClient.removeEventParticipant(relationId);
      await loadEventParticipants(editingEvent.id);
    } catch (error) {
      console.error('Failed to remove participant:', error);
      alert('Не удалось удалить участника');
    }
  };

  const handleAddParticipants = async () => {
    if (selectedEmployeeIds.length === 0) return;

    // Если событие еще не создано - добавляем в pending список
    if (!editingEvent.id) {
      setPendingParticipantIds([...pendingParticipantIds, ...selectedEmployeeIds]);
      setSelectedEmployeeIds([]);
      setShowAddParticipants(false);
      setSearchQuery('');
      return;
    }

    // Если событие уже существует - добавляем сразу
    setAddingParticipants(true);
    try {
      await Promise.all(
        selectedEmployeeIds.map(userId =>
          apiClient.addEventParticipant(editingEvent.id, userId, 'attendee')
        )
      );
      await loadEventParticipants(editingEvent.id);
      setSelectedEmployeeIds([]);
      setShowAddParticipants(false);
      setSearchQuery('');
    } catch (error) {
      console.error('Failed to add participants:', error);
      alert('Не удалось добавить участников');
    } finally {
      setAddingParticipants(false);
    }
  };

  const handleSave = async () => {
    if (!editingEvent || !editingEvent.title?.trim()) return;

    try {
      setSaving(true);
      let ruleId = editingEvent.rule || null;

      // Если убрали галочку "Повторяющееся событие" - сбрасываем rule
      if (!editingEvent.isRecurring && editingEvent.id && editingEvent.rule) {
        ruleId = null;
      }

      // Если это повторяющееся событие - создаем или обновляем правило
      if (editingEvent.isRecurring) {
        const params: any = {
          interval: editingEvent.interval || 1,
        };

        // Добавляем byweekday для еженедельных событий
        const normalizedByweekday = normalizeByweekday(editingEvent.byweekday);
        if (editingEvent.frequency === 'WEEKLY' && normalizedByweekday.length > 0) {
          params.byweekday = normalizedByweekday;
        }

        // Добавляем count если выбран режим "Количество раз"
        if (editingEvent.repeatMode === 'count' && editingEvent.count) {
          params.count = editingEvent.count;
        }

        const ruleData = {
          name: `Rule for ${editingEvent.title}`,
          description: `Recurring rule for ${editingEvent.title}`,
          frequency: editingEvent.frequency || 'WEEKLY',
          params,
        };

        if (ruleId) {
          // Обновляем существующее правило
          await apiClient.updateRule(ruleId, ruleData);
        } else {
          // Создаем новое правило
          const rule = await apiClient.createRule(ruleData);
          ruleId = rule.id;
        }
      }

      const eventData: any = {
        title: editingEvent.title,
        description: editingEvent.description,
        start: typeof editingEvent.start === 'string'
          ? editingEvent.start
          : editingEvent.start?.toISOString?.() || new Date(editingEvent.start).toISOString(),
        end: typeof editingEvent.end === 'string'
          ? editingEvent.end
          : editingEvent.end?.toISOString?.() || new Date(editingEvent.end).toISOString(),
        calendar: editingEvent.calendar,
        color_event: editingEvent.color_event || '#3498db',
        rule: ruleId,
      };

      if (editingEvent.id) {
        await apiClient.updateEvent(editingEvent.id, eventData);
      } else {
        const savedEvent = await apiClient.createEvent(eventData);

        // Если есть ожидающие участники - добавляем их
        if (pendingParticipantIds.length > 0 && savedEvent.id) {
          try {
            await Promise.all(
              pendingParticipantIds.map(userId =>
                apiClient.addEventParticipant(savedEvent.id, userId, 'attendee')
              )
            );
          } catch (error) {
            console.error('Failed to add participants to new event:', error);
          }
        }
      }

      setPendingParticipantIds([]);
      onSave();
      onClose();
    } catch (err: any) {
      console.error('❌ Ошибка сохранения события:', err);
      alert('Не удалось сохранить событие:\n' + (err.message || 'Неизвестная ошибка'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!editingEvent?.id || !confirm(`Удалить событие "${editingEvent.title}"?`)) return;

    try {
      setSaving(true);
      await apiClient.deleteEvent(editingEvent.id);
      onSave();
      onClose();
    } catch (err) {
      console.error('Ошибка удаления события:', err);
      alert('Не удалось удалить событие');
    } finally {
      setSaving(false);
    }
  };

  if (!editingEvent) return null;

  const footerContent = (
    <div className="flex gap-2">
      <button
        onClick={handleSave}
        disabled={!editingEvent.title?.trim() || saving}
        className="app-action-primary flex-1"
      >
        {saving ? 'Сохранение...' : (editingEvent.id ? 'Сохранить' : 'Создать')}
      </button>

      {editingEvent.id && (
        <button
          onClick={handleDelete}
          disabled={saving}
          className="app-action-danger px-4 py-2.5"
          title="Удалить событие"
        >
          <Trash2 size={16} />
        </button>
      )}
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editingEvent.id ? "Редактировать событие" : "Создать событие"}
      size="sm"
      closeOnEsc={!saving}
      footer={footerContent}
    >
      <div className="space-y-4">
          <div>
            <label className="app-field-label">Название</label>
            <input
              type="text"
              value={editingEvent.title || ''}
              onChange={(e) => setEditingEvent({ ...editingEvent, title: e.target.value })}
              className="app-input w-full"
              placeholder="Название события"
              autoFocus
            />
          </div>

          <div>
            <label className="app-field-label">Описание</label>
            <textarea
              value={editingEvent.description || ''}
              onChange={(e) => setEditingEvent({ ...editingEvent, description: e.target.value })}
              className="app-input min-h-28 w-full resize-y"
              placeholder="Описание (необязательно)"
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="app-field-label">Начало</label>
              <input
                type="datetime-local"
                value={
                  editingEvent.start
                    ? toLocalDateTimeString(editingEvent.start)
                    : ''
                }
                onChange={(e) => setEditingEvent({
                  ...editingEvent,
                  start: new Date(e.target.value).toISOString()
                })}
                className="app-input w-full"
              />
            </div>

            <div>
              <label className="app-field-label">Конец</label>
              <input
                type="datetime-local"
                value={
                  editingEvent.end
                    ? toLocalDateTimeString(editingEvent.end)
                    : ''
                }
                onChange={(e) => setEditingEvent({
                  ...editingEvent,
                  end: new Date(e.target.value).toISOString()
                })}
                className="app-input w-full"
              />
            </div>
          </div>


          <div>
            <label className="app-field-label">Цвет</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={editingEvent.color_event || '#3498db'}
                onChange={(e) => setEditingEvent({ ...editingEvent, color_event: e.target.value })}
                className="app-color-input"
              />
              <span className="app-text-muted text-xs">{editingEvent.color_event || '#3498db'}</span>
            </div>
          </div>

          {/* Повторяющееся событие */}
          <div>
            <label className="app-choice-label">
              <input
                type="checkbox"
                checked={editingEvent.isRecurring || false}
                    onChange={(e) => setEditingEvent({
                      ...editingEvent,
                      isRecurring: e.target.checked,
                      frequency: e.target.checked ? 'WEEKLY' : undefined,
                      interval: e.target.checked ? 1 : undefined,
                      repeatMode: e.target.checked ? 'count' : undefined,
                      count: e.target.checked ? 10 : undefined
                    })}
                    className="app-checkbox"
                  />
                  <span className="text-sm font-medium">Повторяющееся событие</span>
                </label>

              {editingEvent.isRecurring && (
                <div className="app-surface space-y-4 rounded-xl p-4">
                  <div>
                    <label className="app-field-label">Частота повторения</label>
                    <select
                      value={editingEvent.frequency || 'WEEKLY'}
                      onChange={(e) => setEditingEvent({ ...editingEvent, frequency: e.target.value })}
                      className="app-select w-full"
                    >
                      <option value="DAILY">Ежедневно</option>
                      <option value="WEEKLY">Еженедельно</option>
                      <option value="MONTHLY">Ежемесячно</option>
                      <option value="YEARLY">Ежегодно</option>
                    </select>
                  </div>

                  <div>
                    <label className="app-field-label">Интервал</label>
                    <div className="flex items-center gap-2">
                      <span className="app-text-muted text-sm">Каждые</span>
                      <input
                        type="number"
                        min="1"
                        max="365"
                        value={editingEvent.interval || 1}
                        onChange={(e) => setEditingEvent({ ...editingEvent, interval: parseInt(e.target.value) })}
                        className="app-input w-20"
                      />
                      <span className="app-text-muted text-sm">
                        {editingEvent.frequency === 'DAILY' && 'дней'}
                        {editingEvent.frequency === 'WEEKLY' && (editingEvent.interval === 1 ? 'неделю' : 'недели')}
                        {editingEvent.frequency === 'MONTHLY' && (editingEvent.interval === 1 ? 'месяц' : 'месяца')}
                        {editingEvent.frequency === 'YEARLY' && (editingEvent.interval === 1 ? 'год' : 'года')}
                      </span>
                    </div>
                  </div>

                  {editingEvent.frequency === 'WEEKLY' && (
                    <div>
                      <label className="app-field-label">Дни недели</label>
                      <div className="grid grid-cols-7 gap-1">
                        {[
                          { value: 0, label: 'ПН' },
                          { value: 1, label: 'ВТ' },
                          { value: 2, label: 'СР' },
                          { value: 3, label: 'ЧТ' },
                          { value: 4, label: 'ПТ' },
                          { value: 5, label: 'СБ' },
                          { value: 6, label: 'ВС' },
                        ].map((day) => {
                          const byweekday = normalizeByweekday(editingEvent.byweekday);
                          const isSelected = byweekday.includes(day.value);
                          return (
                            <button
                              key={day.value}
                              type="button"
                              onClick={() => {
                                const current = normalizeByweekday(editingEvent.byweekday);
                                const updated = isSelected
                                  ? current.filter((d: number) => d !== day.value)
                                  : [...current, day.value].sort();
                                setEditingEvent({ ...editingEvent, byweekday: updated });
                              }}
                              className={`px-2 py-1.5 text-xs ${
                                isSelected
                                  ? 'app-pill-active'
                                  : 'app-pill'
                              }`}
                            >
                              {day.label}
                            </button>
                          );
                        })}
                      </div>
                      {(() => {
                        const firstOccurrence = getFirstOccurrenceDate();
                        return firstOccurrence ? (
                          <div className="app-selected mt-2 flex items-start gap-2 rounded-xl px-3 py-2">
                            <svg className="app-accent-text mt-0.5 h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="app-accent-text text-xs">
                              Первое событие: <span className="font-medium">{firstOccurrence}</span>
                            </p>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  )}

                  <div>
                    <label className="app-field-label">Окончание повторения</label>
                    <div className="mb-2 flex flex-wrap items-center gap-3">
                      <label className="app-choice-label">
                        <input
                          type="radio"
                          checked={editingEvent.repeatMode === 'count'}
                          onChange={() => setEditingEvent({ ...editingEvent, repeatMode: 'count', end_recurring_period: undefined })}
                          className="app-radio"
                        />
                        <span className="text-sm">Количество раз</span>
                      </label>
                      <label className="app-choice-label">
                        <input
                          type="radio"
                          checked={editingEvent.repeatMode === 'forever'}
                          onChange={() => setEditingEvent({ ...editingEvent, repeatMode: 'forever', count: undefined, end_recurring_period: undefined })}
                          className="app-radio"
                        />
                        <span className="text-sm">Бесконечно</span>
                      </label>
                    </div>

                    {editingEvent.repeatMode === 'count' ? (
                      <input
                        type="number"
                        min="1"
                        max="999"
                        value={editingEvent.count || 10}
                        onChange={(e) => setEditingEvent({ ...editingEvent, count: parseInt(e.target.value) })}
                        className="app-input w-full"
                        placeholder="Количество повторений"
                      />
                    ) : (
                      <p className="app-text-muted text-xs italic">
                        Событие будет повторяться бесконечно
                      </p>
                    )}
                  </div>
                </div>
              )}
          </div>

          {/* Event Participants */}
          {showParticipants && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-[var(--foreground)]">
                  Участники события
                  {!eventParticipantsLoading && eventParticipants.length > 0 && (
                    <span className="app-text-muted ml-1">({eventParticipants.length})</span>
                  )}
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddParticipants(!showAddParticipants);
                    if (!showAddParticipants && availableEmployees.length === 0) {
                      loadAvailableEmployees();
                    }
                  }}
                  className="app-link-accent text-xs font-medium"
                >
                  {showAddParticipants ? 'Отмена' : '+ Добавить участников'}
                </button>
              </div>

              {/* Pending участники для нового события */}
              {!editingEvent.id && pendingParticipantIds.length > 0 && (
                <div className="space-y-2 mb-3">
                  <p className="app-accent-text text-xs font-medium">Будут добавлены после создания:</p>
                  {pendingParticipantIds.map(userId => {
                    const emp = availableEmployees.find(e => e.id === userId);
                    return emp ? (
                      <div
                        key={userId}
                        className="app-selected flex items-center justify-between rounded-xl px-3 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <div className="app-avatar-fallback h-6 w-6">
                            <span className="text-xs font-medium">
                              {emp.first_name?.[0] || '?'}
                            </span>
                          </div>
                          <div className="text-xs">
                            <div className="font-medium text-[var(--foreground)]">{emp.first_name} {emp.last_name}</div>
                            <div className="app-text-muted">attendee</div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setPendingParticipantIds(pendingParticipantIds.filter(id => id !== userId))}
                          className="app-action-danger p-1.5"
                          title="Удалить"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : null;
                  })}
                </div>
              )}

              {eventParticipantsLoading ? (
                <p className="app-text-muted py-2 text-xs">Загрузка...</p>
              ) : editingEvent.id && eventParticipants.length > 0 ? (
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {eventParticipants.map((participant: any) => (
                    <div
                      key={participant.id}
                      className="app-surface-muted flex items-center justify-between rounded-xl px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <div className="app-avatar-fallback h-6 w-6">
                          <span className="text-xs font-medium">
                            {participant.user_name?.[0] || '?'}
                          </span>
                        </div>
                        <div className="text-xs">
                          <div className="font-medium text-[var(--foreground)]">{participant.user_name}</div>
                          <div className="app-text-muted">{participant.distinction || 'attendee'}</div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveParticipant(participant.id)}
                        className="app-action-danger p-1.5"
                        title="Удалить участника"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : editingEvent.id ? (
                <p className="app-text-muted py-2 text-xs">Нет участников</p>
              ) : !pendingParticipantIds.length ? (
                <p className="app-text-muted py-2 text-xs">Добавьте участников после создания или выберите их до сохранения</p>
              ) : null}

              {/* Форма добавления участников */}
              {showAddParticipants && (
                <div className="app-surface-muted space-y-3 rounded-xl p-3">
                  <input
                    type="text"
                    placeholder="Поиск сотрудников..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="app-input w-full"
                  />

                  {loadingEmployees ? (
                    <p className="app-text-muted py-2 text-xs">Загрузка сотрудников...</p>
                  ) : (
                    <>
                      <div className="max-h-48 overflow-y-auto space-y-1">
                        {availableEmployees
                          .filter(emp => {
                            const fullName = `${emp.first_name} ${emp.last_name} ${emp.email || ''}`.toLowerCase();
                            const matchesSearch = fullName.includes(searchQuery.toLowerCase());
                            const notParticipant = !eventParticipants.find(p => p.object_id === emp.id);
                            const notPending = !pendingParticipantIds.includes(emp.id);
                            return matchesSearch && notParticipant && notPending;
                          })
                          .map(emp => (
                            <label
                              key={emp.id}
                              className="app-surface flex cursor-pointer items-center gap-2 rounded-xl p-2"
                            >
                              <input
                                type="checkbox"
                                checked={selectedEmployeeIds.includes(emp.id)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedEmployeeIds([...selectedEmployeeIds, emp.id]);
                                  } else {
                                    setSelectedEmployeeIds(selectedEmployeeIds.filter(id => id !== emp.id));
                                  }
                                }}
                                className="app-checkbox"
                              />
                              <div className="text-xs">
                                <div className="font-medium text-[var(--foreground)]">
                                  {emp.first_name} {emp.last_name}
                                </div>
                                {emp.email && <div className="app-text-muted">{emp.email}</div>}
                              </div>
                            </label>
                          ))}
                      </div>

                      {selectedEmployeeIds.length > 0 && (
                        <button
                          type="button"
                          onClick={handleAddParticipants}
                          disabled={addingParticipants}
                          className="app-action-primary w-full"
                        >
                          {addingParticipants ? 'Добавление...' : `Добавить выбранных (${selectedEmployeeIds.length})`}
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          )}
      </div>
    </Modal>
  );
}
