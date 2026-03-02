'use client';

import { useState, useEffect } from 'react';
import { DocumentVersion } from '@/types/api';
import { apiClient } from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

interface DocumentVersionHistoryProps {
  documentId: number;
  onRevert?: () => void;
}

export default function DocumentVersionHistory({
  documentId,
  onRevert,
}: DocumentVersionHistoryProps) {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reverting, setReverting] = useState<number | null>(null);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);

  useEffect(() => {
    loadVersions();
  }, [documentId]);

  const loadVersions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getDocumentVersions(documentId);
      setVersions(response.results || response);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки версий');
      console.error('Failed to load versions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRevert = async (versionId: number) => {
    if (!confirm('Вернуться к этой версии документа? Текущее состояние будет сохранено как новая версия.')) {
      return;
    }

    try {
      setReverting(versionId);
      await apiClient.revertDocumentToVersion(documentId, versionId);
      await loadVersions();
      if (onRevert) onRevert();
    } catch (err: any) {
      alert(err.message || 'Ошибка при откате к версии');
    } finally {
      setReverting(null);
    }
  };

  const toggleExpanded = (versionId: number) => {
    setExpandedVersion(expandedVersion === versionId ? null : versionId);
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

  if (versions.length === 0) {
    return (
      <div className="text-muted text-center py-3">
        История версий пуста
      </div>
    );
  }

  return (
    <div className="document-version-history">
      <h5 className="mb-3">История версий ({versions.length})</h5>

      <div className="timeline">
        {versions.map((version, index) => {
          const isLatest = index === 0;
          const timeAgo = formatDistanceToNow(new Date(version.created_at), {
            addSuffix: true,
            locale: ru,
          });
          const hasChanges = version.changes && Object.keys(version.changes).length > 0;
          const isExpanded = expandedVersion === version.id;

          return (
            <div key={version.id} className="timeline-item mb-3">
              <div className="card">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div className="flex-grow-1">
                      <h6 className="mb-1">
                        Версия {version.version}
                        {isLatest && (
                          <span className="badge bg-success ms-2 small">Текущая</span>
                        )}
                      </h6>
                      <div className="text-muted small">
                        <i className="bi bi-person"></i> {version.user}
                        <span className="mx-2">·</span>
                        <i className="bi bi-clock"></i> {timeAgo}
                      </div>
                      {version.comment && (
                        <div className="mt-2 small">{version.comment}</div>
                      )}
                    </div>

                    {!isLatest && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onClick={() => handleRevert(version.revision_id)}
                        disabled={reverting !== null}
                      >
                        {reverting === version.revision_id ? (
                          <>
                            <span className="spinner-border spinner-border-sm me-1"></span>
                            Откат...
                          </>
                        ) : (
                          <>
                            <i className="bi bi-arrow-counterclockwise"></i> Откатить
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {/* Изменения */}
                  {hasChanges && (
                    <div className="mt-2">
                      <button
                        type="button"
                        className="btn btn-sm btn-link text-decoration-none p-0"
                        onClick={() => toggleExpanded(version.id)}
                      >
                        <i className={`bi bi-chevron-${isExpanded ? 'up' : 'down'}`}></i>
                        {isExpanded ? 'Скрыть' : 'Показать'} изменения
                      </button>

                      {isExpanded && (
                        <div className="mt-2 p-2 bg-light rounded">
                          <table className="table table-sm table-borderless mb-0">
                            <tbody>
                              {Object.entries(version.changes).map(([field, value]) => (
                                <tr key={field}>
                                  <td className="text-muted small" style={{ width: '30%' }}>
                                    {field}:
                                  </td>
                                  <td className="small">
                                    <code className="text-dark">
                                      {typeof value === 'object'
                                        ? JSON.stringify(value, null, 2)
                                        : String(value)}
                                    </code>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
