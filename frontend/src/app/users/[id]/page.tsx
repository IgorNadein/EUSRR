"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Award,
  Building2,
  Calendar,
  Check,
  Clock,
  Copy,
  Mail,
  MessageCircle,
  Pencil,
  Phone,
} from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import EditUserProfileModal from "@/components/users/EditUserProfileModal";
import EmployeeActionModal from "@/components/users/EmployeeActionModal";
import EmployeeActionsTimeline from "@/components/users/EmployeeActionsTimeline";
import { useUser } from "@/contexts/UserContext";
import { useUserDetailPage } from "@/hooks/useUserDetailPage";
import {
  formatBirthday,
  formatPhoneForLink,
  getEmployeeActionBadgeClass,
  getWorkDuration,
} from "@/lib/users/userDetailUtils";

export default function UserDetailPage() {
  const params = useParams<{ id: string }>();
  const { user: currentUser } = useUser();
  const userId = Number(params?.id);

  const {
    actionForm,
    actionLoading,
    actionTypes,
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
    handleCopyToClipboard,
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
  } = useUserDetailPage(userId, currentUser);

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
            <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
              <div className="flex items-start gap-4">
                <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xl font-semibold text-white">
                  {avatarUrl && !avatarFailed ? (
                    // eslint-disable-next-line @next/next/no-img-element
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

                <div className="min-w-0 flex-1">
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
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getEmployeeActionBadgeClass(latestAction.action)}`}>
                        {latestAction.action_display || latestAction.action}
                      </span>
                    )}
                    {canManageActions && (
                      <button
                        onClick={handleOpenActionModal}
                        className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 transition hover:bg-gray-200"
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
                        {creatingChat ? "Загрузка..." : "Написать"}
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

            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                <h2 className="mb-3 text-sm font-semibold text-gray-900">Контакты</h2>
                <div className="space-y-2">
                  {person.email && (
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1 flex items-center gap-2">
                        <Mail size={16} className="flex-shrink-0 text-gray-400" />
                        <a href={`mailto:${person.email}`} className="truncate text-sm text-sky-600 hover:underline">
                          {person.email}
                        </a>
                      </div>
                      <button
                        onClick={() => handleCopyToClipboard(person.email, "email")}
                        className="ml-2 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        {copySuccess === "email" ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                    </div>
                  )}

                  {person.phone_number && (
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1 flex items-center gap-2">
                        <Phone size={16} className="flex-shrink-0 text-gray-400" />
                        <a href={`tel:${formatPhoneForLink(person.phone_number)}`} className="truncate text-sm text-sky-600 hover:underline">
                          {person.phone_number}
                        </a>
                      </div>
                      <button
                        onClick={() => handleCopyToClipboard(person.phone_number ?? "", "phone")}
                        className="ml-2 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        {copySuccess === "phone" ? <Check size={14} /> : <Copy size={14} />}
                      </button>
                    </div>
                  )}

                  {person.telegram && (
                    <div className="flex items-center gap-2">
                      <MessageCircle size={16} className="flex-shrink-0 text-gray-400" />
                      <a
                        href={`https://t.me/${person.telegram.replace("@", "")}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate text-sm text-sky-600 hover:underline"
                      >
                        {person.telegram}
                      </a>
                      <span className="ml-auto text-xs text-gray-400">Telegram</span>
                    </div>
                  )}

                  {person.whatsapp && (
                    <div className="flex items-center gap-2">
                      <Phone size={16} className="flex-shrink-0 text-gray-400" />
                      <a
                        href={`https://wa.me/${formatPhoneForLink(person.whatsapp)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate text-sm text-sky-600 hover:underline"
                      >
                        {person.whatsapp}
                      </a>
                      <span className="ml-auto text-xs text-gray-400">WhatsApp</span>
                    </div>
                  )}

                  {person.wechat && (
                    <div className="flex items-center gap-2">
                      <MessageCircle size={16} className="flex-shrink-0 text-gray-400" />
                      <span className="truncate text-sm text-gray-700">{person.wechat}</span>
                      <span className="ml-auto text-xs text-gray-400">WeChat</span>
                    </div>
                  )}

                  {!person.email && !person.phone_number && !person.telegram && !person.whatsapp && !person.wechat && (
                    <p className="text-sm text-gray-500">Нет контактов</p>
                  )}
                </div>
              </section>

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
                            <p className="font-medium text-gray-900">{getWorkDuration(person.date_joined)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <Calendar size={16} className="text-gray-400" />
                          <div>
                            <p className="text-xs text-gray-500">Дата найма</p>
                            <p className="font-medium text-gray-900">
                              {new Date(person.date_joined).toLocaleDateString("ru-RU")}
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
                          <p className="font-medium text-gray-900">{formatBirthday(person.birth_date)}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}
            </div>

            {person.departments && person.departments.length > 0 && (
              <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900">
                  <Building2 size={16} />
                  Отделы
                </h2>
                <div className="space-y-2">
                  {person.departments.map((department) => (
                    <Link
                      key={department.id}
                      href={`/departments/${department.id}`}
                      className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 transition hover:bg-gray-100"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-900">{department.name}</p>
                        {department.role_name && (
                          <p className="text-xs text-gray-500">{department.role_name}</p>
                        )}
                      </div>
                      {department.is_head && (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">
                          Руководитель
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            <EmployeeActionsTimeline
              actionLoading={actionLoading}
              canManageActions={canManageActions}
              canViewActions={canViewActions}
              latestActionId={latestAction?.id ?? null}
              onAddAction={handleOpenActionModal}
              onDeleteAction={handleDeleteAction}
              onEditAction={handleEditAction}
              sortedActions={sortedActions}
            />
          </>
        ) : null}
      </div>

      <EditUserProfileModal
        actionLoading={actionLoading}
        avatarFailed={avatarFailed}
        avatarUrl={avatarUrl}
        form={editForm}
        initials={initials}
        isOpen={isEditModalOpen}
        onAvatarChange={handleAvatarChange}
        onClose={handleCloseEditModal}
        onSave={handleSaveEdit}
        onTextFieldChange={(field, value) => setEditField(field, value)}
        person={person}
      />

      <EmployeeActionModal
        actionLoading={actionLoading}
        actionTypes={actionTypes}
        form={actionForm}
        isOpen={isActionModalOpen}
        onClose={handleCloseActionModal}
        onFieldChange={(field, value) => setActionField(field, value)}
        onSave={handleSaveAction}
      />
    </AppShell>
  );
}
