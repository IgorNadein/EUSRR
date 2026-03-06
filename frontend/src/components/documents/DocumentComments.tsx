"use client";

import { useState, useEffect } from "react";
import { MessageCircle, Send, Edit2, Trash2, CornerDownRight } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import { useUser } from "@/contexts/UserContext";

interface Comment {
  id: number;
  text: string;
  author: {
    id: number;
    first_name: string;
    last_name: string;
    patronymic?: string;
  };
  created_at: string;
  updated_at: string;
  parent?: number;
  replies?: Comment[];
}

interface DocumentCommentsProps {
  documentId: number;
}

export function DocumentComments({ documentId }: DocumentCommentsProps) {
  const { user } = useUser();
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState("");
  const [replyTo, setReplyTo] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadComments();
  }, [documentId]);

  const loadComments = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getDocumentComments(documentId);
      const data = Array.isArray(response) ? response : (response.results || []);
      
      // Структурируем комментарии в дерево
      const commentsMap = new Map<number, Comment>();
      const rootComments: Comment[] = [];

      // Сначала создаем все комментарии
      data.forEach((comment: Comment) => {
        commentsMap.set(comment.id, { ...comment, replies: [] });
      });

      // Затем строим дерево
      data.forEach((comment: Comment) => {
        const commentNode = commentsMap.get(comment.id)!;
        if (comment.parent) {
          const parentNode = commentsMap.get(comment.parent);
          if (parentNode) {
            parentNode.replies!.push(commentNode);
          }
        } else {
          rootComments.push(commentNode);
        }
      });

      setComments(rootComments);
    } catch (error) {
      console.error("Ошибка загрузки комментариев:", error);
      toast.error("Не удалось загрузить комментарии");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitComment = async () => {
    if (!newComment.trim()) return;

    setSubmitting(true);
    try {
      await apiClient.createDocumentComment({
        document: documentId,
        text: newComment,
        parent: replyTo || undefined,
      });
      
      toast.success("Комментарий добавлен");
      setNewComment("");
      setReplyTo(null);
      await loadComments();
    } catch (error) {
      console.error("Ошибка добавления комментария:", error);
      toast.error("Не удалось добавить комментарий");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateComment = async (id: number) => {
    if (!editText.trim()) return;

    setSubmitting(true);
    try {
      await apiClient.updateDocumentComment(id, editText);
      toast.success("Комментарий обновлен");
      setEditingId(null);
      setEditText("");
      await loadComments();
    } catch (error) {
      console.error("Ошибка обновления комментария:", error);
      toast.error("Не удалось обновить комментарий");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteComment = async (id: number) => {
    if (!window.confirm("Удалить комментарий?")) return;

    try {
      await apiClient.deleteDocumentComment(id);
      toast.success("Комментарий удален");
      await loadComments();
    } catch (error) {
      console.error("Ошибка удаления комментария:", error);
      toast.error("Не удалось удалить комментарий");
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "только что";
    if (diffMins < 60) return `${diffMins} мин назад`;
    if (diffHours < 24) return `${diffHours} ч назад`;
    if (diffDays < 7) return `${diffDays} дн назад`;
    
    return date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    });
  };

  const renderComment = (comment: Comment, depth: number = 0) => {
    const isAuthor = user?.id === comment.author.id;
    const isEditing = editingId === comment.id;

    return (
      <div
        key={comment.id}
        className={`${depth > 0 ? "ml-6 border-l-2 border-gray-200 pl-4" : ""}`}
      >
        <div className="rounded-lg bg-gray-50 p-3">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">
                  {comment.author.last_name} {comment.author.first_name}
                </span>
                <span className="text-xs text-gray-500">
                  {formatDate(comment.created_at)}
                </span>
                {comment.updated_at !== comment.created_at && (
                  <span className="text-xs text-gray-400">(изменено)</span>
                )}
              </div>
            </div>
            
            {isAuthor && !isEditing && (
              <div className="flex gap-1">
                <button
                  onClick={() => {
                    setEditingId(comment.id);
                    setEditText(comment.text);
                  }}
                  className="rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
                  title="Редактировать"
                >
                  <Edit2 size={14} />
                </button>
                <button
                  onClick={() => handleDeleteComment(comment.id)}
                  className="rounded p-1 text-gray-400 hover:bg-red-100 hover:text-red-600"
                  title="Удалить"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )}
          </div>

          {isEditing ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full rounded-lg border border-gray-300 p-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
                rows={2}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => handleUpdateComment(comment.id)}
                  disabled={submitting || !editText.trim()}
                  className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
                >
                  Сохранить
                </button>
                <button
                  onClick={() => {
                    setEditingId(null);
                    setEditText("");
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
                >
                  Отмена
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{comment.text}</p>
              {depth < 3 && (
                <button
                  onClick={() => setReplyTo(comment.id)}
                  className="mt-2 inline-flex items-center gap-1 text-xs text-gray-500 hover:text-sky-600"
                >
                  <CornerDownRight size={12} />
                  Ответить
                </button>
              )}
            </>
          )}
        </div>

        {/* Replies */}
        {comment.replies && comment.replies.length > 0 && (
          <div className="mt-2 space-y-2">
            {comment.replies.map((reply) => renderComment(reply, depth + 1))}
          </div>
        )}

        {/* Reply form */}
        {replyTo === comment.id && (
          <div className="ml-6 mt-2 border-l-2 border-sky-300 pl-4">
            <div className="flex gap-2">
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Напишите ответ..."
                className="flex-1 rounded-lg border border-gray-300 p-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
                rows={2}
              />
            </div>
            <div className="mt-2 flex gap-2">
              <button
                onClick={handleSubmitComment}
                disabled={submitting || !newComment.trim()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
              >
                <Send size={12} />
                Отправить
              </button>
              <button
                onClick={() => {
                  setReplyTo(null);
                  setNewComment("");
                }}
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
              >
                Отмена
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <MessageCircle size={18} className="text-gray-500" />
        <h3 className="text-sm font-medium text-gray-900">
          Комментарии ({comments.reduce((acc, c) => acc + 1 + (c.replies?.length || 0), 0)})
        </h3>
      </div>

      {/* New comment form */}
      {!replyTo && (
        <div className="space-y-2">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Добавить комментарий..."
            className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100"
            rows={3}
          />
          <button
            onClick={handleSubmitComment}
            disabled={submitting || !newComment.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
          >
            <Send size={14} />
            Отправить
          </button>
        </div>
      )}

      {/* Comments list */}
      {comments.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-500">
          Пока нет комментариев. Будьте первым!
        </p>
      ) : (
        <div className="space-y-3">
          {comments.map((comment) => renderComment(comment))}
        </div>
      )}
    </div>
  );
}
