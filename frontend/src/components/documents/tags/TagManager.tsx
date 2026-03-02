'use client';

import { useState, useEffect } from 'react';
import { DocumentTag } from '@/types/api';
import { apiClient } from '@/lib/api';
import TagBadge from './TagBadge';

export default function TagManager() {
  const [tags, setTags] = useState<DocumentTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingTag, setEditingTag] = useState<DocumentTag | null>(null);
  const [formData, setFormData] = useState({ name: '', color: '#6c757d' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadTags();
  }, []);

  const loadTags = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getDocumentTags();
      setTags(response.results || response);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки тегов');
      console.error('Failed to load tags:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      alert('Введите название тега');
      return;
    }

    try {
      setSubmitting(true);

      if (editingTag) {
        const updated = await apiClient.updateDocumentTag(editingTag.id, formData);
        setTags(prev => prev.map(t => (t.id === updated.id ? updated : t)));
      } else {
        const created = await apiClient.createDocumentTag(formData);
        setTags(prev => [created, ...prev]);
      }

      setFormData({ name: '', color: '#6c757d' });
      setShowForm(false);
      setEditingTag(null);
    } catch (err: any) {
      alert(err.message || 'Ошибка при сохранении тега');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (tag: DocumentTag) => {
    setEditingTag(tag);
    setFormData({ name: tag.name, color: tag.color || '#6c757d' });
    setShowForm(true);
  };

  const handleDelete = async (tag: DocumentTag) => {
    if (!confirm(`Удалить тег "${tag.name}"? У ${tag.documents_count} документов будет удален этот тег.`)) {
      return;
    }

    try {
      await apiClient.deleteDocumentTag(tag.id);
      setTags(prev => prev.filter(t => t.id !== tag.id));
    } catch (err: any) {
      alert(err.message || 'Ошибка при удалении тега');
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingTag(null);
    setFormData({ name: '', color: '#6c757d' });
  };

  return (
    <div className="tag-manager">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>Управление тегами</h4>
        {!showForm && (
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowForm(true)}
          >
            <i className="bi bi-plus-lg"></i> Создать тег
          </button>
        )}
      </div>

      {/* Форма создания/редактирования */}
      {showForm && (
        <div className="card mb-3">
          <div className="card-body">
            <h5 className="card-title">
              {editingTag ? 'Редактировать тег' : 'Новый тег'}
            </h5>
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label className="form-label">Название</label>
                <input
                  type="text"
                  className="form-control"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Название тега"
                  required
                />
              </div>

              <div className="mb-3">
                <label className="form-label">Цвет</label>
                <div className="d-flex gap-2 align-items-center">
                  <input
                    type="color"
                    className="form-control form-control-color"
                    value={formData.color}
                    onChange={e => setFormData({ ...formData, color: e.target.value })}
                  />
                  <input
                    type="text"
                    className="form-control"
                    style={{ maxWidth: '100px' }}
                    value={formData.color}
                    onChange={e => setFormData({ ...formData, color: e.target.value })}
                    placeholder="#6c757d"
                  />
                </div>
              </div>

              <div className="d-flex gap-2">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? 'Сохранение...' : editingTag ? 'Сохранить' : 'Создать'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCancel}
                  disabled={submitting}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Список тегов */}
      {loading && (
        <div className="text-center py-3">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Загрузка...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {!loading && !error && tags.length === 0 && (
        <div className="text-muted text-center py-3">
          Теги не найдены. Создайте первый тег!
        </div>
      )}

      {!loading && !error && tags.length > 0 && (
        <div className="list-group">
          {tags.map(tag => (
            <div key={tag.id} className="list-group-item">
              <div className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                  <TagBadge tag={tag} />
                  <small className="text-muted">
                    ({tag.documents_count} {tag.documents_count === 1 ? 'документ' : 'документов'})
                  </small>
                </div>

                <div className="btn-group btn-group-sm" role="group">
                  <button
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={() => handleEdit(tag)}
                    title="Редактировать"
                  >
                    <i className="bi bi-pencil"></i>
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline-danger"
                    onClick={() => handleDelete(tag)}
                    title="Удалить"
                  >
                    <i className="bi bi-trash"></i>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
