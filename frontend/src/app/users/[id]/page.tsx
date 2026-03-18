"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Mail, Phone, MessageCircle, Copy, Check, Building2, Award, Calendar, Clock, Pencil, X, History, Trash2 } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import { useUser } from "@/contexts/UserContext";
import type { User } from "@/types/api";

export default function UserDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user: currentUser } = useUser();
  const userId = Number(params?.id);

  const [person, setPerson] = useState<User | null>(null);
  const [avatarFailed, setAvatarFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingChat, setCreatingChat] = useState(false);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);

  // Состояния для модального окна редактирования
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isActionModalOpen, setIsActionModalOpen] = useState(false);
  const [editFirstName, setEditFirstName] = useState("");
  const [editLastName, setEditLastName] = useState("");
  const [editPatronymic, setEditPatronymic] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editTelegram, setEditTelegram] = useState("");
  const [editWhatsApp, setEditWhatsApp] = useState("");
  const [editWeChat, setEditWeChat] = useState("");
  const [editAvatarFile, setEditAvatarFile] = useState<File | null>(null);
  const [editAvatarPreview, setEditAvatarPreview] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Состояния для модального окна кадровых событий
  const [actionType, setActionType] = useState("");
  const [actionDate, setActionDate] = useState(new Date().toISOString().split('T')[0]);
  const [actionComment, setActionComment] = useState("");
  const [editingActionId, setEditingActionId] = useState<number | null>(null);

  useEffect(() => {
    async function loadUser() {
      if (!userId || Number.isNaN(userId)) {
        setError("Некорректный идентификатор пользователя");
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getEmployee(userId);
        setPerson(data);
      } catch (e: any) {
        setError(String(e?.message || "Не удалось загрузить пользователя"));
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, [userId]);

  useEffect(() => {
    setAvatarFailed(false);
  }, [person?.avatar, person?.id]);

  const fullName = useMemo(() => {
    if (!person) return "";
    return `${person.last_name || ""} ${person.first_name || ""} ${person.patronymic || ""}`.trim() || "Пользователь";
  }, [person]);

  // Последний статус сотрудника
  const latestAction = useMemo(() => {
    if (!person?.actions || person.actions.length === 0) return null;
    return person.actions.reduce((latest, action) => 
      new Date(action.date) > new Date(latest.date) ? action : latest
    );
  }, [person?.actions]);

  // Отсортированная история событий (от новых к старым)
  const sortedActions = useMemo(() => {
    if (!person?.actions || person.actions.length === 0) return [];
    return [...person.actions].sort((a, b) => 
      new Date(b.date).getTime() - new Date(a.date).getTime()
    );
  }, [person?.actions]);

  const avatarUrl = resolveMediaUrl(person?.avatar);
  const initials = `${person?.last_name?.[0] || ""}${person?.first_name?.[0] || ""}` || "П";

  // Копирование в буфер обмена
  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopySuccess(label);
      setTimeout(() => setCopySuccess(null), 2000);
    } catch (err) {
      console.error("Ошибка копирования:", err);
    }
  };

  // Создание чата с пользователем
  const handleStartChat = async () => {
    if (!person || !currentUser || creatingChat) return;
    
    try {
      setCreatingChat(true);
      
      // Сначала ищем существующий директ-чат с этим пользователем
      const chatsResponse = await apiClient.getChats();
      const allChats = chatsResponse.results || chatsResponse;
      
      // Ищем приватный чат где участники - только мы и нужный пользователь
      const existingChat = allChats.find((chat: any) => {
        if (chat.type !== 'private') return false;
        
        const memberIds: number[] = chat.member_ids || [];
        return memberIds.length === 2 &&
               memberIds.includes(currentUser.id) &&
               memberIds.includes(person.id);
      });
      
      if (existingChat) {
        // Если чат уже существует - переходим в него
        router.push(`/messages/${existingChat.id}`);
      } else {
        // Если не существует - создаем новый
        const chat = await apiClient.createChat({
          type: 'private',
          name: 'Диалог',
          participants: [person.id]
        });
        router.push(`/messages/${chat.id}`);
      }
    } catch (err: any) {
      console.error("Ошибка создания чата:", err);
      alert("Не удалось открыть чат");
    } finally {
      setCreatingChat(false);
    }
  };

  // Форматирование телефона для ссылок
  const formatPhoneForLink = (phone: string) => {
    return phone.replace(/[^0-9+]/g, '');
  };

  // Вычисление стажа
  const getWorkDuration = (dateJoined?: string) => {
    if (!dateJoined) return null;
    const start = new Date(dateJoined);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    const years = Math.floor(diffDays / 365);
    const months = Math.floor((diffDays % 365) / 30);
    
    const parts = [];
    if (years > 0) parts.push(`${years} ${years === 1 ? 'год' : years < 5 ? 'года' : 'лет'}`);
    if (months > 0) parts.push(`${months} ${months === 1 ? 'месяц' : months < 5 ? 'месяца' : 'месяцев'}`);
    
    return parts.join(' ') || 'меньше месяца';
  };

  // Форматирование даты рождения (без года)
  const formatBirthday = (birthDate?: string) => {
    if (!birthDate) return null;
    const date = new Date(birthDate);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
  };

  // Закрытие модального окна действий
  const handleCloseActionModal = () => {
    setIsActionModalOpen(false);
    setActionType("");
    setActionDate(new Date().toISOString().split('T')[0]);
    setActionComment("");
    setEditingActionId(null);
  };

  // Открытие модального окна действий для создания
  const handleOpenActionModal = () => {
    setEditingActionId(null);
    setActionType("");
    setActionDate(new Date().toISOString().split('T')[0]);
    setActionComment("");
    setIsActionModalOpen(true);
  };

  // Открытие модального окна для редактирования события
  const handleEditAction = (action: any) => {
    setEditingActionId(action.id);
    setActionType(action.action);
    setActionDate(action.date);
    setActionComment(action.comment || "");
    setIsActionModalOpen(true);
  };

  // Удаление кадрового события
  const handleDeleteAction = async (actionId: number) => {
    if (!confirm('Вы уверены, что хотите удалить это событие?')) return;
    
    setActionLoading(`delete-${actionId}`);
    try {
      await apiClient.deleteEmployeeAction(actionId);
      
      // Перезагружаем данные
      const refreshedData = await apiClient.getEmployee(userId);
      setPerson(refreshedData);
    } catch (err: any) {
      console.error("Ошибка при удалении события:", err);
      alert("Не удалось удалить событие");
    } finally {
      setActionLoading(null);
    }
  };

  // Сохранение кадрового события
  const handleSaveAction = async () => {
    if (!person || !userId || !actionType) return;
    
    setActionLoading("action");
    try {
      if (editingActionId) {
        // Редактирование существующего события
        await apiClient.updateEmployeeAction(editingActionId, {
          action: actionType,
          date: actionDate,
          comment: actionComment.trim() || undefined,
        });
      } else {
        // Создание нового события
        await apiClient.createEmployeeAction({
          employee: userId,
          action: actionType,
          date: actionDate,
          comment: actionComment.trim() || undefined,
        });
      }

      // Перезагружаем данные сотрудника
      const refreshedData = await apiClient.getEmployee(userId);
      setPerson(refreshedData);
      
      handleCloseActionModal();
    } catch (err: any) {
      console.error("Ошибка при создании события:", err);
      alert("Не удалось сохранить событие");
    } finally {
      setActionLoading(null);
    }
  };

  // Открытие модального окна редактирования
  const handleOpenEditModal = () => {
    if (!person) return;
    setEditFirstName(person.first_name || "");
    setEditLastName(person.last_name || "");
    setEditPatronymic(person.patronymic || "");
    setEditEmail(person.email || "");
    setEditPhone(person.phone_number || "");
    setEditTelegram(person.telegram || "");
    setEditWhatsApp(person.whatsapp || "");
    setEditWeChat(person.wechat || "");
    setEditAvatarFile(null);
    setEditAvatarPreview(null);
    setIsEditModalOpen(true);
  };

  // Закрытие модального окна
  const handleCloseEditModal = () => {
    setIsEditModalOpen(false);
    setEditAvatarFile(null);
    setEditAvatarPreview(null);
  };

  // Обработка выбора аватара
  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Проверка размера (макс 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert("Файл слишком большой. Максимальный размер: 5MB");
      return;
    }

    // Проверка типа
    if (!file.type.startsWith("image/")) {
      alert("Можно загружать только изображения");
      return;
    }

    setEditAvatarFile(file);

    // Создаём preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setEditAvatarPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  // Сохранение изменений
  const handleSaveEdit = async () => {
    if (!person || !userId) return;
    
    setActionLoading("edit");
    try {
      // Обновляем данные сотрудника
      const updatedData = await apiClient.updateEmployee(userId, {
        first_name: editFirstName.trim(),
        last_name: editLastName.trim(),
        patronymic: editPatronymic.trim() || undefined,
        email: editEmail.trim(),
        phone_number: editPhone.trim() || undefined,
        telegram: editTelegram.trim() || undefined,
        whatsapp: editWhatsApp.trim() || undefined,
        wechat: editWeChat.trim() || undefined,
      });

      // Загружаем аватар если выбран
      if (editAvatarFile) {
        await apiClient.uploadEmployeeAvatar(userId, editAvatarFile);
      }

      // Перезагружаем данные сотрудника
      const refreshedData = await apiClient.getEmployee(userId);
      setPerson(refreshedData);
      
      handleCloseEditModal();
    } catch (err: any) {
      console.error("Ошибка при обновлении сотрудника:", err);
      alert("Не удалось обновить данные");
    } finally {
      setActionLoading(null);
    }
  };

  // Проверка прав на редактирование
  const canEdit = currentUser && (
    currentUser.auth?.is_staff || 
    currentUser.auth?.is_superuser || 
    currentUser.id === userId
  );

  // Проверка прав на управление кадровыми событиями (только админы)
  const canManageActions = currentUser && (
    currentUser.auth?.is_staff || 
    currentUser.auth?.is_superuser
  );

  // Проверка прав на просмотр истории кадровых событий
  const canViewActions = currentUser && (
    currentUser.auth?.is_staff || 
    currentUser.auth?.is_superuser ||
    currentUser.id === userId  // Сам пользователь может видеть свою историю
  );

  // Список типов кадровых событий
  const actionTypes = [
    { value: 'hired', label: 'Принят' },
    { value: 'dismissed', label: 'Уволен' },
    { value: 'on_leave', label: 'В отпуске' },
    { value: 'returned_from_leave', label: 'Вернулся из отпуска' },
    { value: 'on_maternity', label: 'В декрете' },
    { value: 'returned_from_maternity', label: 'Вернулся из декрета' },
    { value: 'transferred', label: 'Переведен' },
    { value: 'rehired', label: 'Восстановлен' },
  ];

  return (
    <AppShell>
      <div className="space-y-4">
        <Link href="/employees" className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
          ← К списку сотрудников
        </Link>

        {loading ? (
          <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
            <p className="text-sm text-gray-500">Загрузка...</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-red-50 p-6 text-center">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        ) : person ? (
          <>
            {/* Основная информация */}
            <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
              <div className="flex items-start gap-4">
                <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xl font-semibold text-white">
                  {avatarUrl && !avatarFailed ? (
                    <img
                      src={avatarUrl}
                      alt={fullName}
                      className="h-full w-full object-cover"
                      onError={() => setAvatarFailed(true)}
                    />
                  ) : (
                    <span>{initials}</span>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start gap-2">
                    <h1 className="flex-1 text-xl font-bold text-gray-900">{fullName}</h1>
                    {canEdit && (
                      <button
                        type="button"
                        onClick={handleOpenEditModal}
                        className="flex h-9 w-9 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
                        aria-label="Редактировать профиль"
                        title="Редактировать профиль"
                      >
                        <Pencil size={16} />
                      </button>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <p className="text-sm text-gray-600">{person.position?.name || "—"}</p>
                    {latestAction && (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        latestAction.action === 'on_leave' ? 'bg-yellow-100 text-yellow-700' :
                        latestAction.action === 'on_maternity' ? 'bg-purple-100 text-purple-700' :
                        latestAction.action === 'transferred' ? 'bg-blue-100 text-blue-700' :
                        latestAction.action === 'dismissed' ? 'bg-red-100 text-red-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {latestAction.action_display || latestAction.action}
                      </span>
                    )}
                    {canManageActions && (
                      <button
                        onClick={handleOpenActionModal}
                        className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 hover:bg-gray-200 transition"
                      >
                        + Событие
                      </button>
                    )}
                  </div>
                  {person.departments && person.departments.length > 0 && (
                    <p className="mt-1 text-sm text-gray-500">{person.departments[0].name}</p>
                  )}

                  {currentUser && currentUser.id !== person.id && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        onClick={handleStartChat}
                        disabled={creatingChat}
                        className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50"
                      >
                        <MessageCircle size={16} />
                        {creatingChat ? 'Загрузка...' : 'Написать'}
                      </button>
                      
                      {person.phone_number && (
                        <a
                          href={`tel:${formatPhoneForLink(person.phone_number)}`}
                          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                        >
                          <Phone size={16} />
                          Позвонить
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* Контакты и детали */}
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Контакты */}
              <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                <h2 className="mb-3 text-sm font-semibold text-gray-900">Контакты</h2>
                <div className="space-y-2">
                  {person.email && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <Mail size={16} className="text-gray-400 flex-shrink-0" />
                        <a href={`mailto:${person.email}`} className="text-sm text-sky-600 hover:underline truncate">
                          {person.email}
                        </a>
                      </div>
                      <button
                        onClick={() => copyToClipboard(person.email, 'email')}
                        className="ml-2 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        {copySuccess === 'email' ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                    </div>
                  )}

                  {person.phone_number && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <Phone size={16} className="text-gray-400 flex-shrink-0" />
                        <a href={`tel:${formatPhoneForLink(person.phone_number)}`} className="text-sm text-sky-600 hover:underline truncate">
                          {person.phone_number}
                        </a>
                      </div>
                      <button
                        onClick={() => copyToClipboard(person.phone_number!, 'phone')}
                        className="ml-2 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        {copySuccess === 'phone' ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                    </div>
                  )}

                  {person.telegram && (
                    <div className="flex items-center gap-2">
                      <MessageCircle size={16} className="text-gray-400 flex-shrink-0" />
                      <a
                        href={`https://t.me/${person.telegram.replace('@', '')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-sky-600 hover:underline truncate"
                      >
                        {person.telegram}
                      </a>
                      <span className="ml-auto text-xs text-gray-400">Telegram</span>
                    </div>
                  )}

                  {person.whatsapp && (
                    <div className="flex items-center gap-2">
                      <Phone size={16} className="text-gray-400 flex-shrink-0" />
                      <a
                        href={`https://wa.me/${formatPhoneForLink(person.whatsapp)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-sky-600 hover:underline truncate"
                      >
                        {person.whatsapp}
                      </a>
                      <span className="ml-auto text-xs text-gray-400">WhatsApp</span>
                    </div>
                  )}

                  {person.wechat && (
                    <div className="flex items-center gap-2">
                      <MessageCircle size={16} className="text-gray-400 flex-shrink-0" />
                      <span className="text-sm text-gray-700 truncate">{person.wechat}</span>
                      <span className="ml-auto text-xs text-gray-400">WeChat</span>
                    </div>
                  )}

                  {!person.email && !person.phone_number && !person.telegram && !person.whatsapp && !person.wechat && (
                    <p className="text-sm text-gray-500">Нет контактов</p>
                  )}
                </div>
              </section>

              {/* Навыки */}
              <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <Award size={16} />
                  Навыки
                </h2>
                {person.skills && person.skills.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {person.skills.map((skill) => (
                      <span
                        key={skill.id}
                        className="rounded-lg bg-gray-100 px-2.5 py-1 text-sm text-gray-700"
                      >
                        {skill.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Навыки не указаны</p>
                )}
              </section>

              {/* Информация */}
              {(person.date_joined || person.birth_date) && (
                <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100 lg:col-span-2">
                  <h2 className="mb-3 text-sm font-semibold text-gray-900">Информация</h2>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {person.date_joined && (
                      <>
                        <div className="flex items-center gap-2 text-sm">
                          <Clock size={16} className="text-gray-400" />
                          <div>
                            <p className="text-xs text-gray-500">В компании</p>
                            <p className="font-medium text-gray-900">
                              {getWorkDuration(person.date_joined)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <Calendar size={16} className="text-gray-400" />
                          <div>
                            <p className="text-xs text-gray-500">Дата найма</p>
                            <p className="font-medium text-gray-900">
                              {new Date(person.date_joined).toLocaleDateString('ru-RU')}
                            </p>
                          </div>
                        </div>
                      </>
                    )}
                    
                    {person.birth_date && (
                      <div className="flex items-center gap-2 text-sm">
                        <Calendar size={16} className="text-gray-400" />
                        <div>
                          <p className="text-xs text-gray-500">День рождения</p>
                          <p className="font-medium text-gray-900">
                            {formatBirthday(person.birth_date)}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}
            </div>

            {/* Отделы */}
            {person.departments && person.departments.length > 0 && (
              <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <Building2 size={16} />
                  Отделы
                </h2>
                <div className="space-y-2">
                  {person.departments.map((dept) => (
                    <Link
                      key={dept.id}
                      href={`/departments/${dept.id}`}
                      className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 hover:bg-gray-100 transition"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-900">{dept.name}</p>
                        {dept.role_name && (
                          <p className="text-xs text-gray-500">{dept.role_name}</p>
                        )}
                      </div>
                      {dept.is_head && (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">
                          Руководитель
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* История кадровых событий */}
            {canViewActions && sortedActions.length > 0 && (
              <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                    <History size={16} />
                    История кадровых событий
                  </h2>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                      {sortedActions.length} {sortedActions.length === 1 ? 'событие' : sortedActions.length < 5 ? 'события' : 'событий'}
                    </span>
                    {canManageActions && (
                      <button
                        onClick={handleOpenActionModal}
                        className="rounded-lg bg-sky-100 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-200 transition"
                      >
                        + Добавить
                      </button>
                    )}
                  </div>
                </div>
                <div className="space-y-3">
                  {sortedActions.map((action, index) => (
                    <div
                      key={action.id}
                      className="flex gap-3 border-l-2 pl-3 py-1"
                      style={{
                        borderColor: 
                          action.action === 'on_leave' ? '#eab308' :
                          action.action === 'on_maternity' ? '#a855f7' :
                          action.action === 'transferred' ? '#3b82f6' :
                          action.action === 'dismissed' ? '#ef4444' :
                          '#22c55e'
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                                action.action === 'on_leave' ? 'bg-yellow-100 text-yellow-700' :
                                action.action === 'on_maternity' ? 'bg-purple-100 text-purple-700' :
                                action.action === 'transferred' ? 'bg-blue-100 text-blue-700' :
                                action.action === 'dismissed' ? 'bg-red-100 text-red-700' :
                                'bg-green-100 text-green-700'
                              }`}>
                                {action.action_display || action.action}
                              </span>
                              {index === 0 && (
                                <span className="text-xs text-gray-500">текущий</span>
                              )}
                            </div>
                            {action.comment && (
                              <p className="mt-1 text-sm text-gray-600">{action.comment}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <time className="flex-shrink-0 text-xs text-gray-500">
                              {new Date(action.date).toLocaleDateString('ru-RU', {
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric'
                              })}
                            </time>
                            {canManageActions && (
                              <div className="flex gap-1">
                                <button
                                  onClick={() => handleEditAction(action)}
                                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-sky-600 transition"
                                  title="Редактировать"
                                  disabled={actionLoading === `delete-${action.id}`}
                                >
                                  <Pencil size={14} />
                                </button>
                                <button
                                  onClick={() => handleDeleteAction(action.id)}
                                  className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 transition"
                                  title="Удалить"
                                  disabled={actionLoading === `delete-${action.id}`}
                                >
                                  {actionLoading === `delete-${action.id}` ? (
                                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-red-600 border-t-transparent" />
                                  ) : (
                                    <Trash2 size={14} />
                                  )}
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        ) : null}
      </div>

      {/* Модальное окно редактирования */}
      {isEditModalOpen && person && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">Редактировать профиль</h2>
              <button
                type="button"
                onClick={handleCloseEditModal}
                className="text-gray-400 hover:text-gray-600"
                disabled={actionLoading === "edit"}
              >
                <X size={24} />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* Аватар */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Аватар
                </label>
                <div className="flex items-center gap-4">
                  <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xl font-semibold text-white">
                    {editAvatarPreview ? (
                      <img
                        src={editAvatarPreview}
                        alt="Preview"
                        className="h-full w-full object-cover"
                      />
                    ) : avatarUrl && !avatarFailed ? (
                      <img
                        src={avatarUrl}
                        alt="Avatar"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span>{initials}</span>
                    )}
                  </div>
                  <label className="cursor-pointer rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleAvatarChange}
                      className="hidden"
                    />
                    Загрузить
                  </label>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Максимальный размер: 5MB. Форматы: JPG, PNG, GIF
                </p>
              </div>

              {/* ФИО */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label htmlFor="edit-last-name" className="mb-2 block text-sm font-medium text-gray-700">
                    Фамилия *
                  </label>
                  <input
                    id="edit-last-name"
                    type="text"
                    value={editLastName}
                    onChange={(e) => setEditLastName(e.target.value)}
                    placeholder="Иванов"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                    maxLength={150}
                  />
                </div>
                
                <div>
                  <label htmlFor="edit-first-name" className="mb-2 block text-sm font-medium text-gray-700">
                    Имя *
                  </label>
                  <input
                    id="edit-first-name"
                    type="text"
                    value={editFirstName}
                    onChange={(e) => setEditFirstName(e.target.value)}
                    placeholder="Иван"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                    maxLength={150}
                  />
                </div>
                
                <div>
                  <label htmlFor="edit-patronymic" className="mb-2 block text-sm font-medium text-gray-700">
                    Отчество
                  </label>
                  <input
                    id="edit-patronymic"
                    type="text"
                    value={editPatronymic}
                    onChange={(e) => setEditPatronymic(e.target.value)}
                    placeholder="Иванович"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                    maxLength={150}
                  />
                </div>
              </div>

              {/* Контакты */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="edit-email" className="mb-2 block text-sm font-medium text-gray-700">
                    Email *
                  </label>
                  <input
                    id="edit-email"
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    placeholder="ivan@example.com"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  />
                </div>
                
                <div>
                  <label htmlFor="edit-phone" className="mb-2 block text-sm font-medium text-gray-700">
                    Телефон
                  </label>
                  <input
                    id="edit-phone"
                    type="tel"
                    value={editPhone}
                    onChange={(e) => setEditPhone(e.target.value)}
                    placeholder="+7 999 123-45-67"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  />
                </div>
              </div>

              {/* Мессенджеры */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label htmlFor="edit-telegram" className="mb-2 block text-sm font-medium text-gray-700">
                    Telegram
                  </label>
                  <input
                    id="edit-telegram"
                    type="text"
                    value={editTelegram}
                    onChange={(e) => setEditTelegram(e.target.value)}
                    placeholder="@username"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  />
                </div>
                
                <div>
                  <label htmlFor="edit-whatsapp" className="mb-2 block text-sm font-medium text-gray-700">
                    WhatsApp
                  </label>
                  <input
                    id="edit-whatsapp"
                    type="tel"
                    value={editWhatsApp}
                    onChange={(e) => setEditWhatsApp(e.target.value)}
                    placeholder="+7 999 123-45-67"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  />
                </div>
                
                <div>
                  <label htmlFor="edit-wechat" className="mb-2 block text-sm font-medium text-gray-700">
                    WeChat
                  </label>
                  <input
                    id="edit-wechat"
                    type="text"
                    value={editWeChat}
                    onChange={(e) => setEditWeChat(e.target.value)}
                    placeholder="username"
                    className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  />
                </div>
              </div>
            </div>

            {/* Кнопки */}
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={handleCloseEditModal}
                disabled={actionLoading === "edit"}
                className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                disabled={actionLoading === "edit" || !editFirstName.trim() || !editLastName.trim() || !editEmail.trim()}
                className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
              >
                {actionLoading === "edit" ? "Сохранение..." : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно создания кадрового события */}
      {isActionModalOpen && person && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">
                {editingActionId ? 'Редактировать событие' : 'Кадровое событие'}
              </h2>
              <button
                type="button"
                onClick={handleCloseActionModal}
                className="text-gray-400 hover:text-gray-600"
                disabled={actionLoading === "action"}
              >
                <X size={24} />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* Тип события */}
              <div>
                <label htmlFor="action-type" className="mb-2 block text-sm font-medium text-gray-700">
                  Тип события *
                </label>
                <select
                  id="action-type"
                  value={actionType}
                  onChange={(e) => setActionType(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                >
                  <option value="">Выберите тип события</option>
                  {actionTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Дата */}
              <div>
                <label htmlFor="action-date" className="mb-2 block text-sm font-medium text-gray-700">
                  Дата *
                </label>
                <input
                  id="action-date"
                  type="date"
                  value={actionDate}
                  onChange={(e) => setActionDate(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                />
              </div>

              {/* Комментарий */}
              <div>
                <label htmlFor="action-comment" className="mb-2 block text-sm font-medium text-gray-700">
                  Комментарий
                </label>
                <textarea
                  id="action-comment"
                  value={actionComment}
                  onChange={(e) => setActionComment(e.target.value)}
                  placeholder="Дополнительная информация..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                />
              </div>
            </div>

            {/* Кнопки */}
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={handleCloseActionModal}
                disabled={actionLoading === "action"}
                className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSaveAction}
                disabled={actionLoading === "action" || !actionType || !actionDate}
                className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
              >
                {actionLoading === "action" ? "Сохранение..." : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
