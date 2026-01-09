import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { feedApi } from '@/api/feed';
import type { Comment } from '@/types';
import { Button } from '@/components/ui/Button';

const commentSchema = z.object({
  text: z.string().min(1, 'Комментарий не может быть пустым').max(1000, 'Максимум 1000 символов'),
});

type CommentFormData = z.infer<typeof commentSchema>;

interface CommentsListProps {
  postId: number;
}

export function CommentsList({ postId }: CommentsListProps) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const { register, handleSubmit, formState: { errors }, reset } = useForm<CommentFormData>({
    resolver: zodResolver(commentSchema),
  });

  const { data: comments, isLoading } = useQuery({
    queryKey: ['comments', postId],
    queryFn: () => feedApi.getComments(postId),
  });

  const createMutation = useMutation({
    mutationFn: (data: CommentFormData) => feedApi.createComment(postId, data.text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', postId] });
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      reset();
      setShowForm(false);
    },
  });

  const likeMutation = useMutation({
    mutationFn: (comment: Comment) =>
      comment.liked_by_me
        ? feedApi.unlikeComment(comment.id)
        : feedApi.likeComment(comment.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', postId] });
    },
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 1) return 'только что';
    if (diffMins < 60) return `${diffMins} мин назад`;
    if (diffHours < 24) return `${diffHours} ч назад`;
    return date.toLocaleDateString('ru-RU');
  };

  const onSubmit = (data: CommentFormData) => {
    createMutation.mutate(data);
  };

  if (isLoading) {
    return <div className="text-center py-4 text-gray-500">Загрузка...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Форма добавления */}
      {showForm ? (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-2">
          <textarea
            {...register('text')}
            placeholder="Напишите комментарий..."
            rows={3}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
          {errors.text && (
            <p className="text-sm text-red-600">{errors.text.message}</p>
          )}
          <div className="flex space-x-2">
            <Button
              type="submit"
              size="sm"
              isLoading={createMutation.isPending}
            >
              Отправить
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setShowForm(false);
                reset();
              }}
            >
              Отмена
            </Button>
          </div>
        </form>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(true)}
          className="w-full"
        >
          💬 Добавить комментарий
        </Button>
      )}

      {/* Список комментариев */}
      {comments && comments.length > 0 ? (
        <div className="space-y-3">
          {comments.map((comment) => (
            <div key={comment.id} className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-start space-x-3">
                {/* Аватар автора */}
                {comment.author.photo ? (
                  <img
                    src={comment.author.photo}
                    alt={comment.author.full_name}
                    className="h-8 w-8 rounded-full object-cover"
                  />
                ) : (
                  <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <span className="text-blue-600 font-medium text-xs">
                      {comment.author.first_name?.[0]}{comment.author.last_name?.[0]}
                    </span>
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  {/* Заголовок */}
                  <div className="flex items-center space-x-2 mb-1">
                    <span className="font-medium text-sm text-gray-900">
                      {comment.author.full_name}
                    </span>
                    <span className="text-xs text-gray-500">
                      {formatDate(comment.created_at)}
                    </span>
                  </div>

                  {/* Текст комментария */}
                  <p className="text-sm text-gray-700 whitespace-pre-wrap break-words">
                    {comment.text}
                  </p>

                  {/* Лайк */}
                  <button
                    onClick={() => likeMutation.mutate(comment)}
                    disabled={likeMutation.isPending}
                    className={`mt-2 flex items-center space-x-1 text-xs ${
                      comment.liked_by_me ? 'text-blue-600' : 'text-gray-500'
                    } hover:text-blue-600 transition-colors`}
                  >
                    <span>{comment.liked_by_me ? '❤️' : '🤍'}</span>
                    {comment.likes_count > 0 && (
                      <span>{comment.likes_count}</span>
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-center text-sm text-gray-500 py-4">
          Комментариев пока нет. Будьте первым!
        </p>
      )}
    </div>
  );
}
