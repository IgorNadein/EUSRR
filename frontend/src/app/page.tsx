"use client";

import { Heart, ImageIcon, MessageSquare, Paperclip, Pencil, Plus, Send, Trash2, X } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import { Suspense, useEffect, useRef, useState } from "react";
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
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [newComment, setNewComment] = useState("");
  const [commentSending, setCommentSending] = useState(false);
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editingCommentText, setEditingCommentText] = useState("");
  const [commentImage, setCommentImage] = useState<File | null>(null);
  const [commentAttachment, setCommentAttachment] = useState<File | null>(null);
  const commentImageRef = useRef<HTMLInputElement | null>(null);
  const commentAttachmentRef = useRef<HTMLInputElement | null>(null);
  const [commentActionId, setCommentActionId] = useState<number | null>(null);
  const commentsBottomRef = useRef<HTMLDivElement | null>(null);
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
  const userDepartments = user?.departments || [];
  const canManageAnyPost = Boolean(
    auth?.is_staff ||
    auth?.is_superuser ||
    hasPermission("feed.change_post") ||
    hasPermission("change_post") ||
    hasPermission("feed.delete_post") ||
    hasPermission("delete_post") ||
    hasPermission("employees.manage_feed")
  );

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

  const scrollCommentsToBottom = (smooth = true) => {
    requestAnimationFrame(() => {
      commentsBottomRef.current?.scrollIntoView({
        behavior: smooth ? "smooth" : "auto",
        block: "end",
      });
    });
  };

  const refreshPosts = async () => {
    const response = await apiClient.getPosts();
    setPosts(response.results);
  };

  useEffect(() => {
    async function loadPosts() {
      try {
        await refreshPosts();
      } catch (err: any) {
        console.error('Ошибка загрузки ленты:', err);
        setError('Не удалось загрузить ленту');
      } finally {
        setLoading(false);
      }
    }
    loadPosts();
  }, []);

  useEffect(() => {
    if (!commentsOpen && !createPostOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeCommentsModal();
      }
    };

    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [commentsOpen, createPostOpen]);

  useEffect(() => {
    if (createType !== "department") return;
    if (createDepartmentId) return;
    if (!userDepartments.length) return;
    setCreateDepartmentId(String(userDepartments[0].id));
  }, [createType, createDepartmentId, userDepartments]);

  useEffect(() => {
    if (!commentsOpen || commentsLoading) return;
    scrollCommentsToBottom(false);
  }, [commentsOpen, commentsLoading, comments.length]);

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

  const loadComments = async (postId: number) => {
    setCommentsLoading(true);
    setCommentsError(null);
    try {
      const response = await apiClient.getComments({ post: postId });
      const items = Array.isArray(response)
        ? response
        : Array.isArray(response?.results)
          ? response.results
          : [];
      setComments(items);
    } catch (err) {
      console.error("Ошибка загрузки комментариев:", err);
      setCommentsError("Не удалось загрузить комментарии");
      setComments([]);
    } finally {
      setCommentsLoading(false);
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
    } catch (err: any) {
      const message = String(err?.message || "");
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

  const openComments = async (post: Post) => {
    setActivePost(post);
    setCommentsOpen(true);
    setNewComment("");
    setEditingCommentId(null);
    setEditingCommentText("");
    await loadComments(post.id);
  };

  useEffect(() => {
    if (!linkedPostId || posts.length === 0) return;
    if (commentsOpen && activePost?.id === linkedPostId) return;

    const targetPost = posts.find((post) => post.id === linkedPostId);
    if (!targetPost) return;

    void openComments(targetPost);
  }, [activePost?.id, commentsOpen, linkedPostId, posts]);

  const handleCreateComment = async () => {
    if (!activePost) return;
    const text = newComment.trim();
    if (!text && !commentImage && !commentAttachment) return;

    setCommentSending(true);
    try {
      const created = await apiClient.createComment(
        activePost.id,
        text || " ",
        commentImage || undefined,
        commentAttachment || undefined
      );
      setComments((prev) => [...prev, created]);
      setNewComment("");
      setCommentImage(null);
      setCommentAttachment(null);
      setPosts((prev) =>
        prev.map((p) =>
          p.id === activePost.id
            ? { ...p, comments_count: (p.comments_count || 0) + 1 }
            : p
        )
      );
      setActivePost((prev) =>
        prev ? { ...prev, comments_count: (prev.comments_count || 0) + 1 } : prev
      );
      scrollCommentsToBottom();
    } catch (err) {
      console.error("Ошибка отправки комментария:", err);
    } finally {
      setCommentSending(false);
    }
  };

  const startEditComment = (comment: Comment) => {
    setEditingCommentId(comment.id);
    setEditingCommentText((comment.text || comment.content || "").trim());
  };

  const cancelEditComment = () => {
    setEditingCommentId(null);
    setEditingCommentText("");
  };

  const saveEditComment = async (commentId: number) => {
    const text = editingCommentText.trim();
    if (!text) return;

    setCommentActionId(commentId);
    try {
      const updated = await apiClient.updateComment(commentId, text);
      setComments((prev) => prev.map((c) => (c.id === commentId ? { ...c, ...updated } : c)));
      cancelEditComment();
    } catch (err) {
      console.error("Ошибка редактирования комментария:", err);
    } finally {
      setCommentActionId(null);
    }
  };

  const removeComment = async (comment: Comment) => {
    if (!activePost) return;

    setCommentActionId(comment.id);
    try {
      await apiClient.deleteComment(comment.id);
      setComments((prev) => prev.filter((c) => c.id !== comment.id));

      setPosts((prev) =>
        prev.map((p) =>
          p.id === activePost.id
            ? { ...p, comments_count: Math.max(0, (p.comments_count || 0) - 1) }
            : p
        )
      );
      setActivePost((prev) =>
        prev
          ? { ...prev, comments_count: Math.max(0, (prev.comments_count || 0) - 1) }
          : prev
      );

      if (editingCommentId === comment.id) {
        cancelEditComment();
      }
    } catch (err) {
      console.error("Ошибка удаления комментария:", err);
    } finally {
      setCommentActionId(null);
    }
  };

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
    } catch (err: any) {
      const message = String(err?.message || "Не удалось сохранить публикацию");
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
            const authorName = post.author
              ? `${post.author.last_name} ${post.author.first_name}`.trim()
              : 'Аноним';
            const authorInitials = post.author
              ? `${post.author.last_name?.[0] || ''}${post.author.first_name?.[0] || ''}`
              : 'А';

            const postText = (post.body || post.content || "").trim();

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
              <article id={`post-${post.id}`} key={post.id} className="app-surface rounded-2xl p-5">
                <header className="mb-3 flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="relative h-10 w-10">
                      <div className="app-avatar-fallback flex h-10 w-10 items-center justify-center overflow-hidden rounded-full text-sm font-semibold">
                        {post.author?.avatar ? (
                          <img src={resolveMediaUrl(post.author.avatar)} alt={authorName} className="h-full w-full object-cover" />
                        ) : (
                          authorInitials
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--foreground)]">{authorName}</p>
                      <p className="app-text-muted text-xs">{timeAgo}</p>
                    </div>
                  </div>

                  {(canEditPost(post) || canDeletePost(post)) ? (
                    <div className="flex items-center gap-1">
                      {canEditPost(post) ? (
                        <button
                          type="button"
                          onClick={() => openEditPostModal(post)}
                          className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                          title="Редактировать публикацию"
                        >
                          <Pencil size={15} />
                        </button>
                      ) : null}

                      {canDeletePost(post) ? (
                        <button
                          type="button"
                          disabled={postActionId === post.id}
                          onClick={() => removePost(post)}
                          className="app-action-danger flex h-8 w-8 items-center justify-center rounded-md disabled:opacity-50"
                          title="Удалить публикацию"
                        >
                          <Trash2 size={15} />
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                </header>
                {post.title ? (
                  <h3 className="app-text-wrap mb-1 text-base font-semibold text-[var(--foreground)]">{post.title}</h3>
                ) : null}
                {postText ? (
                  <p className="app-text-wrap whitespace-pre-line text-sm leading-6 text-[var(--foreground)]">{postText}</p>
                ) : null}
                {post.image && (
                  <div className="mt-3 overflow-hidden rounded-lg">
                    <img src={withImageCacheBuster(resolveMediaUrl(post.image), post.id)} alt="" className="w-full" />
                  </div>
                )}
                {(post.attachment || post.attachment_url) && (
                  <div className="mt-3">
                    <a
                      href={resolveMediaUrl(post.attachment || post.attachment_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
                    >
                      📎 Вложение
                    </a>
                  </div>
                )}
                <div className="app-text-muted mt-4 flex items-center gap-4 text-sm">
                  <div
                    className="relative"
                    onMouseEnter={() => openLikesPopover(post.id, post.likes_count || 0)}
                    onMouseLeave={() => setLikesPopoverPostId((prev) => (prev === post.id ? null : prev))}
                  >
                    <button
                      type="button"
                      disabled={likeBusyId === post.id}
                      onClick={() => handleLikeToggle(post)}
                      className={`flex items-center gap-2 rounded-lg px-3 py-2 transition ${
                        post.is_liked
                          ? "app-action-ghost text-[var(--accent-primary)]"
                          : "app-action-ghost"
                      }`}
                    >
                      <Heart
                        size={16}
                        className={post.is_liked ? "fill-[var(--accent-primary)] text-[var(--accent-primary)]" : "app-text-muted"}
                      />
                      {post.likes_count || 0}
                    </button>

                    {likesPopoverPostId === post.id ? (
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
                                  <div className="app-avatar-fallback flex h-6 w-6 items-center justify-center overflow-hidden rounded-full text-[10px] font-semibold">
                                    {u.avatar ? (
                                      <img src={resolveMediaUrl(u.avatar)} alt={name} className="h-full w-full object-cover" />
                                    ) : (
                                      initials
                                    )}
                                  </div>
                                  <p className="truncate text-xs text-[var(--foreground)]">{name}</p>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => openComments(post)}
                    className="app-action-ghost flex items-center gap-2 rounded-lg px-3 py-2"
                  >
                    <MessageSquare size={16} className="app-text-muted" /> {post.comments_count || 0}
                  </button>
                </div>
              </article>
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

      <Modal
        isOpen={commentsOpen && !!activePost}
        onClose={closeCommentsModal}
        title="Комментарии"
        size="lg"
        noPadding
        footer={
          <div>
            {(commentImage || commentAttachment) && (
              <div className="mb-2 flex flex-wrap gap-2">
                {commentImage && (
                  <div className="app-badge app-badge-accent flex items-center gap-1.5 rounded-md px-2 py-1 text-xs">
                    <ImageIcon size={12} />
                    <span className="max-w-[120px] truncate">{commentImage.name}</span>
                    <button type="button" onClick={() => setCommentImage(null)} className="app-accent-text ml-0.5 hover:text-[var(--accent-primary)]"><X size={12} /></button>
                  </div>
                )}
                {commentAttachment && (
                  <div className="app-badge flex items-center gap-1.5 rounded-md px-2 py-1 text-xs">
                    <Paperclip size={12} />
                    <span className="max-w-[120px] truncate">{commentAttachment.name}</span>
                    <button type="button" onClick={() => setCommentAttachment(null)} className="app-text-muted ml-0.5 hover:text-[var(--foreground)]"><X size={12} /></button>
                  </div>
                )}
              </div>
            )}
            <div className="flex items-center gap-2">
              <input ref={commentImageRef} type="file" accept="image/*" className="hidden" onChange={(e) => { setCommentImage(e.target.files?.[0] || null); e.target.value = ""; }} />
              <input ref={commentAttachmentRef} type="file" className="hidden" onChange={(e) => { setCommentAttachment(e.target.files?.[0] || null); e.target.value = ""; }} />
              <button
                type="button"
                onClick={() => commentImageRef.current?.click()}
                className="app-action-ghost flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                title="Прикрепить изображение"
              >
                <ImageIcon size={18} />
              </button>
              <button
                type="button"
                onClick={() => commentAttachmentRef.current?.click()}
                className="app-action-ghost flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                title="Прикрепить файл"
              >
                <Paperclip size={18} />
              </button>
              <input
                type="text"
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleCreateComment();
                  }
                }}
                placeholder="Напишите комментарий..."
                className="app-input h-10 flex-1 rounded-lg px-3 text-sm"
              />
              <button
                type="button"
                disabled={commentSending || (!newComment.trim() && !commentImage && !commentAttachment)}
                onClick={handleCreateComment}
                className="app-action-primary flex h-10 w-10 items-center justify-center rounded-lg disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        }
      >
        {activePost && (
          <>
            <p className="app-text-muted px-4 pb-2 pt-1 text-[10px] sm:text-xs">Публикация #{activePost.id}</p>
            <div className="flex-1 overflow-y-auto px-4 py-3">
              {commentsLoading ? (
                <p className="app-text-muted text-sm">Загрузка комментариев...</p>
              ) : commentsError ? (
                <p className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{commentsError}</p>
              ) : comments.length === 0 ? (
                <p className="app-text-muted text-sm">Комментариев пока нет</p>
              ) : (
                <div className="space-y-3">
                  {comments.map((comment) => {
                    const commentText = (comment.text || comment.content || "").trim();
                    const authorName = comment.author
                      ? `${comment.author.last_name || ""} ${comment.author.first_name || ""}`.trim() || "Пользователь"
                      : "Пользователь";
                    const authorInitials = comment.author
                      ? `${comment.author.last_name?.[0] || ""}${comment.author.first_name?.[0] || ""}` || "П"
                      : "П";

                    return (
                      <div key={comment.id} className="app-surface-muted rounded-xl px-3 py-2.5">
                        <div className="flex items-start gap-2.5">
                          <div className="app-avatar-fallback flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full text-[11px] font-semibold">
                            {comment.author?.avatar ? (
                              <img src={resolveMediaUrl(comment.author.avatar)} alt={authorName} className="h-full w-full object-cover" />
                            ) : (
                              authorInitials
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-xs font-semibold text-[var(--foreground)]">{authorName}</p>
                              <div className="flex items-center gap-1">
                                {canEditComment(comment) ? (
                                  <button
                                    type="button"
                                    onClick={() => startEditComment(comment)}
                                    className="app-action-ghost flex h-6 w-6 items-center justify-center rounded-md"
                                    title="Редактировать"
                                  >
                                    <Pencil size={13} />
                                  </button>
                                ) : null}

                                {canDeleteComment(comment) ? (
                                  <button
                                    type="button"
                                    disabled={commentActionId === comment.id}
                                    onClick={() => removeComment(comment)}
                                    className="app-action-danger flex h-6 w-6 items-center justify-center rounded-md disabled:opacity-50"
                                    title="Удалить"
                                  >
                                    <Trash2 size={13} />
                                  </button>
                                ) : null}
                              </div>
                            </div>

                            {editingCommentId === comment.id ? (
                              <div className="mt-1 space-y-2">
                                <textarea
                                  value={editingCommentText}
                                  onChange={(e) => setEditingCommentText(e.target.value)}
                                  className="app-input min-h-20 w-full rounded-lg px-2.5 py-2 text-sm"
                                />
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    disabled={commentActionId === comment.id || !editingCommentText.trim()}
                                    onClick={() => saveEditComment(comment.id)}
                                    className="app-action-primary rounded-md px-2.5 py-1.5 text-xs font-medium disabled:opacity-50"
                                  >
                                    Сохранить
                                  </button>
                                  <button
                                    type="button"
                                    disabled={commentActionId === comment.id}
                                    onClick={cancelEditComment}
                                    className="app-action-secondary rounded-md px-2.5 py-1.5 text-xs font-medium"
                                  >
                                    Отмена
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                {commentText && <p className="app-text-wrap mt-1 text-sm leading-6 text-[var(--foreground)]">{commentText}</p>}
                                {comment.image && (
                                  <div className="mt-2 overflow-hidden rounded-lg">
                                    <img src={resolveMediaUrl(comment.image)} alt="" className="max-h-60 rounded-lg" />
                                  </div>
                                )}
                                {comment.attachment && (
                                  <div className="mt-2">
                                    <a
                                      href={resolveMediaUrl(comment.attachment)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="app-action-secondary inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs"
                                    >
                                      📎 Вложение
                                    </a>
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={commentsBottomRef} />
                </div>
              )}
            </div>
          </>
        )}
      </Modal>
    </AppShell>
  );
}
