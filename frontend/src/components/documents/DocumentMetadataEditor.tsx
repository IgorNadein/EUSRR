'use client';

import { useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/ui';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import {
  AlertCircle,
  FileText,
  Folder,
  Loader2,
  ScrollText,
  Tag as TagIcon,
  Upload,
  X,
} from 'lucide-react';
import type { Department, Document, User } from '@/types/api';
import { DocumentTagQuickCreate, type QuickDocumentTag } from './DocumentTagQuickCreate';
import {
  DocumentAudienceSelector,
  type DocumentAudienceMode,
} from './DocumentAudienceSelector';

type DocumentTagOption = NonNullable<Document["tags"]>[number];

interface FolderOption {
  id: number;
  name: string;
  parent_id?: number | null;
  path?: string;
}

interface FolderOptionRow {
  folder: FolderOption;
  level: number;
}

interface DocumentUpdatePayload {
  title?: string;
  description?: string;
  extracted_text?: string;
  file?: File;
  tag_ids?: number[];
  folder?: number | null;
  is_regulation?: boolean;
  sent_to_all?: boolean;
  acknowledgement_required?: boolean;
  acknowledgement_for_all?: boolean;
  recipient_ids?: number[];
  department_ids?: number[];
  acknowledgement_recipient_ids?: number[];
  acknowledgement_department_ids?: number[];
}

interface DocumentMetadataEditorProps {
  isOpen: boolean;
  onClose: () => void;
  document: Document;
  onUpdate?: () => void;
}

type ListResponse<T> = T[] | { results?: T[] };

function normalizeList<T>(response: ListResponse<T>): T[] {
  return Array.isArray(response) ? response : response.results || [];
}

function arraysEqual(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const sortedA = [...a].sort((left, right) => left - right);
  const sortedB = [...b].sort((left, right) => left - right);
  return sortedA.every((value, index) => value === sortedB[index]);
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
}

function buildFolderOptionRows(folders: FolderOption[]): FolderOptionRow[] {
  const childrenByParent = new Map<number | null, FolderOption[]>();

  folders.forEach((folder) => {
    const parentId = folder.parent_id ?? null;
    const children = childrenByParent.get(parentId) || [];
    children.push(folder);
    childrenByParent.set(parentId, children);
  });

  childrenByParent.forEach((children) => {
    children.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  });

  const rows: FolderOptionRow[] = [];
  const appendChildren = (parentId: number | null, level: number) => {
    (childrenByParent.get(parentId) || []).forEach((folder) => {
      rows.push({ folder, level });
      appendChildren(folder.id, level + 1);
    });
  };

  appendChildren(null, 0);
  return rows;
}

