"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronRight,
  ImageIcon,
  Paperclip,
  Pencil,
  Pin,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { extractDepartmentApiErrorMessage } from "@/components/departments/api-error";
import { FeedPostCard } from "@/components/feed/FeedPostCard";
import { PostCommentsModal } from "@/components/feed/PostCommentsModal";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { Modal } from "@/components/ui/Modal";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import type { PaginatedResponse, Post } from "@/types/api";

type DepartmentFeedSectionProps = {
  canCreatePosts: boolean;
  canManageFeed?: boolean;
  currentUserId?: number | null;
  departmentId: number;
  departmentName: string;
};

export function DepartmentFeedSection({
  canCreatePosts,
  canManageFeed = false,
  currentUserId,
  departmentId,
  departmentName,
}: DepartmentFeedSectionProps) {
  const { user } = useUser();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createBody, setCreateBody] = useState("");
  const [createImage, setCreateImage] = useState<File | null>(null);
  const [createAttachment, setCreateAttachment] = useState<File | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [activePost, setActivePost] = useState<Post | null>(null);
  const [editingPostId, setEditingPostId] = useState<number | null>(null);
  const [postActionId, setPostActionId] = useState<number | null>(null);
  const [postMenuOpenId, setPostMenuOpenId] = useState<number | null>(null);
  const [likeBusyId, setLikeBusyId] = useState<number | null>(null);
  const [likesPopoverPostId, setLikesPopoverPostId] = useState<number | null>(null);
  const [likesLoadingPostId, setLikesLoadingPostId] = useState<number | null>(null);
  const [likesUsersMap, setLikesUsersMap] = useState<Record<number, Array<{ id: number; first_name?: string; last_name?: string; full_name?: string; avatar?: string | null }>>>({});
  const [likesUsersEndpointUnavailable, setLikesUsersEndpointUnavailable] = useState(false);
  const postMenuRef = useRef<HTMLDivElement | null>(null);

  const auth = user?.auth;
  const authPerms = useMemo(() => auth?.permissions || [], [auth?.permissions]);
  const authByApp = useMemo(() => auth?.permissions_by_app || {}, [auth?.permissions_by_app]);

  const hasPermission = useCallback((perm: string) => {
    if (!perm) return false;
    if (authPerms.includes(perm)) return true;
    if (perm.includes(".")) {
      const [app, code] = perm.split(".", 2);
      return Boolean(authByApp?.[app]?.includes(code));
    }
    return Object.values(authByApp).some((codes) => codes.includes(perm));
  }, [authByApp, authPerms]);

  const canPinPost = Boolean(
    auth?.is_staff ||
    auth?.is_superuser ||
    hasPermission("feed.pin_post") ||
    hasPermission("pin_post")
  );

  const canEditPost = useCallback((post: Post) => {
    if (canManageFeed) return true;
    return Boolean(post.author?.id && currentUserId && post.author.id === currentUserId);
  }, [canManageFeed, currentUserId]);

  const canDeletePost = useCallback((post: Post) => {
    if (canManageFeed) return true;
    return Boolean(post.author?.id && currentUserId && post.author.id === currentUserId);
  }, [canManageFeed, currentUserId]);

  const sortPostsPinnedFirst = useCallback((items: Post[]) => {
    return [...items].sort((left, right) => {
      const leftPinned = left.pinned ? 1 : 0;
      const rightPinned = right.pinned ? 1 : 0;
      if (leftPinned !== rightPinned) return rightPinned - leftPinned;
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }, []);

  const loadPosts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getPosts({
        type: "department",
        department: departmentId,
        limit: 20,
        pinScope: "department",
      }) as PaginatedResponse<Post>;
      setPosts(sortPostsPinnedFirst(response.results || []));
    } catch (loadError) {
      console.error("Не удалось загрузить новости отдела:", loadError);
      setError("Не удалось загрузить новости отдела");
    } finally {
      setLoading(false);
    }
  }, [departmentId, sortPostsPinnedFirst]);

  useEffect(() => {
    void loadPosts();
  }, [loadPosts]);

  const resetCreateForm = useCallback(() => {
    setCreateTitle("");
    setCreateBody("");
    setCreateImage(null);
    setCreateAttachment(null);
    setCreateError(null);
  }, []);

  const openCreateModal = () => {
    resetCreateForm();
    setEditingPostId(null);
    setCreateOpen(true);
  };

  const closeCreateModal = () => {
    if (createSubmitting) return;
    resetCreateForm();
    setEditingPostId(null);
    setCreateOpen(false);
  };

  const openEditPostModal = useCallback((post: Post) => {
    setCreateError(null);
    setEditingPostId(post.id);
    setCreateTitle((post.title || "").trim());
    setCreateBody((post.body || post.content || "").trim());
    setCreateImage(null);
    setCreateAttachment(null);
    setCreateOpen(true);
  }, []);

  const openCommentsModal = useCallback((post: Post) => {
    setActivePost(post);
    setCommentsOpen(true);
  }, []);

  const closeCommentsModal = useCallback(() => {
    setCommentsOpen(false);
    setActivePost(null);
  }, []);

  const applyCommentCountDelta = useCallback(
    (postId: number, delta: number) => {
      setPosts((previous) =>
        previous.map((item) =>
          item.id === postId
            ? {
                ...item,
                comments_count: Math.max(0, (item.comments_count || 0) + delta),
              }
            : item,
        ),
      );
      setActivePost((previous) =>
        previous && previous.id === postId
          ? {
              ...previous,
              comments_count: Math.max(
                0,
                (previous.comments_count || 0) + delta,
              ),
            }
          : previous,
      );
    },
    [],
  );

  const submitCreatePost = useCallback(async () => {
    const title = createTitle.trim();
    const body = createBody.trim();

    if (!title) {
      setCreateError("Заполни заголовок публикации");
      return;
    }

    if (!body && !createImage && !createAttachment) {
      setCreateError("Добавь текст, изображение или вложение");
      return;
    }

    try {
      setCreateSubmitting(true);
      setCreateError(null);
      if (editingPostId) {
        await apiClient.updatePost(editingPostId, {
          type: "department",
          department: departmentId,
          title,
          body: body || undefined,
          image: createImage || undefined,
          attachment: createAttachment || undefined,
        });
      } else {
        await apiClient.createPost({
          type: "department",
          department: departmentId,
          title,
          body: body || undefined,
          image: createImage || undefined,
          attachment: createAttachment || undefined,
        });
      }
      await loadPosts();
      setCreateOpen(false);
      resetCreateForm();
      setEditingPostId(null);
      toast.success(editingPostId ? "Публикация обновлена" : "Публикация добавлена в ленту отдела");
    } catch (submitError) {
      console.error("Не удалось создать публикацию отдела:", submitError);
      setCreateError(
        extractDepartmentApiErrorMessage(
          submitError,
          "Не удалось создать публикацию отдела",
        ),
      );
    } finally {
      setCreateSubmitting(false);
    }
  }, [
    createAttachment,
    createBody,
    createImage,
    createTitle,
    departmentId,
    editingPostId,
    loadPosts,
    resetCreateForm,
  ]);

  const removePost = useCallback(async (post: Post) => {
    setPostActionId(post.id);
    try {
      await apiClient.deletePost(post.id);
      setPosts((previous) => previous.filter((item) => item.id !== post.id));
      setPostMenuOpenId(null);
      toast.success("Публикация удалена");
    } catch (deleteError) {
      console.error("Не удалось удалить публикацию:", deleteError);
      toast.error(
        extractDepartmentApiErrorMessage(
          deleteError,
          "Не удалось удалить публикацию",
        ),
      );
    } finally {
      setPostActionId(null);
    }
  }, []);

  const handlePinToggle = useCallback(async (post: Post) => {
    if (postActionId === post.id) return;
    const currentlyPinned = Boolean(post.pinned);
    setPostActionId(post.id);
    setPostMenuOpenId(null);
    setPosts((previous) =>
      sortPostsPinnedFirst(
        previous.map((item) =>
          item.id === post.id ? { ...item, pinned: !currentlyPinned } : item,
        ),
      ),
    );
    try {
      const response = currentlyPinned
        ? await apiClient.unpinPost(post.id, "department")
        : await apiClient.pinPost(post.id, "department");
      setPosts((previous) =>
        sortPostsPinnedFirst(
          previous.map((item) =>
            item.id === post.id
              ? {
                  ...item,
                  pinned: Boolean(response?.pinned),
                  pinned_global: Boolean(response?.pinned_global),
                  pinned_department: Boolean(response?.pinned_department),
                }
              : item,
          ),
        ),
      );
    } catch (pinError) {
      console.error("Не удалось изменить закрепление публикации:", pinError);
      setPosts((previous) =>
        sortPostsPinnedFirst(
          previous.map((item) =>
            item.id === post.id ? { ...item, pinned: currentlyPinned } : item,
          ),
        ),
      );
    } finally {
      setPostActionId(null);
    }
  }, [postActionId, sortPostsPinnedFirst]);

  const handleLikeToggle = useCallback(async (post: Post) => {
    if (likeBusyId === post.id) return;

    const currentlyLiked = Boolean(post.is_liked);
    const optimisticLikes = Math.max(0, (post.likes_count || 0) + (currentlyLiked ? -1 : 1));
    setLikeBusyId(post.id);
    setPosts((previous) =>
      previous.map((item) =>
        item.id === post.id
          ? { ...item, is_liked: !currentlyLiked, likes_count: optimisticLikes }
          : item,
      ),
    );

    try {
      const response = currentlyLiked
        ? await apiClient.unlikePost(post.id)
        : await apiClient.likePost(post.id);
      setPosts((previous) =>
        previous.map((item) =>
          item.id === post.id
            ? { ...item, is_liked: response.liked, likes_count: response.likes_count }
            : item,
        ),
      );
    } catch (likeError) {
      console.error("Не удалось переключить лайк:", likeError);
      setPosts((previous) =>
        previous.map((item) =>
          item.id === post.id
            ? { ...item, is_liked: currentlyLiked, likes_count: post.likes_count }
            : item,
        ),
      );
    } finally {
      setLikeBusyId(null);
    }
  }, [likeBusyId]);

  const formatUserName = useCallback((person: { first_name?: string; last_name?: string; full_name?: string }) => {
    const composed = `${person.last_name || ""} ${person.first_name || ""}`.trim();
    return composed || person.full_name || "Пользователь";
  }, []);

  const formatInitials = useCallback((firstName?: string, lastName?: string) => {
    return `${(lastName || "").trim().charAt(0)}${(firstName || "").trim().charAt(0)}` || "П";
  }, []);

  const openLikesPopover = useCallback(async (postId: number, likesCount: number) => {
    setLikesPopoverPostId(postId);
    if (!likesCount) {
      setLikesUsersMap((prev) => ({ ...prev, [postId]: [] }));
      return;
    }
    if (likesUsersEndpointUnavailable) return;
    if (likesUsersMap[postId]) return;
    setLikesLoadingPostId(postId);
    try {
      const response = await apiClient.getPostLikers(postId);
      setLikesUsersMap((prev) => ({ ...prev, [postId]: response.results || [] }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "";
      if (
        message.includes("404") ||
        message.includes("NetworkError") ||
        message.includes("Failed to fetch")
      ) {
        setLikesUsersEndpointUnavailable(true);
      }
      setLikesUsersMap((prev) => ({ ...prev, [postId]: [] }));
    } finally {
      setLikesLoadingPostId((prev) => (prev === postId ? null : prev));
    }
  }, [likesUsersEndpointUnavailable, likesUsersMap]);

  useEffect(() => {
    if (postMenuOpenId === null) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (postMenuRef.current && !postMenuRef.current.contains(event.target as Node)) {
        setPostMenuOpenId(null);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPostMenuOpenId(null);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [postMenuOpenId, postMenuRef]);

  const postsContent = useMemo(() => {
    if (loading) {
      return (
        <div className="py-8 text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted mt-3 text-sm">Загрузка новостей отдела...</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="app-feedback-danger rounded-xl p-4">
          <p className="text-sm">{error}</p>
          <button
            type="button"
            onClick={() => void loadPosts()}
            className="app-action-secondary mt-3 rounded-lg px-3 py-2 text-sm"
          >
            Повторить
          </button>
        </div>
      );
    }

    if (!posts.length) {
      return (
        <div className="app-surface rounded-xl px-4 py-8 text-center">
          <p className="text-sm font-medium text-[var(--foreground)]">
            В отделе пока нет публикаций
          </p>
          <p className="app-text-muted mt-2 text-sm">
            Здесь будут появляться новости, объявления и важные сообщения отдела.
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-3">
        {posts.map((post) => {
          return (
            <FeedPostCard
              key={post.id}
              post={post}
              authorSubtitle={
                <span>
                  {post.created_at_display ||
                    new Date(post.created_at).toLocaleString("ru-RU")}
                </span>
              }
              headerActions={(
                (canEditPost(post) || canDeletePost(post)) ? (
                  <div
                    ref={postMenuOpenId === post.id ? postMenuRef : undefined}
                    className="relative shrink-0"
                  >
                    <button
                      type="button"
                      onClick={() => setPostMenuOpenId((prev) => (prev === post.id ? null : post.id))}
                      className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                      title="Действия с публикацией"
                      aria-label="Действия с публикацией"
                      aria-expanded={postMenuOpenId === post.id}
                      aria-haspopup="menu"
                    >
                      <ChevronRight
                        size={15}
                        className={`transition-transform duration-200 ${postMenuOpenId === post.id ? "rotate-90" : ""}`}
                      />
                    </button>

                    {postMenuOpenId === post.id ? (
                      <div className="app-menu absolute right-0 top-full z-20 mt-2 w-48 rounded-xl py-1.5">
                        {canPinPost ? (
                          <button
                            type="button"
                            disabled={postActionId === post.id}
                            onClick={() => void handlePinToggle(post)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                          >
                            <Pin size={14} className={post.pinned ? "fill-current app-accent-text" : ""} />
                            {post.pinned ? "Открепить в ленте отдела" : "Закрепить в ленте отдела"}
                          </button>
                        ) : null}
                        {canEditPost(post) ? (
                          <button
                            type="button"
                            onClick={() => {
                              setPostMenuOpenId(null);
                              openEditPostModal(post);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                            <Pencil size={14} />
                            Редактировать
                          </button>
                        ) : null}
                        {canDeletePost(post) ? (
                          <button
                            type="button"
                            disabled={postActionId === post.id}
                            onClick={() => {
                              setPostMenuOpenId(null);
                              void removePost(post);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                          >
                            <Trash2 size={14} />
                            Удалить
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null
              )}
              isLikeActive={Boolean(post.is_liked)}
              likeDisabled={likeBusyId === post.id}
              likesPopover={likesPopoverPostId === post.id ? (
                <div className="app-menu absolute left-0 top-full z-20 mt-1 w-64 rounded-xl p-2">
                  <p className="app-text-muted px-1 pb-1 text-xs font-semibold">Лайкнули</p>
                  {likesLoadingPostId === post.id ? (
                    <p className="app-text-muted px-1 py-1 text-xs">Загрузка...</p>
                  ) : likesUsersEndpointUnavailable ? (
                    <p className="app-text-muted px-1 py-1 text-xs">Список лайкнувших временно недоступен</p>
                  ) : (likesUsersMap[post.id] || []).length === 0 ? (
                    <p className="app-text-muted px-1 py-1 text-xs">Пока нет лайков</p>
                  ) : (
                    <div className="max-h-56 space-y-1 overflow-y-auto">
                      {(likesUsersMap[post.id] || []).map((person) => {
                        const name = formatUserName(person);
                        return (
                          <div key={person.id} className="flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-[var(--surface-secondary)]">
                            <RequestAvatar
                              alt={name}
                              fallback={formatInitials(person.first_name, person.last_name)}
                              size="sm"
                              src={person.avatar}
                            />
                            <p className="truncate text-xs text-[var(--foreground)]">{name}</p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}
              likesWrapperProps={{
                onMouseEnter: () => openLikesPopover(post.id, post.likes_count || 0),
                onMouseLeave: () => setLikesPopoverPostId((prev) => (prev === post.id ? null : prev)),
              }}
              onLikeToggle={handleLikeToggle}
              onOpenComments={openCommentsModal}
              pinMarkerTitle="Закреплено в ленте отдела"
              pinnedStyle="inline"
            />
          );
        })}
      </div>
    );
  }, [
    canDeletePost,
    canEditPost,
    canPinPost,
    error,
    formatInitials,
    formatUserName,
    handleLikeToggle,
    handlePinToggle,
    likeBusyId,
    likesLoadingPostId,
    likesPopoverPostId,
    likesUsersEndpointUnavailable,
    likesUsersMap,
    loadPosts,
    loading,
    openCommentsModal,
    openEditPostModal,
    openLikesPopover,
    postActionId,
    postMenuOpenId,
    posts,
    removePost,
  ]);

  return (
    <>
      <section className="app-surface rounded-2xl p-5">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="app-card-caption">Лента отдела</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--foreground)]">
              Новости {departmentName}
            </h2>
            <p className="app-text-muted mt-2 text-sm">
              Публикации, объявления и важные сообщения отдела.
            </p>
          </div>
          {canCreatePosts ? (
            <button
              type="button"
              onClick={openCreateModal}
              className="app-action-primary inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm"
            >
              <Plus size={14} />
              Создать публикацию
            </button>
          ) : null}
        </div>

        <div className="app-surface-muted rounded-2xl p-4">
          {postsContent}
        </div>
      </section>

      <Modal
        isOpen={createOpen}
        onClose={closeCreateModal}
        title={editingPostId ? "Редактировать публикацию отдела" : "Новая публикация отдела"}
        size="lg"
        footer={
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={closeCreateModal}
              className="app-action-secondary rounded-lg px-4 py-2 text-sm"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void submitCreatePost()}
              disabled={createSubmitting}
              className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
            >
              {createSubmitting
                ? editingPostId
                  ? "Сохраняем..."
                  : "Публикуем..."
                : editingPostId
                  ? "Сохранить"
                  : "Опубликовать"}
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {createError ? (
            <div className="app-feedback-danger rounded-lg px-3 py-2 text-sm">
              {createError}
            </div>
          ) : null}

          <section className="app-surface-muted rounded-xl p-4">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Заголовок *
            </label>
            <input
              value={createTitle}
              onChange={(event) => {
                setCreateTitle(event.target.value);
                if (createError) setCreateError(null);
              }}
              className="app-input w-full rounded-lg px-3 py-2 text-sm"
              placeholder="Короткий заголовок публикации"
            />
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Текст
            </label>
            <textarea
              value={createBody}
              onChange={(event) => {
                setCreateBody(event.target.value);
                if (createError) setCreateError(null);
              }}
              rows={6}
              className="app-input w-full rounded-xl px-3 py-2 text-sm"
              placeholder="Текст новости, объявления или сообщения для отдела. Можно оставить пустым, если добавишь изображение или файл."
            />
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Изображение
            </label>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => {
                setCreateImage(event.target.files?.[0] || null);
                if (createError) setCreateError(null);
              }}
              className="block w-full text-sm text-[var(--foreground)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--accent-soft)] file:px-3 file:py-2 file:text-sm file:text-[var(--accent-primary-strong)] hover:file:bg-[color:color-mix(in_srgb,var(--accent-primary)_18%,var(--surface-primary))]"
            />
            {createImage ? (
              <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2 text-sm text-[var(--foreground)]">
                <ImageIcon size={14} />
                <span className="max-w-[18rem] truncate">{createImage.name}</span>
                <button
                  type="button"
                  onClick={() => setCreateImage(null)}
                  className="app-text-muted hover:text-[var(--foreground)]"
                  aria-label="Убрать изображение"
                >
                  <X size={14} />
                </button>
              </div>
            ) : null}
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Вложение
            </label>
            <input
              type="file"
              onChange={(event) => {
                setCreateAttachment(event.target.files?.[0] || null);
                if (createError) setCreateError(null);
              }}
              className="block w-full text-sm text-[var(--foreground)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--surface-secondary)] file:px-3 file:py-2 file:text-sm file:text-[var(--foreground)] hover:file:bg-[var(--surface-tertiary)]"
            />
            {createAttachment ? (
              <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2 text-sm text-[var(--foreground)]">
                <Paperclip size={14} />
                <span className="max-w-[18rem] truncate">
                  {createAttachment.name}
                </span>
                <button
                  type="button"
                  onClick={() => setCreateAttachment(null)}
                  className="app-text-muted hover:text-[var(--foreground)]"
                  aria-label="Убрать вложение"
                >
                  <X size={14} />
                </button>
              </div>
            ) : null}
          </section>
        </div>
      </Modal>

      <PostCommentsModal
        currentUserId={currentUserId}
        isOpen={commentsOpen}
        onClose={closeCommentsModal}
        onCommentCountChange={applyCommentCountDelta}
        post={activePost}
      />
    </>
  );
}
