"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  Bell, 
  BellOff, 
  Pin, 
  Trash2, 
  UserPlus, 
  UserMinus,
  Users,
  Pencil,
  ChevronDown,
  Shield,
  ShieldCheck
} from "lucide-react";
import { AppShell } from "../../../../components/AppShell";
import { apiClient } from "@/lib/api";
import { getChatAvatar, getChatInitials, getChatTitle, getUserFullName } from "@/lib/messages/chatUtils";
import type { Chat, User } from "@/types/api";
import { useUser } from "@/contexts/UserContext";
import { resolveMediaUrl } from "@/lib/url";

type MemberSearchResult = Pick<User, "id" | "first_name" | "last_name" | "email" | "avatar"> & {
  name?: string;
};

function getChatTypeLabel(chat: Chat): string {
  const type = chat.chat_type || chat.type;
  switch (type) {
    case "global":
      return "Глобальный чат";
    case "channel":
      return "Канал";
    case "private":
    case "direct":
      return "Личный чат";
    case "group":
      return "Групповой чат";
    case "announcement":
      return "Канал объявлений";
    case "comments":
      return "Комментарии";
    default:
      return "Диалог";
  }
}

export default function ChatSettingsPage() {
  const params = useParams<{ chatId: string }>();
  const router = useRouter();
  const chatId = Number(params.chatId);
  const { user } = useUser();
  const currentUserId = user?.id;

  const [chat, setChat] = useState<Chat | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Локальное состояние для настроек
  const [isPinned, setIsPinned] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  
  // Состояние модала редактирования
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editAvatarFile, setEditAvatarFile] = useState<File | null>(null);
  const [editAvatarPreview, setEditAvatarPreview] = useState<string | null>(null);
  
  // Состояние модала добавления участников
  const [isAddMemberModalOpen, setIsAddMemberModalOpen] = useState(false);
  const [memberSearchQuery, setMemberSearchQuery] = useState("");
  const [memberSearchResults, setMemberSearchResults] = useState<MemberSearchResult[]>([]);
  const [memberSearchLoading, setMemberSearchLoading] = useState(false);
  
  // Состояние для отображения полного списка участников
  const [showAllParticipants, setShowAllParticipants] = useState(false);
  
  // Состояние для управления ролями
  const [roleDropdownOpen, setRoleDropdownOpen] = useState<number | null>(null);

  useEffect(() => {
    async function loadChat() {
      // Retry логика для только что созданных чатов
      const maxRetries = 3;
      let attempt = 0;
      
      while (attempt < maxRetries) {
        try {
          setLoading(true);
          setError(null);
          const chatData = await apiClient.getChat(chatId);
          setChat(chatData);
          setIsPinned(chatData.is_pinned ?? false);
          setNotificationsEnabled(chatData.notifications_enabled ?? true);
          // Инициализация формы редактирования
          setEditName(chatData.name || "");
          setEditDescription(chatData.description || "");
          setLoading(false);
          return; // Успех - выходим
        } catch (e) {
          attempt++;
          
          if (attempt < maxRetries) {
            // Ждем перед повторной попыткой (экспоненциальная задержка)
            const delay = Math.min(1000 * Math.pow(2, attempt - 1), 3000);
            await new Promise(resolve => setTimeout(resolve, delay));
          } else {
            // Исчерпаны попытки
            console.error("Ошибка загрузки чата:", e);
            setError("Не удалось загрузить информацию о чате");
            setLoading(false);
          }
        }
      }
    }

    if (chatId) {
      loadChat();
    }
  }, [chatId]);

  // Закрываем dropdown при прокрутке
  useEffect(() => {
    const handleScroll = () => {
      if (roleDropdownOpen !== null) {
        setRoleDropdownOpen(null);
      }
    };
    
    window.addEventListener('scroll', handleScroll, true);
    return () => window.removeEventListener('scroll', handleScroll, true);
  }, [roleDropdownOpen]);

  const handleTogglePin = async () => {
    if (!chatId) return;
    
    setActionLoading("pin");
    try {
      const response = await apiClient.togglePinChat(chatId);
      const newIsPinned = response.is_pinned ?? !isPinned;
      setIsPinned(newIsPinned);
      
      if (chat) {
        setChat({ ...chat, is_pinned: newIsPinned });
      }
    } catch (e) {
      console.error("Ошибка переключения закрепления:", e);
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleNotifications = async () => {
    if (!chatId) return;
    
    setActionLoading("notifications");
    try {
      const response = await apiClient.toggleChatNotifications(chatId);
      const newNotificationsEnabled = response.notifications_enabled ?? !notificationsEnabled;
      setNotificationsEnabled(newNotificationsEnabled);
      
      if (chat) {
        setChat({ ...chat, notifications_enabled: newNotificationsEnabled });
      }
    } catch (e) {
      console.error("Ошибка переключения уведомлений:", e);
    } finally {
      setActionLoading(null);
    }
  };

  const handleLeaveChat = async () => {
    if (!chatId || !confirm("Вы уверены, что хотите покинуть этот чат?")) return;
    
    setActionLoading("leave");
    try {
      await apiClient.leaveChat(chatId);
      router.push("/messages");
    } catch (e) {
      console.error("Ошибка при выходе из чата:", e);
      alert("Не удалось покинуть чат");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteChat = async () => {
    if (!chatId || !confirm("Вы уверены, что хотите удалить этот чат? Это действие необратимо.")) return;
    
    setActionLoading("delete");
    try {
      await apiClient.deleteChat(chatId);
      router.push("/messages");
    } catch (e) {
      console.error("Ошибка при удалении чата:", e);
      alert("Не удалось удалить чат");
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpenEditModal = () => {
    if (!chat) return;
    setEditName(chat.name || "");
    setEditDescription(chat.description || "");
    setEditAvatarFile(null);
    setEditAvatarPreview(null);
    setIsEditModalOpen(true);
  };

  const handleCloseEditModal = () => {
    setIsEditModalOpen(false);
    setEditAvatarFile(null);
    setEditAvatarPreview(null);
  };

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

  const handleSaveEdit = async () => {
    if (!chatId) return;
    
    setActionLoading("edit");
    try {
      // Обновляем название и описание
      await apiClient.updateChat(chatId, {
        name: editName.trim() || undefined,
        description: editDescription.trim() || undefined,
      });

      // Загружаем аватар если выбран
      if (editAvatarFile) {
        await apiClient.uploadChatAvatar(chatId, editAvatarFile);
      }

      // Перезагружаем данные чата
      const refreshedChat = await apiClient.getChat(chatId);
      setChat(refreshedChat);
      
      handleCloseEditModal();
    } catch (e) {
      console.error("Ошибка при обновлении чата:", e);
      alert("Не удалось обновить чат");
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpenAddMemberModal = () => {
    setMemberSearchQuery("");
    setMemberSearchResults([]);
    setIsAddMemberModalOpen(true);
  };

  const handleCloseAddMemberModal = () => {
    setIsAddMemberModalOpen(false);
    setMemberSearchQuery("");
    setMemberSearchResults([]);
  };

  const handleMemberSearch = async (query: string) => {
    setMemberSearchQuery(query);
    
    if (query.trim().length < 2) {
      setMemberSearchResults([]);
      return;
    }
    
    setMemberSearchLoading(true);
    try {
      const response = await apiClient.getEmployees({ search: query, limit: 10 });
      const results = response.results || response;
      
      // Фильтруем уже добавленных участников
      const currentMemberIds = new Set(
        chat?.participant_details?.map(p => p.id) || []
      );
      const filtered = (results as MemberSearchResult[]).filter((result) => !currentMemberIds.has(result.id));
      
      setMemberSearchResults(filtered);
    } catch (e) {
      console.error("Ошибка поиска:", e);
    } finally {
      setMemberSearchLoading(false);
    }
  };

  const handleAddMember = async (userId: number) => {
    if (!chatId) return;
    
    setActionLoading(`add-member-${userId}`);
    try {
      await apiClient.addChatMember(chatId, userId);
      
      // Перезагружаем данные чата
      const refreshedChat = await apiClient.getChat(chatId);
      setChat(refreshedChat);
      
      // Обновляем результаты поиска с учетом новых данных
      if (memberSearchQuery.trim().length >= 2) {
        const response = await apiClient.getEmployees({ 
          search: memberSearchQuery, 
          limit: 10 
        });
        const results = response.results || response;
        
        // Используем свежие данные чата для фильтрации
        const currentMemberIds = new Set(
          refreshedChat?.participant_details?.map((participant) => participant.id) || []
        );
        const filtered = (results as MemberSearchResult[]).filter((result) => !currentMemberIds.has(result.id));
        
        setMemberSearchResults(filtered);
      }
    } catch (e) {
      console.error("Ошибка при добавлении участника:", e);
      alert("Не удалось добавить участника");
    } finally {
      setActionLoading(null);
    }
  };

  const handleChangeRole = async (userId: number, newRole: 'admin' | 'moderator' | 'member' | 'guest') => {
    if (!chatId || !chat) return;
    
    setActionLoading(`change-role-${userId}`);
    setRoleDropdownOpen(null);
    
    try {
      const response = await apiClient.changeChatMemberRole(chatId, userId, newRole);
      console.log('[handleChangeRole] API response:', response);
      
      // Оптимистичное обновление: сразу обновляем локальное состояние
      setChat(prevChat => {
        if (!prevChat) return prevChat;
        
        // Обновляем memberships
        const updatedMemberships = prevChat.memberships?.map(m => 
          m.user === userId ? { ...m, role: newRole } : m
        ) || [];
        
        // Если membership не найден, добавляем его
        if (!updatedMemberships.find(m => m.user === userId)) {
          updatedMemberships.push({
            id: 0, // временное значение
            user: userId,
            role: newRole,
            joined_at: new Date().toISOString(),
            invited_by: currentUserId || null,
            is_active: true,
            can_send_messages: true,
            can_add_members: false,
            can_remove_members: false,
            can_pin_messages: false,
          });
        }
        
        console.log('[handleChangeRole] Updated memberships:', updatedMemberships);
        return { ...prevChat, memberships: updatedMemberships };
      });
      
      // Перезагружаем данные чата с сервера для синхронизации
      const refreshedChat = await apiClient.getChat(chatId);
      console.log('[handleChangeRole] Refreshed chat from server:', refreshedChat);
      console.log('[handleChangeRole] Refreshed memberships:', refreshedChat.memberships);
      setChat(refreshedChat);
    } catch (e) {
      console.error("Ошибка при изменении роли:", e);
      alert("Не удалось изменить роль участника");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemoveMember = async (userId: number) => {
    if (!chatId || !confirm("Вы уверены, что хотите удалить этого участника?")) return;
    
    setActionLoading(`remove-member-${userId}`);
    try {
      await apiClient.removeChatMember(chatId, userId);
      
      // Перезагружаем данные чата
      const refreshedChat = await apiClient.getChat(chatId);
      setChat(refreshedChat);
    } catch (e) {
      console.error("Ошибка при удалении участника:", e);
      alert("Не удалось удалить участника");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка настроек...</p>
        </div>
      </AppShell>
    );
  }

  if (error || !chat) {
    return (
      <AppShell>
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error || "Чат не найден"}</p>
          <Link
            href="/messages"
            className="mt-4 inline-block text-sm text-sky-600 hover:text-sky-700"
          >
            Вернуться к списку чатов
          </Link>
        </div>
      </AppShell>
    );
  }

  const chatType = chat.chat_type || chat.type;
  // Чаты с управлением участниками (группы, каналы, объявления)
  const hasMembers = chatType === "group" || chatType === "channel" || chatType === "announcement";
  
  // Проверка прав: владелец или админ
  const isOwner = chat.created_by === currentUserId;
  const isAdmin = chat.memberships?.some(
    (m) => m.user === currentUserId && m.role === 'admin'
  ) ?? false;
  const canEdit = isOwner || isAdmin;

  // Получить роль участника
  const getMemberRole = (userId: number): 'admin' | 'moderator' | 'member' | 'guest' | null => {
    if (chat.created_by === userId) return null; // Владелец не имеет роли в membership
    const membership = chat.memberships?.find(m => m.user === userId);
    return membership?.role || 'member';
  };

  // Получить отображаемое имя роли
  const getRoleLabel = (role: 'admin' | 'moderator' | 'member' | 'guest' | null): string => {
    if (role === null) return 'Владелец';
    switch (role) {
      case 'admin': return 'Админ';
      case 'moderator': return 'Модератор';
      case 'member': return 'Участник';
      case 'guest': return 'Гость';
      default: return 'Участник';
    }
  };

  // Цвет бейджа роли
  const getRoleBadgeColor = (role: 'admin' | 'moderator' | 'member' | 'guest' | null): string => {
    if (role === null) return 'bg-purple-100 text-purple-700 ring-purple-200'; // Владелец
    switch (role) {
      case 'admin': return 'bg-red-100 text-red-700 ring-red-200';
      case 'moderator': return 'bg-blue-100 text-blue-700 ring-blue-200';
      case 'member': return 'bg-gray-100 text-gray-700 ring-gray-200';
      case 'guest': return 'bg-amber-100 text-amber-700 ring-amber-200';
      default: return 'bg-gray-100 text-gray-700 ring-gray-200';
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        {/* Хедер */}
        <div className="mb-6 flex items-center gap-3">
          <Link
            href={`/messages/${chatId}`}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
            aria-label="Вернуться к чату"
          >
            <ArrowLeft size={16} />
          </Link>
          <h1 className="text-xl font-bold text-gray-900">Настройки чата</h1>
        </div>

        {/* Информация о чате */}
        <section className="mb-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-100">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-lg font-semibold text-white">
              {getChatAvatar(chat, currentUserId) ? (
                <Image
                  src={resolveMediaUrl(getChatAvatar(chat, currentUserId))}
                  alt={getChatTitle(chat, currentUserId)}
                  width={64}
                  height={64}
                  unoptimized
                  className="h-full w-full object-cover"
                />
              ) : (
                getChatInitials(chat, currentUserId)
              )}
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-gray-900">
                {getChatTitle(chat, currentUserId)}
              </h2>
              <p className="text-sm text-gray-500">{getChatTypeLabel(chat)}</p>
            </div>
            {canEdit && (
              <button
                type="button"
                onClick={handleOpenEditModal}
                className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
                aria-label="Редактировать чат"
                title="Редактировать чат"
              >
                <Pencil size={16} />
              </button>
            )}
          </div>

          {chat.description && (
            <div className="mt-4 rounded-lg bg-gray-50 p-3">
              <p className="text-sm text-gray-700">{chat.description}</p>
            </div>
          )}
        </section>

        {/* Быстрые действия */}
        <section className="mb-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <h3 className="mb-3 text-sm font-semibold text-gray-700">Быстрые действия</h3>
          
          <div className="space-y-2">
            {/* Закрепление */}
            <button
              type="button"
              onClick={handleTogglePin}
              disabled={actionLoading === "pin"}
              className="flex w-full items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 text-left transition hover:bg-gray-50 disabled:opacity-50"
            >
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                isPinned ? "bg-sky-100 text-sky-600" : "bg-gray-100 text-gray-600"
              }`}>
                <Pin size={18} className={isPinned ? "fill-current" : ""} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {isPinned ? "Открепить чат" : "Закрепить чат"}
                </p>
                <p className="text-xs text-gray-500">
                  {isPinned 
                    ? "Убрать чат из списка закрепленных" 
                    : "Чат будет отображаться вверху списка"
                  }
                </p>
              </div>
            </button>

            {/* Уведомления */}
            <button
              type="button"
              onClick={handleToggleNotifications}
              disabled={actionLoading === "notifications"}
              className="flex w-full items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 text-left transition hover:bg-gray-50 disabled:opacity-50"
            >
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                notificationsEnabled ? "bg-green-100 text-green-600" : "bg-amber-100 text-amber-600"
              }`}>
                {notificationsEnabled ? <Bell size={18} /> : <BellOff size={18} />}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {notificationsEnabled ? "Отключить уведомления" : "Включить уведомления"}
                </p>
                <p className="text-xs text-gray-500">
                  {notificationsEnabled 
                    ? "Вы не будете получать уведомления из этого чата" 
                    : "Включить уведомления для новых сообщений"
                  }
                </p>
              </div>
            </button>
          </div>
        </section>

        {/* Участники (для групповых чатов, каналов и объявлений) */}
        {hasMembers && (
          <section className="mb-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-700">Участники</h3>
                {isOwner && (
                  <p className="mt-0.5 text-xs text-gray-500">
                    Вы можете изменять роли участников
                  </p>
                )}
              </div>
              {canEdit && (
                <button
                  type="button"
                  onClick={handleOpenAddMemberModal}
                  className="flex items-center gap-1 rounded-lg border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-700 transition hover:bg-sky-100"
                >
                  <UserPlus size={14} />
                  <span>Добавить</span>
                </button>
              )}
            </div>
            
            <div className="space-y-2">
              {(chat.participant_details || [])
                .slice(0, showAllParticipants ? undefined : 5)
                .map((participant) => {
                  const memberRole = getMemberRole(participant.id);
                  const roleLabel = getRoleLabel(memberRole);
                  const roleBadgeColor = getRoleBadgeColor(memberRole);
                  const isCurrentUserOwner = chat.created_by === participant.id;
                  
                  return (
                    <div
                      key={participant.id}
                      className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3"
                    >
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xs font-semibold text-white">
                        {participant.avatar ? (
                          <Image
                            src={resolveMediaUrl(participant.avatar)}
                            alt={participant.name || "User"}
                            width={40}
                            height={40}
                            unoptimized
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <span>
                            {(participant.name || "?")
                              .split(" ")
                              .filter(Boolean)
                              .slice(0, 2)
                              .map((p) => p[0])
                              .join("")
                              .toUpperCase()}
                          </span>
                        )}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">
                          {participant.name || "Без имени"}
                          {participant.id === currentUserId && (
                            <span className="ml-1.5 text-xs text-gray-500">(вы)</span>
                          )}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${roleBadgeColor}`}>
                            {isCurrentUserOwner && <ShieldCheck size={10} />}
                            {!isCurrentUserOwner && memberRole === 'admin' && <Shield size={10} />}
                            {roleLabel}
                          </span>
                        </div>
                      </div>
                      
                      {/* Управление ролью (только для владельца) */}
                      {isOwner && !isCurrentUserOwner && participant.id !== currentUserId && (
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setRoleDropdownOpen(roleDropdownOpen === participant.id ? null : participant.id)}
                            disabled={actionLoading?.startsWith(`change-role-${participant.id}`) || actionLoading === `remove-member-${participant.id}`}
                            className="flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
                            title="Изменить роль"
                          >
                            <span>Роль</span>
                            <ChevronDown size={12} />
                          </button>
                          
                          {roleDropdownOpen === participant.id && (
                            <>
                              <button
                                type="button"
                                onClick={() => setRoleDropdownOpen(null)}
                                className="fixed inset-0 z-40"
                                aria-label="Закрыть меню"
                              />
                              <div className="absolute right-0 top-full z-50 mt-1 w-36 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
                                <button
                                  type="button"
                                  onClick={() => handleChangeRole(participant.id, 'admin')}
                                  disabled={memberRole === 'admin'}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <Shield size={12} className="text-red-600" />
                                  <span>Админ</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleChangeRole(participant.id, 'moderator')}
                                  disabled={memberRole === 'moderator'}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <Shield size={12} className="text-blue-600" />
                                  <span>Модератор</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleChangeRole(participant.id, 'member')}
                                  disabled={memberRole === 'member'}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <Users size={12} className="text-gray-600" />
                                  <span>Участник</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleChangeRole(participant.id, 'guest')}
                                  disabled={memberRole === 'guest'}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  <Users size={12} className="text-amber-600" />
                                  <span>Гость</span>
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      )}
                      
                      {/* Кнопка удаления */}
                      {canEdit && !isCurrentUserOwner && participant.id !== currentUserId && (
                        <button
                          type="button"
                          onClick={() => handleRemoveMember(participant.id)}
                          disabled={actionLoading === `remove-member-${participant.id}` || actionLoading?.startsWith(`change-role-${participant.id}`)}
                          className="text-gray-400 hover:text-red-600 disabled:opacity-50"
                          title="Удалить из чата"
                        >
                          <UserMinus size={16} />
                        </button>
                      )}
                    </div>
                  );
                })}
            </div>
            
            {/* Кнопка показать всех участников */}
            {(chat.participant_details || []).length > 5 && (
              <button
                type="button"
                onClick={() => setShowAllParticipants(!showAllParticipants)}
                className="mt-3 w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100"
              >
                {showAllParticipants 
                  ? "Свернуть" 
                  : `Посмотреть всех (${chat.participant_details?.length || 0})`
                }
              </button>
            )}
            
            {/* Легенда ролей */}
            {isOwner && (
              <div className="mt-4 rounded-lg bg-gray-50 p-3">
                <p className="mb-2 text-xs font-semibold text-gray-700">Роли участников:</p>
                <div className="space-y-1 text-xs text-gray-600">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-purple-100 text-purple-700 ring-1 ring-purple-200">
                      <ShieldCheck size={10} />
                      Владелец
                    </span>
                    <span>— полный контроль над чатом</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-red-100 text-red-700 ring-1 ring-red-200">
                      <Shield size={10} />
                      Админ
                    </span>
                    <span>— управление участниками, редактирование</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-blue-100 text-blue-700 ring-1 ring-blue-200">
                      <Shield size={10} />
                      Модератор
                    </span>
                    <span>— закрепление и удаление сообщений</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-gray-100 text-gray-700 ring-1 ring-gray-200">
                      Участник
                    </span>
                    <span>— отправка сообщений</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 ring-1 ring-amber-200">
                      Гость
                    </span>
                    <span>— только чтение</span>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Опасная зона */}
        {(hasMembers || canEdit) && (
          <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <h3 className="mb-3 text-sm font-semibold text-red-700">Опасная зона</h3>
            
            <div className="space-y-2">
              {hasMembers && (
                <button
                  type="button"
                  onClick={handleLeaveChat}
                  disabled={actionLoading === "leave"}
                  className="flex w-full items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-left transition hover:bg-red-100 disabled:opacity-50"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600">
                    <UserMinus size={18} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-red-900">Покинуть чат</p>
                    <p className="text-xs text-red-700">
                      Вы больше не будете видеть сообщения из этого чата
                    </p>
                  </div>
                </button>
              )}

              {canEdit && (
                <button
                  type="button"
                  onClick={handleDeleteChat}
                  disabled={actionLoading === "delete"}
                  className="flex w-full items-center gap-3 rounded-lg border border-red-300 bg-red-100 p-3 text-left transition hover:bg-red-200 disabled:opacity-50"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-200 text-red-700">
                    <Trash2 size={18} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-red-900">Удалить чат</p>
                    <p className="text-xs text-red-700">
                      Чат и все сообщения будут удалены навсегда
                    </p>
                  </div>
                </button>
              )}
            </div>
          </section>
        )}
      </div>

      {/* Модал редактирования чата */}
      {isEditModalOpen && chat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-xl font-bold text-gray-900">Редактировать чат</h2>
            
            <div className="space-y-4">
              {/* Аватар */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Аватар
                </label>
                <div className="flex items-center gap-4">
                  <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-lg font-semibold text-white">
                    {editAvatarPreview ? (
                      <img
                        src={editAvatarPreview || ""}
                        alt="Preview"
                        className="h-full w-full object-cover"
                      />
                    ) : getChatAvatar(chat, currentUserId) ? (
                      <Image
                        src={resolveMediaUrl(getChatAvatar(chat, currentUserId))}
                        alt="Avatar"
                        width={64}
                        height={64}
                        unoptimized
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      getChatInitials(chat, currentUserId)
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

              {/* Название */}
              <div>
                <label htmlFor="edit-name" className="mb-2 block text-sm font-medium text-gray-700">
                  Название чата
                </label>
                <input
                  id="edit-name"
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Введите название чата"
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  maxLength={100}
                />
              </div>

              {/* Описание */}
              <div>
                <label htmlFor="edit-description" className="mb-2 block text-sm font-medium text-gray-700">
                  Описание
                </label>
                <textarea
                  id="edit-description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Введите описание чата (необязательно)"
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                  maxLength={500}
                />
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
                disabled={actionLoading === "edit" || !editName.trim()}
                className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
              >
                {actionLoading === "edit" ? "Сохранение..." : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модал добавления участника */}
      {isAddMemberModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">Добавить участника</h2>
              <button
                type="button"
                onClick={handleCloseAddMemberModal}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* Поиск */}
            <div className="mb-4">
              <input
                type="text"
                value={memberSearchQuery}
                onChange={(e) => handleMemberSearch(e.target.value)}
                placeholder="Введите имя или email..."
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                autoFocus
              />
              <p className="mt-1 text-xs text-gray-500">
                Минимум 2 символа для поиска
              </p>
            </div>

            {/* Результаты поиска */}
            <div className="max-h-96 overflow-y-auto">
              {memberSearchLoading ? (
                <div className="py-8 text-center">
                  <div className="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
                  <p className="text-sm text-gray-500">Поиск...</p>
                </div>
              ) : memberSearchQuery.trim().length < 2 ? (
                <div className="py-8 text-center">
                  <Users className="mx-auto mb-2 h-12 w-12 text-gray-300" />
                  <p className="text-sm text-gray-500">
                    Начните вводить имя или email для поиска
                  </p>
                </div>
              ) : memberSearchResults.length === 0 ? (
                <div className="py-8 text-center">
                  <p className="text-sm text-gray-500">Пользователи не найдены</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {memberSearchResults.map((result) => (
                    <div
                      key={result.id}
                      className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 transition hover:bg-gray-50"
                    >
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                        {result.avatar ? (
                          <Image
                            src={resolveMediaUrl(result.avatar)}
                            alt={result.name || ""}
                            width={40}
                            height={40}
                            unoptimized
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <span>
                            {result.name ? result.name.split(" ").map((n: string) => n[0]).join("") : "?"}
                          </span>
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">
                          {result.name || getUserFullName(result.last_name, result.first_name)}
                        </p>
                        {result.email && (
                          <p className="text-xs text-gray-500">{result.email}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleAddMember(result.id)}
                        disabled={actionLoading === `add-member-${result.id}`}
                        className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
                      >
                        {actionLoading === `add-member-${result.id}` ? "..." : "Добавить"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

