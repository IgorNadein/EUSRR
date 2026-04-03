"use client";

import { useState, useEffect } from "react";
import { X, Search, Check } from "lucide-react";
import apiClient from "@/lib/api";
import { Modal } from "@/components/ui";

interface Employee {
  id: number;
  first_name: string;
  last_name: string;
  middle_name?: string;
  avatar?: string;
  position?: string;
  department?: {
    id: number;
    name: string;
  };
}

interface NewChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onChatCreated: (chatId: number) => void;
}

export default function NewChatModal({ isOpen, onClose, onChatCreated }: NewChatModalProps) {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployees, setSelectedEmployees] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [chatName, setChatName] = useState("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  // Загрузка сотрудников
  useEffect(() => {
    if (isOpen) {
      loadEmployees();
    }
  }, [isOpen, searchQuery]);

  const loadEmployees = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getEmployees({ search: searchQuery });
      setEmployees(response.results || response);
    } catch (error) {
      console.error("Failed to load employees:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleEmployee = (employeeId: number) => {
    setSelectedEmployees(prev => 
      prev.includes(employeeId)
        ? prev.filter(id => id !== employeeId)
        : [...prev, employeeId]
    );
  };

  const handleCreateChat = async () => {
    if (selectedEmployees.length === 0) {
      alert("Выберите хотя бы одного участника");
      return;
    }

    setCreating(true);
    try {
      // Определяем тип чата (приватный или групповой)
      const isGroup = selectedEmployees.length > 1;
      const chatType = isGroup ? "group" : "private";

      const chatData: any = {
        type: chatType,
        participants: selectedEmployees,
      };

      // Для групповых чатов добавляем название
      if (isGroup && chatName.trim()) {
        chatData.name = chatName.trim();
      }

      const newChat = await apiClient.createChat(chatData);
      
      // Уведомляем родительский компонент о новом чате
      onChatCreated(newChat.id);
      
      // Сбрасываем форму
      setSelectedEmployees([]);
      setChatName("");
      setSearchQuery("");
      onClose();
    } catch (error) {
      console.error("Failed to create chat:", error);
      alert("Не удалось создать чат. Попробуйте еще раз.");
    } finally {
      setCreating(false);
    }
  };

  const getEmployeeFullName = (emp: Employee) => {
    return `${emp.last_name} ${emp.first_name} ${emp.middle_name || ""}`.trim();
  };

  const isGroup = selectedEmployees.length > 1;

  const footerContent = (
    <div className="flex justify-end gap-2">
      <button
        onClick={onClose}
        disabled={creating}
        className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
      >
        Отмена
      </button>
      <button
        onClick={handleCreateChat}
        disabled={selectedEmployees.length === 0 || creating}
        className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {creating ? "Создание..." : "Создать чат"}
      </button>
    </div>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Новый чат" size="md" closeOnEsc={!creating} noPadding footer={footerContent}>
      {/* Chat Name (for groups) */}
      {isGroup && (
        <div className="p-3 sm:p-4 border-b">
          <input
            type="text"
            placeholder="Название группы (необязательно)"
            value={chatName}
            onChange={(e) => setChatName(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm sm:text-base"
          />
        </div>
      )}

      {/* Selected Employees */}
      {selectedEmployees.length > 0 && (
        <div className="p-3 sm:p-4 border-b bg-gray-50">
          <div className="text-sm text-gray-600 mb-2">
            Выбрано: {selectedEmployees.length}
          </div>
          <div className="flex flex-wrap gap-2">
            {employees
              .filter(emp => selectedEmployees.includes(emp.id))
              .map(emp => (
                <div
                  key={emp.id}
                  className="flex items-center gap-2 bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm"
                >
                  <span>{getEmployeeFullName(emp)}</span>
                  <button
                    onClick={() => toggleEmployee(emp.id)}
                    className="hover:bg-blue-200 rounded-full p-0.5"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Search */}
      <div className="p-3 sm:p-4 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Поиск сотрудников..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm sm:text-base"
          />
        </div>
      </div>

      {/* Employee List */}
      <div className="max-h-[60vh] overflow-y-auto p-4">
        {loading ? (
          <div className="text-center py-8 text-gray-500">
            Загрузка сотрудников...
          </div>
        ) : employees.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Сотрудники не найдены
          </div>
        ) : (
          <div className="space-y-2">
            {employees.map((emp) => {
              const isSelected = selectedEmployees.includes(emp.id);
              return (
                <button
                  key={emp.id}
                  onClick={() => toggleEmployee(emp.id)}
                  className={`
                    w-full flex items-center gap-3 p-3 rounded-lg transition-colors
                    ${isSelected 
                      ? "bg-blue-50 border-2 border-blue-500" 
                      : "bg-gray-50 hover:bg-gray-100 border-2 border-transparent"
                    }
                  `}
                >
                  {/* Avatar */}
                  <div className="relative flex-shrink-0">
                    {emp.avatar ? (
                      <img
                        src={emp.avatar}
                        alt={getEmployeeFullName(emp)}
                        className="w-10 h-10 rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-semibold">
                        {emp.first_name[0]}{emp.last_name[0]}
                      </div>
                    )}
                    {isSelected && (
                      <div className="absolute -top-1 -right-1 bg-blue-500 rounded-full p-0.5">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                  </div>

                  {/* Employee Info */}
                  <div className="flex-1 text-left">
                    <div className="font-medium text-gray-900">
                      {getEmployeeFullName(emp)}
                    </div>
                    {emp.position && (
                      <div className="text-sm text-gray-600">{emp.position}</div>
                    )}
                    {emp.department && (
                      <div className="text-xs text-gray-500">{emp.department.name}</div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}
