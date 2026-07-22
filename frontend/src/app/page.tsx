"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { ChevronRight, Link2, Newspaper, Pencil, Pin, Plus, ScrollText, Trash2 } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { FeedPostCard } from "@/components/feed/FeedPostCard";
import { FeedRegulationCard } from "@/components/feed/FeedRegulationCard";
import { DocumentAcknowledgementsReport } from "@/components/documents/DocumentAcknowledgementsReport";
import { DocumentDetailModal } from "@/components/documents/DocumentDetailModal";
import { DocumentMetadataEditor } from "@/components/documents/DocumentMetadataEditor";
import { DocumentTaskLinks } from "@/components/documents/DocumentTaskLinks";
import { Modal } from "@/components/ui";
import { PostCommentsModal } from "@/components/feed/PostCommentsModal";
import { RequestAvatar } from "@/components/requests/RequestAvatar";
import { RelatedTaskLinks } from "@/components/tasks/RelatedTaskLinks";
import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import { useNotifications } from "@/contexts/NotificationsContext";
import { apiClient } from "@/lib/api";
import { getDocumentFileExtension } from "@/lib/document-preview";
import { NAV_NOTIFICATION_CATEGORIES } from "@/lib/navigation-notifications";
import {
  getRegulationAcknowledgementDepartments,
  isCompanyAcknowledgementRegulation,
  regulationMatchesAcknowledgementSource,
} from "@/lib/feed-regulation-filters";
import { loadAllPages, userProfileLink } from "@/lib/shared";
import { resolveMediaUrl } from "@/lib/url";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Comment, Document, Post } from "@/types/api";
import { useUser } from "@/contexts/UserContext";
import { toast } from "sonner";

const EnhancedPDFViewer = dynamic(
  () => import("@/components/documents/viewer").then((mod) => ({ default: mod.EnhancedPDFViewer })),
  { ssr: false },
);

const DocumentPreview = dynamic(
  () => import("@/components/documents/DocumentPreview").then((mod) => ({ default: mod.DocumentPreview })),
  { ssr: false },
);

const RegulationCreateForm = dynamic(
  () => import("@/components/documents/DocumentUploadForm").then((mod) => ({ default: mod.RegulationCreateForm })),
  { ssr: false },
);

type LikeUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  avatar?: string | null;
};

type PostSourceFilter = "all" | "company" | `department:${number}`;
type FeedFilterKey = PostSourceFilter | "regulations";

type FeedEntry =
  | { kind: "post"; post: Post; timestamp: string }
  | { kind: "regulation"; document: Document; timestamp: string };