export function DocumentMetadataEditor({
  isOpen,
  onClose,
  document,
  onUpdate,
}: DocumentMetadataEditorProps) {
  const [title, setTitle] = useState(document.title || '');
  const [description, setDescription] = useState(document.description || '');
  const [extractedText, setExtractedText] = useState(document.extracted_text || '');
  const [replacementFile, setReplacementFile] = useState<File | null>(null);
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<number | null>(document.folder?.id || null);
  const [isRegulation, setIsRegulation] = useState(Boolean(document.is_regulation));
  const [sentToAll, setSentToAll] = useState(Boolean(document.sent_to_all ?? true));
  const [acknowledgementMode, setAcknowledgementMode] = useState<DocumentAudienceMode>(
    !document.acknowledgement_required
      ? 'none'
      : document.acknowledgement_for_all === false
        ? 'restricted'
        : 'all'
  );
  const [selectedDepartments, setSelectedDepartments] = useState<number[]>([]);
  const [selectedRecipients, setSelectedRecipients] = useState<number[]>([]);
  const [acknowledgementDepartments, setAcknowledgementDepartments] = useState<number[]>([]);
  const [acknowledgementRecipients, setAcknowledgementRecipients] = useState<number[]>([]);

  const [documentTags, setDocumentTags] = useState<DocumentTagOption[]>([]);
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);

  const [loadingReferences, setLoadingReferences] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const folderOptionRows = useMemo(() => buildFolderOptionRows(folders), [folders]);

  useEffect(() => {
    if (!isOpen) return;

    setTitle(document.title || '');
    setDescription(document.description || '');
    setExtractedText(document.extracted_text || '');
    setReplacementFile(null);
    setSelectedTags((document.tags || []).map((tag) => tag.id));
    setSelectedFolder(document.folder?.id || null);
    setIsRegulation(Boolean(document.is_regulation));
    setSentToAll(Boolean(document.sent_to_all ?? true));
    setAcknowledgementMode(
      !document.acknowledgement_required
        ? 'none'
        : document.acknowledgement_for_all === false
          ? 'restricted'
          : 'all'
    );
    setSelectedDepartments((document.departments || []).map((department) => department.id));
    setSelectedRecipients((document.recipients || []).map((recipient) => recipient.id));
    setAcknowledgementDepartments(
      (document.acknowledgement_departments || []).map((department) => department.id)
    );
    setAcknowledgementRecipients(
      (document.acknowledgement_recipients || []).map((recipient) => recipient.id)
    );
    setError(null);
  }, [isOpen, document]);

  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;

    const loadReferenceData = async () => {
      setLoadingReferences(true);
      try {
        const [tagsResponse, foldersResponse, departmentsResponse, employeesResponse] = await Promise.all([
          apiClient.getDocumentTags({ limit: 1000 }),
          apiClient.getFolders({ limit: 1000 }),
          apiClient.getDepartments({ limit: 1000 }),
          apiClient.getEmployees({ limit: 1000, is_active: true, ordering: 'last_name,first_name' }),
        ]);

        if (cancelled) return;

        setDocumentTags(normalizeList<DocumentTagOption>(tagsResponse));
        setFolders(normalizeList<FolderOption>(foldersResponse));
        setDepartments(normalizeList<Department>(departmentsResponse));
        setEmployees(normalizeList<User>(employeesResponse));
      } catch (err) {
        console.error('Error loading document edit references:', err);
        if (!cancelled) {
          toast.error('Не удалось загрузить справочники для редактирования');
        }
      } finally {
        if (!cancelled) setLoadingReferences(false);
      }
    };

    void loadReferenceData();

    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const acknowledgementEmployees = useMemo(() => {
    if (sentToAll) return employees;
    const departmentIds = new Set(selectedDepartments);
    const recipientIds = new Set(selectedRecipients);
    return employees.filter((employee) => (
      recipientIds.has(employee.id)
      || (employee.departments || []).some((department) => departmentIds.has(department.id))
    ));
  }, [employees, selectedDepartments, selectedRecipients, sentToAll]);

  const acknowledgementDepartmentOptions = useMemo(() => {
    if (sentToAll) return departments;
    const departmentIds = new Set(selectedDepartments);
    return departments.filter((department) => departmentIds.has(department.id));
  }, [departments, selectedDepartments, sentToAll]);

  useEffect(() => {
    if (sentToAll) return;
    const allowedEmployeeIds = new Set(acknowledgementEmployees.map((employee) => employee.id));
    const allowedDepartmentIds = new Set(selectedDepartments);
    setAcknowledgementRecipients((current) => current.filter((id) => allowedEmployeeIds.has(id)));
    setAcknowledgementDepartments((current) => current.filter((id) => allowedDepartmentIds.has(id)));
  }, [acknowledgementEmployees, selectedDepartments, sentToAll]);

  const toggleTag = (tagId: number) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  const handleCreatedTag = (tag: QuickDocumentTag) => {
    setDocumentTags((prev) => {
      const next = prev.some((item) => item.id === tag.id) ? prev : [...prev, tag];
      return [...next].sort((left, right) => left.name.localeCompare(right.name, 'ru'));
    });
    setSelectedTags((prev) => (prev.includes(tag.id) ? prev : [...prev, tag.id]));
  };

  const handleSave = async () => {
    const nextTitle = title.trim();
    setError(null);

    if (!nextTitle) {
      setError('Укажите название документа');
      return;
    }

    if (!sentToAll && selectedDepartments.length === 0 && selectedRecipients.length === 0) {
      setError('Выберите хотя бы один отдел или сотрудника либо включите доступ для всей компании');
      return;
    }

    if (
      acknowledgementMode === 'restricted'
      && acknowledgementDepartments.length === 0
      && acknowledgementRecipients.length === 0
    ) {
      setError('Выберите хотя бы один отдел или сотрудника для ознакомления');
      return;
    }

    setIsSaving(true);

    try {
      const updateData: DocumentUpdatePayload = {};
      const currentTagIds = (document.tags || []).map((tag) => tag.id);
      const currentDepartmentIds = (document.departments || []).map((department) => department.id);
      const currentRecipientIds = (document.recipients || []).map((recipient) => recipient.id);
      const currentAcknowledgementDepartmentIds = (document.acknowledgement_departments || []).map(
        (department) => department.id
      );
      const currentAcknowledgementRecipientIds = (document.acknowledgement_recipients || []).map(
        (recipient) => recipient.id
      );
      const currentFolder = document.folder?.id || null;
      const currentSentToAll = Boolean(document.sent_to_all ?? true);

      if (nextTitle !== document.title) {
        updateData.title = nextTitle;
      }

      if (description !== (document.description || '')) {
        updateData.description = description;
      }

      if (extractedText !== (document.extracted_text || '')) {
        updateData.extracted_text = extractedText;
      }

      if (replacementFile) {
        updateData.file = replacementFile;
      }

      if (selectedFolder !== currentFolder) {
        updateData.folder = selectedFolder;
      }

      if (isRegulation !== Boolean(document.is_regulation)) {
        updateData.is_regulation = isRegulation;
      }

      if (sentToAll !== currentSentToAll) {
        updateData.sent_to_all = sentToAll;
      }

      const acknowledgementRequired = acknowledgementMode !== 'none';
      const acknowledgementForAll = acknowledgementMode === 'all';
      if (acknowledgementRequired !== Boolean(document.acknowledgement_required)) {
        updateData.acknowledgement_required = acknowledgementRequired;
      }
      if (acknowledgementForAll !== Boolean(document.acknowledgement_for_all ?? true)) {
        updateData.acknowledgement_for_all = acknowledgementForAll;
      }

      if (!arraysEqual(currentTagIds, selectedTags)) {
        updateData.tag_ids = selectedTags;
      }

      if (!sentToAll) {
        if (sentToAll !== currentSentToAll || !arraysEqual(currentDepartmentIds, selectedDepartments)) {
          updateData.department_ids = selectedDepartments;
        }

        if (sentToAll !== currentSentToAll || !arraysEqual(currentRecipientIds, selectedRecipients)) {
          updateData.recipient_ids = selectedRecipients;
        }
      }

      if (acknowledgementMode === 'restricted') {
        if (!arraysEqual(currentAcknowledgementDepartmentIds, acknowledgementDepartments)) {
          updateData.acknowledgement_department_ids = acknowledgementDepartments;
        }
        if (!arraysEqual(currentAcknowledgementRecipientIds, acknowledgementRecipients)) {
          updateData.acknowledgement_recipient_ids = acknowledgementRecipients;
        }
      }

      if (Object.keys(updateData).length === 0) {
        toast.info('Нет изменений для сохранения');
        onClose();
        return;
      }

      await apiClient.updateDocument(document.id, updateData);

      toast.success('Документ обновлён');
      onUpdate?.();
      onClose();
    } catch (err) {
      console.error('Error updating document:', err);
      const errorMsg = err instanceof Error ? err.message : 'Не удалось обновить документ';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Редактирование документа"
      size="xl"
    >
      <div className="space-y-5">
        {error && (
          <div className="app-feedback-danger flex items-start gap-2 rounded-lg p-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        )}

        <section className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
            <FileText className="h-4 w-4" />
            Основное
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(240px,320px)]">
            <div className="space-y-4">
              <div>
                <label htmlFor="documentEditTitle" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
                  Название
                </label>
                <input
                  id="documentEditTitle"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  disabled={isSaving}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  placeholder="Название документа"
                />
              </div>

              <div>
                <label htmlFor="documentEditDescription" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
                  Описание
                </label>
                <textarea
                  id="documentEditDescription"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  disabled={isSaving}
                  rows={4}
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                  placeholder="Описание документа"
                />
              </div>
            </div>

            <div className="app-surface-muted rounded-lg p-3 text-sm">
              <p className="font-medium text-[var(--foreground)]">ID: {document.id}</p>
              <div className="app-text-muted mt-2 space-y-1 text-xs">
                <p>Текущий файл: {document.file_name || 'не прикреплён'}</p>
                {document.file_size ? <p>Размер: {formatFileSize(document.file_size)}</p> : null}
                {document.folder_path ? <p>Папка: {document.folder_path}</p> : null}
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
            <Upload className="h-4 w-4" />
            Файл документа
          </div>

          <div className="app-surface-muted rounded-lg p-3">
            <label
              htmlFor="documentEditFile"
              className="app-action-secondary inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium"
            >
              <Upload className="h-4 w-4" />
              Выбрать новый файл
            </label>
            <input
              id="documentEditFile"
              type="file"
              onChange={(event) => setReplacementFile(event.target.files?.[0] || null)}
              disabled={isSaving}
              className="sr-only"
            />
            <p className="app-text-muted mt-2 text-xs">
              Если файл не выбрать, текущий файл останется без изменений.
            </p>

            {replacementFile && (
              <div className="app-selected app-accent-text mt-3 flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm">
                <span className="min-w-0 truncate">
                  Новый файл: {replacementFile.name} ({formatFileSize(replacementFile.size)})
                </span>
                <button
                  type="button"
                  onClick={() => setReplacementFile(null)}
                  disabled={isSaving}
                  className="app-action-secondary inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                  title="Убрать выбранный файл"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="documentEditExtractedText" className="mb-1.5 block text-sm font-medium text-[var(--foreground)]">
              Текст для поиска
            </label>
            <textarea
              id="documentEditExtractedText"
              value={extractedText}
              onChange={(event) => setExtractedText(event.target.value)}
              disabled={isSaving}
              rows={5}
              className="app-input w-full rounded-lg px-3 py-2 font-mono text-sm"
              placeholder="Распознанный или вручную добавленный текст документа"
            />
            <p className="app-text-muted mt-1 text-xs">Символов: {extractedText.length}</p>
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
            <TagIcon className="h-4 w-4" />
            Категоризация
          </div>

          <div>
            <label htmlFor="documentEditFolder" className="mb-1.5 flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
              <Folder className="h-4 w-4" />
              Папка
            </label>
            <select
              id="documentEditFolder"
              value={selectedFolder || ''}
              onChange={(event) => setSelectedFolder(event.target.value ? Number(event.target.value) : null)}
              disabled={loadingReferences || isSaving}
              className="app-select w-full rounded-lg px-3 py-2 text-sm"
            >
              <option value="">Без папки (корень)</option>
              {folderOptionRows.map(({ folder, level }) => (
                <option key={folder.id} value={folder.id}>
                  {`${'— '.repeat(level)}${folder.name}`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div id="document-edit-tags-label" className="mb-1.5 flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
              <TagIcon className="h-4 w-4" />
              Теги
            </div>
            <DocumentTagQuickCreate
              existingTags={documentTags}
              disabled={loadingReferences || isSaving}
              onCreated={handleCreatedTag}
              className="mb-2"
            />
            <div
              role="group"
              aria-labelledby="document-edit-tags-label"
              className="app-surface-muted flex min-h-12 flex-wrap items-center gap-2 rounded-lg p-2"
            >
              {loadingReferences ? (
                <span className="app-text-muted px-1 text-sm">Загрузка тегов...</span>
              ) : documentTags.length === 0 ? (
                <span className="app-text-muted px-1 text-sm">Нет доступных тегов</span>
              ) : (
                documentTags.map((tag) => (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => toggleTag(tag.id)}
                    disabled={isSaving}
                    className={`inline-flex max-w-full items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
                      selectedTags.includes(tag.id)
                        ? 'app-badge app-badge-accent'
                        : 'app-badge hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]'
                    }`}
                    aria-pressed={selectedTags.includes(tag.id)}
                  >
                    {tag.color && (
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ backgroundColor: tag.color }}
                      />
                    )}
                    <span className="truncate">{tag.name}</span>
                  </button>
                ))
              )}
            </div>
            <p className="app-text-muted mt-1 text-xs">Выбрано: {selectedTags.length}</p>
          </div>

          <div className="app-surface-muted flex items-start gap-3 rounded-lg p-3">
            <input
              type="checkbox"
              id="metadataIsRegulation"
              checked={isRegulation}
              onChange={(event) => setIsRegulation(event.target.checked)}
              disabled={isSaving}
              className="mt-0.5 h-4 w-4 rounded border-[var(--border-strong)] text-[var(--accent-primary)] disabled:opacity-50"
            />
            <div className="flex-1">
              <label htmlFor="metadataIsRegulation" className="block cursor-pointer text-sm font-medium text-[var(--foreground)]">
                <ScrollText className="mr-1 inline h-4 w-4" />
                Регламент
              </label>
              <p className="app-text-muted mt-0.5 text-xs">
                Документ будет отображаться в отдельном разделе регламентов.
              </p>
            </div>
          </div>
        </section>

        <section className="space-y-6">
          <DocumentAudienceSelector
            kind="access"
            mode={sentToAll ? 'all' : 'restricted'}
            onModeChange={(mode) => setSentToAll(mode === 'all')}
            employees={employees}
            departments={departments}
            selectedEmployeeIds={selectedRecipients}
            selectedDepartmentIds={selectedDepartments}
            onSelectedEmployeeIdsChange={setSelectedRecipients}
            onSelectedDepartmentIdsChange={setSelectedDepartments}
            loading={loadingReferences}
            disabled={isSaving}
          />

          <div className="app-divider border-t pt-5">
            <DocumentAudienceSelector
              kind="acknowledgement"
              mode={acknowledgementMode}
              onModeChange={setAcknowledgementMode}
              employees={acknowledgementEmployees}
              departments={acknowledgementDepartmentOptions}
              selectedEmployeeIds={acknowledgementRecipients}
              selectedDepartmentIds={acknowledgementDepartments}
              onSelectedEmployeeIdsChange={setAcknowledgementRecipients}
              onSelectedDepartmentIdsChange={setAcknowledgementDepartments}
              loading={loadingReferences}
              disabled={isSaving}
            />
          </div>
        </section>

        <div className="app-divider sticky bottom-0 z-10 -mx-4 flex items-center justify-end gap-3 border-t bg-[var(--surface-elevated)] px-4 pt-4 sm:-mx-6 sm:px-6">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="app-action-primary flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Сохранение...
              </>
            ) : (
              'Сохранить изменения'
            )}
          </button>
        </div>
      </div>
    </Modal>
  );
}
