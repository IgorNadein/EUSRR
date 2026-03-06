'use client';

import { useState, useEffect } from 'react';
import { DocumentComment } from '@/types/api';
import { apiClient } from '@/lib/api';
import CommentItem from './CommentItem';
import CommentForm from './CommentForm';

interface DocumentCommentsProps {
  documentId: number;
}

export default function DocumentComments({ documentId }: DocumentCommentsProps) {
  const [comments, setComments] = useState<DocumentComment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadComments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getDocumentComments(documentId);
      setComments(response.results || response);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки комментариев');
      console.error('Failed to load comments:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadComments();
  }, [documentId]);

  const handleCommentAdded = async (newComment: DocumentComment) => {
    setComments(prev => [newComment, ...prev]);
  };

  const handleCommentUpdated = (updatedComment: DocumentComment) => {
    setComments(prev =>
      prev.map(comment =>
        comment.id === updatedComment.id ? updatedComment : comment
      )
    );
  };

  const handleCommentDeleted = (commentId: number) => {
    setComments(prev => prev.filter(comment => comment.id !== commentId));
  };

  const topLevelComments = comments.filter(c => !c.parent);

  return (
    <div className="document-comments mt-4">
      <h3 className="h5 mb-3">
        Комментарии
        {comments.length > 0 && (
          <span className="badge bg-secondary ms-2">{comments.length}</span>
        )}
      </h3>

      {/* Форма добавления нового комментария */}
      <div className="mb-4">
        <CommentForm
          documentId={documentId}
          onCommentAdded={handleCommentAdded}
        />
      </div>

      {/* Список комментариев */}
      {loading && (
        <div className="text-center py-3">
          <div className="spinner-border spinner-border-sm" role="status">
            <span className="visually-hidden">Загрузка...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {!loading && !error && topLevelComments.length === 0 && (
        <div className="text-muted text-center py-3">
          Пока нет комментариев. Будьте первым!
        </div>
      )}

      {!loading && !error && topLevelComments.length > 0 && (
        <div className="comments-list">
          {topLevelComments.map(comment => (
            <CommentItem
              key={comment.id}
              comment={comment}
              allComments={comments}
              onCommentUpdated={handleCommentUpdated}
              onCommentDeleted={handleCommentDeleted}
              onReplyAdded={handleCommentAdded}
            />
          ))}
        </div>
      )}
    </div>
  );
}
