"use client";

import { ChevronRight, Pencil, Pin, Plus, Trash2 } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { FeedPostCard } from "@/components/feed/FeedPostCard";
import { Modal } from "@/components/ui";
import { PostCommentsModal } from "@/components/feed/PostCommentsModal";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Comment, Post } from "@/types/api";
import { useUser } from "@/contexts/UserContext";

type LikeUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  avatar?: string | null;
};

export default function Home() {
  return (
    <Suspense fallback={<HomePageFallback />}>
      <HomePageContent />
    </Suspense>
  );
}

function HomePageFallback() {
  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-6 text-center">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]"></div>
        <p className="app-text-muted mt-3 text-sm">Загрузка ленты...</p>
      </section>
    </AppShell>
  );
}

function HomePageContent() {
  const { user } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [likeBusyId, setLikeBusyId] = useState<number | null>(null);

  const [commentsOpen, setCommentsOpen] = useState(false);
  const [activePost, setActivePost] = useState<Post | null>(null);
  const [createPostOpen, setCreatePostOpen] = useState(false);
  const [createType, setCreateType] = useState<"company" | "department">("company");
  const [createDepartmentId, setCreateDepartmentId] = useState<string>("");
  const [createTitle, setCreateTitle] = useState("");
  const [createBody, setCreateBody] = useState("");
  const [createImage, setCreateImage] = useState<File | null>(null);
  const [createAttachment, setCreateAttachment] = useState<File | null>(null);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [editingPostId, setEditingPostId] = useState<number | null>(null);
  const [postActionId, setPostActionId] = useState<number | null>(null);
  const [likesPopoverPostId, setLikesPopoverPostId] = useState<number | null>(null);
  const [likesLoadingPostId, setLikesLoadingPostId] = useState<number | null>(null);
  const [likesUsersMap, setLikesUsersMap] = useState<Record<number, LikeUser[]>>({});
  const [likesUsersEndpointUnavailable, setLikesUsersEndpointUnavailable] = useState(false);
  const [imageCacheBuster, setImageCacheBuster] = useState<Record<number, number>>({});
  const [postMenuOpenId, setPostMenuOpenId] = useState<number | null>(null);
  const postMenuRef = useRef<HTMLDivElement | null>(null);

  const formatUserName = (u: LikeUser) => {
    const composed = `${u.last_name || ""} ${u.first_name || ""}`.trim();
    return composed || u.full_name || "Пользователь";
  };

  const formatInitials = (firstName?: string, lastName?: string) => {
    return `${(lastName || "").trim().charAt(0)}${(firstName || "").trim().charAt(0)}` || "П";
  };



  const withImageCacheBuster = (url: string, postId: number) => {
    if (!url) return "";
    const marker = imageCacheBuster[postId] || 0;
    if (!marker) return url;
    return `${url}${url.includes("?") ? "&" : "?"}v=${marker}`;
  };

  const auth = user?.auth;
  const authPerms = auth?.permissions || [];
  const authByApp = auth?.permissions_by_app || {};
  const linkedPostId = Number(searchParams.get("post") || "");

  const clearPostParam = () => {
    if (!searchParams.get("post")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("post");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  };

  const closeCommentsModal = () => {
    setCommentsOpen(false);
    setActivePost(null);
    clearPostParam();
  };

  const hasPermission = (perm: string) => {
    if (!perm) return false;
    if (authPerms.includes(perm)) return true;

    if (perm.includes(".")) {
      const [app, code] = perm.split(".", 2);
      return Boolean(authByApp?.[app]?.includes(code));
    }

    return Object.values(authByApp).some((codes) => codes.includes(perm));
  };

  const canDeleteAnyComments = Boolean(auth?.is_staff || auth?.is_superuser);
  const canCreateCompanyPost = Boolean(
    auth?.is_staff ||
    auth?.is_superuser ||
    hasPermission("feed.add_post") ||
    hasPermission("add_post") ||
    hasPermission("feed.publish_company_post") ||
    hasPermission("publish_company_post")
  );
  const canCreateDepartmentPost = Boolean(
    auth?.is_staff ||
    auth?.is_superuser ||
    hasPermission("feed.publish_department_post") ||
    hasPermission("publish_department_post") ||
    hasPermission("feed.create_post") ||
    hasPermission("create_post") ||
    hasPermission("employees.manage_feed")
  );
  const canCreatePost = canCreateCompanyPost || canCreateDepartmentPost || ((user?.departments?.length || 0) > 0);
  const userDepartments = useMemo(() => user?.departments || [], [user?.departments]);
  const canManageAnyPost = Boolean(
    auth?.is_staff ||
    auth?.is_superuser ||
    hasPermission("feed.change_post") ||
    hasPermission("change_post") ||
    hasPermission("feed.delete_post") ||
    hasPermission("delete_post") ||
    hasPermission("employees.manage_feed")
  );
  const canPinPost = Boolean(
    auth?.is_staff ||
    auth?.is_superuser ||
    hasPermission("feed.pin_post") ||
    hasPermission("pin_post")
  );

  const sortPostsPinnedFirst = useCallback((items: Post[]) => [...items].sort((left, right) => {
    const leftPinned = left.pinned ? 1 : 0;
    const rightPinned = right.pinned ? 1 : 0;
    if (leftPinned !== rightPinned) return rightPinned - leftPinned;
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  }), []);

  const canEditPost = (post: Post) => {
    if (canManageAnyPost) return true;
    return Boolean(post.author?.id && user?.id && post.author.id === user.id);
  };

  const canDeletePost = (post: Post) => {
    if (canManageAnyPost) return true;
    return Boolean(post.author?.id && user?.id && post.author.id === user.id);
  };

  const canEditComment = (comment: Comment) => {
    return Boolean(comment.author?.id && user?.id && comment.author.id === user.id);
  };

  const canDeleteComment = (comment: Comment) => {
    if (canEditComment(comment)) return true;
    return canDeleteAnyComments;
  };

  const refreshPosts = useCallback(async () => {
    const response = await apiClient.getPosts();
    setPosts(sortPostsPinnedFirst(response.results));
  }, [sortPostsPinnedFirst]);

  useEffect(() => {
    async function loadPosts() {
      try {
        await refreshPosts();
      } catch (err: unknown) {
        console.error('Ошибка загрузки ленты:', err);
        setError('Не удалось загрузить ленту');
      } finally {
        setLoading(false);
      }
    }
    loadPosts();
  }, [refreshPosts]);

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
  }, [postMenuOpenId]);

  useEffect(() => {
    if (createType !== "department") return;
    if (createDepartmentId) return;
    if (!userDepartments.length) return;
    setCreateDepartmentId(String(userDepartments[0].id));
  }, [createType, createDepartmentId, userDepartments]);

  const handleLikeToggle = async (post: Post) => {
    if (likeBusyId === post.id) return;

    const currentlyLiked = Boolean(post.is_liked);
    const optimisticLikes = Math.max(0, (post.likes_count || 0) + (currentlyLiked ? -1 : 1));

    setLikeBusyId(post.id);
    setPosts((prev) =>
      prev.map((p) =>
        p.id === post.id
          ? { ...p, is_liked: !currentlyLiked, likes_count: optimisticLikes }
          : p
      )
    );

    try {
      const res = currentlyLiked
        ? await apiClient.unlikePost(post.id)
        : await apiClient.likePost(post.id);

      setPosts((prev) =>
        prev.map((p) =>
          p.id === post.id
            ? { ...p, is_liked: res.liked, likes_count: res.likes_count }
            : p
        )
      );
    } catch (err) {
      console.error("Ошибка лайка:", err);
      // rollback
      setPosts((prev) =>
        prev.map((p) =>
          p.id === post.id
            ? { ...p, is_liked: currentlyLiked, likes_count: post.likes_count }
            : p
        )
      );
    } finally {
      setLikeBusyId(null);
    }
  };

  const handlePinToggle = async (post: Post) => {
    if (postActionId === post.id) return;

    const currentlyPinned = Boolean(post.pinned);
    setPostActionId(post.id);
    setPostMenuOpenId(null);

    setPosts((prev) => sortPostsPinnedFirst(
      prev.map((item) => item.id === post.id ? { ...item, pinned: !currentlyPinned } : item)
    ));

    try {
      const response = currentlyPinned
        ? await apiClient.unpinPost(post.id, "global")
        : await apiClient.pinPost(post.id, "global");

      setPosts((prev) => sortPostsPinnedFirst(
        prev.map((item) =>
          item.id === post.id
            ? {
                ...item,
                pinned: Boolean(response?.pinned),
                pinned_global: Boolean(response?.pinned_global),
                pinned_department: Boolean(response?.pinned_department),
              }
            : item
        )
      ));
    } catch (err) {
      console.error("Ошибка закрепления публикации:", err);
      setPosts((prev) => sortPostsPinnedFirst(
        prev.map((item) => item.id === post.id ? { ...item, pinned: currentlyPinned } : item)
      ));
    } finally {
      setPostActionId(null);
    }
  };

  const openLikesPopover = async (postId: number, likesCount: number) => {
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
  };

  const openComments = (post: Post) => {
    setActivePost(post);
    setCommentsOpen(true);
  };

  const applyCommentCountDelta = (postId: number, delta: number) => {
    setPosts((prev) =>
      prev.map((item) =>
        item.id === postId
          ? {
              ...item,
              comments_count: Math.max(0, (item.comments_count || 0) + delta),
            }
          : item
      )
    );
    setActivePost((prev) =>
      prev && prev.id === postId
        ? {
            ...prev,
            comments_count: Math.max(0, (prev.comments_count || 0) + delta),
          }
        : prev
    );
  };

  useEffect(() => {
    if (!linkedPostId || posts.length === 0) return;
    if (commentsOpen && activePost?.id === linkedPostId) return;

    const targetPost = posts.find((post) => post.id === linkedPostId);
    if (!targetPost) return;

    openComments(targetPost);
  }, [activePost?.id, commentsOpen, linkedPostId, posts]);

  const openCreatePostModal = () => {
    setCreateError(null);
    setEditingPostId(null);
    setCreateTitle("");
    setCreateBody("");
    setCreateImage(null);
    setCreateAttachment(null);
    if (canCreateCompanyPost) {
      setCreateType("company");
    } else {
      setCreateType("department");
      setCreateDepartmentId(userDepartments[0] ? String(userDepartments[0].id) : "");
    }
    setCreatePostOpen(true);
  };

  const openEditPostModal = (post: Post) => {
    setCreateError(null);
    setEditingPostId(post.id);
    setCreateType(post.type === "department" ? "department" : "company");
    setCreateDepartmentId(post.department_id ? String(post.department_id) : "");
    setCreateTitle((post.title || "").trim());
    setCreateBody((post.body || post.content || "").trim());
    setCreateImage(null);
    setCreateAttachment(null);
    setCreatePostOpen(true);
  };

  const handleCreatePost = async () => {
    const title = createTitle.trim();
    const body = createBody.trim();
    if (!title || !body) {
      setCreateError("Заполните заголовок и содержание");
      return;
    }

    if (createType === "department" && !createDepartmentId) {
      setCreateError("Выберите отдел");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);
    try {
      if (editingPostId) {
        await apiClient.updatePost(editingPostId, {
          type: createType,
          title,
          body,
          department: createType === "department" ? Number(createDepartmentId) : undefined,
          image: createImage || undefined,
          attachment: createAttachment || undefined,
        });

        if (createImage) {
          setImageCacheBuster((prev) => ({
            ...prev,
            [editingPostId]: Date.now(),
          }));
        }
      } else {
        await apiClient.createPost({
          type: createType,
          title,
          body,
          department: createType === "department" ? Number(createDepartmentId) : undefined,
          image: createImage || undefined,
          attachment: createAttachment || undefined,
        });
      }

      // Важно: часть backend-инсталляций возвращает неполные данные в create/update,
      // поэтому всегда обновляем ленту с сервера и берем актуальные URL файлов.
      await refreshPosts();

      setCreatePostOpen(false);
      setEditingPostId(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Не удалось сохранить публикацию";
      setCreateError(message);
    } finally {
      setCreateSubmitting(false);
    }
  };

  const removePost = async (post: Post) => {
    setPostActionId(post.id);
    try {
      await apiClient.deletePost(post.id);
      setPosts((prev) => prev.filter((p) => p.id !== post.id));
    } catch (err) {
      console.error("Ошибка удаления публикации:", err);
    } finally {
      setPostActionId(null);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-strong)] border-t-[var(--accent-primary)]"></div>
            <p className="app-text-muted text-sm">Загрузка ленты...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="app-feedback-danger rounded-2xl p-6 text-center">
          <p className="text-sm">{error}</p>
        </div>
      </AppShell>
    );
  }
  return (
    <AppShell>
      <div className="space-y-4">
        {posts.length === 0 ? (
          <div className="app-surface-muted rounded-2xl p-8 text-center">
            <p className="app-text-muted text-sm">Пока нет постов в ленте</p>
          </div>
        ) : (
          posts.map((post) => {
            // Форматируем дату
            const postDate = new Date(post.created_at);
            const now = new Date();
            const diffMs = now.getTime() - postDate.getTime();
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const timeAgo = diffHours < 1
              ? 'только что'
              : diffHours < 24
                ? `${diffHours} ч. назад`
                : `${Math.floor(diffHours / 24)} дн. назад`;

            return (
              <FeedPostCard
                key={post.id}
                post={post}
                authorSubtitle={<span>{timeAgo}</span>}
                headerActions={(
                  (canEditPost(post) || canDeletePost(post)) ? (
                    <div
                      ref={postMenuOpenId === post.id ? postMenuRef : null}
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
                              {post.pinned ? "Открепить в общей ленте" : "Закрепить в общей ленте"}
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
                imageSrc={withImageCacheBuster(resolveMediaUrl(post.image), post.id)}
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
                        {(likesUsersMap[post.id] || []).map((u) => {
                          const name = formatUserName(u);
                          const initials = formatInitials(u.first_name, u.last_name);
                          return (
                            <div key={u.id} className="flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-[var(--surface-secondary)]">
                              <RequestAvatar
                                alt={name}
                                fallback={initials}
                                size="sm"
                                src={u.avatar}
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
                onOpenComments={openComments}
                pinMarkerTitle="Закреплено в общей ленте"
                pinnedStyle="inline"
              />
            );
          })
        )}
      </div>

      {canCreatePost && !createPostOpen ? (
        <div className="pointer-events-none fixed bottom-[calc(env(safe-area-inset-bottom)+5.5rem)] right-4 z-30 lg:bottom-6 lg:right-[max(2rem,calc((100vw-72rem)/2+21.5rem))]">
          <button
            type="button"
            onClick={openCreatePostModal}
            className="app-action-primary pointer-events-auto inline-flex h-12 w-12 items-center justify-center rounded-full p-0 leading-none shadow-[var(--shadow-card)] transition active:scale-[0.98]"
            title="Создать публикацию"
            aria-label="Создать публикацию"
          >
            <Plus size={22} />
          </button>
        </div>
      ) : null}

      <Modal
        isOpen={createPostOpen}
        onClose={() => setCreatePostOpen(false)}
        title={editingPostId ? "Редактировать публикацию" : "Создать публикацию"}
        size="lg"
        closeOnEsc={!createSubmitting}
        footer={
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreatePostOpen(false)}
              className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium"
            >
              Отмена
            </button>
            <button
              type="button"
              disabled={createSubmitting}
              onClick={handleCreatePost}
              className="app-action-primary rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              {createSubmitting ? (editingPostId ? "Сохраняем..." : "Публикуем...") : (editingPostId ? "Сохранить" : "Опубликовать")}
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {createError ? (
            <div className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{createError}</div>
          ) : null}

          {(canCreateCompanyPost || canCreateDepartmentPost) ? (
            <div>
              <label className="app-text-muted mb-1 block text-xs font-semibold uppercase tracking-wide">Тип публикации</label>
              <select
                value={createType}
                onChange={(e) => setCreateType(e.target.value as "company" | "department")}
                className="app-select h-10 w-full rounded-lg px-3 text-sm"
              >
                {canCreateCompanyPost ? <option value="company">Новость компании</option> : null}
                {canCreateDepartmentPost ? <option value="department">Новость отдела</option> : null}
              </select>
            </div>
          ) : null}

          {createType === "department" ? (
            <div>
              <label className="app-text-muted mb-1 block text-xs font-semibold uppercase tracking-wide">Отдел</label>
              <select
                value={createDepartmentId}
                onChange={(e) => setCreateDepartmentId(e.target.value)}
                className="app-select h-10 w-full rounded-lg px-3 text-sm"
              >
                <option value="">Выберите отдел</option>
                {userDepartments.map((dept) => (
                  <option key={dept.id} value={String(dept.id)}>{dept.name}</option>
                ))}
              </select>
            </div>
          ) : null}

          <div>
            <label className="app-text-muted mb-1 block text-xs font-semibold uppercase tracking-wide">Заголовок</label>
            <input
              type="text"
              value={createTitle}
              onChange={(e) => setCreateTitle(e.target.value)}
              className="app-input h-10 w-full rounded-lg px-3 text-sm"
            />
          </div>

          <div>
            <label className="app-text-muted mb-1 block text-xs font-semibold uppercase tracking-wide">Содержание</label>
            <textarea
              value={createBody}
              onChange={(e) => setCreateBody(e.target.value)}
              className="app-input min-h-32 w-full rounded-lg px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="app-text-muted mb-1 block text-xs font-semibold uppercase tracking-wide">Изображение</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setCreateImage(e.target.files?.[0] || null)}
              className="block w-full text-sm text-[var(--foreground)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--accent-soft)] file:px-3 file:py-2 file:text-sm file:text-[var(--accent-primary-strong)] hover:file:bg-[color:color-mix(in_srgb,var(--accent-primary)_18%,var(--surface-primary))]"
            />
          </div>

          <div>
            <label className="app-text-muted mb-1 block text-xs font-semibold uppercase tracking-wide">Вложение</label>
            <input
              type="file"
              onChange={(e) => setCreateAttachment(e.target.files?.[0] || null)}
              className="block w-full text-sm text-[var(--foreground)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--surface-secondary)] file:px-3 file:py-2 file:text-sm file:text-[var(--foreground)] hover:file:bg-[var(--surface-tertiary)]"
            />
          </div>
        </div>
      </Modal>

      <PostCommentsModal
        canDeleteComment={canDeleteComment}
        canEditComment={canEditComment}
        currentUserId={user?.id}
        isOpen={commentsOpen}
        onClose={closeCommentsModal}
        onCommentCountChange={applyCommentCountDelta}
        post={activePost}
      />
    </AppShell>
  );
}
