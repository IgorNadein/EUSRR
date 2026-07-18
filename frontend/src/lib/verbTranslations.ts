/**
 * Переводы и категоризация notification verbs
 * 
 * Backend возвращает verb как есть (например: 'request_new', 'chat_new_message')
 * Frontend отвечает за перевод и группировку по категориям
 */

// Маппинг verb → категория для группировки
export const VERB_CATEGORIES: Record<string, string> = {
  // Заявки
  request_new: 'Заявления',
  request_created: 'Заявления',
  request_updated: 'Заявления',
  request_approved: 'Заявления',
  request_rejected: 'Заявления',
  request_comment: 'Заявления',
  request_commented: 'Заявления',
  request_status_changed: 'Заявления',

  // Гости
  guest_visit_submitted: 'Гости',
  guest_visit_info_provided: 'Гости',
  guest_visit_needs_info: 'Гости',
  guest_visit_approved: 'Гости',
  guest_visit_rejected: 'Гости',
  guest_visit_revoked: 'Гости',
  guest_visit_expired: 'Гости',
  guest_inviter_inactive: 'Гости',
  guest_ldap_failed: 'Гости',
  
  // Сообщения и чат
  chat_new_message: 'Сообщения',
  chat_mention: 'Упоминания',
  chat_reply: 'Сообщения',
  chat_added_to_chat: 'Чат',
  announcement_new_message: 'Объявления',
  message_received: 'Сообщения',
  commented: 'Комментарии',
  liked: 'Реакции',
  approved: 'Согласования',
  reminder: 'Напоминания',
  mention: 'Упоминания',
  mentioned: 'Упоминания',
  replied: 'Сообщения',
  
  // Документы
  document_ready: 'Документы',
  document_uploaded: 'Документы',
  document_shared: 'Документы',
  document_signed_all: 'Документы',
  document_reminder: 'Документы',
  document_comment: 'Документы',
  document_comment_reply: 'Документы',
  document_related: 'Документы',
  
  // Календарь
  calendar_invitation: 'Календарь',
  calendar_event: 'Календарь',
  event_created: 'Календарь',
  event_changed: 'Календарь',
  event_updated: 'Календарь',
  event_cancelled: 'Календарь',
  event_reminder: 'Календарь',
  event_reminder_hour: 'Календарь',
  event_reminder_day: 'Календарь',
  
  // Закупки
  procurement_new_request: 'Закупки',
  procurement_department_request: 'Закупки',
  procurement_pending_approval: 'Закупки',
  procurement_stage_approved: 'Закупки',
  procurement_approved: 'Закупки',
  procurement_rejected: 'Закупки',
  procurement_in_progress: 'Закупки',
  procurement_executor_reassigned: 'Закупки',
  procurement_arrival_notice: 'Закупки',
  procurement_completed: 'Закупки',
  procurement_cancelled: 'Закупки',
  procurement_item_updated: 'Закупки',
  procurement_request_commented: 'Закупки',
  procurement_item_commented: 'Закупки',
  equipment_transferred: 'Закупки',
  equipment_maintenance: 'Закупки',
  
  // Новости
  feed_new_post: 'Новости',
  feed_post_comment: 'Новости',
  feed_post_reaction: 'Новости',

  // Доска
  task_assigned: 'Доска',
  task_reassigned: 'Доска',
  task_comment: 'Доска',
  task_due_date_changed: 'Доска',
  task_due_soon: 'Доска',
  task_overdue: 'Доска',
  task_completed: 'Доска',
  task_reopened: 'Доска',
  task_linked_object_added: 'Доска',
  task_board_member_added: 'Доска',

  // Отделы
  department_new_employee: 'Отдел',
  department_employee_left: 'Отдел',
  department_structure_changed: 'Отдел',
  department_new_head: 'Отдел',
  department_announcement: 'Отдел',

  // Профиль
  profile_data_changed: 'Профиль',
  profile_password_changed: 'Профиль',
  profile_email_changed: 'Профиль',
  profile_messenger_linked: 'Профиль',
  profile_new_login: 'Профиль',
  
  // Системные
  notification: 'Система',
  system_notice: 'Система',
  system_maintenance: 'Система',
  system_announcement: 'Система',
  system_new_feature: 'Система',
  system_policy_change: 'Система',
  system_notification: 'Система',
};

