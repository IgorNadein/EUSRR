"use client";

import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import {
  createEmptyActionForm,
  createEmptyEditForm,
  employeeActionTypes,
  getLatestEmployeeAction,
  getUserFullName,
  getUserInitials,
  type EmployeeActionField,
  type EmployeeActionForm,
  type UserProfileEditForm,
  type UserProfileTextField,
  sortEmployeeActions,
} from "@/lib/users/userDetailUtils";
import type { Chat, EmployeeAction, User } from "@/types/api";

type ChatWithMemberIds = Chat & { member_ids?: number[] };

const getErrorMessage = (error: unknown, fallback: string): string => (
  String((error as Error)?.message || fallback)
);

export function useUserDetailPage(userId: number, currentUser: User | null) {
  const router = useRouter();

  const [person, setPerson] = useState<User | null>(null);
  const [avatarFailed, setAvatarFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingChat, setCreatingChat] = useState(false);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isActionModalOpen, setIsActionModalOpen] = useState(false);
  const [editForm, setEditForm] = useState<UserProfileEditForm>(createEmptyEditForm);
  const [actionForm, setActionForm] = useState<EmployeeActionForm>(createEmptyActionForm);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const refreshPerson = useCallback(async () => {
    const data = await apiClient.getEmployee(userId) as User;
    setPerson(data);
    return data;
  }, [userId]);

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
        await refreshPerson();
      } catch (loadError) {
        setError(getErrorMessage(loadError, "Не удалось загрузить пользователя"));
      } finally {
        setLoading(false);
      }
    }

    void loadUser();
  }, [refreshPerson, userId]);

  useEffect(() => {
    setAvatarFailed(false);
  }, [person?.avatar, person?.id]);

  const fullName = useMemo(() => getUserFullName(person), [person]);

  const latestAction = useMemo(() => getLatestEmployeeAction(person?.actions), [person?.actions]);
  const sortedActions = useMemo(() => sortEmployeeActions(person?.actions), [person?.actions]);

  const avatarUrl = resolveMediaUrl(person?.avatar);
  const initials = getUserInitials(person);

  const copyToClipboard = useCallback(async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopySuccess(label);
      window.setTimeout(() => setCopySuccess(null), 2000);
    } catch (copyError) {
      console.error("Ошибка копирования:", copyError);
    }
  }, []);

  const handleStartChat = useCallback(async () => {
    if (!person || !currentUser || creatingChat) return;

    try {
      setCreatingChat(true);

      const allChats = await apiClient.getAllChats() as ChatWithMemberIds[];
      const existingChat = allChats.find((chat) => {
        if (chat.type !== "private") return false;

        const memberIds = Array.isArray(chat.member_ids) ? chat.member_ids : [];
        return memberIds.length === 2 && memberIds.includes(currentUser.id) && memberIds.includes(person.id);
      });

      if (existingChat) {
        router.push(`/messages/${existingChat.id}`);
        return;
      }

      const chat = await apiClient.createChat({
        type: "private",
        name: "Диалог",
        participants: [person.id],
      }) as Chat;
      router.push(`/messages/${chat.id}`);
    } catch (chatError) {
      console.error("Ошибка создания чата:", chatError);
      alert("Не удалось открыть чат");
    } finally {
      setCreatingChat(false);
    }
  }, [creatingChat, currentUser, person, router]);

  const handleOpenActionModal = useCallback(() => {
    setActionForm(createEmptyActionForm());
    setIsActionModalOpen(true);
  }, []);

  const handleCloseActionModal = useCallback(() => {
    setIsActionModalOpen(false);
    setActionForm(createEmptyActionForm());
  }, []);

  const handleEditAction = useCallback((action: EmployeeAction) => {
    setActionForm({
      editingId: action.id,
      type: action.action,
      date: action.date,
      comment: action.comment || "",
    });
    setIsActionModalOpen(true);
  }, []);

  const handleDeleteAction = useCallback(async (actionId: number) => {
    if (!confirm("Вы уверены, что хотите удалить это событие?")) return;

    setActionLoading(`delete-${actionId}`);
    try {
      await apiClient.deleteEmployeeAction(actionId);
      await refreshPerson();
    } catch (deleteError) {
      console.error("Ошибка при удалении события:", deleteError);
      alert("Не удалось удалить событие");
    } finally {
      setActionLoading(null);
    }
  }, [refreshPerson]);

  const handleSaveAction = useCallback(async () => {
    if (!person || !userId || !actionForm.type) return;

    setActionLoading("action");
    try {
      if (actionForm.editingId) {
        await apiClient.updateEmployeeAction(actionForm.editingId, {
          action: actionForm.type,
          date: actionForm.date,
          comment: actionForm.comment.trim() || undefined,
        });
      } else {
        await apiClient.createEmployeeAction({
          employee: userId,
          action: actionForm.type,
          date: actionForm.date,
          comment: actionForm.comment.trim() || undefined,
        });
      }

      await refreshPerson();
      handleCloseActionModal();
    } catch (saveError) {
      console.error("Ошибка при создании события:", saveError);
      alert("Не удалось сохранить событие");
    } finally {
      setActionLoading(null);
    }
  }, [actionForm, handleCloseActionModal, person, refreshPerson, userId]);

  const handleOpenEditModal = useCallback(() => {
    if (!person) return;

    setEditForm({
      firstName: person.first_name || "",
      lastName: person.last_name || "",
      patronymic: person.patronymic || "",
      email: person.email || "",
      phone: person.phone_number || "",
      telegram: person.telegram || "",
      whatsapp: person.whatsapp || "",
      wechat: person.wechat || "",
      avatarFile: null,
      avatarPreview: null,
    });
    setIsEditModalOpen(true);
  }, [person]);

  const handleCloseEditModal = useCallback(() => {
    setIsEditModalOpen(false);
    setEditForm((current) => ({ ...current, avatarFile: null, avatarPreview: null }));
  }, []);

  const handleAvatarChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      alert("Файл слишком большой. Максимальный размер: 5MB");
      return;
    }

    if (!file.type.startsWith("image/")) {
      alert("Можно загружать только изображения");
      return;
    }

    setEditForm((current) => ({ ...current, avatarFile: file }));

    const reader = new FileReader();
    reader.onloadend = () => {
      setEditForm((current) => ({
        ...current,
        avatarFile: file,
        avatarPreview: typeof reader.result === "string" ? reader.result : null,
      }));
    };
    reader.readAsDataURL(file);
  }, []);

  const setEditField = useCallback(<K extends UserProfileTextField>(field: K, value: UserProfileEditForm[K]) => {
    setEditForm((current) => ({ ...current, [field]: value }));
  }, []);

  const setActionField = useCallback(<K extends EmployeeActionField>(field: K, value: EmployeeActionForm[K]) => {
    setActionForm((current) => ({ ...current, [field]: value }));
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!person || !userId) return;

    setActionLoading("edit");
    try {
      await apiClient.updateEmployee(userId, {
        first_name: editForm.firstName.trim(),
        last_name: editForm.lastName.trim(),
        patronymic: editForm.patronymic.trim() || undefined,
        email: editForm.email.trim(),
        phone_number: editForm.phone.trim() || undefined,
        telegram: editForm.telegram.trim() || undefined,
        whatsapp: editForm.whatsapp.trim() || undefined,
        wechat: editForm.wechat.trim() || undefined,
      });

      if (editForm.avatarFile) {
        await apiClient.uploadEmployeeAvatar(userId, editForm.avatarFile);
      }

      await refreshPerson();
      handleCloseEditModal();
    } catch (saveError) {
      console.error("Ошибка при обновлении сотрудника:", saveError);
      alert("Не удалось обновить данные");
    } finally {
      setActionLoading(null);
    }
  }, [editForm, handleCloseEditModal, person, refreshPerson, userId]);

  const canEdit = Boolean(currentUser && (
    currentUser.auth?.is_staff ||
    currentUser.auth?.is_superuser ||
    currentUser.id === userId
  ));

  const canManageActions = Boolean(currentUser && (
    currentUser.auth?.is_staff ||
    currentUser.auth?.is_superuser
  ));

  const canViewActions = Boolean(currentUser && (
    currentUser.auth?.is_staff ||
    currentUser.auth?.is_superuser ||
    currentUser.id === userId
  ));

  return {
    actionForm,
    actionLoading,
    actionTypes: employeeActionTypes,
    avatarFailed,
    avatarUrl,
    canEdit,
    canManageActions,
    canViewActions,
    copySuccess,
    creatingChat,
    editForm,
    error,
    fullName,
    handleAvatarChange,
    handleCloseActionModal,
    handleCloseEditModal,
    handleCopyToClipboard: copyToClipboard,
    handleDeleteAction,
    handleEditAction,
    handleOpenActionModal,
    handleOpenEditModal,
    handleSaveAction,
    handleSaveEdit,
    handleStartChat,
    initials,
    isActionModalOpen,
    isEditModalOpen,
    latestAction,
    loading,
    person,
    setActionField,
    setAvatarFailed,
    setEditField,
    sortedActions,
  };
}