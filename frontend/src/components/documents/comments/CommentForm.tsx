'use client';

import { useState } from 'react';
import { DocumentComment } from '@/types/api';
import { apiClient } from '@/lib/api';

interface CommentFormProps {
  documentId: number;
  parentId?: number;
  onCommentAdded: (comment: DocumentComment) => void;
  onCancel?: () => void;
}

export default function CommentForm({
  documentId,
  parentId,
  onCommentAdded,
  onCancel,
}: CommentFormProps) {
  const [text, setText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!text.trim()) {
      setError('Комментарий не может быть пустым');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      const data: any = {
        document: documentId,
        text: text.trim(),
      };

      if (parentId) {
        data.parent = parentId;
      }

      const newComment = await apiClient.createDocumentComment(data);
      onCommentAdded(newComment);
      setText('');
    } catch (err: any) {
      setError(err.message || 'Ошибка при добавлении комментария');
      console.error('Failed to create comment:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="comment-form">
      <div className="mb-2">
        <textarea
          className="form-control"
          rows={parentId ? 2 : 3}
          placeholder={parentId ? 'Написать ответ...' : 'Добавить комментарий...'}
          value={text}
          onChange={e => setText(e.target.value)}
          disabled={isSubmitting}
        />
        {error && (
          <div className="text-danger small mt-1">{error}</div>
        )}
      </div>

      <div className="d-flex gap-2">
        <button
          type="submit"
          className="btn btn-primary btn-sm"
          disabled={isSubmitting || !text.trim()}
        >
          {isSubmitting ? (
            <>
              <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
              Отправка...
            </>
          ) : (
            parentId ? 'Ответить' : 'Отправить'
          )}
        </button>

        {onCancel && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Отмена
          </button>
        )}
      </div>
    </form>
  );
}