// Маппинг verb → название для UI (используется когда нет title в data)
export const VERB_NAMES: Record<string, string> = {
  // Заявки
  request_new: 'Новое заявление',
  request_created: 'Новое заявление',
  request_updated: 'Заявление обновлено',
  request_approved: 'Заявление одобрено',
  request_rejected: 'Заявление отклонено',
  request_comment: 'Комментарий к заявлению',
  request_commented: 'Комментарий к заявлению',
  request_status_changed: 'Статус заявления изменён',

  // Гости
  guest_visit_submitted: 'Гостевой визит на рассмотрении',
  guest_visit_info_provided: 'Информация по гостевому визиту предоставлена',
  guest_visit_needs_info: 'Нужна информация по гостевому визиту',
  guest_visit_approved: 'Гостевой визит одобрен',
  guest_visit_rejected: 'Гостевой визит отклонён',
  guest_visit_revoked: 'Гостевой доступ отозван',
  guest_visit_expired: 'Гостевой доступ истёк',
  guest_inviter_inactive: 'Приглашающий гостя неактивен',
  guest_ldap_failed: 'Ошибка синхронизации гостя',
  
  // Сообщения и чат
  chat_new_message: 'Новое сообщение',
  chat_mention: 'Вас упомянули',
  chat_reply: 'Ответ на сообщение',
  chat_added_to_chat: 'Добавление в чат',
  announcement_new_message: 'Новое объявление',
  message_received: 'Личное сообщение',
  commented: 'Новый комментарий',
  liked: 'Новая реакция',
  approved: 'Одобрение',
  reminder: 'Напоминание',
  mention: 'Вас упомянули',
  mentioned: 'Вас упомянули',
  replied: 'Ответ на сообщение',
  
  // Документы
  document_ready: 'Документ на ознакомление',
  document_uploaded: 'Новый документ',
  document_shared: 'Документ предоставлен',
  document_signed_all: 'Все ознакомились с документом',
  document_reminder: 'Напоминание об ознакомлении',
  document_comment: 'Комментарий к документу',
  document_comment_reply: 'Ответ на комментарий к документу',
  document_related: 'Связанный документ',
  
  // Календарь
  calendar_invitation: 'Приглашение на событие',
  calendar_event: 'Событие календаря',
  event_created: 'Событие создано',
  event_changed: 'Событие изменено',
  event_updated: 'Событие изменено',
  event_cancelled: 'Событие отменено',
  event_reminder: 'Напоминание о событии',
  event_reminder_hour: 'Напоминание за час',
  event_reminder_day: 'Напоминание за день',
  
  // Закупки
  procurement_new_request: 'Новая заявка на закупку',
  procurement_department_request: 'Заявка на закупку для отдела',
  procurement_pending_approval: 'Требуется согласование закупки',
  procurement_stage_approved: 'Этап согласования закупки пройден',
  procurement_approved: 'Заявка на закупку одобрена',
  procurement_rejected: 'Заявка на закупку отклонена',
  procurement_in_progress: 'Заявка на закупку взята в работу',
  procurement_executor_reassigned: 'Заявку забрал другой сотрудник',
  procurement_arrival_notice: 'Поступление по закупке',
  procurement_completed: 'Заявка на закупку завершена',
  procurement_cancelled: 'Заявка на закупку отменена',
  procurement_item_updated: 'Позиция закупки изменена',
  procurement_request_commented: 'Комментарий к закупке',
  procurement_item_commented: 'Комментарий к позиции закупки',
  equipment_transferred: 'Оборудование передано',
  equipment_maintenance: 'Обслуживание оборудования',
  
  // Новости
  feed_new_post: 'Новая публикация',
  feed_post_comment: 'Комментарий к публикации',
  feed_post_reaction: 'Реакция на публикацию',

  // Доска
  task_assigned: 'Вам назначена задача',
  task_reassigned: 'Исполнитель задачи изменён',
  task_comment: 'Комментарий к задаче',
  task_due_date_changed: 'Срок задачи изменён',
  task_due_soon: 'Срок задачи сегодня',
  task_overdue: 'Задача просрочена',
  task_completed: 'Задача завершена',
  task_reopened: 'Задача возвращена в работу',
  task_linked_object_added: 'К задаче добавлен связанный объект',
  task_board_member_added: 'Вас добавили на доску',

  // Отделы
  department_new_employee: 'Новый сотрудник в отделе',
  department_employee_left: 'Сотрудник покинул отдел',
  department_structure_changed: 'Структура отдела изменена',
  department_new_head: 'Новый руководитель отдела',
  department_announcement: 'Объявление отдела',

  // Профиль
  profile_data_changed: 'Данные профиля изменены',
  profile_password_changed: 'Пароль изменён',
  profile_email_changed: 'Email изменён',
  profile_messenger_linked: 'Мессенджер привязан',
  profile_new_login: 'Вход из нового места',
  
  // Системные
  notification: 'Уведомление',
  system_notice: 'Системное уведомление',
  system_maintenance: 'Технические работы',
  system_announcement: 'Системное объявление',
  system_new_feature: 'Новый функционал',
  system_policy_change: 'Изменение политик',
  system_notification: 'Системное уведомление',
};

