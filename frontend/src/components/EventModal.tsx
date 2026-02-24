"use client";

import { useState, useEffect, useRef } from "react";
import { X, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api";

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
      if (!editingEvent.byweekday || editingEvent.byweekday.length === 0) {
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
      setEditingEvent({
        ...event,
        isRecurring: event.isRecurring ?? false,
        useCount: event.useCount ?? false,
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
    if (editingEvent?.frequency !== 'WEEKLY' || !editingEvent?.start || !editingEvent?.byweekday || editingEvent.byweekday.length === 0) {
      return null;
    }

    const startDate = new Date(editingEvent.start);
    const startDay = startDate.getDay();
    const startDayIndex = startDay === 0 ? 6 : startDay - 1;

    // Если день начала выбран - первое вхождение это сам день начала
    if (editingEvent.byweekday.includes(startDayIndex)) {
      return null; // Не показываем подсказку
    }

    // Ищем ближайший выбранный день недели
    const sortedDays = [...editingEvent.byweekday].sort((a, b) => a - b);
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

      // Если это повторяющееся событие и у него нет Rule - создаем правило
      if (editingEvent.isRecurring && !ruleId) {
        const params: any = {
          interval: editingEvent.interval || 1,
        };

        // Добавляем byweekday для еженедельных событий
        if (editingEvent.frequency === 'WEEKLY' && editingEvent.byweekday && editingEvent.byweekday.length > 0) {
          params.byweekday = editingEvent.byweekday;
        }

        // Добавляем count если выбран этот вариант
        if (editingEvent.useCount && editingEvent.count) {
          params.count = editingEvent.count;
        }

        const rule = await apiClient.createRule({
          name: `Rule for ${editingEvent.title}`,
          description: `Recurring rule for ${editingEvent.title}`,
          frequency: editingEvent.frequency || 'WEEKLY',
          params,
        });
        ruleId = rule.id;
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

      // Добавляем end_recurring_period только для повторяющихся событий (если не используется count)
      if (editingEvent.isRecurring && !editingEvent.useCount && editingEvent.end_recurring_period) {
        const endDate = new Date(editingEvent.end_recurring_period);
        endDate.setHours(23, 59, 59, 999);
        eventData.end_recurring_period = endDate.toISOString();
      }

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

  if (!isOpen || !editingEvent) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">
            {editingEvent.id ? "Редактировать событие" : "Создать событие"}
          </h3>
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-full p-1 hover:bg-gray-100 disabled:opacity-50"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Название
            </label>
            <input
              type="text"
              value={editingEvent.title || ''}
              onChange={(e) => setEditingEvent({ ...editingEvent, title: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              placeholder="Название события"
              autoFocus
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Описание
            </label>
            <textarea
              value={editingEvent.description || ''}
              onChange={(e) => setEditingEvent({ ...editingEvent, description: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              placeholder="Описание (необязательно)"
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Начало</label>
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
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Конец</label>
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
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              />
            </div>
          </div>


          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Цвет
            </label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={editingEvent.color_event || '#3498db'}
                onChange={(e) => setEditingEvent({ ...editingEvent, color_event: e.target.value })}
                className="h-10 w-20 rounded-lg border border-gray-300 cursor-pointer"
              />
              <span className="text-xs text-gray-500">{editingEvent.color_event || '#3498db'}</span>
            </div>
          </div>

          {/* Повторяющееся событие */}
          {editingEvent.id && ruleDetails ? (
            // Для существующих повторяющихся событий - readonly информация
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 space-y-2">
              <div className="flex items-center gap-2 text-blue-700 font-medium text-sm">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="18" height="18" x="3" y="4" rx="2" ry="2"></rect>
                  <line x1="16" x2="16" y1="2" y2="6"></line>
                  <line x1="8" x2="8" y1="2" y2="6"></line>
                  <line x1="3" x2="21" y1="10" y2="10"></line>
                </svg>
                <span>Повторяющееся событие</span>
              </div>
              <div className="text-sm text-blue-600 space-y-1">
                <div>Частота: <span className="font-medium">
                  {ruleDetails.frequency === 'DAILY' && 'Каждый день'}
                  {ruleDetails.frequency === 'WEEKLY' && 'Каждую неделю'}
                  {ruleDetails.frequency === 'MONTHLY' && 'Каждый месяц'}
                  {ruleDetails.frequency === 'YEARLY' && 'Каждый год'}
                </span></div>
                {ruleDetails.params?.interval && ruleDetails.params.interval > 1 && (
                  <div>Интервал: <span className="font-medium">{ruleDetails.params.interval}</span></div>
                )}
                {ruleDetails.params?.byweekday && ruleDetails.params.byweekday.length > 0 && (
                  <div>Дни недели: <span className="font-medium">
                    {ruleDetails.params.byweekday.map((d: number) => ['ПН','ВТ','СР','ЧТ','ПТ','СБ','ВС'][d]).join(', ')}
                  </span></div>
                )}
                {ruleDetails.params?.count && (
                  <div>Повторений: <span className="font-medium">{ruleDetails.params.count}</span></div>
                )}
              </div>
              <div className="text-xs text-blue-600 mt-2">
                💡 Редактирование параметров повторения пока не поддерживается
              </div>
            </div>
          ) : (!editingEvent.id || !editingEvent.rule) && (
            <>

              <div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingEvent.isRecurring || false}
                    onChange={(e) => setEditingEvent({
                      ...editingEvent,
                      isRecurring: e.target.checked,
                      frequency: e.target.checked ? 'WEEKLY' : undefined,
                      interval: e.target.checked ? 1 : undefined,
                      end_recurring_period: e.target.checked && !editingEvent.end_recurring_period
                        ? new Date(new Date().setMonth(new Date().getMonth() + 3)).toISOString().slice(0, 10)
                        : editingEvent.end_recurring_period
                    })}
                    className="h-4 w-4 rounded border-gray-300 text-sky-500 focus:ring-2 focus:ring-sky-100"
                  />
                  <span className="text-sm font-medium text-gray-700">Повторяющееся событие</span>
                </label>
              </div>

              {editingEvent.isRecurring && (
                <div className="space-y-3 rounded-lg bg-gray-50 p-3">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Частота повторения
                    </label>
                    <select
                      value={editingEvent.frequency || 'WEEKLY'}
                      onChange={(e) => setEditingEvent({ ...editingEvent, frequency: e.target.value })}
                      className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                    >
                      <option value="DAILY">Ежедневно</option>
                      <option value="WEEKLY">Еженедельно</option>
                      <option value="MONTHLY">Ежемесячно</option>
                      <option value="YEARLY">Ежегодно</option>
                    </select>
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Интервал
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-600">Каждые</span>
                      <input
                        type="number"
                        min="1"
                        max="365"
                        value={editingEvent.interval || 1}
                        onChange={(e) => setEditingEvent({ ...editingEvent, interval: parseInt(e.target.value) })}
                        className="w-20 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                      />
                      <span className="text-sm text-gray-600">
                        {editingEvent.frequency === 'DAILY' && 'дней'}
                        {editingEvent.frequency === 'WEEKLY' && (editingEvent.interval === 1 ? 'неделю' : 'недели')}
                        {editingEvent.frequency === 'MONTHLY' && (editingEvent.interval === 1 ? 'месяц' : 'месяца')}
                        {editingEvent.frequency === 'YEARLY' && (editingEvent.interval === 1 ? 'год' : 'года')}
                      </span>
                    </div>
                  </div>

                  {editingEvent.frequency === 'WEEKLY' && (
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-700">
                        Дни недели
                      </label>
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
                          const byweekday = editingEvent.byweekday || [];
                          const isSelected = byweekday.includes(day.value);
                          return (
                            <button
                              key={day.value}
                              type="button"
                              onClick={() => {
                                const current = editingEvent.byweekday || [];
                                const updated = isSelected
                                  ? current.filter((d: number) => d !== day.value)
                                  : [...current, day.value].sort();
                                setEditingEvent({ ...editingEvent, byweekday: updated });
                              }}
                              className={`rounded-lg px-2 py-1.5 text-xs font-medium transition ${
                                isSelected
                                  ? 'bg-sky-500 text-white'
                                  : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
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
                          <div className="mt-2 flex items-start gap-2 rounded-lg bg-blue-50 px-3 py-2 border border-blue-200">
                            <svg className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-xs text-blue-800">
                              Первое событие: <span className="font-medium">{firstOccurrence}</span>
                            </p>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  )}

                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      Окончание повторения
                    </label>
                    <div className="flex items-center gap-2 mb-2">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={editingEvent.useCount === false}
                          onChange={() => setEditingEvent({ ...editingEvent, useCount: false, count: undefined })}
                          className="h-4 w-4 text-sky-500 focus:ring-sky-500"
                        />
                        <span className="text-sm text-gray-700">До даты</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={editingEvent.useCount === true}
                          onChange={() => setEditingEvent({ ...editingEvent, useCount: true, end_recurring_period: undefined })}
                          className="h-4 w-4 text-sky-500 focus:ring-sky-500"
                        />
                        <span className="text-sm text-gray-700">Количество раз</span>
                      </label>
                    </div>

                    {editingEvent.useCount ? (
                      <input
                        type="number"
                        min="1"
                        max="999"
                        value={editingEvent.count || 10}
                        onChange={(e) => setEditingEvent({ ...editingEvent, count: parseInt(e.target.value) })}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                        placeholder="Количество повторений"
                      />
                    ) : (
                      <input
                        type="date"
                        value={editingEvent.end_recurring_period || ''}
                        onChange={(e) => setEditingEvent({ ...editingEvent, end_recurring_period: e.target.value })}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                        min={new Date().toISOString().slice(0, 10)}
                      />
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Event Participants */}
          {showParticipants && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">
                  Участники события
                  {!eventParticipantsLoading && eventParticipants.length > 0 && (
                    <span className="ml-1 text-gray-500">({eventParticipants.length})</span>
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
                  className="text-xs text-sky-600 hover:text-sky-700 font-medium"
                >
                  {showAddParticipants ? 'Отмена' : '+ Добавить участников'}
                </button>
              </div>

              {/* Pending участники для нового события */}
              {!editingEvent.id && pendingParticipantIds.length > 0 && (
                <div className="space-y-2 mb-3">
                  <p className="text-xs text-blue-600 font-medium">Будут добавлены после создания:</p>
                  {pendingParticipantIds.map(userId => {
                    const emp = availableEmployees.find(e => e.id === userId);
                    return emp ? (
                      <div
                        key={userId}
                        className="flex items-center justify-between rounded-lg bg-blue-50 px-3 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <div className="h-6 w-6 rounded-full bg-blue-100 flex items-center justify-center">
                            <span className="text-xs font-medium text-blue-700">
                              {emp.first_name?.[0] || '?'}
                            </span>
                          </div>
                          <div className="text-xs">
                            <div className="font-medium text-gray-900">{emp.first_name} {emp.last_name}</div>
                            <div className="text-gray-500">attendee</div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setPendingParticipantIds(pendingParticipantIds.filter(id => id !== userId))}
                          className="text-red-600 hover:text-red-700 p-1 rounded hover:bg-red-50"
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
                <p className="text-xs text-gray-500 py-2">Загрузка...</p>
              ) : editingEvent.id && eventParticipants.length > 0 ? (
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {eventParticipants.map((participant: any) => (
                    <div
                      key={participant.id}
                      className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full bg-sky-100 flex items-center justify-center">
                          <span className="text-xs font-medium text-sky-700">
                            {participant.user_name?.[0] || '?'}
                          </span>
                        </div>
                        <div className="text-xs">
                          <div className="font-medium text-gray-900">{participant.user_name}</div>
                          <div className="text-gray-500">{participant.distinction || 'attendee'}</div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveParticipant(participant.id)}
                        className="text-red-600 hover:text-red-700 p-1 rounded hover:bg-red-50"
                        title="Удалить участника"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : editingEvent.id ? (
                <p className="text-xs text-gray-500 py-2">Нет участников</p>
              ) : !pendingParticipantIds.length ? (
                <p className="text-xs text-gray-500 py-2">Добавьте участников после создания или выберите их до сохранения</p>
              ) : null}

              {/* Форма добавления участников */}
              {showAddParticipants && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-3">
                  <input
                    type="text"
                    placeholder="Поиск сотрудников..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  />

                  {loadingEmployees ? (
                    <p className="text-xs text-gray-500 py-2">Загрузка сотрудников...</p>
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
                              className="flex items-center gap-2 p-2 rounded hover:bg-white cursor-pointer"
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
                                className="h-4 w-4 rounded border-gray-300 text-sky-500 focus:ring-2 focus:ring-sky-100"
                              />
                              <div className="text-xs">
                                <div className="font-medium text-gray-900">
                                  {emp.first_name} {emp.last_name}
                                </div>
                                {emp.email && <div className="text-gray-500">{emp.email}</div>}
                              </div>
                            </label>
                          ))}
                      </div>

                      {selectedEmployeeIds.length > 0 && (
                        <button
                          type="button"
                          onClick={handleAddParticipants}
                          disabled={addingParticipants}
                          className="w-full rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-600 disabled:opacity-50"
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

          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={!editingEvent.title?.trim() || saving}
              className="flex-1 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Сохранение...' : (editingEvent.id ? 'Сохранить' : 'Создать')}
            </button>

            {editingEvent.id && (
              <button
                onClick={handleDelete}
                disabled={saving}
                className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-100 disabled:opacity-50"
                title="Удалить событие"
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
