'use client';

import React, { useState, useEffect } from 'react';
import { X, UserPlus, Trash2 } from 'lucide-react';
import api from '@/lib/api';
import { Modal } from '@/components/ui';
import { loadAllPages } from '@/lib/shared';
import { resolveMediaUrl } from '@/lib/url';

interface Participant {
  id: number;
  user: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    email?: string;
    avatar?: string | null;
  };
  distinction: string;
}

interface Employee {
  id: number;
  username?: string;
  first_name: string;
  last_name: string;
  email?: string;
  avatar?: string | null;
  departments?: Array<{
    id: number;
    name: string;
  }>;
}

interface Department {
  id: number;
  name: string;
}

interface CalendarParticipantsModalProps {
  isOpen: boolean;
  onClose: () => void;
  calendarId: number;
  calendarName: string;
  userRole?: string; // owner, editor, viewer
}

export default function CalendarParticipantsModal({
  isOpen,
  onClose,
  calendarId,
  calendarName,
  userRole,
}: CalendarParticipantsModalProps) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([]);
  const [selectedRole, setSelectedRole] = useState<string>('viewer');
  const [selectedDepartment, setSelectedDepartment] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const isOwner = userRole === 'owner';

  useEffect(() => {
    if (isOpen) {
      loadParticipants();
      loadEmployees();
      loadDepartments();
    }
  }, [isOpen, calendarId]);

  const loadParticipants = async () => {
    try {
      const data = await api.getCalendarParticipants(calendarId);
      setParticipants(data);
    } catch (error) {
      console.error('Failed to load participants:', error);
    }
  };

  const loadEmployees = async () => {
    try {
      const allEmployees = await loadAllPages<Employee>((params) => api.getEmployees(params));
      setEmployees(allEmployees);
    } catch (error) {
      console.error('Failed to load employees:', error);
    }
  };

  const loadDepartments = async () => {
    try {
      const data = await api.getDepartments({ limit: 100 });
      setDepartments(data.results || []);
    } catch (error) {
      console.error('Failed to load departments:', error);
    }
  };

  const handleAddParticipants = async () => {
    if (selectedUserIds.length === 0) {
      alert('Выберите хотя бы одного сотрудника');
      return;
    }

    setLoading(true);
    try {
      // Добавляем всех выбранных участников последовательно
      for (const userId of selectedUserIds) {
        await api.addCalendarParticipant(calendarId, userId, selectedRole);
      }
      
      await loadParticipants();
      setSelectedUserIds([]);
      setSearchQuery('');
      setSelectedRole('viewer');
      alert(`Успешно добавлено участников: ${selectedUserIds.length}`);
    } catch (error) {
      console.error('Failed to add participants:', error);
      alert('Не удалось добавить участников');
    } finally {
      setLoading(false);
    }
  };

  const toggleUserSelection = (userId: number) => {
    setSelectedUserIds(prev => 
      prev.includes(userId) 
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  const selectAll = () => {
    const availableUserIds = filteredAndDepartmentEmployees.map(emp => emp.id);
    setSelectedUserIds(availableUserIds);
  };

  const selectAllFromDepartment = () => {
    if (!selectedDepartment) return;
    const departmentEmployees = filteredAndDepartmentEmployees.filter(emp =>
      emp.departments?.some(d => d.id === parseInt(selectedDepartment))
    );
    const departmentUserIds = departmentEmployees.map(emp => emp.id);
    setSelectedUserIds(prev => [...new Set([...prev, ...departmentUserIds])]);
  };

  const deselectAll = () => {
    setSelectedUserIds([]);
  };

  const handleRemoveParticipant = async (userId: number) => {
    if (!confirm('Удалить участника из календаря?')) return;

    setLoading(true);
    try {
      await api.removeCalendarParticipant(calendarId, userId);
      await loadParticipants();
    } catch (error) {
      console.error('Failed to remove participant:', error);
      alert('Не удалось удалить участника');
    } finally {
      setLoading(false);
    }
  };

  const filteredEmployees = employees.filter(emp => {
    const fullName = `${emp.first_name} ${emp.last_name} ${emp.email || ''}`.toLowerCase();
    const matchesSearch = fullName.includes(searchQuery.toLowerCase());
    
    return matchesSearch;
  });

  const filteredAndDepartmentEmployees = filteredEmployees.filter(emp => {
    // Если выбран отдел, фильтруем по нему
    if (selectedDepartment) {
      return emp.departments?.some(d => d.id === parseInt(selectedDepartment));
    }
    return true;
  });

  const availableEmployees = filteredAndDepartmentEmployees.filter(emp =>
    !participants.find(p => p.user?.id === emp.id)
  );

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md" noPadding noHeader>
      <div className="overflow-y-auto">
        <div className="app-divider flex items-center justify-between border-b px-4 py-3 sm:px-6 sm:py-4">
          <div>
            <h2 className="text-base font-semibold text-[var(--foreground)] sm:text-lg">Участники календаря</h2>
            <p className="app-text-muted text-xs sm:text-sm">{calendarName}</p>
          </div>
          <button
            onClick={onClose}
            className="app-action-ghost rounded-lg p-2 transition"
          >
            <X size={20} className="app-text-muted" />
          </button>
        </div>

        <div className="space-y-6 p-6">
          {/* Add Participant Section - только для владельца */}
          {isOwner && (
            <div className="app-surface-muted space-y-3 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-[var(--foreground)]">
                  Добавить участников 
                  {selectedUserIds.length > 0 && (
                    <span className="app-accent-text ml-2">
                      (выбрано: {selectedUserIds.length})
                    </span>
                  )}
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    disabled={availableEmployees.length === 0}
                    className="app-link-accent text-xs disabled:opacity-50"
                  >
                    Выбрать всех
                  </button>
                  {selectedDepartment && (
                    <button
                      onClick={selectAllFromDepartment}
                      className="app-link-accent text-xs"
                    >
                      Добавить весь отдел
                    </button>
                  )}
                  <button
                    onClick={deselectAll}
                    disabled={selectedUserIds.length === 0}
                    className="app-text-muted text-xs hover:text-[var(--foreground)] disabled:opacity-50"
                  >
                    Снять выбор
                  </button>
                </div>
              </div>
              
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Поиск сотрудника..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="app-input flex-1 rounded-lg px-3 py-2 text-sm"
                />
                
                <select
                  value={selectedDepartment}
                  onChange={(e) => {
                    setSelectedDepartment(e.target.value);
                    setSelectedUserIds([]); // Сбрасываем выбор при смене отдела
                  }}
                  className="app-select rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Все отделы</option>
                  {departments.map(dept => (
                    <option key={dept.id} value={dept.id}>
                      {dept.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Employee list with checkboxes */}
              {availableEmployees.length > 0 && (
                <div className="app-surface max-h-60 overflow-y-auto rounded-lg">
                  {availableEmployees.map(emp => (
                    <label
                      key={emp.id}
                      className="flex cursor-pointer items-center gap-3 px-3 py-2 transition hover:bg-[var(--surface-secondary)]"
                    >
                      <input
                        type="checkbox"
                        checked={selectedUserIds.includes(emp.id)}
                        onChange={() => toggleUserSelection(emp.id)}
                        className="h-4 w-4 rounded border-[var(--border-strong)] text-[var(--accent-primary)]"
                      />
                      {emp.avatar ? (
                        <img
                          src={resolveMediaUrl(emp.avatar)}
                          alt={`${emp.first_name} ${emp.last_name}`.trim() || 'Сотрудник'}
                          className="app-avatar-frame h-9 w-9 shrink-0 rounded-full object-cover"
                        />
                      ) : (
                        <div className="app-avatar-fallback flex h-9 w-9 shrink-0 items-center justify-center rounded-full">
                          <span className="text-xs font-medium">
                            {emp.first_name?.[0] || emp.last_name?.[0] || '?'}
                          </span>
                        </div>
                      )}
                      <div className="min-w-0">
                        <div className="truncate text-sm text-[var(--foreground)]">
                          {emp.first_name} {emp.last_name}
                        </div>
                        {emp.email && (
                          <div className="truncate app-text-muted text-xs">{emp.email}</div>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {availableEmployees.length === 0 && (
                <p className="app-text-muted py-4 text-center text-sm">
                  {searchQuery ? 'Сотрудники не найдены' : 'Все сотрудники уже добавлены'}
                </p>
              )}

              <div className="flex gap-2">
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className="app-select flex-1 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="viewer">Просмотр</option>
                  <option value="editor">Редактор</option>
                  <option value="owner">Владелец</option>
                </select>

                <button
                  onClick={handleAddParticipants}
                  disabled={selectedUserIds.length === 0 || loading}
                  className="app-action-primary flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <UserPlus size={16} />
                  {loading ? 'Добавление...' : `Добавить (${selectedUserIds.length})`}
                </button>
              </div>
            </div>
          )}

          {/* Participants List */}
          <div>
            <h3 className="mb-3 text-sm font-medium text-[var(--foreground)]">
              Текущие участники ({participants.length})
            </h3>
            
            <div className="space-y-2">
              {participants.length === 0 ? (
                <p className="app-text-muted py-4 text-center text-sm">Нет участников</p>
              ) : (
                participants.map((participant) => {
                  const user = participant.user || {};
                  const firstName = user.first_name || 'N';
                  const lastName = user.last_name || 'A';
                  const username = user.username || 'unknown';
                  
                  return (
                    <div
                      key={participant.id}
                      className="app-surface-elevated flex items-center justify-between rounded-lg px-4 py-3 transition hover:bg-[var(--surface-secondary)]"
                    >
                      <div className="flex items-center gap-3">
                        {user.avatar ? (
                          <img
                            src={resolveMediaUrl(user.avatar)}
                            alt={`${firstName} ${lastName}`.trim() || 'Сотрудник'}
                            className="app-avatar-frame h-10 w-10 shrink-0 rounded-full object-cover"
                          />
                        ) : (
                          <div className="app-avatar-fallback flex h-10 w-10 items-center justify-center rounded-full">
                            <span className="text-sm font-medium">
                              {firstName[0]}{lastName[0]}
                            </span>
                          </div>
                        )}
                        <div>
                          <div className="text-sm font-medium text-[var(--foreground)]">
                            {firstName} {lastName}
                          </div>
                          <div className="app-text-muted text-xs">{user.email || `@${username}`}</div>
                        </div>
                      </div>

                    <div className="flex items-center gap-3">
                      <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                        participant.distinction === 'owner'
                          ? 'app-badge'
                          : participant.distinction === 'editor'
                          ? 'app-selected app-accent-text'
                          : 'app-badge'
                      }`}>
                        {participant.distinction === 'owner' ? 'Владелец' :
                         participant.distinction === 'editor' ? 'Редактор' : 'Просмотр'}
                      </span>

                      {isOwner && participant.distinction !== 'owner' && (
                        <button
                          onClick={() => handleRemoveParticipant(participant.user.id)}
                          disabled={loading}
                          className="app-action-danger rounded-lg p-2 transition disabled:opacity-50"
                          title="Удалить участника"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <div className="app-divider flex justify-end gap-3 border-t px-6 py-4">
          <button
            onClick={onClose}
            className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium"
          >
            Закрыть
          </button>
        </div>
      </div>
    </Modal>
  );
}