const VERB_TOKEN_NAMES: Record<string, string> = {
  announcement: 'объявление',
  approval: 'согласование',
  approved: 'одобрено',
  cancelled: 'отменено',
  changed: 'изменено',
  chat: 'чат',
  comment: 'комментарий',
  commented: 'комментарий',
  completed: 'завершено',
  created: 'создано',
  day: 'за день',
  document: 'документ',
  employee: 'сотрудник',
  event: 'событие',
  feed: 'лента',
  guest: 'гость',
  guests: 'гости',
  hour: 'за час',
  item: 'позиция',
  maintenance: 'обслуживание',
  message: 'сообщение',
  new: 'новое',
  notification: 'уведомление',
  pending: 'ожидает',
  post: 'публикация',
  procurement: 'закупка',
  profile: 'профиль',
  reaction: 'реакция',
  rejected: 'отклонено',
  reminder: 'напоминание',
  reply: 'ответ',
  request: 'заявка',
  signed: 'подписан',
  status: 'статус',
  system: 'система',
  transferred: 'передано',
  updated: 'обновлено',
};

/**
 * Получить категорию для verb
 */
export function getVerbCategory(verb: string): string {
  if (VERB_CATEGORIES[verb]) return VERB_CATEGORIES[verb];
  if (verb.startsWith('guest_')) return 'Гости';
  if (verb.startsWith('procurement_') || verb.startsWith('equipment_')) return 'Закупки';
  return 'Общее';
}

/**
 * Получить все verb'ы для заданной категории
 */
export function getVerbsByCategory(category: string): string[] {
  return Object.entries(VERB_CATEGORIES)
    .filter((entry) => entry[1] === category)
    .map((entry) => entry[0]);
}

/**
 * Получить название для verb (fallback если нет title в notification.data)
 */
export function getVerbName(verb: string): string {
  return VERB_NAMES[verb] || humanizeVerb(verb);
}

/**
 * Получить человеко-читаемое название из verb
 * Преобразует snake_case в Title Case
 */
export function humanizeVerb(verb: string): string {
  const translated = verb
    .split('_')
    .map((word) => VERB_TOKEN_NAMES[word] || word)
    .join(' ');

  return translated.charAt(0).toUpperCase() + translated.slice(1);
}
