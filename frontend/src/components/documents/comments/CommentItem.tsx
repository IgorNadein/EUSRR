'use client';

import { useState } from 'react';
import { DocumentComment } from '@/types/api';
import { apiClient } from '@/lib/api';
import CommentForm from './CommentForm';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

interface CommentItemProps {
  comment: DocumentComment;
  allComments: DocumentComment[];
  onCommentUpdated: (comment: DocumentComment) => void;
  onCommentDeleted: (commentId: number) => void;
  onReplyAdded: (comment: DocumentComment) => void;
  depth?: number;
}

export default function CommentItem({
  comment,
  allComments,
  onCommentUpdated,
  onCommentDeleted,
  onReplyAdded,
  depth = 0,
}: CommentItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isReplying, setIsReplying] = useState(false);
  const [editText, setEditText] = useState(comment.text);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showReplies, setShowReplies] = useState(true);

  const replies = allComments.filter(c => c.parent === comment.id);
  const maxDepth = 3; // Максимальная глубина вложенности

  const handleEdit = async () => {
    try {
      const updated = await apiClient.updateDocumentComment(comment.document, comment.id, editText);
      onCommentUpdated(updated);
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to update comment:', err);
      alert('Ошибка при обновлении комментария');
    }
  };

  const handleDelete = async () => {
    if (!confirm('Удалить комментарий?')) return;

    try {
      setIsDeleting(true);
      await apiClient.deleteDocumentComment(comment.document, comment.id);
      onCommentDeleted(comment.id);
    } catch (err) {
      console.error('Failed to delete comment:', err);
      alert('Ошибка при удалении комментария');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReplyAdded = (newComment: DocumentComment) => {
    onReplyAdded(newComment);
    setIsReplying(false);
  };

  const timeAgo = formatDistanceToNow(new Date(comment.created_at), {
    addSuffix: true,
    locale: ru,
  });

  return (
    <div
      className={`comment-item mb-3 ${depth > 0 ? 'ms-4' : ''}`}
      style={{ borderLeft: depth > 0 ? '2px solid #dee2e6' : 'none', paddingLeft: depth > 0 ? '1rem' : 0 }}
    >
      <div className="card">
        <div className="card-body">
          {/* Заголовок комментария */}
          <div className="d-flex align-items-start mb-2">
            <div className="flex-grow-1">
              <strong>{comment.author.full_name}</strong>
              <small className="text-muted ms-2">{timeAgo}</small>
              {comment.updated_at !== comment.created_at && (
                <small className="text-muted ms-1">(изменено)</small>
              )}
            </div>

            {/* Действия */}
            {(comment.can_edit || comment.can_delete) && !isEditing && (
              <div className="btn-group btn-group-sm" role="group">
                {comment.can_edit && (
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={() => setIsEditing(true)}
                    title="Редактировать"
                  >
                    <i className="bi bi-pencil"></i>
                  </button>
                )}
                {comment.can_delete && (
                  <button
                    type="button"
                    className="btn btn-outline-danger"
                    onClick={handleDelete}
                    disabled={isDeleting}
                    title="Удалить"
                  >
                    <i className="bi bi-trash"></i>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Текст комментария */}
          {!isEditing ? (
            <div className="comment-text mb-2">{comment.text}</div>
          ) : (
            <div className="mb-2">
              <textarea
                className="form-control mb-2"
                rows={3}
                value={editText}
                onChange={e => setEditText(e.target.value)}
              />
              <div className="d-flex gap-2">
                <button
                  className="btn btn-sm btn-primary"
                  onClick={handleEdit}
                  disabled={!editText.trim()}
                >
                  Сохранить
                </button>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => {
                    setIsEditing(false);
                    setEditText(comment.text);
                  }}
                >
                  Отмена
                </button>
              </div>
            </div>
          )}

          {/* Кнопка ответить */}
          {!isEditing && depth < maxDepth && (
            <button
              className="btn btn-sm btn-link text-decoration-none p-0"
              onClick={() => setIsReplying(!isReplying)}
            >
              <i className="bi bi-reply"></i> Ответить
            </button>
          )}
        </div>
      </div>

      {/* Форма ответа */}
      {isReplying && (
        <div className="mt-2 ms-4">
          <CommentForm
            documentId={comment.document}
            parentId={comment.id}
            onCommentAdded={handleReplyAdded}
            onCancel={() => setIsReplying(false)}
          />
        </div>
      )}

      {/* Ответы */}
      {replies.length > 0 && (
        <div className="replies mt-2">
          {depth < maxDepth ? (
            <>
              <button
                className="btn btn-sm btn-link text-decoration-none"
                onClick={() => setShowReplies(!showReplies)}
              >
                <i className={`bi bi-chevron-${showReplies ? 'up' : 'down'}`}></i>
                {showReplies ? 'Скрыть' : 'Показать'} ответы ({replies.length})
              </button>
              {showReplies && (
                <div>
                  {replies.map(reply => (
                    <CommentItem
                      key={reply.id}
                      comment={reply}
                      allComments={allComments}
                      onCommentUpdated={onCommentUpdated}
                      onCommentDeleted={onCommentDeleted}
                      onReplyAdded={onReplyAdded}
                      depth={depth + 1}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="text-muted small">
              Ещё {replies.length} {replies.length === 1 ? 'ответ' : 'ответов'}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