function postMatchesSource(post: Post, source: PostSourceFilter) {
  if (source === "all") return true;
  if (source === "company") return post.type !== "department";
  return post.department_id === Number(source.split(":")[1]);
}

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
  const {
    notifications,
    unreadCategoryCounts,
    unreadRegulationDepartmentCounts,
    unreadCompanyRegulationCount,
  } = useNotifications();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [posts, setPosts] = useState<Post[]>([]);
  const [regulations, setRegulations] = useState<Document[]>([]);
  const [selectedRegulation, setSelectedRegulation] = useState<Document | null>(null);
  const [selectedRegulationInitialTab, setSelectedRegulationInitialTab] = useState<"comments" | undefined>();
  const [metadataRegulation, setMetadataRegulation] = useState<Document | null>(null);
  const [taskLinkRegulation, setTaskLinkRegulation] = useState<Document | null>(null);
  const [regulationPreviewFile, setRegulationPreviewFile] = useState<{ url: string; name: string } | null>(null);
  const [regulationPdfFile, setRegulationPdfFile] = useState<{ url: string; name: string } | null>(null);
  const [acknowledgingRegulationId, setAcknowledgingRegulationId] = useState<number | null>(null);
  const [acknowledgementsReport, setAcknowledgementsReport] = useState<{
    documentId: number;
    documentTitle: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [likeBusyId, setLikeBusyId] = useState<number | null>(null);
  const [sourceFilter, setSourceFilter] = useState<PostSourceFilter>("all");
  const [regulationsOnly, setRegulationsOnly] = useState(false);

  const [commentsOpen, setCommentsOpen] = useState(false);
  const [activePost, setActivePost] = useState<Post | null>(null);
  const [createPostOpen, setCreatePostOpen] = useState(false);
  const [createRegulationOpen, setCreateRegulationOpen] = useState(false);
  const [createMenuOpen, setCreateMenuOpen] = useState(false);
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
  const [taskLinkPost, setTaskLinkPost] = useState<Post | null>(null);
  const postMenuRef = useRef<HTMLDivElement | null>(null);
  const createMenuRef = useRef<HTMLDivElement | null>(null);

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
    hasPermission("employees.manage_feed") ||
    ((user?.departments?.length || 0) > 0)
  );
  const canCreatePost = canCreateCompanyPost || canCreateDepartmentPost;
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

  const renderPostOrigin = useCallback((post: Post) => {
    if (post.type === "department") {
      return (
        <Link
          href={post.department_id ? `/departments/${post.department_id}` : "/departments"}
          className="app-badge inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium transition hover:border-[var(--border-strong)] hover:text-[var(--foreground)]"
        >
          {post.department_name ? `${post.department_name}` : "Отдел"}
        </Link>
      );
    }

    return (
      <span className="app-badge app-badge-accent inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium">
        Компания
      </span>
    );
  }, []);

  const getPostTaskSubtitle = (post: Post) => {
    if (post.type === "department") {
      return post.department_name ? `Отдел: ${post.department_name}` : "Отдел";
    }
    return "Компания";
  };

  const getPostDefaultTaskTitle = (post: Post) => {
    const title = (post.title || "").trim();
    return title ? `Задача по новости: ${title}` : `Задача по новости #${post.id}`;
  };

  const refreshPosts = useCallback(async () => {
    const response = await apiClient.getPosts();
    setPosts(sortPostsPinnedFirst(response.results));
  }, [sortPostsPinnedFirst]);

  const refreshRegulations = useCallback(async () => {
    const items = await loadAllPages<Document>((pagination) => (
      apiClient.getDocuments({
        ...pagination,
        scope: "mine",
        is_regulation: true,
      })
    ));
    setRegulations(items);
  }, []);

  const handleAcknowledgeRegulation = async (documentItem: Document) => {
    if (acknowledgingRegulationId !== null) return;

    setAcknowledgingRegulationId(documentItem.id);
    try {
      await apiClient.acknowledgeDocument(documentItem.id);
      setRegulations((current) => current.map((document) => (
        document.id === documentItem.id ? { ...document, is_acknowledged: true } : document
      )));
      if (selectedRegulation?.id === documentItem.id) {
        setSelectedRegulation({ ...selectedRegulation, is_acknowledged: true });
      }
      toast.success("Ознакомление подтверждено");
      void refreshRegulations();
    } catch (err) {
      console.error("Ошибка подтверждения ознакомления:", err);
      toast.error("Не удалось подтвердить ознакомление");
    } finally {
      setAcknowledgingRegulationId(null);
    }
  };

  const openRegulation = (document: Document) => {
    setSelectedRegulationInitialTab(undefined);
    setSelectedRegulation(document);
  };

  const openRegulationComments = (document: Document) => {
    setSelectedRegulationInitialTab("comments");
    setSelectedRegulation(document);
  };

  const openRegulationPreview = (document: Document) => {
    if (!document.file_url) return;

    const previewFile = {
      url: document.file_url,
      name: document.file_name || document.title,
    };
    if (getDocumentFileExtension(previewFile.name) === "pdf") {
      setRegulationPdfFile(previewFile);
    } else {
      setRegulationPreviewFile(previewFile);
    }
  };

  const deleteRegulation = async (document: Document) => {
    if (!window.confirm(`Удалить документ "${document.title}"?`)) return;

    try {
      await apiClient.deleteDocument(document.id);
      setRegulations((current) => current.filter((item) => item.id !== document.id));
      if (selectedRegulation?.id === document.id) {
        setSelectedRegulation(null);
        setSelectedRegulationInitialTab(undefined);
      }
      toast.success("Документ удалён");
    } catch (err) {
      console.error("Ошибка удаления документа:", err);
      toast.error("Не удалось удалить документ");
    }
  };

  const postSourceCounts = useMemo(() => {
    const departmentCounts = new Map<number, { id: number; name: string; total: number }>();
    let companyCount = 0;

    for (const post of posts) {
      if (post.type === "department" && post.department_id) {
        const current = departmentCounts.get(post.department_id);
        if (current) {
          current.total += 1;
        } else {
          departmentCounts.set(post.department_id, {
            id: post.department_id,
            name: post.department_name || "Отдел",
            total: 1,
          });
        }
      } else {
        companyCount += 1;
      }
    }

    for (const document of regulations) {
      if (isCompanyAcknowledgementRegulation(document)) companyCount += 1;
      for (const department of getRegulationAcknowledgementDepartments(document)) {
        const current = departmentCounts.get(department.id);
        if (current) {
          current.total += 1;
        } else {
          departmentCounts.set(department.id, {
            id: department.id,
            name: department.name,
            total: 1,
          });
        }
      }
    }

    const departments = Array.from(departmentCounts.values()).sort((left, right) => {
      if (right.total !== left.total) return right.total - left.total;
      return left.name.localeCompare(right.name, "ru");
    });

    return {
      all: posts.length + regulations.length,
      company: companyCount,
      regulations: regulations.length,
      departments,
    };
  }, [posts, regulations]);

  const postSourceUnreadCounts = useMemo(() => {
    const departmentUnread = new Map<number, number>();
    let companyUnread = 0;
    let regulationsUnread = (
      unreadCategoryCounts[NAV_NOTIFICATION_CATEGORIES.regulations] || 0
    );
    let companyRegulationsUnread = unreadCompanyRegulationCount;
    const departmentRegulationsUnread = new Map<number, number>(
      Object.entries(unreadRegulationDepartmentCounts).map(([id, unread]) => (
        [Number(id), unread]
      )),
    );
    const regulationsById = new Map(regulations.map((document) => [document.id, document]));

    for (const notification of notifications) {
      const rawData = notification.data;
      const data = rawData && typeof rawData === "object"
        ? rawData as Record<string, unknown>
        : null;

      // Обратная совместимость до применения миграции, которая переводит
      // старые уведомления регламентов из document_ready в regulation_ready.
      if ((notification.verb || "") === "document_ready") {
        const rawDocumentId = data?.document_id;
        const documentId = typeof rawDocumentId === "number"
          ? rawDocumentId
          : typeof rawDocumentId === "string"
            ? Number(rawDocumentId)
            : null;
        const regulation = documentId !== null ? regulationsById.get(documentId) : undefined;
        if (regulation) {
          regulationsUnread += 1;
          if (isCompanyAcknowledgementRegulation(regulation)) companyRegulationsUnread += 1;
          for (const department of getRegulationAcknowledgementDepartments(regulation)) {
            departmentRegulationsUnread.set(
              department.id,
              (departmentRegulationsUnread.get(department.id) || 0) + 1,
            );
          }
        }
        continue;
      }

      if ((notification.verb || "").startsWith("regulation_")) continue;

      if ((notification.verb || "") !== "feed_new_post") continue;

      const postType = typeof data?.post_type === "string" ? data.post_type : "";
      const departmentId =
        typeof data?.department_id === "number"
          ? data.department_id
          : typeof data?.department_id === "string" && data.department_id.trim()
            ? Number(data.department_id)
            : null;

      if (postType === "department" && Number.isFinite(departmentId) && departmentId !== null) {
        departmentUnread.set(departmentId, (departmentUnread.get(departmentId) || 0) + 1);
      } else {
        companyUnread += 1;
      }
    }

    const departmentIds = new Set([
      ...departmentUnread.keys(),
      ...departmentRegulationsUnread.keys(),
    ]);
    const departmentEntries = Array.from(departmentIds).map((id) => ({
      id,
      unread: (departmentUnread.get(id) || 0) + (departmentRegulationsUnread.get(id) || 0),
      regulationsUnread: departmentRegulationsUnread.get(id) || 0,
    }));

    return {
      all: companyUnread + regulationsUnread + Array.from(departmentUnread.values()).reduce((sum, unread) => sum + unread, 0),
      company: companyUnread + companyRegulationsUnread,
      regulations: regulationsUnread,
      companyRegulations: companyRegulationsUnread,
      departments: departmentEntries,
    };
  }, [
    notifications,
    regulations,
    unreadCategoryCounts,
    unreadCompanyRegulationCount,
    unreadRegulationDepartmentCounts,
  ]);

  const postSourceOptions = useMemo(() => {
    const unreadByDepartment = new Map(
      postSourceUnreadCounts.departments.map((entry) => [entry.id, entry.unread]),
    );

    const departmentRegulationsUnread = new Map(
      postSourceUnreadCounts.departments.map((entry) => [entry.id, entry.regulationsUnread]),
    );
    const scopedRegulations = regulations.filter((document) => (
      regulationMatchesAcknowledgementSource(document, sourceFilter)
    ));
    const scopedRegulationsUnread = sourceFilter === "all"
      ? postSourceUnreadCounts.regulations
      : sourceFilter === "company"
        ? postSourceUnreadCounts.companyRegulations
        : departmentRegulationsUnread.get(Number(sourceFilter.split(":")[1])) || 0;

    const options: Array<{ key: FeedFilterKey; label: string; total: number; unread: number }> = [
      { key: "all", label: "Все", total: postSourceCounts.all, unread: postSourceUnreadCounts.all },
      { key: "regulations", label: "Регламенты", total: scopedRegulations.length, unread: scopedRegulationsUnread },
      { key: "company", label: "Компания", total: postSourceCounts.company, unread: postSourceUnreadCounts.company },
    ];

    for (const department of postSourceCounts.departments) {
      options.push({
        key: `department:${department.id}`,
        label: department.name,
        total: department.total,
        unread: unreadByDepartment.get(department.id) || 0,
      });
    }

    return options.filter(({ key, total }) => key === "all" || key === "regulations" || total > 0);
  }, [postSourceCounts, postSourceUnreadCounts, regulations, sourceFilter]);

  const filteredEntries = useMemo<FeedEntry[]>(() => {
    const postEntries: FeedEntry[] = posts.map((post) => ({
      kind: "post",
      post,
      timestamp: post.created_at,
    }));
    const regulationEntries: FeedEntry[] = regulations.map((document) => ({
      kind: "regulation",
      document,
      timestamp: document.uploaded_at || document.created_at,
    }));

    return [...postEntries, ...regulationEntries].filter((entry) => {
      if (regulationsOnly && entry.kind !== "regulation") return false;
      return entry.kind === "post"
        ? postMatchesSource(entry.post, sourceFilter)
        : regulationMatchesAcknowledgementSource(entry.document, sourceFilter);
    }).sort((left, right) => {
      const leftPinned = left.kind === "post" && left.post.pinned ? 1 : 0;
      const rightPinned = right.kind === "post" && right.post.pinned ? 1 : 0;
      if (leftPinned !== rightPinned) return rightPinned - leftPinned;
      return new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime();
    });
  }, [posts, regulations, regulationsOnly, sourceFilter]);

  useEffect(() => {
    async function loadPosts() {
      try {
        await Promise.all([refreshPosts(), refreshRegulations()]);
      } catch (err: unknown) {
        console.error('Ошибка загрузки ленты:', err);
        setError('Не удалось загрузить ленту');
      } finally {
        setLoading(false);
      }
    }
    loadPosts();
  }, [refreshPosts, refreshRegulations]);

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
    if (!createMenuOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (createMenuRef.current && !createMenuRef.current.contains(event.target as Node)) {
        setCreateMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setCreateMenuOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [createMenuOpen]);

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

  const openTaskLinkModal = (post: Post) => {
    setPostMenuOpenId(null);
    setTaskLinkPost(post);
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
    setCreateMenuOpen(false);
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

  const openCreateRegulationModal = () => {
    setCreateMenuOpen(false);
    setCreateRegulationOpen(true);
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
        <div className="flex flex-wrap gap-2">
          {postSourceOptions.map(({ key, label, total, unread }) => {
            const active = key === "regulations" ? regulationsOnly : sourceFilter === key;

            return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    if (key === "regulations") {
                      setRegulationsOnly((current) => !current);
                    } else {
                      setSourceFilter(key);
                    }
                  }}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                    active ? "app-pill-active" : "app-pill"
                  }`}
                >
                  <span>{label}</span>
                  <span
                    className={`app-badge inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold ${
                      active ? "app-pill-count-active" : "app-pill-count"
                    }`}
                  >
                    <span>{total}</span>
                    {unread > 0 ? (
                      <>
                        <span className="app-text-muted">•</span>
                        <span className="app-accent-text">{unread}</span>
                      </>
                    ) : null}
                  </span>
                </button>
              );
            })}
        </div>

        {posts.length === 0 && regulations.length === 0 ? (
          <div className="app-surface-muted rounded-2xl p-8 text-center">
            <p className="app-text-muted text-sm">Пока нет публикаций в ленте</p>
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="app-surface-muted rounded-2xl p-8 text-center">
            <p className="text-sm font-medium text-[var(--foreground)]">
              Публикации не найдены
            </p>
            <p className="app-text-muted mt-2 text-sm">
              В выбранном источнике пока нет публикаций.
            </p>
          </div>
        ) : (
          filteredEntries.map((entry) => {
            if (entry.kind === "regulation") {
              return (
                <FeedRegulationCard
                  key={`regulation-${entry.document.id}`}
                  currentUserId={user?.id}
                  document={entry.document}
                  isAcknowledging={acknowledgingRegulationId === entry.document.id}
                  onAcknowledge={(document) => void handleAcknowledgeRegulation(document)}
                  onDelete={(document) => void deleteRegulation(document)}
                  onEdit={setMetadataRegulation}
                  onLinkTask={setTaskLinkRegulation}
                  onMove={setMetadataRegulation}
                  onOpen={openRegulation}
                  onOpenComments={openRegulationComments}
                  onPreview={openRegulationPreview}
                  onOpenAcknowledgements={(document) => setAcknowledgementsReport({
                    documentId: document.id,
                    documentTitle: document.title,
                  })}
                />
              );
            }

            const post = entry.post;
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
            const linkedTasks = post.linked_tasks || [];

            return (
              <FeedPostCard
                key={`post-${post.id}`}
                authorHref={post.author ? userProfileLink(post.author, user?.id) : null}
                post={post}
                authorSubtitle={
                  <>
                    <span>{timeAgo}</span>
                    {renderPostOrigin(post)}
                  </>
                }
                headerActions={(
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
                      <div className="app-menu absolute right-0 top-full z-20 mt-2 w-56 rounded-xl py-1.5">
                        <button
                          type="button"
                          onClick={() => openTaskLinkModal(post)}
                          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                        >
                          <Link2 size={14} />
                          Связать с задачей
                        </button>
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
                )}
                footerAction={linkedTasks.length > 0 ? (
                  <div className="flex max-w-full flex-wrap justify-end gap-1.5">
                    {linkedTasks.slice(0, 3).map((task) => (
                      <TaskLinkPill
                        key={task.link_id || task.id}
                        task={task}
                        maxTitleClassName="max-w-40"
                      />
                    ))}
                    {linkedTasks.length > 3 ? (
                      <span className="app-badge rounded-full px-2 py-0.5 text-[11px] font-medium">
                        +{linkedTasks.length - 3}
                      </span>
                    ) : null}
                  </div>
                ) : null}
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

      {user && !createPostOpen && !createRegulationOpen ? (
        <div
          ref={createMenuRef}
          className="pointer-events-none fixed bottom-[calc(env(safe-area-inset-bottom)+5.5rem)] right-4 z-30 flex flex-col items-end gap-2 lg:bottom-6 lg:right-[max(2rem,calc((100vw-72rem)/2+21.5rem))]"
        >
          {createMenuOpen ? (
            <div className="flex flex-col items-end gap-2" role="menu" aria-label="Создать в ленте">
              {canCreatePost ? (
                <button
                  type="button"
                  role="menuitem"
                  onClick={openCreatePostModal}
                  className="app-action-primary pointer-events-auto inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-medium shadow-[var(--shadow-card)]"
                >
                  <Newspaper size={17} />
                  Новость
                </button>
              ) : null}
              <button
                type="button"
                role="menuitem"
                onClick={openCreateRegulationModal}
                className="app-action-primary pointer-events-auto inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-medium shadow-[var(--shadow-card)]"
              >
                <ScrollText size={17} />
                Регламент
              </button>
            </div>
          ) : null}
          <button
            type="button"
            onClick={() => setCreateMenuOpen((current) => !current)}
            className="app-action-primary pointer-events-auto inline-flex h-12 w-12 items-center justify-center rounded-full p-0 leading-none shadow-[var(--shadow-card)] transition active:scale-[0.98]"
            title={createMenuOpen ? "Закрыть меню создания" : "Создать"}
            aria-label={createMenuOpen ? "Закрыть меню создания" : "Открыть меню создания"}
            aria-expanded={createMenuOpen}
            aria-haspopup="menu"
          >
            <Plus size={22} className={`transition-transform duration-200 ${createMenuOpen ? "rotate-45" : ""}`} />
          </button>
        </div>
      ) : null}

      <Modal
        isOpen={createRegulationOpen}
        onClose={() => setCreateRegulationOpen(false)}
        title="Создать регламент"
        size="xl"
      >
        <RegulationCreateForm
          onCancel={() => setCreateRegulationOpen(false)}
          onSuccess={() => {
            setCreateRegulationOpen(false);
            void refreshRegulations();
          }}
        />
      </Modal>

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

      <DocumentDetailModal
        key={selectedRegulation ? `${selectedRegulation.id}-${selectedRegulationInitialTab || "default"}` : "regulation-detail"}
        document={selectedRegulation}
        isOpen={Boolean(selectedRegulation)}
        initialTab={selectedRegulationInitialTab}
        onClose={() => {
          setSelectedRegulation(null);
          setSelectedRegulationInitialTab(undefined);
        }}
        onUpdate={() => {
          void refreshRegulations();
          if (selectedRegulation) {
            void apiClient.getDocument(selectedRegulation.id).then(setSelectedRegulation);
          }
        }}
        onEditMetadata={() => {
          if (selectedRegulation) setMetadataRegulation(selectedRegulation);
        }}
        onViewReport={() => {
          if (!selectedRegulation) return;
          setAcknowledgementsReport({
            documentId: selectedRegulation.id,
            documentTitle: selectedRegulation.title,
          });
        }}
        onNavigateToRelated={(documentId) => {
          setSelectedRegulationInitialTab(undefined);
          void apiClient.getDocument(documentId).then(setSelectedRegulation);
        }}
      />

      {metadataRegulation ? (
        <DocumentMetadataEditor
          isOpen
          document={metadataRegulation}
          onClose={() => setMetadataRegulation(null)}
          onUpdate={() => {
            void refreshRegulations();
            if (selectedRegulation?.id === metadataRegulation.id) {
              void apiClient.getDocument(metadataRegulation.id).then(setSelectedRegulation);
            }
          }}
        />
      ) : null}

      {taskLinkRegulation ? (
        <DocumentTaskLinks
          document={taskLinkRegulation}
          variant="dialog"
          open
          onClose={() => setTaskLinkRegulation(null)}
          onLinked={() => void refreshRegulations()}
        />
      ) : null}

      {regulationPreviewFile ? (
        <DocumentPreview
          fileUrl={regulationPreviewFile.url}
          fileName={regulationPreviewFile.name}
          onClose={() => setRegulationPreviewFile(null)}
        />
      ) : null}

      {regulationPdfFile ? (
        <EnhancedPDFViewer
          fileUrl={regulationPdfFile.url}
          fileName={regulationPdfFile.name}
          onClose={() => setRegulationPdfFile(null)}
        />
      ) : null}

      {acknowledgementsReport ? (
        <DocumentAcknowledgementsReport
          documentId={acknowledgementsReport.documentId}
          documentTitle={acknowledgementsReport.documentTitle}
          onClose={() => setAcknowledgementsReport(null)}
        />
      ) : null}

      {taskLinkPost ? (
        <RelatedTaskLinks
          key={`post-task-link-${taskLinkPost.id}`}
          entityLabel="Новость"
          entityTitle={taskLinkPost.title || `Новость #${taskLinkPost.id}`}
          entitySubtitle={getPostTaskSubtitle(taskLinkPost)}
          defaultTaskTitle={getPostDefaultTaskTitle(taskLinkPost)}
          defaultTaskDescription={(taskLinkPost.body || taskLinkPost.content || "").trim()}
          successMessage="Новость связана с задачей"
          variant="dialog"
          open
          loadLinkedTasks={() => apiClient.getPostLinkedTasks(taskLinkPost.id)}
          linkTask={(taskId) => apiClient.linkTaskPost(taskId, taskLinkPost.id)}
          onClose={() => setTaskLinkPost(null)}
          onLinked={() => void refreshPosts()}
        />
      ) : null}
    </AppShell>
  );
}
