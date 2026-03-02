'use client';

import { useState, useEffect } from 'react';
import { DocumentActivity } from '@/types/api';
import { apiClient } from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

interface DocumentActivityTimelineProps {
  documentId: number;
}

export default function DocumentActivityTimeline({ documentId }: DocumentActivityTimelineProps) {
  const [activities, setActivities] = useState<DocumentActivity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadActivities();
  }, [documentId]);

  const loadActivities = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getDocumentActivity(documentId);
      setActivities(response.results || response);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки активности');
      console.error('Failed to load activity:', err);
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (action: string) => {
    const actionLower = action.toLowerCase();
    if (actionLower.includes('created') || actionLower.includes('создан')) return 'bi-plus-circle-fill text-success';
    if (actionLower.includes('updated') || actionLower.includes('обновлен')) return 'bi-pencil-fill text-primary';
    if (actionLower.includes('deleted') || actionLower.includes('удалён')) return 'bi-trash-fill text-danger';
    if (actionLower.includes('comment') || actionLower.includes('комментарий')) return 'bi-chat-fill text-info';
    if (actionLower.includes('version') || actionLower.includes('версия')) return 'bi-clock-history text-warning';
    return 'bi-circle-fill text-secondary';
  };

  if (loading) {
    return (
      <div className="text-center py-3">
        <div className="spinner-border" role="status">
          <span className="visually-hidden">Загрузка...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        {error}
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="text-muted text-center py-3">
        История активности пуста
      </div>
    );
  }

  return (
    <div className="document-activity-timeline">
      <h5 className="mb-3">Активность ({activities.length})</h5>

      <div className="timeline">
        {activities.map((activity, index) => {
          const timeAgo = formatDistanceToNow(new Date(activity.timestamp), {
            addSuffix: true,
            locale: ru,
          });

          return (
            <div key={activity.id} className="d-flex gap-3 mb-3">
              {/* Иконка */}
              <div className="flex-shrink-0">
                <i className={`bi ${getActionIcon(activity.action)} fs-5`}></i>
              </div>

              {/* Содержимое */}
              <div className="flex-grow-1">
                <div className="card">
                  <div className="card-body py-2 px-3">
                    <div className="d-flex justify-content-between align-items-start">
                      <div>
                        <strong>{activity.user}</strong>
                        <span className="mx-2">·</span>
                        <span className="text-muted">{activity.action}</span>
                      </div>
                      <small className="text-muted">{timeAgo}</small>
                    </div>
                    {activity.description && (
                      <div className="mt-1 small">{activity.description}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
