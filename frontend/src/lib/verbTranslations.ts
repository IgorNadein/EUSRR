/**
 * Переводы и категоризация notification verbs
 * 
 * Backend возвращает verb как есть (например: 'request_new', 'chat_new_message')
 * Frontend отвечает за перевод и группировку по категориям
 */

// Маппинг verb → категория для группировки
export const VERB_CATEGORIES: Record<string, string> = {
  // Заявки
  request_new: 'Заявки',
  request_created: 'Заявки',
  request_updated: 'Заявки',
  request_approved: 'Заявки',
  request_rejected: 'Заявки',
  request_comment: 'Заявки',
  request_commented: 'Заявки',
  request_status_changed: 'Заявки',
  
  // Сообщения и чат
  chat_new_message: 'Сообщения',
  chat_mention: 'Упоминания',
  chat_reply: 'Сообщения',
  chat_added_to_chat: 'Чат',
  announcement_new_message: 'Объявления',
  message_received: 'Сообщения',
  mention: 'Упоминания',
  
  // Документы
  document_ready: 'Документы',
  document_uploaded: 'Документы',
  document_shared: 'Документы',
  
  // Календарь
  calendar_invitation: 'Календарь',
  calendar_event: 'Календарь',
  event_created: 'Календарь',
  
  // Закупки
  procurement_new_request: 'Закупки',
  procurement_department_request: 'Закупки',
  procurement_pending_approval: 'Закупки',
  procurement_stage_approved: 'Закупки',
  procurement_approved: 'Закупки',
  procurement_rejected: 'Закупки',
  procurement_in_progress: 'Закупки',
  procurement_completed: 'Закупки',
  procurement_cancelled: 'Закупки',
  procurement_item_updated: 'Закупки',
  procurement_request_commented: 'Закупки',
  procurement_item_commented: 'Закупки',
  
  // Новости
  feed_new_post: 'Новости',
  feed_post_comment: 'Новости',
  feed_post_reaction: 'Новости',
  
  // Системные
  system_announcement: 'Система',
  system_notification: 'Система',
};

// Маппинг verb → название для UI (используется когда нет title в data)
export const VERB_NAMES: Record<string, string> = {
  // Заявки
  request_new: 'Новая заявка',
  request_created: 'Новая заявка',
  request_updated: 'Заявка обновлена',
  request_approved: 'Заявка одобрена',
  request_rejected: 'Заявка отклонена',
  request_comment: 'Комментарий к заявке',
  request_commented: 'Комментарий к заявке',
  request_status_changed: 'Статус заявки изменен',
  
  // Сообщения и чат
  chat_new_message: 'Новое сообщение',
  chat_mention: 'Вас упомянули',
  chat_reply: 'Ответ на сообщение',
  chat_added_to_chat: 'Добавлены в чат',
  announcement_new_message: 'Новое объявление',
  message_received: 'Новое сообщение',
  mention: 'Вас упомянули',
  
  // Документы
  document_ready: 'Документ готов',
  document_uploaded: 'Новый документ',
  document_shared: 'Документ предоставлен',
  
  // Календарь
  calendar_invitation: 'Приглашение на событие',
  calendar_event: 'Событие календаря',
  event_created: 'Событие создано',
  
  // Закупки
  procurement_new_request: 'Новая закупка',
  procurement_department_request: 'Новая заявка для отдела',
  procurement_pending_approval: 'Требуется согласование закупки',
  procurement_stage_approved: 'Этап согласования закупки пройден',
  procurement_approved: 'Закупка одобрена',
  procurement_rejected: 'Закупка отклонена',
  procurement_in_progress: 'Закупка взята в работу',
  procurement_completed: 'Закупка завершена',
  procurement_cancelled: 'Закупка отменена',
  procurement_item_updated: 'Позиция закупки изменена',
  procurement_request_commented: 'Комментарий к закупке',
  procurement_item_commented: 'Комментарий к позиции закупки',
  
  // Новости
  feed_new_post: 'Новая публикация',
  feed_post_comment: 'Комментарий к публикации',
  feed_post_reaction: 'Реакция на публикацию',
  
  // Системные
  system_announcement: 'Системное объявление',
  system_notification: 'Системное уведомление',
};

/**
 * Получить категорию для verb
 */
export function getVerbCategory(verb: string): string {
  return VERB_CATEGORIES[verb] || 'Общее';
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
  return VERB_NAMES[verb] || verb.replace(/_/g, ' ');
}

/**
 * Получить человеко-читаемое название из verb
 * Преобразует snake_case в Title Case
 */
export function humanizeVerb(verb: string): string {
  return verb
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
