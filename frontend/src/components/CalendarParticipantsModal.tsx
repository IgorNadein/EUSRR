'use client';

import React, { useState, useEffect } from 'react';
import { X, UserPlus, Trash2 } from 'lucide-react';
import api from '@/lib/api';
import { Modal } from '@/components/ui';

interface Participant {
  id: number;
  user: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
  };
  distinction: string;
}

interface Employee {
  id: number;
  username?: string;
  first_name: string;
  last_name: string;
  email?: string;
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
      const data = await api.getEmployees({ limit: 200 });
      setEmployees(data.results || []);
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
    <Modal isOpen={isOpen} onClose={onClose} size="md" noPadding>
      <div className="overflow-y-auto">
        <div className="flex items-center justify-between border-b px-4 sm:px-6 py-3 sm:py-4">
          <div>
            <h2 className="text-base sm:text-lg font-semibold text-gray-900">Участники календаря</h2>
            <p className="text-xs sm:text-sm text-gray-500">{calendarName}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 hover:bg-gray-100 transition"
          >
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Add Participant Section - только для владельца */}
          {isOwner && (
            <div className="rounded-lg bg-gray-50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-900">
                  Добавить участников 
                  {selectedUserIds.length > 0 && (
                    <span className="ml-2 text-sky-600">
                      (выбрано: {selectedUserIds.length})
                    </span>
                  )}
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    disabled={availableEmployees.length === 0}
                    className="text-xs text-sky-600 hover:text-sky-700 disabled:opacity-50"
                  >
                    Выбрать всех
                  </button>
                  {selectedDepartment && (
                    <button
                      onClick={selectAllFromDepartment}
                      className="text-xs text-sky-600 hover:text-sky-700"
                    >
                      Добавить весь отдел
                    </button>
                  )}
                  <button
                    onClick={deselectAll}
                    disabled={selectedUserIds.length === 0}
                    className="text-xs text-gray-600 hover:text-gray-700 disabled:opacity-50"
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
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                />
                
                <select
                  value={selectedDepartment}
                  onChange={(e) => {
                    setSelectedDepartment(e.target.value);
                    setSelectedUserIds([]); // Сбрасываем выбор при смене отдела
                  }}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
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
                <div className="max-h-60 overflow-y-auto rounded-lg border border-gray-200 bg-white">
                  {availableEmployees.map(emp => (
                    <label
                      key={emp.id}
                      className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer transition"
                    >
                      <input
                        type="checkbox"
                        checked={selectedUserIds.includes(emp.id)}
                        onChange={() => toggleUserSelection(emp.id)}
                        className="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                      />
                      <span className="text-sm text-gray-900">
                        {emp.first_name} {emp.last_name}
                      </span>
                      {emp.email && (
                        <span className="text-xs text-gray-500">({emp.email})</span>
                      )}
                    </label>
                  ))}
                </div>
              )}

              {availableEmployees.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">
                  {searchQuery ? 'Сотрудники не найдены' : 'Все сотрудники уже добавлены'}
                </p>
              )}

              <div className="flex gap-2">
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                >
                  <option value="viewer">Просмотр</option>
                  <option value="editor">Редактор</option>
                  <option value="owner">Владелец</option>
                </select>

                <button
                  onClick={handleAddParticipants}
                  disabled={selectedUserIds.length === 0 || loading}
                  className="flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <UserPlus size={16} />
                  {loading ? 'Добавление...' : `Добавить (${selectedUserIds.length})`}
                </button>
              </div>
            </div>
          )}

          {/* Participants List */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">
              Текущие участники ({participants.length})
            </h3>
            
            <div className="space-y-2">
              {participants.length === 0 ? (
                <p className="text-sm text-gray-500 py-4 text-center">Нет участников</p>
              ) : (
                participants.map((participant) => {
                  const user = participant.user || {};
                  const firstName = user.first_name || 'N';
                  const lastName = user.last_name || 'A';
                  const username = user.username || 'unknown';
                  
                  return (
                    <div
                      key={participant.id}
                      className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50 transition"
                    >
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-sky-100 flex items-center justify-center">
                          <span className="text-sm font-medium text-sky-700">
                            {firstName[0]}{lastName[0]}
                          </span>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {firstName} {lastName}
                          </div>
                          <div className="text-xs text-gray-500">@{username}</div>
                        </div>
                      </div>

                    <div className="flex items-center gap-3">
                      <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                        participant.distinction === 'owner'
                          ? 'bg-purple-100 text-purple-700'
                          : participant.distinction === 'editor'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}>
                        {participant.distinction === 'owner' ? 'Владелец' :
                         participant.distinction === 'editor' ? 'Редактор' : 'Просмотр'}
                      </span>

                      {isOwner && participant.distinction !== 'owner' && (
                        <button
                          onClick={() => handleRemoveParticipant(participant.user.id)}
                          disabled={loading}
                          className="rounded-lg p-2 hover:bg-red-50 text-red-600 transition disabled:opacity-50"
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

        <div className="flex justify-end gap-3 border-t px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-200"
          >
            Закрыть
          </button>
        </div>
      </div>
    </Modal>
  );
}
