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
  UserMinus,
  Pencil
} from "lucide-react";
import { AppShell } from "../../../../components/AppShell";
import { apiClient } from "@/lib/api";
import { getChatAvatar, getChatInitials, getChatTitle } from "@/lib/messages/chatUtils";
import ChatParticipantsSection from "@/components/messages/ChatParticipantsSection";
import EditChatModal from "@/components/messages/EditChatModal";
import AddChatMemberModal from "@/components/messages/AddChatMemberModal";
import { getChatTypeLabel, type MemberSearchResult } from "@/lib/messages/chatSettingsUtils";
import type { Chat } from "@/types/api";
import { useUser } from "@/contexts/UserContext";
import { resolveMediaUrl } from "@/lib/url";

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
      const refreshedChat: Chat = await apiClient.getChat(chatId);
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
      const refreshedChat: Chat = await apiClient.getChat(chatId);
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
      const refreshedChat: Chat = await apiClient.getChat(chatId);
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
        <div className="app-surface mx-auto max-w-3xl rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка настроек...</p>
        </div>
      </AppShell>
    );
  }

  if (error || !chat) {
    return (
      <AppShell>
        <div className="app-feedback-danger mx-auto max-w-3xl rounded-2xl p-6 text-center">
          <p className="text-sm">{error || "Чат не найден"}</p>
          <Link
            href="/messages"
            className="app-link-accent mt-4 inline-block text-sm"
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

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        {/* Хедер */}
        <div className="mb-6 flex items-center gap-3">
          <Link
            href={`/messages/${chatId}`}
            className="app-action-secondary flex h-10 w-10 items-center justify-center rounded-full p-0"
            aria-label="Вернуться к чату"
          >
            <ArrowLeft size={16} />
          </Link>
          <h1 className="text-xl font-bold text-[var(--foreground)]">Настройки чата</h1>
        </div>

        {/* Информация о чате */}
        <section className="app-surface mb-4 rounded-2xl p-6">
          <div className="flex items-center gap-4">
            <div className="app-avatar-fallback flex h-16 w-16 items-center justify-center overflow-hidden rounded-full text-lg font-semibold">
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
              <h2 className="text-lg font-semibold text-[var(--foreground)]">
                {getChatTitle(chat, currentUserId)}
              </h2>
              <p className="app-text-muted text-sm">{getChatTypeLabel(chat)}</p>
            </div>
            {canEdit && (
              <button
                type="button"
                onClick={handleOpenEditModal}
                className="app-action-secondary flex h-10 w-10 items-center justify-center rounded-full p-0"
                aria-label="Редактировать чат"
                title="Редактировать чат"
              >
                <Pencil size={16} />
              </button>
            )}
          </div>

          {chat.description && (
            <div className="app-surface-muted mt-4 rounded-xl p-3">
              <p className="text-sm text-[var(--foreground)]">{chat.description}</p>
            </div>
          )}
        </section>

        {/* Быстрые действия */}
        <section className="app-surface mb-4 rounded-2xl p-4">
          <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">Быстрые действия</h3>
          
          <div className="space-y-2">
            {/* Закрепление */}
            <button
              type="button"
              onClick={handleTogglePin}
              disabled={actionLoading === "pin"}
              className="app-surface-muted flex w-full items-center gap-3 rounded-xl p-3 text-left transition hover:bg-[var(--surface-elevated)] disabled:opacity-50"
            >
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                isPinned ? "app-selected app-accent-text" : "app-surface-elevated app-text-muted"
              }`}>
                <Pin size={18} className={isPinned ? "fill-current" : ""} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-[var(--foreground)]">
                  {isPinned ? "Открепить чат" : "Закрепить чат"}
                </p>
                <p className="app-text-muted text-xs">
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
              className="app-surface-muted flex w-full items-center gap-3 rounded-xl p-3 text-left transition hover:bg-[var(--surface-elevated)] disabled:opacity-50"
            >
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                notificationsEnabled ? "app-feedback-success" : "app-feedback-warning"
              }`}>
                {notificationsEnabled ? <Bell size={18} /> : <BellOff size={18} />}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-[var(--foreground)]">
                  {notificationsEnabled ? "Отключить уведомления" : "Включить уведомления"}
                </p>
                <p className="app-text-muted text-xs">
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
          <ChatParticipantsSection
            chat={chat}
            currentUserId={currentUserId}
            isOwner={isOwner}
            canEdit={canEdit}
            showAllParticipants={showAllParticipants}
            roleDropdownOpen={roleDropdownOpen}
            actionLoading={actionLoading}
            onOpenAddMemberModal={handleOpenAddMemberModal}
            onToggleShowAllParticipants={() => setShowAllParticipants((prev) => !prev)}
            onToggleRoleDropdown={(participantId) => setRoleDropdownOpen((prev) => prev === participantId ? null : participantId)}
            onCloseRoleDropdown={() => setRoleDropdownOpen(null)}
            onChangeRole={handleChangeRole}
            onRemoveMember={handleRemoveMember}
          />
        )}

        {/* Опасная зона */}
        {(hasMembers || canEdit) && (
          <section className="app-surface rounded-2xl p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--foreground)]">Опасная зона</h3>
            
            <div className="space-y-2">
              {hasMembers && (
                <button
                  type="button"
                  onClick={handleLeaveChat}
                  disabled={actionLoading === "leave"}
                  className="app-feedback-danger flex w-full items-center gap-3 rounded-xl p-3 text-left transition hover:opacity-90 disabled:opacity-50"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--danger-soft)] text-[color:#dc2626]">
                    <UserMinus size={18} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium">Покинуть чат</p>
                    <p className="text-xs opacity-80">
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
                  className="app-feedback-danger flex w-full items-center gap-3 rounded-xl p-3 text-left transition hover:opacity-90 disabled:opacity-50"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--danger-soft)] text-[color:#b91c1c]">
                    <Trash2 size={18} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium">Удалить чат</p>
                    <p className="text-xs opacity-80">
                      Чат и все сообщения будут удалены навсегда
                    </p>
                  </div>
                </button>
              )}
            </div>
          </section>
        )}
      </div>

      <EditChatModal
        chat={chat}
        open={isEditModalOpen}
        currentUserId={currentUserId}
        editName={editName}
        editDescription={editDescription}
        editAvatarPreview={editAvatarPreview}
        actionLoading={actionLoading}
        onClose={handleCloseEditModal}
        onNameChange={setEditName}
        onDescriptionChange={setEditDescription}
        onAvatarChange={handleAvatarChange}
        onSave={handleSaveEdit}
      />

      <AddChatMemberModal
        open={isAddMemberModalOpen}
        memberSearchQuery={memberSearchQuery}
        memberSearchResults={memberSearchResults}
        memberSearchLoading={memberSearchLoading}
        actionLoading={actionLoading}
        onClose={handleCloseAddMemberModal}
        onSearchChange={handleMemberSearch}
        onAddMember={handleAddMember}
      />
    </AppShell>
  );
}
