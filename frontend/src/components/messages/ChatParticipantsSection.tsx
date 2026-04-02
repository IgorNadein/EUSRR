"use client";

import Image from "next/image";
import { ChevronDown, Shield, ShieldCheck, UserMinus, UserPlus, Users } from "lucide-react";

import { resolveMediaUrl } from "@/lib/url";
import {
  getMemberRole,
  getParticipantInitials,
  getRoleBadgeColor,
  getRoleLabel,
  type ChatMemberRole,
} from "@/lib/messages/chatSettingsUtils";
import type { Chat } from "@/types/api";

type ChatParticipantsSectionProps = {
  chat: Chat;
  currentUserId?: number;
  isOwner: boolean;
  canEdit: boolean;
  showAllParticipants: boolean;
  roleDropdownOpen: number | null;
  actionLoading: string | null;
  onOpenAddMemberModal: () => void;
  onToggleShowAllParticipants: () => void;
  onToggleRoleDropdown: (participantId: number) => void;
  onCloseRoleDropdown: () => void;
  onChangeRole: (userId: number, newRole: Exclude<ChatMemberRole, null>) => void;
  onRemoveMember: (userId: number) => void;
};

const assignableRoles: Array<Exclude<ChatMemberRole, null>> = ["admin", "moderator", "member", "guest"];

function getRoleIcon(role: ChatMemberRole) {
  switch (role) {
    case "admin":
      return <Shield size={12} className="text-red-600" />;
    case "moderator":
      return <Shield size={12} className="text-blue-600" />;
    case "guest":
      return <Users size={12} className="text-amber-600" />;
    default:
      return <Users size={12} className="text-gray-600" />;
  }
}

export default function ChatParticipantsSection({
  chat,
  currentUserId,
  isOwner,
  canEdit,
  showAllParticipants,
  roleDropdownOpen,
  actionLoading,
  onOpenAddMemberModal,
  onToggleShowAllParticipants,
  onToggleRoleDropdown,
  onCloseRoleDropdown,
  onChangeRole,
  onRemoveMember,
}: ChatParticipantsSectionProps) {
  const visibleParticipants = (chat.participant_details || []).slice(0, showAllParticipants ? undefined : 5);

  return (
    <section className="mb-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Участники</h3>
          {isOwner ? <p className="mt-0.5 text-xs text-gray-500">Вы можете изменять роли участников</p> : null}
        </div>
        {canEdit ? (
          <button
            type="button"
            onClick={onOpenAddMemberModal}
            className="flex items-center gap-1 rounded-lg border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-700 transition hover:bg-sky-100"
          >
            <UserPlus size={14} />
            <span>Добавить</span>
          </button>
        ) : null}
      </div>

      <div className="space-y-2">
        {visibleParticipants.map((participant) => {
          const memberRole = getMemberRole(chat, participant.id);
          const roleLabel = getRoleLabel(memberRole);
          const roleBadgeColor = getRoleBadgeColor(memberRole);
          const isParticipantOwner = chat.created_by === participant.id;

          return (
            <div key={participant.id} className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3">
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
                  <span>{getParticipantInitials(participant.name)}</span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {participant.name || "Без имени"}
                  {participant.id === currentUserId ? <span className="ml-1.5 text-xs text-gray-500">(вы)</span> : null}
                </p>
                <div className="mt-0.5 flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${roleBadgeColor}`}>
                    {isParticipantOwner ? <ShieldCheck size={10} /> : memberRole === "admin" ? <Shield size={10} /> : null}
                    {roleLabel}
                  </span>
                </div>
              </div>

              {isOwner && !isParticipantOwner && participant.id !== currentUserId ? (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => onToggleRoleDropdown(participant.id)}
                    disabled={actionLoading?.startsWith(`change-role-${participant.id}`) || actionLoading === `remove-member-${participant.id}`}
                    className="flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
                    title="Изменить роль"
                  >
                    <span>Роль</span>
                    <ChevronDown size={12} />
                  </button>

                  {roleDropdownOpen === participant.id ? (
                    <>
                      <button type="button" onClick={onCloseRoleDropdown} className="fixed inset-0 z-40" aria-label="Закрыть меню" />
                      <div className="absolute right-0 top-full z-50 mt-1 w-36 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
                        {assignableRoles.map((role) => (
                          <button
                            key={`${participant.id}-${role}`}
                            type="button"
                            onClick={() => onChangeRole(participant.id, role)}
                            disabled={memberRole === role}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {getRoleIcon(role)}
                            <span>{getRoleLabel(role)}</span>
                          </button>
                        ))}
                      </div>
                    </>
                  ) : null}
                </div>
              ) : null}

              {canEdit && !isParticipantOwner && participant.id !== currentUserId ? (
                <button
                  type="button"
                  onClick={() => onRemoveMember(participant.id)}
                  disabled={actionLoading === `remove-member-${participant.id}` || actionLoading?.startsWith(`change-role-${participant.id}`)}
                  className="text-gray-400 hover:text-red-600 disabled:opacity-50"
                  title="Удалить из чата"
                >
                  <UserMinus size={16} />
                </button>
              ) : null}
            </div>
          );
        })}
      </div>

      {(chat.participant_details || []).length > 5 ? (
        <button
          type="button"
          onClick={onToggleShowAllParticipants}
          className="mt-3 w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100"
        >
          {showAllParticipants ? "Свернуть" : `Посмотреть всех (${chat.participant_details?.length || 0})`}
        </button>
      ) : null}

      {isOwner ? (
        <div className="mt-4 rounded-lg bg-gray-50 p-3">
          <p className="mb-2 text-xs font-semibold text-gray-700">Роли участников:</p>
          <div className="space-y-1 text-xs text-gray-600">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-medium text-purple-700 ring-1 ring-purple-200">
                <ShieldCheck size={10} />
                Владелец
              </span>
              <span>— полный контроль над чатом</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700 ring-1 ring-red-200">
                <Shield size={10} />
                Админ
              </span>
              <span>— управление участниками, редактирование</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700 ring-1 ring-blue-200">
                <Shield size={10} />
                Модератор
              </span>
              <span>— закрепление и удаление сообщений</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-700 ring-1 ring-gray-200">Участник</span>
              <span>— отправка сообщений</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 ring-1 ring-amber-200">Гость</span>
              <span>— только чтение</span>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
