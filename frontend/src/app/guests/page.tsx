"use client";

import { Suspense, type RefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowUpDown,
  Ban,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Filter,
  History,
  IdCard,
  Info,
  Link2,
  Loader2,
  Mail,
  MessageSquare,
  Pencil,
  Phone,
  PlayCircle,
  Plus,
  RefreshCcw,
  Search,
  Send,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Upload,
  UserRoundPlus,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { CommentComposer, CommentDeleteButton } from "@/components/shared/CommentControls";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import TaskLinkPill from "@/components/tasks/TaskLinkPill";
import { RelatedTaskLinks } from "@/components/tasks/RelatedTaskLinks";
import { Modal } from "@/components/ui";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { canManageGuestAccounts, canViewAllGuestVisits } from "@/lib/permissions";
import { displayUserName, extractNextPage, formatDateTime } from "@/lib/shared";
import { resolveMediaUrl } from "@/lib/url";
import type { Document, Guest, GuestVisit, GuestVisitComment, GuestVisitStatus, TaskCard } from "@/types/api";

const AvatarCropper = dynamic(() => import("@/components/AvatarCropper"), {
  ssr: false,
});

type PaginatedResponse<T> = {
  count?: number;
  next?: string | null;
  results?: T[];
};

type VisitScope = "all" | "mine" | "pending_decision" | "active" | "expired" | "risk";
type ActionKind = "approve" | "reject" | "request-info" | "provide-info" | "cancel" | "revoke" | "return-to-work" | "delete";
type TabKey = "visits" | "guests";

type GuestVisitFormState = {
  guestMode: "new" | "existing";
  guest_id: string;
  last_name: string;
  first_name: string;
  patronymic: string;
  birth_date: string;
  phone: string;
  email: string;
  avatar: string;
  organization: string;
  position: string;
  guest_comment: string;
  purpose: string;
  all_day: boolean;
  unlimited: boolean;
  date_from: string;
  date_to: string;
  access_starts_at: string;
  access_expires_at: string;
  document_ids: number[];
  pending_documents: PendingGuestDocument[];
};

type PendingGuestDocument = {
  localId: string;
  file: File;
  title: string;
};

type GuestEditState = {
  last_name: string;
  first_name: string;
  patronymic: string;
  birth_date: string;
  phone: string;
  email: string;
  avatar: string;
  organization: string;
  position: string;
};

const statusMeta: Record<GuestVisitStatus, { label: string; className: string }> = {
  draft: { label: "Черновик", className: "app-badge" },
  pending: { label: "На рассмотрении", className: "app-feedback-warning" },
  needs_info: { label: "Требуется информация", className: "app-feedback-approval" },
  approved: { label: "Одобрено", className: "app-feedback-success" },
  rejected: { label: "Отклонено", className: "app-feedback-danger" },
  cancelled: { label: "Отменено", className: "app-badge" },
  expired: { label: "Истекло", className: "app-badge" },
  revoked: { label: "Отозвано", className: "app-feedback-danger" },
};

const statusOptions: { value: "" | GuestVisitStatus; label: string }[] = [
  { value: "", label: "Все статусы" },
  { value: "draft", label: "Черновик" },
  { value: "pending", label: "На рассмотрении" },
  { value: "needs_info", label: "Требуется информация" },
  { value: "approved", label: "Одобрено" },
  { value: "rejected", label: "Отклонено" },
  { value: "cancelled", label: "Отменено" },
  { value: "expired", label: "Истекло" },
  { value: "revoked", label: "Отозвано" },
];

const scopeOptions: { value: VisitScope; label: string; adminOnly?: boolean }[] = [
  { value: "all", label: "Все", adminOnly: true },
  { value: "mine", label: "Мои" },
  { value: "pending_decision", label: "На решение", adminOnly: true },
  { value: "active", label: "Активные", adminOnly: true },
  { value: "expired", label: "Истекшие", adminOnly: true },
  { value: "risk", label: "Риски", adminOnly: true },
];

const orderingOptions = [
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at", label: "Сначала старые" },
  { value: "access_starts_at", label: "Начало доступа ↑" },
  { value: "-access_starts_at", label: "Начало доступа ↓" },
  { value: "access_expires_at", label: "Окончание доступа ↑" },
  { value: "-access_expires_at", label: "Окончание доступа ↓" },
];

const guestOrderingOptions = [
  { value: "last_name", label: "По фамилии ↑" },
  { value: "-last_name", label: "По фамилии ↓" },
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at", label: "Сначала старые" },
  { value: "-updated_at", label: "Недавно обновленные" },
  { value: "-ldap_last_synced_at", label: "Недавно синхронизированные" },
];

const formatDateOnlyInput = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const getDefaultAllDayPeriod = (): Pick<GuestVisitFormState, "date_from" | "date_to"> => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dayAfterTomorrow = new Date(today);
  dayAfterTomorrow.setDate(today.getDate() + 2);

  return {
    date_from: formatDateOnlyInput(today),
    date_to: formatDateOnlyInput(dayAfterTomorrow),
  };
};

const emptyForm = (): GuestVisitFormState => ({
  guestMode: "new",
  guest_id: "",
  last_name: "",
  first_name: "",
  patronymic: "",
  birth_date: "",
  phone: "",
  email: "",
  avatar: "",
  organization: "",
  position: "",
  guest_comment: "",
  purpose: "",
  all_day: true,
  unlimited: false,
  ...getDefaultAllDayPeriod(),
  access_starts_at: "",
  access_expires_at: "",
  document_ids: [],
  pending_documents: [],
});

const toResults = <T,>(payload: PaginatedResponse<T> | T[]): T[] => (
  Array.isArray(payload) ? payload : payload.results || []
);

const getPaginatedCount = <T,>(payload: PaginatedResponse<T> | T[]): number => {
  if (Array.isArray(payload)) return payload.length;
  return typeof payload.count === "number" ? payload.count : (payload.results || []).length;
};

const getReadableError = (error: unknown, fallback: string): string => {
  const raw = String((error as Error)?.message || fallback);
  const jsonStart = raw.indexOf("{");
  const payload = jsonStart >= 0 ? raw.slice(jsonStart) : raw;
  try {
    const parsed = JSON.parse(payload) as Record<string, unknown>;
    if (typeof parsed.detail === "string") return parsed.detail;
    const firstValue = Object.values(parsed)[0];
    if (Array.isArray(firstValue) && firstValue[0]) return String(firstValue[0]);
    if (typeof firstValue === "string") return firstValue;
  } catch {}
  return raw.replace(/^API Error:\s*/i, "") || fallback;
};

const formatLocalDateInput = (value?: string | null): string => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const formatLocalDateTimeInput = (value?: string | null): string => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

const formatAllDayEndDate = (value?: string | null): string => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  date.setDate(date.getDate() - 1);
  return formatLocalDateInput(date.toISOString());
};

const toApiDateTime = (value: string): string | null => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
};

const isGuestVisitPeriodActionable = (visit: GuestVisit): boolean => {
  if (visit.unlimited) return true;
  if (visit.is_expired) return false;
  if (!visit.access_expires_at) return true;
  const expiresAt = new Date(visit.access_expires_at).getTime();
  return Number.isNaN(expiresAt) || expiresAt > Date.now();
};

const canSubmitGuestVisit = (visit: GuestVisit): boolean => (
  Boolean(visit.can_submit && isGuestVisitPeriodActionable(visit))
);

const canApproveGuestVisit = (visit: GuestVisit): boolean => (
  Boolean(visit.can_approve && isGuestVisitPeriodActionable(visit))
);

const canReturnGuestVisitToWork = (visit: GuestVisit): boolean => (
  Boolean(visit.can_return_to_work && isGuestVisitPeriodActionable(visit))
);

const guestName = (guest?: Guest | null): string => (
  guest?.full_name || [guest?.last_name, guest?.first_name, guest?.patronymic].filter(Boolean).join(" ") || "Гость"
);

const guestInitials = (name: string): string => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] || "Г") + (parts[1]?.[0] || "");
};

const normalizeGuestMeta = (value?: string | null): string => {
  const normalized = String(value || "").trim();
  const lower = normalized.toLowerCase();
  return normalized && !["не указан", "не указана", "не указано", "-", "—"].includes(lower)
    ? normalized
    : "";
};

const formatGuestDate = (value?: string | null): string => {
  if (!value) return "";
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) return `${match[3]}.${match[2]}.${match[1]}`;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("ru-RU");
};

const readFileAsDataUrl = (file: File): Promise<string> => (
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  })
);

const guestOptionName = (guest: Guest): string => {
  const meta = [guest.organization, guest.position, guest.email, guest.phone]
    .map(normalizeGuestMeta)
    .filter(Boolean)
    .join(" · ");
  return `${guestName(guest)}${meta ? ` — ${meta}` : ""}`;
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
};

const createPendingGuestDocument = (file: File): PendingGuestDocument => ({
  localId: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
  file,
  title: file.name.replace(/\.[^/.]+$/, "").trim() || file.name,
});

const makeGuestEditState = (guest: Guest): GuestEditState => ({
  last_name: guest.last_name || "",
  first_name: guest.first_name || "",
  patronymic: guest.patronymic || "",
  birth_date: guest.birth_date || "",
  phone: guest.phone || "",
  email: guest.email || "",
  avatar: guest.avatar || "",
  organization: guest.organization || "",
  position: guest.position || "",
});

export default function GuestsPage() {
  return (
    <Suspense fallback={<GuestsPageFallback />}>
      <GuestsPageContent />
    </Suspense>
  );
}

function GuestsPageFallback() {
  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-8 text-center">
        <Loader2 className="mx-auto animate-spin app-accent-text" size={28} />
        <p className="app-text-muted mt-3 text-sm">Загрузка гостевой системы...</p>
      </section>
    </AppShell>
  );
}

function GuestsPageContent() {
  const { user, loading: userLoading } = useUser();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canAdminGuests = canViewAllGuestVisits(user);
  const canManageLdap = canManageGuestAccounts(user);

  const [activeTab, setActiveTab] = useState<TabKey>("visits");
  const [visits, setVisits] = useState<GuestVisit[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [comments, setComments] = useState<Record<number, GuestVisitComment[]>>({});
  const [guestComments, setGuestComments] = useState<Record<number, GuestVisitComment[]>>({});
  const [scopeCounts, setScopeCounts] = useState<Record<VisitScope, number>>({
    all: 0,
    mine: 0,
    pending_decision: 0,
    active: 0,
    expired: 0,
    risk: 0,
  });

  const [scope, setScope] = useState<VisitScope>("all");
  const [status, setStatus] = useState<"" | GuestVisitStatus>("");
  const [search, setSearch] = useState("");
  const [accessFrom, setAccessFrom] = useState("");
  const [accessTo, setAccessTo] = useState("");
  const [unlimitedFilter, setUnlimitedFilter] = useState("");
  const [placementFilter, setPlacementFilter] = useState("");
  const [guestIdFilter, setGuestIdFilter] = useState<number | null>(null);
  const [guestFilterLabel, setGuestFilterLabel] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [guestSearch, setGuestSearch] = useState("");
  const [guestBlacklistFilter, setGuestBlacklistFilter] = useState("");
  const [guestPlacementFilter, setGuestPlacementFilter] = useState("");
  const [guestOrdering, setGuestOrdering] = useState("last_name");
  const [guestFiltersOpen, setGuestFiltersOpen] = useState(false);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [guestsLoading, setGuestsLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [formWarning, setFormWarning] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingVisit, setEditingVisit] = useState<GuestVisit | null>(null);
  const [form, setForm] = useState<GuestVisitFormState>(emptyForm);
  const [detailsVisit, setDetailsVisit] = useState<GuestVisit | null>(null);
  const [actionDialog, setActionDialog] = useState<{ kind: ActionKind; visit: GuestVisit } | null>(null);
  const [actionComment, setActionComment] = useState("");
  const [detailsGuest, setDetailsGuest] = useState<Guest | null>(null);
  const [photoGuest, setPhotoGuest] = useState<Guest | null>(null);
  const [editingGuest, setEditingGuest] = useState<Guest | null>(null);
  const [guestEditForm, setGuestEditForm] = useState<GuestEditState | null>(null);
  const [taskLinkGuest, setTaskLinkGuest] = useState<Guest | null>(null);
  const [taskLinkVisit, setTaskLinkVisit] = useState<GuestVisit | null>(null);
  const [visitMenuOpenId, setVisitMenuOpenId] = useState<number | null>(null);
  const [visitCommentsOpenId, setVisitCommentsOpenId] = useState<number | null>(null);
  const [visitCommentDrafts, setVisitCommentDrafts] = useState<Record<number, string>>({});
  const [guestCommentsOpenId, setGuestCommentsOpenId] = useState<number | null>(null);
  const [guestCommentDrafts, setGuestCommentDrafts] = useState<Record<number, string>>({});

  const openedVisitParamRef = useRef<string | null>(null);
  const openedGuestParamRef = useRef<string | null>(null);
  const visitMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (visitMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target;
      if (target instanceof Node && visitMenuRef.current?.contains(target)) return;
      setVisitMenuOpenId(null);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [visitMenuOpenId]);

  useEffect(() => {
    if (userLoading) return;
    if (!canAdminGuests && scope !== "mine") {
      setScope("mine");
    }
  }, [canAdminGuests, scope, userLoading]);

  const buildVisitParams = useCallback((page: number): Record<string, string | number | boolean> => {
    const params: Record<string, string | number | boolean> = { page, limit: 20, ordering };
    if (canAdminGuests && scope !== "all") params.scope = scope;
    if (!canAdminGuests) params.scope = "mine";
    if (status) params.status = status;
    if (search.trim()) params.q = search.trim();
    if (accessFrom) params.access_from = accessFrom;
    if (accessTo) params.access_to = accessTo;
    if (unlimitedFilter) params.unlimited = unlimitedFilter;
    if (placementFilter) params.is_active = placementFilter;
    if (guestIdFilter) params.guest_id = guestIdFilter;
    return params;
  }, [accessFrom, accessTo, canAdminGuests, guestIdFilter, ordering, placementFilter, scope, search, status, unlimitedFilter]);

  const buildScopeCountParams = useCallback((targetScope: VisitScope): Record<string, string | number | boolean> => {
    const params: Record<string, string | number | boolean> = { page: 1, limit: 1 };
    if (canAdminGuests && targetScope !== "all") params.scope = targetScope;
    if (!canAdminGuests) params.scope = "mine";
    if (status) params.status = status;
    if (search.trim()) params.q = search.trim();
    if (accessFrom) params.access_from = accessFrom;
    if (accessTo) params.access_to = accessTo;
    if (unlimitedFilter) params.unlimited = unlimitedFilter;
    if (placementFilter) params.is_active = placementFilter;
    if (guestIdFilter) params.guest_id = guestIdFilter;
    return params;
  }, [accessFrom, accessTo, canAdminGuests, guestIdFilter, placementFilter, search, status, unlimitedFilter]);

  const loadVisits = useCallback(async (page = 1, append = false) => {
    try {
      if (append) setLoadingMore(true);
      else setLoading(true);
      setError(null);
      const response = await apiClient.getGuestVisits(buildVisitParams(page)) as PaginatedResponse<GuestVisit> | GuestVisit[];
      const nextVisits = toResults(response);
      setVisits((current) => append ? [...current, ...nextVisits] : nextVisits);
      setNextPage(Array.isArray(response) ? null : extractNextPage(response.next));
    } catch (err) {
      setError(getReadableError(err, "Не удалось загрузить гостевые визиты"));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [buildVisitParams]);

  const loadGuests = useCallback(async () => {
    try {
      setGuestsLoading(true);
      const response = await apiClient.getGuests({
        q: guestSearch.trim(),
        is_blacklisted: guestBlacklistFilter,
        is_active: guestPlacementFilter,
        ordering: guestOrdering,
        page: 1,
        limit: 50,
      }) as PaginatedResponse<Guest> | Guest[];
      setGuests(toResults(response));
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось загрузить гостей"));
    } finally {
      setGuestsLoading(false);
    }
  }, [guestBlacklistFilter, guestOrdering, guestPlacementFilter, guestSearch]);

  const loadDocuments = useCallback(async () => {
    try {
      setDocumentsLoading(true);
      const response = await apiClient.getDocuments({
        page: 1,
        page_size: 50,
      }) as PaginatedResponse<Document> | Document[];
      setDocuments(toResults(response));
    } catch {
      setDocuments([]);
    } finally {
      setDocumentsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadVisits();
  }, [loadVisits]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const visibleScopes = scopeOptions
          .filter((option) => !option.adminOnly || canAdminGuests)
          .map((option) => option.value);
        const results = await Promise.all(
          visibleScopes.map(async (scopeKey) => {
            const response = await apiClient.getGuestVisits(buildScopeCountParams(scopeKey)) as PaginatedResponse<GuestVisit> | GuestVisit[];
            return [scopeKey, getPaginatedCount(response)] as const;
          }),
        );
        if (!cancelled) {
          setScopeCounts((current) => ({ ...current, ...Object.fromEntries(results) }));
        }
      } catch {
        if (!cancelled) {
          setScopeCounts({
            all: 0,
            mine: 0,
            pending_decision: 0,
            active: 0,
            expired: 0,
            risk: 0,
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [buildScopeCountParams, canAdminGuests]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    if (activeTab === "guests") {
      void loadGuests();
    }
  }, [activeTab, loadGuests]);

  const refreshVisit = useCallback(async (id: number): Promise<GuestVisit> => {
    const visit = await apiClient.getGuestVisit(id) as GuestVisit;
    setVisits((current) => {
      const exists = current.some((item) => item.id === visit.id);
      if (!exists) return [visit, ...current];
      return current.map((item) => item.id === visit.id ? visit : item);
    });
    setDetailsVisit((current) => current?.id === visit.id ? visit : current);
    return visit;
  }, []);

  const loadComments = useCallback(async (visitId: number) => {
    const response = await apiClient.getGuestVisitComments(visitId) as GuestVisitComment[];
    setComments((current) => ({ ...current, [visitId]: response }));
    await refreshVisit(visitId);
  }, [refreshVisit]);

  const loadGuestComments = useCallback(async (guestId: number) => {
    const response = await apiClient.getGuestComments(guestId) as GuestVisitComment[];
    setGuestComments((current) => ({ ...current, [guestId]: response }));
    const commentsCount = response.length;
    setGuests((current) => current.map((guest) => (
      guest.id === guestId ? { ...guest, comments_count: commentsCount } : guest
    )));
    setVisits((current) => current.map((visit) => (
      visit.guest.id === guestId
        ? { ...visit, guest: { ...visit.guest, comments_count: commentsCount } }
        : visit
    )));
    setDetailsVisit((current) => (
      current?.guest.id === guestId
        ? { ...current, guest: { ...current.guest, comments_count: commentsCount } }
        : current
    ));
    return response;
  }, []);

  useEffect(() => {
    const visitParam = searchParams.get("visit");
    if (!visitParam || openedVisitParamRef.current === visitParam) return;
    const visitId = Number(visitParam);
    if (!Number.isFinite(visitId) || visitId <= 0) return;
    openedVisitParamRef.current = visitParam;
    (async () => {
      try {
        setBusyKey(`open-${visitId}`);
        const visit = await refreshVisit(visitId);
        setDetailsVisit(visit);
        await loadComments(visit.id);
      } catch (err) {
        setActionError(getReadableError(err, "Не удалось открыть гостевой визит"));
      } finally {
        setBusyKey(null);
      }
    })();
  }, [loadComments, refreshVisit, searchParams]);

  useEffect(() => {
    const guestParam = searchParams.get("guest");
    if (!guestParam || openedGuestParamRef.current === guestParam) return;
    const guestId = Number(guestParam);
    if (!Number.isFinite(guestId) || guestId <= 0) return;
    openedGuestParamRef.current = guestParam;
    (async () => {
      try {
        setBusyKey(`open-guest-${guestId}`);
        const guest = await apiClient.getGuest(guestId) as Guest;
        setActiveTab("guests");
        setDetailsGuest(guest);
      } catch (err) {
        setActionError(getReadableError(err, "Не удалось открыть гостя"));
      } finally {
        setBusyKey(null);
      }
    })();
  }, [searchParams]);

  const documentOptions = useMemo(
    () => {
      const map = new Map<number, Document>();
      documents.forEach((doc) => map.set(doc.id, doc));
      editingVisit?.documents?.forEach((doc) => map.set(doc.id, doc));
      detailsVisit?.documents?.forEach((doc) => map.set(doc.id, doc));
      editingGuest?.documents?.forEach((doc) => map.set(doc.id, doc));
      return Array.from(map.values()).map((doc) => ({
        id: doc.id,
        name: doc.title || doc.file_name || `Документ #${doc.id}`,
      }));
    },
    [detailsVisit?.documents, documents, editingGuest?.documents, editingVisit?.documents],
  );

  const guestOptions = useMemo(
    () => guests.map((guest) => ({ id: guest.id, name: guestOptionName(guest) })),
    [guests],
  );

  const activeFiltersCount = [
    status,
    search.trim(),
    accessFrom,
    accessTo,
    unlimitedFilter,
    placementFilter,
    guestIdFilter ? "guest" : "",
    canAdminGuests && scope !== "all" ? scope : "",
  ].filter(Boolean).length;
  const activeGuestFiltersCount = [
    guestBlacklistFilter,
    guestPlacementFilter,
  ].filter(Boolean).length;

  const openCreate = () => {
    setEditingVisit(null);
    setForm(emptyForm());
    setActionError(null);
    setFormWarning(null);
    setIsFormOpen(true);
    void loadGuests();
  };

  const openEdit = (visit: GuestVisit) => {
    setEditingVisit(visit);
    setForm({
      ...emptyForm(),
      guestMode: "existing",
      guest_id: String(visit.guest.id),
      purpose: visit.purpose || "",
      all_day: visit.all_day,
      unlimited: visit.unlimited,
      date_from: formatLocalDateInput(visit.access_starts_at),
      date_to: formatAllDayEndDate(visit.access_expires_at) || formatLocalDateInput(visit.access_expires_at),
      access_starts_at: formatLocalDateTimeInput(visit.access_starts_at),
      access_expires_at: formatLocalDateTimeInput(visit.access_expires_at),
      document_ids: (visit.documents || []).map((doc) => doc.id),
    });
    setActionError(null);
    setFormWarning(null);
    setIsFormOpen(true);
  };

  const closeDetails = () => {
    setDetailsVisit(null);
    if (searchParams.get("visit")) {
      router.replace("/guests");
      openedVisitParamRef.current = null;
    }
  };

  const openDetails = async (visit: GuestVisit) => {
    setDetailsVisit(visit);
    if (!comments[visit.id] || visit.has_unread_info_response) {
      try {
        await loadComments(visit.id);
      } catch {
        setComments((current) => ({ ...current, [visit.id]: [] }));
      }
    }
  };

  const toggleVisitComments = async (visit: GuestVisit) => {
    setVisitMenuOpenId(null);
    if (visitCommentsOpenId === visit.id) {
      setVisitCommentsOpenId(null);
      return;
    }
    setVisitCommentsOpenId(visit.id);
    if (!comments[visit.id] || visit.has_unread_info_response) {
      try {
        await loadComments(visit.id);
      } catch {
        setComments((current) => ({ ...current, [visit.id]: [] }));
      }
    }
  };

  const updateVisitCommentDraft = (visitId: number, value: string) => {
    setVisitCommentDrafts((current) => ({ ...current, [visitId]: value }));
  };

  const addListComment = async (visit: GuestVisit) => {
    const text = (visitCommentDrafts[visit.id] || "").trim();
    if (!text) return;
    await addComment(visit, text);
    setVisitCommentDrafts((current) => ({ ...current, [visit.id]: "" }));
  };

  const buildVisitPayload = (): Record<string, unknown> => {
    const payload: Record<string, unknown> = {
      purpose: form.purpose.trim(),
      all_day: form.all_day,
      unlimited: form.unlimited,
      document_ids: form.document_ids,
    };

    if (!editingVisit) {
      if (form.guestMode === "existing" && form.guest_id) {
        payload.guest_id = Number(form.guest_id);
      } else {
        payload.guest = {
          last_name: form.last_name.trim(),
          first_name: form.first_name.trim(),
          patronymic: form.patronymic.trim(),
          birth_date: form.birth_date || null,
          phone: form.phone.trim(),
          email: form.email.trim(),
          ...(form.avatar ? { avatar: form.avatar } : {}),
          organization: form.organization.trim(),
          position: form.position.trim(),
        };
        payload.guest_comment = form.guest_comment.trim();
      }
    }

    if (form.unlimited) {
      payload.access_expires_at = null;
    } else if (form.all_day) {
      payload.date_from = form.date_from;
      payload.date_to = form.date_to;
    } else {
      payload.access_starts_at = toApiDateTime(form.access_starts_at);
      payload.access_expires_at = toApiDateTime(form.access_expires_at);
    }
    return payload;
  };

  const validateForm = (): string | null => {
    if (!editingVisit) {
      if (form.guestMode === "existing" && !form.guest_id) return "Выберите гостя.";
      if (form.guestMode === "new" && !form.first_name.trim()) {
        return "Укажите имя гостя.";
      }
    }
    if (!form.purpose.trim()) return "Укажите цель приглашения.";
    if (!form.unlimited) {
      if (form.all_day) {
        if (!form.date_from || !form.date_to) return "Укажите даты доступа.";
        if (form.date_to < formatDateOnlyInput(new Date())) {
          return "Нельзя создать заявку с периодом доступа, который уже истек.";
        }
      }
      if (!form.all_day) {
        if (!form.access_starts_at || !form.access_expires_at) return "Укажите время доступа.";
        if (new Date(form.access_expires_at).getTime() <= Date.now()) {
          return "Нельзя создать заявку с периодом доступа, который уже истек.";
        }
      }
    }
    return null;
  };

  const getIncompleteFormWarning = (): string | null => {
    if (editingVisit || form.guestMode !== "new") return null;

    const hasGuestIdentityWarning = !form.last_name.trim() || !form.phone.trim() || !form.avatar;
    const hasGuestDocumentWarning = form.document_ids.length === 0 && form.pending_documents.length === 0;

    return hasGuestIdentityWarning || hasGuestDocumentWarning
      ? "В заявке указаны не все поля. Можно вернуться и заполнить данные или продолжить создание заявки."
      : null;
  };

  const submitForm = async ({ skipIncompleteWarning = false } = {}) => {
    const formError = validateForm();
    if (formError) {
      setActionError(formError);
      setFormWarning(null);
      return;
    }

    if (!skipIncompleteWarning) {
      const incompleteWarning = getIncompleteFormWarning();
      if (incompleteWarning) {
        setFormWarning(incompleteWarning);
        return;
      }
    }

    try {
      setBusyKey(editingVisit ? `update-${editingVisit.id}` : "create");
      setActionError(null);
      setFormWarning(null);
      const payload = buildVisitPayload();
      let saved = editingVisit
        ? await apiClient.updateGuestVisit(editingVisit.id, payload) as GuestVisit
        : await apiClient.createGuestVisit(payload) as GuestVisit;
      for (const pendingDocument of form.pending_documents) {
        const uploadResult = await apiClient.uploadGuestDocument(saved.guest.id, {
          file: pendingDocument.file,
          title: pendingDocument.title,
        }) as { document: Document; guest: Guest };
        saved = await apiClient.attachGuestVisitDocument(
          saved.id,
          uploadResult.document.id,
        ) as GuestVisit;
        setGuests((current) => current.map((guest) => (
          guest.id === uploadResult.guest.id ? uploadResult.guest : guest
        )));
      }
      setVisits((current) => {
        if (editingVisit) return current.map((item) => item.id === saved.id ? saved : item);
        return [saved, ...current];
      });
      setDetailsVisit((current) => current?.id === saved.id ? saved : current);
      setGuests((current) => {
        if (!saved.guest?.id) return current;
        const exists = current.some((item) => item.id === saved.guest.id);
        if (exists) {
          return current.map((item) => item.id === saved.guest.id ? {
            ...item,
            ...saved.guest,
            document_folder: saved.guest.document_folder ?? item.document_folder,
            documents: saved.guest.documents ?? item.documents,
          } : item);
        }
        return [saved.guest, ...current];
      });
      setIsFormOpen(false);
      setEditingVisit(null);
      setForm(emptyForm());
      setActionSuccess(editingVisit ? "Визит обновлен" : "Заявка создана и отправлена на рассмотрение");
      if (form.pending_documents.length > 0) {
        void loadDocuments();
      }
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось сохранить визит"));
    } finally {
      setBusyKey(null);
    }
  };

  const runVisitAction = async (visit: GuestVisit, action: "submit" | "sync") => {
    const key = `${action}-${visit.id}`;
    try {
      setBusyKey(key);
      setActionError(null);
      const updated = action === "submit"
        ? await apiClient.submitGuestVisit(visit.id) as GuestVisit
        : await apiClient.syncGuestVisitLdap(visit.id) as GuestVisit;
      setVisits((current) => current.map((item) => item.id === updated.id ? updated : item));
      setDetailsVisit((current) => current?.id === updated.id ? updated : current);
      setActionSuccess(action === "submit" ? "Визит отправлен на рассмотрение" : "Синхронизация учетки запущена");
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось выполнить действие"));
    } finally {
      setBusyKey(null);
    }
  };

  const executeDialogAction = async () => {
    if (!actionDialog) return;
    if (["request-info", "provide-info"].includes(actionDialog.kind) && !actionComment.trim()) {
      setActionError("Комментарий обязателен.");
      return;
    }
    const { visit, kind } = actionDialog;
    const key = `${kind}-${visit.id}`;
    try {
      setBusyKey(key);
      setActionError(null);
      const payload = { comment: actionComment.trim() };
      if (kind === "delete") {
        await apiClient.deleteGuestVisit(visit.id);
        setVisits((current) => current.filter((item) => item.id !== visit.id));
        setDetailsVisit((current) => current?.id === visit.id ? null : current);
        setComments((current) => {
          const next = { ...current };
          delete next[visit.id];
          return next;
        });
        try {
          const updatedGuest = await apiClient.getGuest(visit.guest.id) as Guest;
          setGuests((current) => current.map((item) => item.id === updatedGuest.id ? updatedGuest : item));
          setVisits((current) => current.map((item) => (
            item.guest.id === updatedGuest.id ? { ...item, guest: updatedGuest } : item
          )));
        } catch {
          // Deleting the visit already succeeded; stale guest badges will refresh on the next load.
        }
        setActionDialog(null);
        setActionComment("");
        setActionSuccess("Заявка удалена, доступ гостя пересчитан");
        return;
      }
      let updated: GuestVisit;
      if (kind === "approve") updated = await apiClient.approveGuestVisit(visit.id, payload) as GuestVisit;
      else if (kind === "reject") updated = await apiClient.rejectGuestVisit(visit.id, payload) as GuestVisit;
      else if (kind === "request-info") updated = await apiClient.requestGuestVisitInfo(visit.id, payload) as GuestVisit;
      else if (kind === "provide-info") updated = await apiClient.provideGuestVisitInfo(visit.id, payload) as GuestVisit;
      else if (kind === "cancel") updated = await apiClient.cancelGuestVisit(visit.id, payload) as GuestVisit;
      else if (kind === "revoke") updated = await apiClient.revokeGuestVisit(visit.id, payload) as GuestVisit;
      else updated = await apiClient.returnGuestVisitToWork(visit.id, payload) as GuestVisit;
      setVisits((current) => current.map((item) => item.id === updated.id ? updated : item));
      setDetailsVisit((current) => current?.id === updated.id ? updated : current);
      if (kind === "provide-info") await loadComments(visit.id);
      setActionDialog(null);
      setActionComment("");
      setActionSuccess("Статус визита обновлен");
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось выполнить действие"));
    } finally {
      setBusyKey(null);
    }
  };

  const addComment = async (visit: GuestVisit, text: string) => {
    try {
      setBusyKey(`comment-${visit.id}`);
      setActionError(null);
      const comment = await apiClient.addGuestVisitComment(visit.id, text) as GuestVisitComment;
      setComments((current) => ({ ...current, [visit.id]: [...(current[visit.id] || []), comment] }));
      await refreshVisit(visit.id);
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось добавить комментарий"));
    } finally {
      setBusyKey(null);
    }
  };

  const deleteComment = async (visit: GuestVisit, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      setActionError(null);
      await apiClient.deleteGuestVisitComment(visit.id, commentId);
      setComments((current) => ({ ...current, [visit.id]: (current[visit.id] || []).filter((item) => item.id !== commentId) }));
      await refreshVisit(visit.id);
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось удалить комментарий"));
    } finally {
      setBusyKey(null);
    }
  };

  const toggleGuestComments = async (guest: Guest) => {
    if (guestCommentsOpenId === guest.id) {
      setGuestCommentsOpenId(null);
      return;
    }
    setGuestCommentsOpenId(guest.id);
    if (!guestComments[guest.id]) {
      try {
        await loadGuestComments(guest.id);
      } catch {
        setGuestComments((current) => ({ ...current, [guest.id]: [] }));
      }
    }
  };

  const updateGuestCommentDraft = (guestId: number, value: string) => {
    setGuestCommentDrafts((current) => ({ ...current, [guestId]: value }));
  };

  const addGuestComment = async (guest: Guest) => {
    const text = (guestCommentDrafts[guest.id] || "").trim();
    if (!text) return;
    try {
      setBusyKey(`guest-comment-${guest.id}`);
      setActionError(null);
      const comment = await apiClient.addGuestComment(guest.id, text) as GuestVisitComment;
      const nextComments = [...(guestComments[guest.id] || []), comment];
      setGuestComments((current) => ({
        ...current,
        [guest.id]: [...(current[guest.id] || []), comment],
      }));
      setGuestCommentDrafts((current) => ({ ...current, [guest.id]: "" }));
      const nextCount = nextComments.length;
      setGuests((current) => current.map((item) => (
        item.id === guest.id ? { ...item, comments_count: nextCount } : item
      )));
      setVisits((current) => current.map((visit) => (
        visit.guest.id === guest.id
          ? { ...visit, guest: { ...visit.guest, comments_count: nextCount } }
          : visit
      )));
      setDetailsVisit((current) => (
        current?.guest.id === guest.id
          ? { ...current, guest: { ...current.guest, comments_count: nextCount } }
          : current
      ));
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось добавить комментарий по гостю"));
    } finally {
      setBusyKey(null);
    }
  };

  const deleteGuestComment = async (guest: Guest, commentId: number) => {
    try {
      setBusyKey(`guest-comment-delete-${commentId}`);
      setActionError(null);
      await apiClient.deleteGuestComment(guest.id, commentId);
      const nextComments = (guestComments[guest.id] || []).filter((item) => item.id !== commentId);
      const nextCount = nextComments.length;
      setGuestComments((current) => ({ ...current, [guest.id]: nextComments }));
      setGuests((current) => current.map((item) => (
        item.id === guest.id ? { ...item, comments_count: nextCount } : item
      )));
      setVisits((current) => current.map((visit) => (
        visit.guest.id === guest.id
          ? { ...visit, guest: { ...visit.guest, comments_count: nextCount } }
          : visit
      )));
      setDetailsVisit((current) => (
        current?.guest.id === guest.id
          ? { ...current, guest: { ...current.guest, comments_count: nextCount } }
          : current
      ));
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось удалить комментарий по гостю"));
    } finally {
      setBusyKey(null);
    }
  };

  const openGuestEdit = (guest: Guest) => {
    setEditingGuest(guest);
    setGuestEditForm(makeGuestEditState(guest));
    setActionError(null);
  };

  const openGuestDetails = (guest: Guest) => {
    setDetailsGuest(guest);
    setActionError(null);
  };

  const openGuestVisits = (guest: Guest) => {
    setActiveTab("visits");
    setGuestIdFilter(guest.id);
    setGuestFilterLabel(guestName(guest));
    setSearch("");
    setStatus("");
    setAccessFrom("");
    setAccessTo("");
    setUnlimitedFilter("");
    setPlacementFilter("");
    setScope(canAdminGuests ? "all" : "mine");
    setFiltersOpen(false);
  };

  const applyGuestUpdate = (updated: Guest) => {
    setGuests((current) => current.map((item) => item.id === updated.id ? updated : item));
    setVisits((current) => current.map((visit) => visit.guest.id === updated.id ? { ...visit, guest: updated } : visit));
    setDetailsVisit((current) => current?.guest.id === updated.id ? { ...current, guest: updated } : current);
    setDetailsGuest((current) => current?.id === updated.id ? updated : current);
    setEditingGuest((current) => current?.id === updated.id ? updated : current);
    setTaskLinkGuest((current) => current?.id === updated.id ? updated : current);
  };

  const handleGuestTaskLinked = async (guestId: number) => {
    const updated = await apiClient.getGuest(guestId) as Guest;
    applyGuestUpdate(updated);
  };

  const handleVisitTaskLinked = async (visitId: number) => {
    const updated = await refreshVisit(visitId);
    setTaskLinkVisit((current) => current?.id === updated.id ? updated : current);
  };

  const saveGuestEdit = async () => {
    if (!editingGuest || !guestEditForm) return;
    try {
      setBusyKey(`guest-update-${editingGuest.id}`);
      setActionError(null);
      const payload: Record<string, unknown> = {
        last_name: guestEditForm.last_name,
        first_name: guestEditForm.first_name,
        patronymic: guestEditForm.patronymic,
        birth_date: guestEditForm.birth_date || null,
        phone: guestEditForm.phone,
        email: guestEditForm.email,
        organization: guestEditForm.organization,
        position: guestEditForm.position,
      };
      if (guestEditForm.avatar) {
        payload.avatar = guestEditForm.avatar;
      }
      const updated = await apiClient.updateGuest(editingGuest.id, payload) as Guest;
      applyGuestUpdate(updated);
      setEditingGuest(null);
      setGuestEditForm(null);
      setActionSuccess("Данные гостя обновлены");
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось обновить гостя"));
    } finally {
      setBusyKey(null);
    }
  };

  const attachGuestProfileDocument = async (guest: Guest, documentId?: number | null) => {
    if (!documentId) return;
    try {
      setBusyKey(`guest-attach-doc-${guest.id}`);
      setActionError(null);
      const response = await apiClient.attachGuestDocument(guest.id, documentId) as { guest: Guest; document: Document };
      applyGuestUpdate(response.guest);
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось прикрепить документ к гостю"));
    } finally {
      setBusyKey(null);
    }
  };

  const uploadGuestProfileDocument = async (guest: Guest, file: File) => {
    try {
      setBusyKey(`guest-upload-doc-${guest.id}`);
      setActionError(null);
      const response = await apiClient.uploadGuestDocument(guest.id, {
        file,
        title: file.name.replace(/\.[^/.]+$/, "").trim() || file.name,
      }) as { guest: Guest; document: Document };
      applyGuestUpdate(response.guest);
      void loadDocuments();
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось загрузить документ гостя"));
    } finally {
      setBusyKey(null);
    }
  };

  const removeGuestProfileDocument = async (guest: Guest, documentId: number) => {
    try {
      setBusyKey(`guest-remove-doc-${documentId}`);
      setActionError(null);
      const response = await apiClient.removeGuestDocument(guest.id, documentId) as { guest: Guest; document: Document };
      applyGuestUpdate(response.guest);
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось убрать документ гостя"));
    } finally {
      setBusyKey(null);
    }
  };

  const runGuestAdminAction = async (guest: Guest, action: "sync" | "blacklist" | "unblacklist") => {
    try {
      setBusyKey(`${action}-guest-${guest.id}`);
      setActionError(null);
      const updated = action === "sync"
        ? await apiClient.syncGuestLdap(guest.id) as Guest
        : action === "blacklist"
          ? await apiClient.blacklistGuest(guest.id) as Guest
          : await apiClient.unblacklistGuest(guest.id) as Guest;
      applyGuestUpdate(updated);
      setActionSuccess(
        action === "sync"
          ? "Учетка синхронизирована"
          : action === "blacklist"
            ? "Гость добавлен в черный список"
            : "Блокировка гостя снята",
      );
    } catch (err) {
      setActionError(getReadableError(err, "Не удалось выполнить действие с гостем"));
    } finally {
      setBusyKey(null);
    }
  };

  const clearFilters = () => {
    setStatus("");
    setSearch("");
    setAccessFrom("");
    setAccessTo("");
    setUnlimitedFilter("");
    setPlacementFilter("");
    setGuestIdFilter(null);
    setGuestFilterLabel("");
    setOrdering("-created_at");
    setScope(canAdminGuests ? "all" : "mine");
  };

  return (
    <AppShell>
      <div className="space-y-4">
        <section className="app-surface flex flex-col gap-4 rounded-2xl p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">ГОСТИ</p>
            <button
              type="button"
              onClick={openCreate}
              className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition"
            >
              <Plus size={14} />
              Новая заявка
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("visits")}
              className={`inline-flex h-10 items-center rounded-full px-4 text-sm font-medium transition ${activeTab === "visits" ? "app-pill-active" : "app-pill"}`}
            >
              Заявки
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("guests")}
              className={`inline-flex h-10 items-center rounded-full px-4 text-sm font-medium transition ${activeTab === "guests" ? "app-pill-active" : "app-pill"}`}
            >
              Гости
            </button>
          </div>
        </section>

        {actionSuccess ? (
          <div className="app-feedback-success flex items-center justify-between gap-3 rounded-xl p-3 text-sm">
            <span>{actionSuccess}</span>
            <button type="button" onClick={() => setActionSuccess(null)} className="app-icon-button rounded-lg p-1">
              <XCircle size={14} />
            </button>
          </div>
        ) : null}

        {activeTab === "visits" ? (
          <section className="app-surface rounded-2xl p-4">
            <GuestVisitControls
              accessFrom={accessFrom}
              accessTo={accessTo}
              activeFiltersCount={activeFiltersCount}
              canAdminGuests={canAdminGuests}
              filtersOpen={filtersOpen}
              guestFilterLabel={guestFilterLabel}
              placementFilter={placementFilter}
              ordering={ordering}
              scope={scope}
              scopeCounts={scopeCounts}
              search={search}
              status={status}
              unlimitedFilter={unlimitedFilter}
              onAccessFromChange={setAccessFrom}
              onAccessToChange={setAccessTo}
              onClearFilters={clearFilters}
              onClearGuestFilter={() => {
                setGuestIdFilter(null);
                setGuestFilterLabel("");
              }}
              onPlacementFilterChange={setPlacementFilter}
              onOrderingChange={setOrdering}
              onScopeChange={setScope}
              onSearchChange={setSearch}
              onStatusChange={setStatus}
              onToggleFilters={() => setFiltersOpen((value) => !value)}
              onUnlimitedFilterChange={setUnlimitedFilter}
            />

            {loading ? (
              <div className="app-surface-muted mt-4 rounded-xl p-8 text-center">
                <Loader2 className="mx-auto animate-spin app-accent-text" size={28} />
                <p className="app-text-muted mt-3 text-sm">Загрузка визитов...</p>
              </div>
            ) : error ? (
              <div className="app-feedback-danger mt-4 rounded-xl p-6 text-center text-sm">{error}</div>
            ) : visits.length === 0 ? (
              <div className="app-surface-muted mt-4 rounded-xl p-8 text-center">
                <UserRoundPlus className="app-text-muted mx-auto" size={32} />
                <p className="mt-3 text-sm font-medium text-[var(--foreground)]">Гостевые визиты не найдены</p>
                <p className="app-text-muted mt-1 text-xs">Создайте новый визит или измените фильтры.</p>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {visits.map((visit) => (
                  <GuestVisitRow
                    key={visit.id}
                    busyKey={busyKey}
                    canDeleteAllComments={canAdminGuests}
                    commentDraft={visitCommentDrafts[visit.id] || ""}
                    comments={comments[visit.id] || []}
                    commentsOpen={visitCommentsOpenId === visit.id}
                    currentUserId={user?.id}
                    isMenuOpen={visitMenuOpenId === visit.id}
                    menuRef={visitMenuOpenId === visit.id ? visitMenuRef : null}
                    visit={visit}
                    onActionDialog={(kind) => {
                      setVisitMenuOpenId(null);
                      setActionDialog({ kind, visit });
                      setActionComment("");
                    }}
                    onEdit={openEdit}
                    onLinkTask={(nextVisit) => {
                      setVisitMenuOpenId(null);
                      setTaskLinkVisit(nextVisit);
                    }}
                    onOpen={openDetails}
                    onAddComment={addListComment}
                    onCommentDraftChange={updateVisitCommentDraft}
                    onDeleteComment={deleteComment}
                    onRunAction={runVisitAction}
                    onOpenGuestPhoto={setPhotoGuest}
                    onToggleComments={toggleVisitComments}
                    onToggleMenu={(visitId) => setVisitMenuOpenId(visitId)}
                  />
                ))}
                {nextPage ? (
                  <div className="flex justify-center pt-2">
                    <button
                      type="button"
                      onClick={() => void loadVisits(nextPage, true)}
                      disabled={loadingMore}
                      className="app-action-secondary inline-flex h-10 items-center gap-2 rounded-lg px-4 text-sm font-medium disabled:opacity-60"
                    >
                      {loadingMore ? <Loader2 className="animate-spin" size={16} /> : null}
                      Загрузить еще
                    </button>
                  </div>
                ) : null}
              </div>
            )}
          </section>
        ) : (
          <GuestRegistryPanel
            busyKey={busyKey}
            canEditGuests={canAdminGuests}
            canManageLdap={canManageLdap}
            filtersOpen={guestFiltersOpen}
            activeFiltersCount={activeGuestFiltersCount}
            blacklistFilter={guestBlacklistFilter}
            canDeleteAllComments={canAdminGuests}
            commentDrafts={guestCommentDrafts}
            commentsByGuest={guestComments}
            commentsOpenId={guestCommentsOpenId}
            currentUserId={user?.id}
            ordering={guestOrdering}
            placementFilter={guestPlacementFilter}
            guestSearch={guestSearch}
            guests={guests}
            loading={guestsLoading}
            onEditGuest={openGuestEdit}
            onLinkTask={(guest) => {
              setTaskLinkGuest(guest);
            }}
            onOpenGuest={openGuestDetails}
            onOpenGuestPhoto={setPhotoGuest}
            onOpenGuestVisits={openGuestVisits}
            onBlacklistFilterChange={setGuestBlacklistFilter}
            onClearFilters={() => {
              setGuestBlacklistFilter("");
              setGuestPlacementFilter("");
              setGuestOrdering("last_name");
            }}
            onOrderingChange={setGuestOrdering}
            onPlacementFilterChange={setGuestPlacementFilter}
            onAddComment={addGuestComment}
            onCommentDraftChange={updateGuestCommentDraft}
            onDeleteComment={deleteGuestComment}
            onGuestSearchChange={setGuestSearch}
            onToggleComments={toggleGuestComments}
            onToggleFilters={() => setGuestFiltersOpen((value) => !value)}
            onRunGuestAction={runGuestAdminAction}
          />
        )}
      </div>

      <GuestVisitFormModal
        key={isFormOpen ? (editingVisit ? `edit-${editingVisit.id}` : "create") : "closed"}
        busy={busyKey === "create" || Boolean(editingVisit && busyKey === `update-${editingVisit.id}`)}
        documents={documentOptions}
        documentsLoading={documentsLoading}
        editingVisit={editingVisit}
        form={form}
        guestOptions={guestOptions}
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false);
          setEditingVisit(null);
          setForm(emptyForm());
          setFormWarning(null);
        }}
        onReloadDocuments={loadDocuments}
        onSubmit={submitForm}
        setForm={setForm}
      />

      <GuestVisitDetailModal
        busyKey={busyKey}
        comments={detailsVisit ? comments[detailsVisit.id] || [] : []}
        visit={detailsVisit}
        onActionDialog={(kind, visit) => {
          setActionDialog({ kind, visit });
          setActionComment("");
        }}
        onAddComment={addComment}
        onClose={closeDetails}
        onDeleteComment={deleteComment}
        onEdit={openEdit}
        onLinkTask={(visit) => {
          setDetailsVisit(null);
          setTaskLinkVisit(visit);
        }}
        onRunAction={runVisitAction}
      />

      {taskLinkGuest ? (
        <RelatedTaskLinks
          key={`guest-task-link-${taskLinkGuest.id}`}
          entityLabel="Гость"
          entityTitle={guestName(taskLinkGuest)}
          entitySubtitle={[taskLinkGuest.organization, taskLinkGuest.email, taskLinkGuest.phone].filter(Boolean).join(" · ")}
          defaultTaskTitle={`Задача по гостю: ${guestName(taskLinkGuest)}`}
          defaultTaskDescription={[
            taskLinkGuest.organization ? `Организация: ${taskLinkGuest.organization}` : "",
            taskLinkGuest.position ? `Должность: ${taskLinkGuest.position}` : "",
            taskLinkGuest.phone ? `Телефон: ${taskLinkGuest.phone}` : "",
            taskLinkGuest.email ? `Email: ${taskLinkGuest.email}` : "",
          ].filter(Boolean).join("\n")}
          successMessage="Гость связан с задачей"
          variant="dialog"
          open
          loadLinkedTasks={() => apiClient.getGuestLinkedTasks(taskLinkGuest.id) as Promise<TaskCard[]>}
          linkTask={(taskId) => apiClient.linkTaskGuest(taskId, taskLinkGuest.id)}
          onClose={() => setTaskLinkGuest(null)}
          onLinked={() => void handleGuestTaskLinked(taskLinkGuest.id)}
        />
      ) : null}

      {taskLinkVisit ? (
        <RelatedTaskLinks
          key={`guest-visit-task-link-${taskLinkVisit.id}`}
          entityLabel="Заявка на гостевой визит"
          entityTitle={`#${taskLinkVisit.id} · ${guestName(taskLinkVisit.guest)}`}
          entitySubtitle={taskLinkVisit.unlimited
            ? "Бессрочно"
            : `${formatDateTime(taskLinkVisit.access_starts_at) || "—"} - ${formatDateTime(taskLinkVisit.access_expires_at) || "—"}`}
          defaultTaskTitle={`Задача по гостевому визиту #${taskLinkVisit.id}: ${guestName(taskLinkVisit.guest)}`}
          defaultTaskDescription={taskLinkVisit.purpose || ""}
          successMessage="Заявка на гостевой визит связана с задачей"
          variant="dialog"
          open
          loadLinkedTasks={() => apiClient.getGuestVisitLinkedTasks(taskLinkVisit.id) as Promise<TaskCard[]>}
          linkTask={(taskId) => apiClient.linkTaskGuestVisit(taskId, taskLinkVisit.id)}
          onClose={() => setTaskLinkVisit(null)}
          onLinked={() => void handleVisitTaskLinked(taskLinkVisit.id)}
        />
      ) : null}

      <ActionCommentModal
        action={actionDialog}
        busyKey={busyKey}
        comment={actionComment}
        onClose={() => {
          setActionDialog(null);
          setActionComment("");
        }}
        onCommentChange={setActionComment}
        onSubmit={executeDialogAction}
      />

      <GuestDetailModal
        canEdit={canAdminGuests}
        guest={detailsGuest}
        onClose={() => {
          setDetailsGuest(null);
          if (searchParams.get("guest")) {
            router.replace("/guests");
            openedGuestParamRef.current = null;
          }
        }}
        onEdit={(guest) => {
          setDetailsGuest(null);
          openGuestEdit(guest);
        }}
        onLinkTask={(guest) => {
          setDetailsGuest(null);
          setTaskLinkGuest(guest);
        }}
      />

      <GuestPhotoModal
        guest={photoGuest}
        onClose={() => setPhotoGuest(null)}
      />

      <GuestEditModal
        busy={Boolean(editingGuest && busyKey === `guest-update-${editingGuest.id}`)}
        busyKey={busyKey}
        documents={documentOptions}
        documentsLoading={documentsLoading}
        form={guestEditForm}
        guest={editingGuest}
        onAttachDocument={attachGuestProfileDocument}
        onClose={() => {
          setEditingGuest(null);
          setGuestEditForm(null);
        }}
        onReloadDocuments={loadDocuments}
        onRemoveDocument={removeGuestProfileDocument}
        onSubmit={saveGuestEdit}
        onUploadDocument={uploadGuestProfileDocument}
        setForm={setGuestEditForm}
      />

      <FeedbackModal
        message={actionError}
        title="Проверьте данные"
        variant="danger"
        onClose={() => setActionError(null)}
      />

      <FeedbackModal
        message={formWarning}
        title="Заявка заполнена не полностью"
        variant="warning"
        closeLabel="Вернуться"
        continueLabel="Продолжить"
        onClose={() => setFormWarning(null)}
        onContinue={() => {
          setFormWarning(null);
          void submitForm({ skipIncompleteWarning: true });
        }}
      />
    </AppShell>
  );
}

function GuestVisitControls({
  accessFrom,
  accessTo,
  activeFiltersCount,
  canAdminGuests,
  filtersOpen,
  guestFilterLabel,
  ordering,
  placementFilter,
  scope,
  scopeCounts,
  search,
  status,
  unlimitedFilter,
  onAccessFromChange,
  onAccessToChange,
  onClearFilters,
  onClearGuestFilter,
  onOrderingChange,
  onPlacementFilterChange,
  onScopeChange,
  onSearchChange,
  onStatusChange,
  onToggleFilters,
  onUnlimitedFilterChange,
}: {
  accessFrom: string;
  accessTo: string;
  activeFiltersCount: number;
  canAdminGuests: boolean;
  filtersOpen: boolean;
  guestFilterLabel: string;
  ordering: string;
  placementFilter: string;
  scope: VisitScope;
  scopeCounts: Record<VisitScope, number>;
  search: string;
  status: "" | GuestVisitStatus;
  unlimitedFilter: string;
  onAccessFromChange: (value: string) => void;
  onAccessToChange: (value: string) => void;
  onClearFilters: () => void;
  onClearGuestFilter: () => void;
  onOrderingChange: (value: string) => void;
  onPlacementFilterChange: (value: string) => void;
  onScopeChange: (value: VisitScope) => void;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: "" | GuestVisitStatus) => void;
  onToggleFilters: () => void;
  onUnlimitedFilterChange: (value: string) => void;
}) {
  const visibleScopes = scopeOptions.filter((option) => !option.adminOnly || canAdminGuests);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Поиск по заявкам..."
            className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <button
          type="button"
          title="Фильтры"
          onClick={onToggleFilters}
          className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${filtersOpen ? "app-selected app-accent-text" : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"}`}
        >
          <Filter size={16} />
          {activeFiltersCount > 0 ? (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">{activeFiltersCount}</span>
          ) : null}
        </button>
        <div className="relative w-full shrink-0 sm:w-[148px]">
          <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <select
            value={ordering}
            onChange={(event) => onOrderingChange(event.target.value)}
            className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-xs font-medium"
            aria-label="Сортировка заявок гостей"
          >
            {orderingOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {visibleScopes.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onScopeChange(option.value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
              scope === option.value ? "app-pill-active" : "app-pill"
            }`}
          >
            <span>{option.label}</span>
            <span className={`app-badge rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
              scope === option.value ? "app-pill-count-active" : "app-pill-count"
            }`}>
              {scopeCounts[option.value] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {guestFilterLabel ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onClearGuestFilter}
            className="app-pill-active inline-flex max-w-full items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium"
            title="Сбросить фильтр по гостю"
          >
            <span className="truncate">Гость: {guestFilterLabel}</span>
            <XCircle size={13} className="shrink-0" />
          </button>
        </div>
      ) : null}

      {filtersOpen ? (
        <div className="app-surface-muted grid grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))] gap-3 rounded-xl border border-[var(--border-subtle)] p-3">
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Статус</span>
            <select
              value={status}
              onChange={(event) => onStatusChange(event.target.value as "" | GuestVisitStatus)}
              className="app-select h-10 w-full rounded-lg px-3 text-sm"
            >
              {statusOptions.map((option) => (
                <option key={option.value || "all"} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Доступ с</span>
            <input
              type="date"
              value={accessFrom}
              onChange={(event) => onAccessFromChange(event.target.value)}
              className="app-input h-10 w-full rounded-lg px-3 text-sm"
            />
          </label>
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Доступ до</span>
            <input
              type="date"
              value={accessTo}
              onChange={(event) => onAccessToChange(event.target.value)}
              className="app-input h-10 w-full rounded-lg px-3 text-sm"
            />
          </label>
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Бессрочный</span>
            <select
              value={unlimitedFilter}
              onChange={(event) => onUnlimitedFilterChange(event.target.value)}
              className="app-select h-10 w-full rounded-lg px-3 text-sm"
            >
              <option value="">Любой</option>
              <option value="true">Да</option>
              <option value="false">Нет</option>
            </select>
          </label>
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Статус гостя</span>
            <select
              value={placementFilter}
              onChange={(event) => onPlacementFilterChange(event.target.value)}
              className="app-select h-10 w-full rounded-lg px-3 text-sm"
            >
              <option value="">Любой</option>
              <option value="true">Доступ есть</option>
              <option value="false">Нет доступа</option>
            </select>
          </label>
          <div className="flex min-w-0 items-end">
            <button
              type="button"
              onClick={onClearFilters}
              className="app-action-secondary h-10 w-full rounded-lg px-3 text-sm font-medium"
            >
              Сбросить
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LinkedTaskPills({
  tasks,
  max = 3,
  className = "",
}: {
  tasks?: Guest["linked_tasks"] | GuestVisit["linked_tasks"];
  max?: number;
  className?: string;
}) {
  if (!tasks || tasks.length === 0) return null;
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {tasks.slice(0, max).map((task) => (
        <TaskLinkPill
          key={task.link_id || task.id}
          task={task}
          maxTitleClassName="max-w-44"
        />
      ))}
      {tasks.length > max ? (
        <span className="app-badge inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium">
          +{tasks.length - max}
        </span>
      ) : null}
    </div>
  );
}

function GuestVisitRow({
  busyKey,
  canDeleteAllComments,
  commentDraft,
  comments,
  commentsOpen,
  currentUserId,
  isMenuOpen,
  menuRef,
  visit,
  onActionDialog,
  onAddComment,
  onCommentDraftChange,
  onDeleteComment,
  onEdit,
  onLinkTask,
  onOpen,
  onOpenGuestPhoto,
  onRunAction,
  onToggleComments,
  onToggleMenu,
}: {
  busyKey: string | null;
  canDeleteAllComments: boolean;
  commentDraft: string;
  comments: GuestVisitComment[];
  commentsOpen: boolean;
  currentUserId?: number | null;
  isMenuOpen: boolean;
  menuRef: RefObject<HTMLDivElement | null> | null;
  visit: GuestVisit;
  onActionDialog: (kind: ActionKind) => void;
  onAddComment: (visit: GuestVisit) => void | Promise<void>;
  onCommentDraftChange: (visitId: number, value: string) => void;
  onDeleteComment: (visit: GuestVisit, commentId: number) => void | Promise<void>;
  onEdit: (visit: GuestVisit) => void;
  onLinkTask: (visit: GuestVisit) => void;
  onOpen: (visit: GuestVisit) => void | Promise<void>;
  onOpenGuestPhoto: (guest: Guest) => void;
  onRunAction: (visit: GuestVisit, action: "submit" | "sync") => void | Promise<void>;
  onToggleComments: (visit: GuestVisit) => void | Promise<void>;
  onToggleMenu: (visitId: number | null) => void;
}) {
  const period = visit.unlimited
    ? "Бессрочно"
    : `${formatDateTime(visit.access_starts_at) || "—"} - ${formatDateTime(visit.access_expires_at) || "—"}`;

  return (
    <article className={`app-surface-muted rounded-xl p-4 transition hover:shadow-[var(--shadow-card)] ${isMenuOpen ? "relative z-20 overflow-visible" : ""}`}>
      <div className="flex min-w-0 gap-3">
        <div className="flex shrink-0 flex-col items-center gap-3">
          <button
            type="button"
            onClick={() => onOpenGuestPhoto(visit.guest)}
            className="self-start rounded-full text-left"
            title="Открыть фото гостя"
          >
            <GuestAvatar guest={visit.guest} />
          </button>
          <button
            type="button"
            title={`Комментарии (${visit.comments_count || comments.length})`}
            onClick={() => void onToggleComments(visit)}
            className={`app-action-secondary relative inline-flex h-8 w-8 items-center justify-center rounded-lg ${commentsOpen ? "app-pill-active" : ""}`}
          >
            <MessageSquare size={15} />
            {(visit.comments_count || comments.length) > 0 ? (
              <span className={`${visit.has_unread_info_response ? "app-counter-danger" : "app-counter"} absolute -right-1.5 -top-1.5 flex h-4 min-w-4 px-1 text-[10px] font-bold`}>
                {visit.comments_count || comments.length}
              </span>
            ) : null}
          </button>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <button type="button" onClick={() => void onOpen(visit)} className="min-w-0 flex-1 text-left">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <GuestAccessStatusBadge guest={visit.guest} />
                {visit.inviter_inactive ? (
                  <span className="app-feedback-warning inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium">
                    <AlertTriangle size={12} />
                    Риск
                  </span>
                ) : null}
              </div>
            </button>
            <VisitActionButtons
              busyKey={busyKey}
              isMenuOpen={isMenuOpen}
              menuRef={menuRef}
              variant="list"
              visit={visit}
              onActionDialog={onActionDialog}
              onEdit={onEdit}
              onLinkTask={onLinkTask}
              onRunAction={onRunAction}
              onToggleMenu={onToggleMenu}
            />
          </div>
          <button type="button" onClick={() => void onOpen(visit)} className="block w-full min-w-0 text-left">
            <h2 className="mt-2 truncate text-base font-semibold text-[var(--foreground)]">{guestName(visit.guest)}</h2>
            <div className="app-text-muted mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <span className="inline-flex items-center gap-1"><CalendarDays size={13} />{period}</span>
              <span className="inline-flex items-center gap-1"><IdCard size={13} />{visit.guest.id}</span>
              {visit.guest.organization ? <span>{visit.guest.organization}</span> : null}
              <span>Приглашающий: {displayUserName(visit.inviter, visit.inviter_snapshot_name, visit.inviter_snapshot_email)}</span>
            </div>
            <p className="app-text-muted mt-2 line-clamp-2 text-sm">{visit.purpose}</p>
          </button>
          <LinkedTaskPills tasks={visit.linked_tasks} className="mt-2" />
          {visit.documents?.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {visit.documents.map((document) => {
                const label = document.title || document.file_name || `Документ #${document.id}`;
                const content = (
                  <>
                    <FileText size={12} className="shrink-0" />
                    <span className="min-w-0 truncate">{label}</span>
                  </>
                );

                return document.file_url ? (
                  <a
                    key={document.id}
                    href={resolveMediaUrl(document.file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="app-badge inline-flex max-w-[150px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium no-underline transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] hover:no-underline lg:max-w-[180px]"
                    title={label}
                  >
                    {content}
                  </a>
                ) : (
                  <span
                    key={document.id}
                    className="app-badge inline-flex max-w-[150px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium lg:max-w-[180px]"
                    title={label}
                  >
                    {content}
                  </span>
                );
              })}
            </div>
          ) : null}
          <VisitQuickActionButtons
            busyKey={busyKey}
            visit={visit}
            onActionDialog={onActionDialog}
            onRunAction={onRunAction}
          />
        </div>
      </div>
      {commentsOpen ? (
        <GuestVisitCommentsPanel
          busyKey={busyKey}
          canDeleteAllComments={canDeleteAllComments}
          commentDraft={commentDraft}
          comments={comments}
          currentUserId={currentUserId}
          visit={visit}
          onAddComment={onAddComment}
          onCommentDraftChange={onCommentDraftChange}
          onDeleteComment={onDeleteComment}
        />
      ) : null}
    </article>
  );
}

function GuestVisitCommentsPanel({
  busyKey,
  canDeleteAllComments,
  commentDraft,
  comments,
  currentUserId,
  visit,
  onAddComment,
  onCommentDraftChange,
  onDeleteComment,
}: {
  busyKey: string | null;
  canDeleteAllComments: boolean;
  commentDraft: string;
  comments: GuestVisitComment[];
  currentUserId?: number | null;
  visit: GuestVisit;
  onAddComment: (visit: GuestVisit) => void | Promise<void>;
  onCommentDraftChange: (visitId: number, value: string) => void;
  onDeleteComment: (visit: GuestVisit, commentId: number) => void | Promise<void>;
}) {
  return (
    <div className="app-surface-elevated mt-4 rounded-xl p-3">
      <div className="space-y-2">
        {comments.length === 0 ? (
          <p className="app-text-muted text-xs">Комментариев пока нет</p>
        ) : comments.map((comment) => {
          const canDelete = canDeleteAllComments || comment.author?.id === currentUserId;
          return (
            <div key={comment.id} className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-medium">{displayUserName(comment.author)}</span>
                <div className="flex items-center gap-2">
                  <span className="app-text-muted">{formatDateTime(comment.created_at)}</span>
                  {canDelete ? (
                    <CommentDeleteButton
                      disabled={busyKey === `comment-delete-${comment.id}`}
                      onClick={() => onDeleteComment(visit, comment.id)}
                    />
                  ) : null}
                </div>
              </div>
              <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-2">
        <CommentComposer
          value={commentDraft}
          onChange={(value) => onCommentDraftChange(visit.id, value)}
          onSubmit={() => onAddComment(visit)}
          disabled={busyKey === `comment-${visit.id}`}
        />
      </div>
    </div>
  );
}

function VisitQuickActionButtons({
  busyKey,
  visit,
  onActionDialog,
  onRunAction,
}: {
  busyKey: string | null;
  visit: GuestVisit;
  onActionDialog: (kind: ActionKind) => void;
  onRunAction: (visit: GuestVisit, action: "submit" | "sync") => void | Promise<void>;
}) {
  const canSubmit = canSubmitGuestVisit(visit);
  const canApprove = canApproveGuestVisit(visit);
  const canSubmitDirectly = canSubmit && visit.status !== "needs_info";
  const canProvideInfo = visit.status === "needs_info" && canSubmit;
  if (!canSubmitDirectly && !canProvideInfo && !canApprove && !visit.can_reject) return null;

  return (
    <div className="mt-3 flex items-center justify-end gap-1.5">
      {canSubmitDirectly ? (
        <button
          type="button"
          onClick={() => void onRunAction(visit, "submit")}
          disabled={busyKey === `submit-${visit.id}`}
          className="app-action-primary inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
          title="Отправить"
        >
          {busyKey === `submit-${visit.id}` ? <Loader2 className="animate-spin" size={15} /> : <Send size={15} />}
        </button>
      ) : null}
      {canProvideInfo ? (
        <button
          type="button"
          onClick={() => onActionDialog("provide-info")}
          className="app-action-approval inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
          title="Предоставить информацию"
        >
          <MessageSquare size={16} />
        </button>
      ) : null}
      {canApprove ? (
          <button
            type="button"
            onClick={() => onActionDialog("approve")}
            className="app-action-approve inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
            title="Одобрить"
          >
            <ThumbsUp size={18} className="text-emerald-500" />
          </button>
      ) : null}
      {visit.can_reject ? (
          <button
            type="button"
            onClick={() => onActionDialog("reject")}
            className="app-action-reject inline-flex h-9 w-9 items-center justify-center rounded-lg disabled:opacity-60"
            title="Отклонить"
          >
            <ThumbsDown size={18} />
          </button>
      ) : null}
    </div>
  );
}

function VisitActionButtons({
  busyKey,
  isMenuOpen = false,
  menuRef = null,
  showLabels = false,
  variant = "full",
  visit,
  onActionDialog,
  onEdit,
  onLinkTask,
  onRunAction,
  onToggleMenu,
}: {
  busyKey: string | null;
  isMenuOpen?: boolean;
  menuRef?: RefObject<HTMLDivElement | null> | null;
  showLabels?: boolean;
  variant?: "full" | "list";
  visit: GuestVisit;
  onActionDialog: (kind: ActionKind) => void;
  onEdit: (visit: GuestVisit) => void;
  onLinkTask: (visit: GuestVisit) => void;
  onRunAction: (visit: GuestVisit, action: "submit" | "sync") => void | Promise<void>;
  onToggleMenu?: (visitId: number | null) => void;
}) {
  const buttonClass = (variantClass: string) =>
    `${variantClass} inline-flex h-9 items-center justify-center rounded-lg disabled:opacity-60 ${
      showLabels ? "gap-1.5 px-3 text-xs font-medium" : "w-9"
    }`;
  const label = (text: string) => (showLabels ? <span>{text}</span> : null);
  const approvalIconSize = showLabels ? 14 : 18;

  if (variant === "full") {
    return (
      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        {canApproveGuestVisit(visit) ? (
          <button type="button" onClick={() => onActionDialog("approve")} className={buttonClass("app-action-approve")} title="Одобрить">
            <ThumbsUp size={approvalIconSize} className="text-emerald-500" />
            {showLabels ? <span className="text-emerald-500">Одобрить</span> : null}
          </button>
        ) : null}
        {visit.can_reject ? (
          <button type="button" onClick={() => onActionDialog("reject")} className={buttonClass("app-action-reject")} title="Отклонить">
            <ThumbsDown size={approvalIconSize} />
            {label("Отклонить")}
          </button>
        ) : null}
        {visit.can_request_info ? (
          <button type="button" onClick={() => onActionDialog("request-info")} className={buttonClass("app-action-secondary")} title="Запросить информацию">
            <Info size={14} />
            {label("Запросить информацию")}
          </button>
        ) : null}
      </div>
    );
  }

  const meta = statusMeta[visit.status] || { label: visit.status, className: "app-badge" };
  const hasSecondaryActions = true;

  return (
    <div className="flex shrink-0 flex-col items-start gap-2 lg:items-end">
      <div ref={isMenuOpen ? menuRef : null} className="flex items-center gap-2">
        <span className={`app-status-pill guest-status-pill ${meta.className}`}>{meta.label}</span>
        {hasSecondaryActions ? (
          <div className="relative">
            <button
              type="button"
              onClick={() => onToggleMenu?.(isMenuOpen ? null : visit.id)}
              className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-lg"
              title="Действия с заявкой"
              aria-label="Действия с заявкой"
              aria-expanded={isMenuOpen}
              aria-haspopup="menu"
            >
              <ChevronRight size={15} className={`transition-transform duration-200 ${isMenuOpen ? "rotate-90" : ""}`} />
            </button>
            {isMenuOpen ? (
              <div className="app-menu absolute right-0 top-full z-20 mt-2 w-56 rounded-xl py-1.5">
                <button
                  type="button"
                  onClick={() => {
                    onToggleMenu?.(null);
                    onLinkTask(visit);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                >
                  <Link2 size={14} className="app-text-muted" />
                  Связать с задачей
                </button>
                {visit.can_edit ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      onEdit(visit);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  >
                    <Pencil size={14} className="app-text-muted" />
                    Редактировать
                  </button>
                ) : null}
                {visit.can_request_info ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      onActionDialog("request-info");
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  >
                    <Info size={14} className="app-text-muted" />
                    Запросить информацию
                  </button>
                ) : null}
                {visit.can_revoke ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      onActionDialog("revoke");
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                  >
                    <Ban size={14} className="text-[var(--danger-foreground)]" />
                    Отозвать доступ
                  </button>
                ) : null}
                {visit.can_cancel ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      onActionDialog("cancel");
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  >
                    <XCircle size={14} className="app-text-muted" />
                    Отменить
                  </button>
                ) : null}
                {canReturnGuestVisitToWork(visit) ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      onActionDialog("return-to-work");
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                  >
                    <PlayCircle size={14} className="app-text-muted" />
                    Вернуть в работу
                  </button>
                ) : null}
                {visit.can_delete ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      onActionDialog("delete");
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
                  >
                    <Trash2 size={14} className="text-[var(--danger-foreground)]" />
                    Удалить заявку
                  </button>
                ) : null}
                {visit.can_sync_ldap ? (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleMenu?.(null);
                      void onRunAction(visit, "sync");
                    }}
                    disabled={busyKey === `sync-${visit.id}`}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                  >
                    {busyKey === `sync-${visit.id}` ? <Loader2 className="animate-spin app-text-muted" size={14} /> : <RefreshCcw size={14} className="app-text-muted" />}
                    Синхронизировать учетку
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

    </div>
  );
}

function VisitSecondaryActionsMenu({
  busyKey,
  visit,
  onActionDialog,
  onEdit,
  onLinkTask,
  onRunAction,
}: {
  busyKey: string | null;
  visit: GuestVisit;
  onActionDialog: (kind: ActionKind) => void;
  onEdit: (visit: GuestVisit) => void;
  onLinkTask: (visit: GuestVisit) => void;
  onRunAction: (visit: GuestVisit, action: "submit" | "sync") => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const hasActions = true;

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target;
      if (target instanceof Node && menuRef.current?.contains(target)) return;
      setOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [open]);

  if (!hasActions) return null;

  return (
    <div ref={menuRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-lg"
        title="Действия с заявкой"
        aria-label="Действия с заявкой"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <ChevronRight size={15} className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`} />
      </button>
      {open ? (
        <div className="app-menu absolute right-0 top-full z-30 mt-2 w-64 rounded-xl py-1.5">
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onLinkTask(visit);
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
          >
            <Link2 size={14} className="app-text-muted" />
            Связать с задачей
          </button>
          {canSubmitGuestVisit(visit) ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                void onRunAction(visit, "submit");
              }}
              disabled={busyKey === `submit-${visit.id}`}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
            >
              {busyKey === `submit-${visit.id}` ? <Loader2 className="animate-spin app-text-muted" size={14} /> : <Send size={14} className="app-text-muted" />}
              Отправить на рассмотрение
            </button>
          ) : null}
          {visit.can_edit ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onEdit(visit);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
            >
              <Pencil size={14} className="app-text-muted" />
              Редактировать
            </button>
          ) : null}
          {visit.status === "needs_info" && canSubmitGuestVisit(visit) ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onActionDialog("provide-info");
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
            >
              <MessageSquare size={14} className="app-text-muted" />
              Предоставить информацию
            </button>
          ) : null}
          {visit.can_revoke ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onActionDialog("revoke");
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
            >
              <Ban size={14} className="text-[var(--danger-foreground)]" />
              Отозвать доступ
            </button>
          ) : null}
          {canReturnGuestVisitToWork(visit) ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onActionDialog("return-to-work");
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
            >
              <PlayCircle size={14} className="app-text-muted" />
              Вернуть в работу
            </button>
          ) : null}
          {visit.can_cancel ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onActionDialog("cancel");
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
            >
              <XCircle size={14} className="app-text-muted" />
              Отменить
            </button>
          ) : null}
          {visit.can_delete ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onActionDialog("delete");
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)]"
            >
              <Trash2 size={14} className="text-[var(--danger-foreground)]" />
              Удалить заявку
            </button>
          ) : null}
          {visit.can_sync_ldap ? (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                void onRunAction(visit, "sync");
              }}
              disabled={busyKey === `sync-${visit.id}`}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
            >
              {busyKey === `sync-${visit.id}` ? <Loader2 className="animate-spin app-text-muted" size={14} /> : <RefreshCcw size={14} className="app-text-muted" />}
              Синхронизировать
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function guestAccessStatusMeta(guest: Guest): { label: string; className: string } {
  if (guest.is_blacklisted) {
    return { label: "Черный список", className: "app-feedback-danger" };
  }
  if (guest.is_active) {
    return { label: "Доступ есть", className: "app-feedback-success" };
  }
  return { label: "Нет доступа", className: "app-badge" };
}

function GuestAccessStatusBadge({ guest }: { guest: Guest }) {
  const meta = guestAccessStatusMeta(guest);
  return (
    <span className={`app-status-pill guest-status-pill ${meta.className}`}>
      {meta.label}
    </span>
  );
}

function GuestAvatar({
  guest,
  name,
  size = "md",
  src,
}: {
  guest?: Guest | null;
  name?: string;
  size?: "sm" | "md" | "lg";
  src?: string;
}) {
  const displayName = name || guestName(guest);
  const imageSrc = resolveMediaUrl(src ?? guest?.avatar ?? "");
  const sizeClass = size === "lg" ? "h-16 w-16 text-lg" : size === "sm" ? "h-10 w-10 text-xs" : "h-12 w-12 text-sm";
  const pixels = size === "lg" ? 64 : size === "sm" ? 40 : 48;

  return (
    <div className={`${imageSrc ? "app-avatar-frame" : "app-avatar-fallback"} flex ${sizeClass} shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold`}>
      {imageSrc ? (
        <Image
          src={imageSrc}
          alt={displayName}
          width={pixels}
          height={pixels}
          className="h-full w-full object-cover"
          unoptimized
        />
      ) : (
        guestInitials(displayName)
      )}
    </div>
  );
}

function GuestAvatarPicker({
  name,
  onSelectImage,
  value,
}: {
  name: string;
  onSelectImage: (value: string) => void;
  value: string;
}) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraStarting, setCameraStarting] = useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState("");

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      onSelectImage(await readFileAsDataUrl(file));
    } finally {
      event.target.value = "";
    }
  };

  const stopCamera = useCallback(() => {
    cameraStream?.getTracks().forEach((track) => track.stop());
    setCameraStream(null);
    setCameraStarting(false);
    setCameraOpen(false);
    setCameraError("");
  }, [cameraStream]);

  const openCamera = async () => {
    setCameraOpen(true);
    setCameraError("");
    setCameraStarting(true);

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera API is not available");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: "user" },
      });
      setCameraStream(stream);
    } catch {
      setCameraError("Не удалось открыть камеру. Проверьте разрешение браузера на доступ к камере.");
    } finally {
      setCameraStarting(false);
    }
  };

  const captureCameraImage = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) {
      setCameraError("Камера ещё не готова. Попробуйте ещё раз через секунду.");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) return;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const capturedImage = canvas.toDataURL("image/jpeg", 0.92);
    stopCamera();
    onSelectImage(capturedImage);
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !cameraStream) return;

    video.srcObject = cameraStream;
    void video.play().catch(() => {
      setCameraError("Не удалось запустить превью камеры.");
    });

    return () => {
      video.srcObject = null;
    };
  }, [cameraStream]);

  useEffect(() => (
    () => {
      cameraStream?.getTracks().forEach((track) => track.stop());
    }
  ), [cameraStream]);

  return (
    <div className="flex items-start gap-3 md:col-span-2">
      <GuestAvatar name={name || "Гость"} src={value} size="lg" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[var(--foreground)]">Фото гостя</p>
        <p className="app-text-muted mt-0.5 text-xs">Используется в учетке и связанных сервисах.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="app-action-secondary inline-flex h-9 items-center gap-2 rounded-lg px-3 text-xs font-medium"
          >
            <Upload size={14} />
            Выбрать файл
          </button>
          <button
            type="button"
            onClick={() => void openCamera()}
            disabled={cameraOpen || cameraStarting}
            className="app-action-secondary inline-flex h-9 items-center gap-2 rounded-lg px-3 text-xs font-medium disabled:opacity-60"
          >
            <Camera size={14} />
            Сделать фото
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" className="sr-only" onChange={handleFileChange} />
        </div>
        {cameraOpen ? (
          <div className="mt-3 overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
            <div className="relative aspect-[4/3] bg-black">
              {cameraStream ? (
                <video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full items-center justify-center px-4 text-center text-xs text-white/80">
                  {cameraStarting ? "Открываем камеру..." : "Камера не запущена"}
                </div>
              )}
            </div>
            {cameraError ? (
              <p className="app-feedback-danger m-2 rounded-lg px-3 py-2 text-xs">{cameraError}</p>
            ) : null}
            <div className="flex flex-wrap justify-end gap-2 p-2">
              <button type="button" onClick={stopCamera} className="app-action-secondary rounded-lg px-3 py-2 text-xs font-medium">
                Отмена
              </button>
              <button
                type="button"
                onClick={captureCameraImage}
                disabled={!cameraStream || cameraStarting}
                className="app-action-primary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium disabled:opacity-60"
              >
                <Camera size={13} />
                Сделать снимок
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function GuestVisitFormModal({
  busy,
  documents,
  documentsLoading,
  editingVisit,
  form,
  guestOptions,
  isOpen,
  onClose,
  onReloadDocuments,
  onSubmit,
  setForm,
}: {
  busy: boolean;
  documents: { id: number; name: string }[];
  documentsLoading: boolean;
  editingVisit: GuestVisit | null;
  form: GuestVisitFormState;
  guestOptions: { id: number; name: string }[];
  isOpen: boolean;
  onClose: () => void;
  onReloadDocuments: () => void | Promise<void>;
  onSubmit: () => void | Promise<void>;
  setForm: (updater: GuestVisitFormState | ((current: GuestVisitFormState) => GuestVisitFormState)) => void;
}) {
  const [step, setStep] = useState(0);
  const [guestAvatarCropperImage, setGuestAvatarCropperImage] = useState<string | null>(null);
  const [documentToAddId, setDocumentToAddId] = useState<number | null>(null);
  const documentFileInputRef = useRef<HTMLInputElement | null>(null);
  const setField = <K extends keyof GuestVisitFormState>(key: K, value: GuestVisitFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };
  const handleClose = () => {
    setGuestAvatarCropperImage(null);
    onClose();
  };

  const addExistingDocument = (id: number | null) => {
    if (!id) return;
    setDocumentToAddId(null);
    setForm((current) => current.document_ids.includes(id)
      ? current
      : { ...current, document_ids: [...current.document_ids, id] });
  };
  const removeExistingDocument = (id: number) => {
    setForm((current) => ({
      ...current,
      document_ids: current.document_ids.filter((item) => item !== id),
    }));
  };
  const addPendingDocuments = (files: FileList | null) => {
    if (!files?.length) return;
    const nextDocuments = Array.from(files).map(createPendingGuestDocument);
    setForm((current) => ({
      ...current,
      pending_documents: [...current.pending_documents, ...nextDocuments],
    }));
  };
  const updatePendingDocumentTitle = (localId: string, title: string) => {
    setForm((current) => ({
      ...current,
      pending_documents: current.pending_documents.map((item) => (
        item.localId === localId ? { ...item, title } : item
      )),
    }));
  };
  const removePendingDocument = (localId: string) => {
    setForm((current) => ({
      ...current,
      pending_documents: current.pending_documents.filter((item) => item.localId !== localId),
    }));
  };

  const isCreateMode = !editingVisit;
  const isLastStep = !isCreateMode || step === 2;
  const stepLabels = ["Гость", "Период", "Цель"];
  const [guestExtraOpen, setGuestExtraOpen] = useState(false);
  const filledGuestExtraCount = [
    form.patronymic,
    form.birth_date,
    form.email,
    form.organization,
    form.position,
    form.guest_comment,
  ].filter((value) => value.trim()).length;

  const documentsSection = (
    <div className="pt-1">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="app-text-muted text-xs font-medium">Документы</span>
        <button
          type="button"
          onClick={() => documentFileInputRef.current?.click()}
          className="app-link-accent inline-flex items-center gap-1 text-xs font-medium"
	                  >
	                    <Plus size={12} /> Загрузить файл
	                  </button>
        <input
          ref={documentFileInputRef}
          type="file"
          multiple
          hidden
          tabIndex={-1}
          onChange={(event) => {
            addPendingDocuments(event.target.files);
            event.target.value = "";
          }}
        />
      </div>
      <div className="mb-3 flex gap-2">
        <div className="min-w-0 flex-1">
          <SearchableSelectSingle
            label="Выбрать существующий"
            items={documents.filter((doc) => !form.document_ids.includes(doc.id))}
            selectedId={documentToAddId}
            onSelect={(id) => {
              setDocumentToAddId(id);
              addExistingDocument(id);
            }}
            placeholder="Найти документ"
          />
        </div>
        <button type="button" onClick={() => void onReloadDocuments()} className="app-action-secondary mt-5 h-10 rounded-lg px-3" title="Обновить документы">
          {documentsLoading ? <Loader2 className="animate-spin" size={15} /> : <Search size={15} />}
        </button>
      </div>
      <div className="space-y-2">
        {form.document_ids.map((documentId) => {
          const document = documents.find((item) => item.id === documentId);
          return (
            <div key={documentId} className="flex items-center gap-2">
              <input
                readOnly
                value={document?.name || `Документ #${documentId}`}
                className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => removeExistingDocument(documentId)}
                className="app-action-secondary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                title="Убрать документ"
              >
                <XCircle size={13} />
              </button>
            </div>
          );
        })}
        {form.pending_documents.map((document) => (
          <div key={document.localId} className="flex items-center gap-2">
            <input
              value={document.title}
              onChange={(event) => updatePendingDocumentTitle(document.localId, event.target.value)}
              className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-sm"
              placeholder="Название документа"
            />
            <span className="app-text-muted hidden w-20 shrink-0 text-right text-[11px] sm:block">{formatFileSize(document.file.size)}</span>
            <button
              type="button"
              onClick={() => removePendingDocument(document.localId)}
              className="app-action-secondary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
              title="Убрать файл"
            >
              <XCircle size={13} />
            </button>
          </div>
        ))}
        {form.document_ids.length === 0 && form.pending_documents.length === 0 ? (
          <p className="app-text-muted text-xs">Документы можно выбрать из реестра или загрузить новым файлом.</p>
        ) : null}
      </div>
    </div>
  );

  const guestSection = !editingVisit ? (
    <section className="app-surface-muted space-y-3 rounded-xl p-3">
      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setField("guestMode", "new")}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium ${form.guestMode === "new" ? "app-selected" : "app-action-ghost"}`}
        >
          Новый гость
        </button>
        <button
          type="button"
          onClick={() => setField("guestMode", "existing")}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium ${form.guestMode === "existing" ? "app-selected" : "app-action-ghost"}`}
        >
          Существующий
        </button>
      </div>
      {form.guestMode === "existing" ? (
        <SearchableSelectSingle
          label="Гость"
          items={guestOptions}
          selectedId={form.guest_id ? Number(form.guest_id) : null}
          onSelect={(id) => setField("guest_id", id ? String(id) : "")}
          placeholder="Выберите гостя"
        />
      ) : (
        <div className="space-y-3">
          <GuestAvatarPicker
            name={[form.last_name, form.first_name].filter(Boolean).join(" ")}
            value={form.avatar}
            onSelectImage={setGuestAvatarCropperImage}
          />
          <div className="grid grid-cols-2 gap-2 sm:gap-3">
            <TextField label="Фамилия" value={form.last_name} onChange={(value) => setField("last_name", value)} />
            <TextField label="Имя" value={form.first_name} onChange={(value) => setField("first_name", value)} required />
          </div>
          <TextField label="Телефон" value={form.phone} onChange={(value) => setField("phone", value)} />
        </div>
      )}
      {documentsSection}
      {form.guestMode === "new" ? (
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setGuestExtraOpen((value) => !value)}
            aria-expanded={guestExtraOpen}
            className="app-action-secondary flex h-10 w-full items-center justify-between rounded-lg px-3 text-sm font-medium"
          >
            <span>Дополнительные данные</span>
            <span className="flex items-center gap-2">
              {filledGuestExtraCount > 0 ? (
                <span className="app-badge rounded-full px-2 py-0.5 text-[11px]">{filledGuestExtraCount}</span>
              ) : null}
              <ChevronDown size={15} className={`transition ${guestExtraOpen ? "rotate-180" : ""}`} />
            </span>
          </button>
          {guestExtraOpen ? (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <TextField label="Отчество" value={form.patronymic} onChange={(value) => setField("patronymic", value)} />
              <TextField label="Дата рождения" value={form.birth_date} onChange={(value) => setField("birth_date", value)} type="date" />
              <TextField label="Email" value={form.email} onChange={(value) => setField("email", value)} type="email" />
              <TextField label="Организация" value={form.organization} onChange={(value) => setField("organization", value)} />
              <TextField label="Должность" value={form.position} onChange={(value) => setField("position", value)} />
              <label className="sm:col-span-2">
                <span className="app-text-muted mb-1 block text-xs font-medium">Комментарий по гостю</span>
                <textarea value={form.guest_comment} onChange={(event) => setField("guest_comment", event.target.value)} rows={2} className="app-input w-full resize-none rounded-lg p-3 text-sm" />
              </label>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  ) : (
    <section className="app-surface-muted space-y-3 rounded-xl p-3">
      <p className="text-sm font-semibold text-[var(--foreground)]">{guestName(editingVisit.guest)}</p>
      <p className="app-text-muted mt-1 text-xs">Данные гостя редактируются администратором в реестре гостей.</p>
      {documentsSection}
    </section>
  );

  const periodSection = (
    <div className="space-y-4">
      <section className="app-surface-muted rounded-xl p-3">
        <p className="mb-3 text-sm font-semibold text-[var(--foreground)]">Период доступа</p>
        <div className="mb-3 flex flex-wrap gap-2">
          <label className="app-badge flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-xs">
            <input type="checkbox" checked={form.all_day} onChange={(event) => setField("all_day", event.target.checked)} />
            Полные сутки
          </label>
          <label className="app-badge flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-xs">
            <input type="checkbox" checked={form.unlimited} onChange={(event) => setField("unlimited", event.target.checked)} />
            Бессрочно
          </label>
        </div>
        {!form.unlimited ? (
          form.all_day ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Дата с" value={form.date_from} onChange={(value) => setField("date_from", value)} type="date" />
              <TextField label="Дата по" value={form.date_to} onChange={(value) => setField("date_to", value)} type="date" />
            </div>
          ) : (
            <div className="grid gap-3">
              <TextField label="Начало" value={form.access_starts_at} onChange={(value) => setField("access_starts_at", value)} type="datetime-local" />
              <TextField label="Окончание" value={form.access_expires_at} onChange={(value) => setField("access_expires_at", value)} type="datetime-local" />
            </div>
          )
        ) : (
          <p className="app-text-muted text-xs">Дата окончания не требуется.</p>
        )}
      </section>
    </div>
  );

  const purposeSection = (
    <section className="grid gap-3 md:grid-cols-2">
      <label className="md:col-span-2">
        <span className="app-text-muted mb-1 block text-xs font-medium">Цель приглашения</span>
        <textarea value={form.purpose} onChange={(event) => setField("purpose", event.target.value)} rows={5} className="app-input w-full resize-none rounded-lg p-3 text-sm" />
      </label>
    </section>
  );

  return (
    <>
      <Modal
      isOpen={isOpen}
      onClose={handleClose}
      closeOnEsc={!guestAvatarCropperImage}
      title={editingVisit ? "Редактирование гостевой заявки" : "Новая заявка на гостевой визит"}
      size="xl"
      footer={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button type="button" onClick={handleClose} className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium">Отмена</button>
          {isCreateMode && step > 0 ? (
            <button
              type="button"
              onClick={() => setStep((current) => Math.max(0, current - 1))}
              disabled={busy}
              className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              Назад
            </button>
          ) : null}
          {isCreateMode && !isLastStep ? (
            <button
              type="button"
              onClick={() => setStep((current) => Math.min(2, current + 1))}
              disabled={busy}
              className="app-action-primary rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              Далее
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void onSubmit()}
              disabled={busy}
              className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {busy ? <Loader2 className="animate-spin" size={15} /> : null}
              {editingVisit ? "Сохранить" : "Создать заявку"}
            </button>
          )}
        </div>
      }
    >
      {isCreateMode ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {stepLabels.map((label, index) => (
              <button
                key={label}
                type="button"
                onClick={() => setStep(index)}
                className={`inline-flex h-9 items-center gap-2 rounded-full px-3 text-xs font-medium transition ${step === index ? "app-pill-active" : "app-pill"}`}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface-elevated)] text-[11px]">{index + 1}</span>
                {label}
              </button>
            ))}
          </div>
          {step === 0 ? guestSection : step === 1 ? periodSection : purposeSection}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
          <div className="space-y-4">
            {guestSection}
            {purposeSection}
          </div>
          {periodSection}
        </div>
      )}
      </Modal>

      {guestAvatarCropperImage ? (
        <AvatarCropper
          initialImage={guestAvatarCropperImage}
          onCropComplete={(croppedImage) => {
            setField("avatar", croppedImage);
            setGuestAvatarCropperImage(null);
          }}
          onCancel={() => setGuestAvatarCropperImage(null)}
        />
      ) : null}
    </>
  );
}

function GuestVisitDetailModal({
  busyKey,
  comments,
  visit,
  onActionDialog,
  onAddComment,
  onClose,
  onDeleteComment,
  onEdit,
  onLinkTask,
  onRunAction,
}: {
  busyKey: string | null;
  comments: GuestVisitComment[];
  visit: GuestVisit | null;
  onActionDialog: (kind: ActionKind, visit: GuestVisit) => void;
  onAddComment: (visit: GuestVisit, text: string) => void | Promise<void>;
  onClose: () => void;
  onDeleteComment: (visit: GuestVisit, commentId: number) => void | Promise<void>;
  onEdit: (visit: GuestVisit) => void;
  onLinkTask: (visit: GuestVisit) => void;
  onRunAction: (visit: GuestVisit, action: "submit" | "sync") => void | Promise<void>;
}) {
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});

  if (!visit) return null;
  const commentDraft = commentDrafts[visit.id] || "";
  const setCommentDraft = (value: string) => {
    setCommentDrafts((current) => ({ ...current, [visit.id]: value }));
  };
  const meta = statusMeta[visit.status] || { label: visit.status, className: "app-badge" };
  const hasDecisionActions = canApproveGuestVisit(visit)
    || visit.can_reject
    || visit.can_request_info;

  return (
    <Modal
      isOpen={Boolean(visit)}
      onClose={onClose}
      title={`Гостевой визит #${visit.id}`}
      size="xl"
      footer={hasDecisionActions ? (
        <div className="flex justify-end">
          <VisitActionButtons
            busyKey={busyKey}
            showLabels
            visit={visit}
            onActionDialog={(kind) => onActionDialog(kind, visit)}
            onEdit={onEdit}
            onLinkTask={onLinkTask}
            onRunAction={onRunAction}
          />
        </div>
      ) : null}
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <section className="app-surface-muted rounded-xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 gap-3">
                <GuestAvatar guest={visit.guest} size="lg" />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`app-status-pill guest-status-pill ${meta.className}`}>{meta.label}</span>
                    <GuestAccessStatusBadge guest={visit.guest} />
                    {visit.is_active_now ? (
                      <span className="app-status-pill guest-status-pill app-feedback-success">
                        Доступ действует
                      </span>
                    ) : null}
                    {visit.inviter_inactive ? <span className="app-feedback-warning rounded-full px-2.5 py-1 text-xs">Приглашающий неактивен</span> : null}
                  </div>
                  <h2 className="mt-3 text-xl font-semibold text-[var(--foreground)]">{guestName(visit.guest)}</h2>
                  {visit.guest.organization ? (
                    <p className="app-text-muted mt-1 text-sm">{visit.guest.organization}</p>
                  ) : null}
                </div>
              </div>
              <VisitSecondaryActionsMenu
                busyKey={busyKey}
                visit={visit}
                onActionDialog={(kind) => onActionDialog(kind, visit)}
                onEdit={onEdit}
                onLinkTask={onLinkTask}
                onRunAction={onRunAction}
              />
            </div>
          </section>

          <section className="grid gap-3 md:grid-cols-2">
            <InfoBlock icon={<IdCard size={16} />} title="Гость">
              <InfoLine label="ID" value={String(visit.guest.id)} />
              <InfoLine label="Телефон" value={visit.guest.phone || "—"} />
              <InfoLine label="Email" value={visit.guest.email || "—"} />
              <InfoLine label="Должность" value={visit.guest.position || "—"} />
            </InfoBlock>
            <InfoBlock icon={<CalendarDays size={16} />} title="Доступ">
              <InfoLine label="Начало" value={visit.unlimited ? "Бессрочно" : formatDateTime(visit.access_starts_at) || "—"} />
              <InfoLine label="Окончание" value={visit.unlimited ? "Бессрочно" : formatDateTime(visit.access_expires_at) || "—"} />
              <InfoLine label="Полные сутки" value={visit.all_day ? "Да" : "Нет"} />
              <InfoLine label="Бессрочно" value={visit.unlimited ? "Да" : "Нет"} />
            </InfoBlock>
            <InfoBlock icon={<ShieldAlert size={16} />} title="Учетка">
              <InfoLine label="Статус гостя" value={guestAccessStatusMeta(visit.guest).label} />
              <InfoLine label="Login" value={visit.guest.ldap_username || "—"} />
              <InfoLine label="UPN" value={visit.guest.ldap_upn || "—"} />
              <InfoLine label="Синхронизация" value={formatDateTime(visit.guest.ldap_last_synced_at) || "—"} />
              {visit.guest.ldap_last_error ? <p className="app-feedback-danger mt-2 rounded-lg p-2 text-xs">{visit.guest.ldap_last_error}</p> : null}
            </InfoBlock>
            <InfoBlock icon={<Clock size={16} />} title="Решение">
              <InfoLine label="Приглашающий" value={displayUserName(visit.inviter, visit.inviter_snapshot_name, visit.inviter_snapshot_email)} />
              <InfoLine label="Отправлено" value={formatDateTime(visit.submitted_at) || "—"} />
              <InfoLine label="Решил" value={displayUserName(visit.decided_by)} />
              <InfoLine label="Дата решения" value={formatDateTime(visit.decided_at) || "—"} />
              {visit.decision_comment ? <p className="app-text-muted mt-2 text-xs">{visit.decision_comment}</p> : null}
            </InfoBlock>
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <h3 className="mb-2 text-sm font-semibold text-[var(--foreground)]">Цель</h3>
            <p className="whitespace-pre-wrap text-sm text-[var(--foreground)]">{visit.purpose}</p>
            {visit.visit_comment ? <p className="app-text-muted mt-3 whitespace-pre-wrap text-sm">{visit.visit_comment}</p> : null}
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <div className="mb-3 flex items-center gap-2">
              <History size={16} className="app-text-muted" />
              <h3 className="text-sm font-semibold text-[var(--foreground)]">История</h3>
            </div>
            {visit.events.length === 0 ? (
              <p className="app-text-muted text-sm">Событий пока нет.</p>
            ) : (
              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {visit.events.map((event) => (
                  <div key={event.id} className="app-surface rounded-lg p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-[var(--foreground)]">{event.event_type}</span>
                      <span className="app-text-muted">{formatDateTime(event.created_at)}</span>
                    </div>
                    <p className="app-text-muted mt-1">
                      {displayUserName(event.actor)}{event.from_status || event.to_status ? ` · ${event.from_status || "—"} → ${event.to_status || "—"}` : ""}
                    </p>
                    {event.comment ? <p className="mt-1 text-[var(--foreground)]">{event.comment}</p> : null}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <aside className="space-y-4">
          <section className="app-surface-muted rounded-xl p-4">
            <div className="mb-3 flex items-center gap-2">
              <Link2 size={16} className="app-text-muted" />
              <h3 className="text-sm font-semibold text-[var(--foreground)]">Связанные задачи</h3>
            </div>
            <LinkedTaskPills tasks={visit.linked_tasks} max={4} />
            {visit.linked_tasks?.length ? null : (
              <p className="app-text-muted text-xs">Связанных задач нет.</p>
            )}
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <div className="mb-3 flex items-center gap-2">
              <div className="flex items-center gap-2">
                <FileText size={16} className="app-text-muted" />
                <h3 className="text-sm font-semibold text-[var(--foreground)]">Документы</h3>
              </div>
            </div>
            {visit.documents.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {visit.documents.map((doc) => {
                  const label = doc.title || doc.file_name || `Документ #${doc.id}`;
                  const content = (
                    <>
                      <FileText size={12} className="shrink-0" />
                      <span className="min-w-0 truncate">{label}</span>
                    </>
                  );

                  return doc.file_url ? (
                    <a
                      key={doc.id}
                      href={resolveMediaUrl(doc.file_url)}
                      target="_blank"
                      rel="noreferrer"
                      className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium no-underline transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] hover:no-underline"
                      title={label}
                    >
                      {content}
                    </a>
                  ) : (
                    <span
                      key={doc.id}
                      className="app-badge inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium"
                      title={label}
                    >
                      {content}
                    </span>
                  );
                })}
              </div>
            ) : (
              <p className="app-text-muted text-xs">Документы не прикреплены.</p>
            )}
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <div className="mb-3 flex items-center gap-2">
              <MessageSquare size={16} className="app-text-muted" />
              <h3 className="text-sm font-semibold text-[var(--foreground)]">Комментарии</h3>
            </div>
            <div className="mb-3 max-h-72 space-y-2 overflow-y-auto pr-1">
              {comments.length === 0 ? (
                <p className="app-text-muted text-sm">Комментариев пока нет.</p>
              ) : comments.map((comment) => (
                <div key={comment.id} className="app-surface rounded-lg p-3 text-sm">
                  <div className="mb-1 flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-[var(--foreground)]">{displayUserName(comment.author)}</p>
                      <p className="app-text-muted text-[11px]">{formatDateTime(comment.created_at)}</p>
                    </div>
                    <CommentDeleteButton
                      disabled={busyKey === `comment-delete-${comment.id}`}
                      onClick={() => onDeleteComment(visit, comment.id)}
                    />
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{comment.text}</p>
                </div>
              ))}
            </div>
            <CommentComposer
              multiline
              rows={2}
              value={commentDraft}
              onChange={setCommentDraft}
              onSubmit={async () => {
                const text = commentDraft.trim();
                if (!text) return;
                await onAddComment(visit, text);
                setCommentDraft("");
              }}
              disabled={busyKey === `comment-${visit.id}`}
            />
          </section>
        </aside>
      </div>
    </Modal>
  );
}

function ActionCommentModal({
  action,
  busyKey,
  comment,
  onClose,
  onCommentChange,
  onSubmit,
}: {
  action: { kind: ActionKind; visit: GuestVisit } | null;
  busyKey: string | null;
  comment: string;
  onClose: () => void;
  onCommentChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
}) {
  if (!action) return null;
  const titleMap: Record<ActionKind, string> = {
    approve: "Одобрить гостевой визит",
    reject: "Отклонить гостевой визит",
    "request-info": "Запросить информацию",
    "provide-info": "Предоставить информацию",
    cancel: "Отменить гостевой визит",
    revoke: "Отозвать доступ",
    "return-to-work": "Вернуть заявку в работу",
    delete: "Удалить заявку",
  };
  const isDelete = action.kind === "delete";
  const required = action.kind === "request-info" || action.kind === "provide-info";
  return (
    <Modal
      isOpen
      onClose={onClose}
      title={titleMap[action.kind]}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium">Отмена</button>
          <button
            type="button"
            onClick={() => void onSubmit()}
            disabled={busyKey === `${action.kind}-${action.visit.id}` || (required && !comment.trim())}
            className={`${isDelete ? "app-action-danger" : "app-action-primary"} inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60`}
          >
            {busyKey === `${action.kind}-${action.visit.id}` ? <Loader2 className="animate-spin" size={15} /> : null}
            {isDelete ? "Удалить" : "Выполнить"}
          </button>
        </div>
      }
    >
      {isDelete ? (
        <p className="app-text-muted text-sm">
          Заявка будет удалена. Доступ гостя будет пересчитан по оставшимся одобренным заявкам.
        </p>
      ) : (
        <label>
          <span className="app-text-muted mb-1 block text-xs font-medium">Комментарий{required ? " *" : ""}</span>
          <textarea value={comment} onChange={(event) => onCommentChange(event.target.value)} rows={4} className="app-input w-full resize-none rounded-lg p-3 text-sm" />
        </label>
      )}
    </Modal>
  );
}

function FeedbackModal({
  closeLabel = "Понятно",
  continueLabel,
  message,
  onClose,
  onContinue,
  title = "Предупреждение",
  variant = "danger",
}: {
  closeLabel?: string;
  continueLabel?: string;
  message: string | null;
  onClose: () => void;
  onContinue?: () => void;
  title?: string;
  variant?: "danger" | "warning";
}) {
  useEffect(() => {
    if (!message) return;

    const handleEsc = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      onClose();
    };

    document.addEventListener("keydown", handleEsc, true);
    return () => document.removeEventListener("keydown", handleEsc, true);
  }, [message, onClose]);

  if (!message) return null;

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={title}
      size="sm"
      closeOnEsc={false}
      footer={
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className={`${onContinue ? "app-action-secondary" : "app-action-primary"} rounded-lg px-4 py-2 text-sm font-medium`}
          >
            {closeLabel}
          </button>
          {onContinue ? (
            <button
              type="button"
              onClick={onContinue}
              className="app-action-primary rounded-lg px-4 py-2 text-sm font-medium"
            >
              {continueLabel || "Продолжить"}
            </button>
          ) : null}
        </div>
      }
    >
      <div className={`${variant === "warning" ? "app-feedback-warning" : "app-feedback-danger"} flex items-start gap-3 rounded-xl p-4 text-sm`}>
        <AlertTriangle size={18} className="mt-0.5 shrink-0" />
        <p className="min-w-0">{message}</p>
      </div>
    </Modal>
  );
}

function GuestRegistryPanel({
  blacklistFilter,
  activeFiltersCount,
  busyKey,
  canDeleteAllComments,
  canEditGuests,
  canManageLdap,
  commentDrafts,
  commentsByGuest,
  commentsOpenId,
  currentUserId,
  filtersOpen,
  guestSearch,
  guests,
  loading,
  ordering,
  placementFilter,
  onBlacklistFilterChange,
  onAddComment,
  onClearFilters,
  onCommentDraftChange,
  onDeleteComment,
  onEditGuest,
  onLinkTask,
  onOpenGuest,
  onOpenGuestPhoto,
  onOpenGuestVisits,
  onGuestSearchChange,
  onOrderingChange,
  onPlacementFilterChange,
  onRunGuestAction,
  onToggleComments,
  onToggleFilters,
}: {
  blacklistFilter: string;
  activeFiltersCount: number;
  busyKey: string | null;
  canDeleteAllComments: boolean;
  canEditGuests: boolean;
  canManageLdap: boolean;
  commentDrafts: Record<number, string>;
  commentsByGuest: Record<number, GuestVisitComment[]>;
  commentsOpenId: number | null;
  currentUserId?: number | null;
  filtersOpen: boolean;
  guestSearch: string;
  guests: Guest[];
  loading: boolean;
  ordering: string;
  placementFilter: string;
  onBlacklistFilterChange: (value: string) => void;
  onAddComment: (guest: Guest) => void | Promise<void>;
  onClearFilters: () => void;
  onCommentDraftChange: (guestId: number, value: string) => void;
  onDeleteComment: (guest: Guest, commentId: number) => void | Promise<void>;
  onEditGuest: (guest: Guest) => void;
  onLinkTask: (guest: Guest) => void;
  onOpenGuest: (guest: Guest) => void;
  onOpenGuestPhoto: (guest: Guest) => void;
  onOpenGuestVisits: (guest: Guest) => void;
  onGuestSearchChange: (value: string) => void;
  onOrderingChange: (value: string) => void;
  onPlacementFilterChange: (value: string) => void;
  onRunGuestAction: (guest: Guest, action: "sync" | "blacklist" | "unblacklist") => void | Promise<void>;
  onToggleComments: (guest: Guest) => void | Promise<void>;
  onToggleFilters: () => void;
}) {
  const [guestMenuOpenId, setGuestMenuOpenId] = useState<number | null>(null);
  const guestMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (guestMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target;
      if (target instanceof Node && guestMenuRef.current?.contains(target)) return;
      setGuestMenuOpenId(null);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [guestMenuOpenId]);

  return (
    <section className="app-surface rounded-2xl p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={guestSearch}
            onChange={(event) => onGuestSearchChange(event.target.value)}
            className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            placeholder="Поиск по гостям..."
          />
        </div>
        <button
          type="button"
          title="Фильтры"
          onClick={onToggleFilters}
          className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${filtersOpen ? "app-selected app-accent-text" : "app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]"}`}
        >
          <Filter size={16} />
          {activeFiltersCount > 0 ? (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">{activeFiltersCount}</span>
          ) : null}
        </button>
        <div className="relative w-full shrink-0 sm:w-[172px]">
          <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <select
            value={ordering}
            onChange={(event) => onOrderingChange(event.target.value)}
            className="app-select w-full appearance-none rounded-lg py-2.5 pl-9 pr-8 text-xs font-medium"
            aria-label="Сортировка гостей"
          >
            {guestOrderingOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
        </div>
      </div>

      {filtersOpen ? (
        <div className="app-surface-muted mt-3 grid grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))] gap-3 rounded-xl border border-[var(--border-subtle)] p-3">
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Черный список</span>
            <select
              value={blacklistFilter}
              onChange={(event) => onBlacklistFilterChange(event.target.value)}
              className="app-select h-10 w-full rounded-lg px-3 text-sm"
            >
              <option value="">Любой</option>
              <option value="false">Не в черном списке</option>
              <option value="true">В черном списке</option>
            </select>
          </label>
          <label className="block min-w-0">
            <span className="app-text-muted mb-1 block text-xs font-medium">Доступ</span>
            <select
              value={placementFilter}
              onChange={(event) => onPlacementFilterChange(event.target.value)}
              className="app-select h-10 w-full rounded-lg px-3 text-sm"
            >
              <option value="">Любой</option>
              <option value="true">Доступ есть</option>
              <option value="false">Нет доступа</option>
            </select>
          </label>
          <div className="flex min-w-0 items-end">
            <button
              type="button"
              onClick={onClearFilters}
              className="app-action-secondary h-10 w-full rounded-lg px-3 text-sm font-medium"
            >
              Сбросить
            </button>
          </div>
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {loading ? (
          <div className="app-surface-muted rounded-xl p-8 text-center">
            <Loader2 className="mx-auto animate-spin app-accent-text" size={26} />
            <p className="app-text-muted mt-2 text-sm">Загрузка гостей...</p>
          </div>
        ) : guests.length === 0 ? (
          <div className="app-surface-muted rounded-xl p-8 text-center text-sm app-text-muted">Гости не найдены</div>
        ) : guests.map((guest) => {
          const metaItems = [
            { label: "ID", value: String(guest.id), icon: IdCard, always: true },
            { label: "Организация", value: normalizeGuestMeta(guest.organization), icon: Building2 },
            { label: "Должность", value: normalizeGuestMeta(guest.position), icon: BriefcaseBusiness },
            { label: "Email", value: normalizeGuestMeta(guest.email), icon: Mail },
            { label: "Телефон", value: normalizeGuestMeta(guest.phone), icon: Phone },
          ].filter((item) => item.always || Boolean(item.value));
          const hasActions = true;
          const isGuestMenuOpen = guestMenuOpenId === guest.id;
          const commentsForGuest = commentsByGuest[guest.id] || [];
          const visibleCommentsCount = guest.comments_count || commentsForGuest.length;
          const visitsCount = guest.visits_count ?? 0;
          const isGuestCommentsOpen = commentsOpenId === guest.id;

          return (
            <article key={guest.id} className={`app-surface-muted rounded-xl p-4 ${isGuestMenuOpen ? "relative z-20 overflow-visible" : ""}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-1 gap-3">
                  <div className="relative w-12 shrink-0">
                    <button
                      type="button"
                      onClick={() => onOpenGuestPhoto(guest)}
                      className="rounded-full text-left"
                      title="Открыть фото гостя"
                    >
                      <GuestAvatar guest={guest} />
                    </button>
                    <button
                      type="button"
                      title={`Комментарии (${visibleCommentsCount})`}
                      onClick={() => void onToggleComments(guest)}
                      className={`app-action-secondary absolute left-1/2 top-14 inline-flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-lg ${isGuestCommentsOpen ? "app-pill-active" : ""}`}
                    >
                      <MessageSquare size={15} />
                      {visibleCommentsCount > 0 ? (
                        <span className="app-counter absolute -right-1.5 -top-1.5 flex h-4 min-w-4 px-1 text-[10px] font-bold">
                          {visibleCommentsCount}
                        </span>
                      ) : null}
                    </button>
                  </div>
                  <div className="min-w-0 flex-1">
                    <button
                      type="button"
                      onClick={() => onOpenGuest(guest)}
                      className="block max-w-full min-w-0 text-left"
                      title="Открыть карточку гостя"
                    >
                      <h3 className="truncate text-base font-semibold text-[var(--foreground)]">{guestName(guest)}</h3>
                    </button>
                    <div className="app-text-muted mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                      {metaItems.map((item) => {
                        const Icon = item.icon;
                        return (
                          <span
                            key={item.label}
                            className="inline-flex max-w-full min-w-0 items-center gap-1"
                            title={`${item.label}: ${item.value}`}
                          >
                            <Icon size={13} className="shrink-0" />
                            <span className="min-w-0 break-all text-[var(--foreground)]/80">{item.value}</span>
                          </span>
                        );
                      })}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <button
                        type="button"
                        onClick={() => onOpenGuestVisits(guest)}
                        className="app-feedback-notify inline-flex max-w-[150px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium transition hover:border-violet-400/60 hover:text-violet-600 lg:max-w-[180px]"
                        title={`Открыть заявки гостя: ${visitsCount}`}
                      >
                        <FileText size={12} className="shrink-0" />
                        <span className="min-w-0 truncate">Заявки {visitsCount}</span>
                      </button>
                    </div>
                    <LinkedTaskPills tasks={guest.linked_tasks} className="mt-2" />
                    {guest.ldap_last_error ? <p className="app-feedback-danger mt-2 rounded-lg p-2 text-xs">{guest.ldap_last_error}</p> : null}
                  </div>
                </div>
                <div ref={isGuestMenuOpen ? guestMenuRef : null} className="flex shrink-0 items-center gap-2">
                  <GuestAccessStatusBadge guest={guest} />
                  {hasActions ? (
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setGuestMenuOpenId(isGuestMenuOpen ? null : guest.id)}
                        className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-lg"
                        title="Действия с гостем"
                        aria-label="Действия с гостем"
                        aria-expanded={isGuestMenuOpen}
                        aria-haspopup="menu"
                      >
                        <ChevronRight size={15} className={`transition-transform duration-200 ${isGuestMenuOpen ? "rotate-90" : ""}`} />
                      </button>
                      {isGuestMenuOpen ? (
                        <div className="app-menu absolute right-0 top-full z-20 mt-2 w-56 rounded-xl py-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setGuestMenuOpenId(null);
                              onLinkTask(guest);
                            }}
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                          >
                            <Link2 size={14} className="app-text-muted" />
                            Связать с задачей
                          </button>
                          {canEditGuests ? (
                            <button
                              type="button"
                              onClick={() => {
                                setGuestMenuOpenId(null);
                                onEditGuest(guest);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)]"
                            >
                              <Pencil size={14} className="app-text-muted" />
                              Изменить
                            </button>
                          ) : null}
                          {canManageLdap ? (
                            <>
                              <button
                                type="button"
                                onClick={() => {
                                  setGuestMenuOpenId(null);
                                  void onRunGuestAction(guest, "sync");
                                }}
                                disabled={busyKey === `sync-guest-${guest.id}`}
                                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                              >
                                {busyKey === `sync-guest-${guest.id}` ? <Loader2 className="animate-spin app-text-muted" size={14} /> : <RefreshCcw size={14} className="app-text-muted" />}
                                Синхронизировать учетку
                              </button>
                              {guest.is_blacklisted ? (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setGuestMenuOpenId(null);
                                    void onRunGuestAction(guest, "unblacklist");
                                  }}
                                  disabled={busyKey === `unblacklist-guest-${guest.id}`}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--foreground)] transition hover:bg-[var(--surface-secondary)] disabled:opacity-50"
                                >
                                  {busyKey === `unblacklist-guest-${guest.id}` ? <Loader2 className="animate-spin app-text-muted" size={14} /> : <CheckCircle2 size={14} className="app-text-muted" />}
                                  Снять блокировку
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setGuestMenuOpenId(null);
                                    void onRunGuestAction(guest, "blacklist");
                                  }}
                                  disabled={busyKey === `blacklist-guest-${guest.id}`}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-[var(--danger-foreground)] transition hover:bg-[var(--danger-soft)] disabled:opacity-50"
                                >
                                  {busyKey === `blacklist-guest-${guest.id}` ? <Loader2 className="animate-spin text-[var(--danger-foreground)]" size={14} /> : <Ban size={14} className="text-[var(--danger-foreground)]" />}
                                  В черный список
                                </button>
                              )}
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
              {guest.documents?.length ? (
                <div className="mt-1 flex flex-wrap gap-1.5 pl-[60px]">
                  {(guest.documents || []).map((document) => {
                    const label = document.title || document.file_name || `Документ #${document.id}`;
                    const content = (
                      <>
                        <FileText size={12} className="shrink-0" />
                        <span className="min-w-0 truncate">{label}</span>
                      </>
                    );
                    return document.file_url ? (
                      <a
                        key={`doc-${document.id}`}
                        href={resolveMediaUrl(document.file_url)}
                        target="_blank"
                        rel="noreferrer"
                        className="app-badge inline-flex max-w-[150px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium no-underline transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] hover:no-underline lg:max-w-[180px]"
                        title={label}
                      >
                        {content}
                      </a>
                    ) : (
                      <span
                        key={`doc-${document.id}`}
                        className="app-badge inline-flex max-w-[150px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium lg:max-w-[180px]"
                        title={label}
                      >
                        {content}
                      </span>
                    );
                  })}
                </div>
              ) : null}
              {isGuestCommentsOpen ? (
                <GuestCommentsPanel
                  busyKey={busyKey}
                  canDeleteAllComments={canDeleteAllComments}
                  commentDraft={commentDrafts[guest.id] || ""}
                  comments={commentsForGuest}
                  currentUserId={currentUserId}
                  guest={guest}
                  onAddComment={onAddComment}
                  onCommentDraftChange={onCommentDraftChange}
                  onDeleteComment={onDeleteComment}
                />
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function GuestCommentsPanel({
  busyKey,
  canDeleteAllComments,
  commentDraft,
  comments,
  currentUserId,
  guest,
  onAddComment,
  onCommentDraftChange,
  onDeleteComment,
}: {
  busyKey: string | null;
  canDeleteAllComments: boolean;
  commentDraft: string;
  comments: GuestVisitComment[];
  currentUserId?: number | null;
  guest: Guest;
  onAddComment: (guest: Guest) => void | Promise<void>;
  onCommentDraftChange: (guestId: number, value: string) => void;
  onDeleteComment: (guest: Guest, commentId: number) => void | Promise<void>;
}) {
  return (
    <div className="app-surface-elevated mt-4 rounded-xl p-3">
      <div className="space-y-2">
        {comments.length === 0 ? (
          <p className="app-text-muted text-xs">Комментариев пока нет</p>
        ) : comments.map((comment) => {
          const canDelete = canDeleteAllComments || comment.author?.id === currentUserId;
          return (
            <div key={comment.id} className="app-surface-muted rounded-lg px-3 py-2 text-xs text-[var(--foreground)]">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-medium">{displayUserName(comment.author)}</span>
                <div className="flex items-center gap-2">
                  <span className="app-text-muted">{formatDateTime(comment.created_at)}</span>
                  {canDelete ? (
                    <CommentDeleteButton
                      disabled={busyKey === `guest-comment-delete-${comment.id}`}
                      onClick={() => onDeleteComment(guest, comment.id)}
                    />
                  ) : null}
                </div>
              </div>
              <p className="app-text-wrap text-[var(--foreground)]">{comment.text}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-2">
        <CommentComposer
          value={commentDraft}
          onChange={(value) => onCommentDraftChange(guest.id, value)}
          onSubmit={() => onAddComment(guest)}
          disabled={busyKey === `guest-comment-${guest.id}`}
        />
      </div>
    </div>
  );
}

function GuestPhotoModal({
  guest,
  onClose,
}: {
  guest: Guest | null;
  onClose: () => void;
}) {
  if (!guest) return null;

  const imageSrc = resolveMediaUrl(guest.avatar || "");
  const name = guestName(guest);

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={name}
      size="md"
      closeOnClickOutside
    >
      <div className="flex min-h-[280px] items-center justify-center">
        {imageSrc ? (
          <Image
            src={imageSrc}
            alt={name}
            width={720}
            height={720}
            className="max-h-[68vh] w-auto max-w-full rounded-xl object-contain"
            unoptimized
          />
        ) : (
          <div className="app-avatar-fallback flex h-48 w-48 items-center justify-center rounded-full text-5xl font-semibold">
            {guestInitials(name)}
          </div>
        )}
      </div>
    </Modal>
  );
}

function GuestDetailModal({
  canEdit,
  guest,
  onClose,
  onEdit,
  onLinkTask,
}: {
  canEdit: boolean;
  guest: Guest | null;
  onClose: () => void;
  onEdit: (guest: Guest) => void;
  onLinkTask: (guest: Guest) => void;
}) {
  if (!guest) return null;

  const profileItems = [
    { label: "ID", value: String(guest.id), icon: IdCard, always: true },
    { label: "Дата рождения", value: formatGuestDate(guest.birth_date), icon: CalendarDays },
    { label: "Организация", value: normalizeGuestMeta(guest.organization), icon: Building2 },
    { label: "Должность", value: normalizeGuestMeta(guest.position), icon: BriefcaseBusiness },
    { label: "Email", value: normalizeGuestMeta(guest.email), icon: Mail },
    { label: "Телефон", value: normalizeGuestMeta(guest.phone), icon: Phone },
  ].filter((item) => item.always || Boolean(item.value));
  const accountItems = [
    { label: "Login", value: normalizeGuestMeta(guest.ldap_username), icon: IdCard },
    { label: "UPN", value: normalizeGuestMeta(guest.ldap_upn), icon: Mail },
    { label: "Синхронизация", value: formatDateTime(guest.ldap_last_synced_at), icon: RefreshCcw },
  ].filter((item) => Boolean(item.value));

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Гость #${guest.id}`}
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium">Закрыть</button>
          <button
            type="button"
            onClick={() => onLinkTask(guest)}
            className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
          >
            <Link2 size={15} />
            Связать с задачей
          </button>
          {canEdit ? (
            <button
              type="button"
              onClick={() => onEdit(guest)}
              className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
            >
              <Pencil size={15} />
              Изменить
            </button>
          ) : null}
        </div>
      }
    >
      <div className="space-y-4">
        <section className="app-surface-muted rounded-xl p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-start gap-4">
              <GuestAvatar guest={guest} size="lg" />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <GuestAccessStatusBadge guest={guest} />
                  {guest.is_blacklisted ? (
                    <span className="app-feedback-danger inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium">
                      <Ban size={12} />
                      Черный список
                    </span>
                  ) : null}
                </div>
                <h2 className="mt-3 truncate text-xl font-semibold text-[var(--foreground)]">{guestName(guest)}</h2>
                {guest.organization ? <p className="app-text-muted mt-1 text-sm">{guest.organization}</p> : null}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <InfoBlock icon={<IdCard size={16} />} title="Данные гостя">
            <div className="space-y-2">
              {profileItems.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex min-w-0 items-center gap-2 text-sm">
                    <Icon size={14} className="app-text-muted shrink-0" />
                    <span className="app-text-muted shrink-0">{item.label}:</span>
                    <span className="min-w-0 break-words text-[var(--foreground)]">{item.value}</span>
                  </div>
                );
              })}
            </div>
          </InfoBlock>
          <InfoBlock icon={<ShieldAlert size={16} />} title="Учетка">
            {accountItems.length > 0 ? (
              <div className="space-y-2">
                {accountItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.label} className="flex min-w-0 items-center gap-2 text-sm">
                      <Icon size={14} className="app-text-muted shrink-0" />
                      <span className="app-text-muted shrink-0">{item.label}:</span>
                      <span className="min-w-0 break-words text-[var(--foreground)]">{item.value}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="app-text-muted text-sm">Учетка еще не синхронизирована.</p>
            )}
            {guest.ldap_last_error ? (
              <p className="app-feedback-danger mt-3 rounded-lg p-2 text-xs">{guest.ldap_last_error}</p>
            ) : null}
          </InfoBlock>
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <div className="mb-3 flex items-center gap-2">
            <Link2 size={16} className="app-text-muted" />
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Связанные задачи</h3>
          </div>
          <LinkedTaskPills tasks={guest.linked_tasks} max={4} />
          {guest.linked_tasks?.length ? null : (
            <p className="app-text-muted text-sm">Связанных задач нет.</p>
          )}
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <div className="mb-3 flex items-center gap-2">
            <FileText size={16} className="app-text-muted" />
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Документы</h3>
          </div>
          {guest.documents?.length ? (
            <div className="flex flex-wrap gap-1.5">
              {guest.documents.map((document) => {
                const label = document.title || document.file_name || `Документ #${document.id}`;
                const content = (
                  <>
                    <FileText size={12} className="shrink-0" />
                    <span className="min-w-0 truncate">{label}</span>
                  </>
                );
                return document.file_url ? (
                  <a
                    key={document.id}
                    href={resolveMediaUrl(document.file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="app-badge inline-flex max-w-[180px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium no-underline transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] hover:no-underline"
                    title={label}
                  >
                    {content}
                  </a>
                ) : (
                  <span
                    key={document.id}
                    className="app-badge inline-flex max-w-[180px] items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium"
                    title={label}
                  >
                    {content}
                  </span>
                );
              })}
            </div>
          ) : (
            <p className="app-text-muted text-sm">Документы не прикреплены.</p>
          )}
        </section>
      </div>
    </Modal>
  );
}

function GuestEditModal({
  busy,
  busyKey,
  documents,
  documentsLoading,
  form,
  guest,
  onAttachDocument,
  onClose,
  onReloadDocuments,
  onRemoveDocument,
  onSubmit,
  onUploadDocument,
  setForm,
}: {
  busy: boolean;
  busyKey: string | null;
  documents: { id: number; name: string }[];
  documentsLoading: boolean;
  form: GuestEditState | null;
  guest: Guest | null;
  onAttachDocument: (guest: Guest, documentId?: number | null) => void | Promise<void>;
  onClose: () => void;
  onReloadDocuments: () => void | Promise<void>;
  onRemoveDocument: (guest: Guest, documentId: number) => void | Promise<void>;
  onSubmit: () => void | Promise<void>;
  onUploadDocument: (guest: Guest, file: File) => void | Promise<void>;
  setForm: (updater: GuestEditState | null | ((current: GuestEditState | null) => GuestEditState | null)) => void;
}) {
  const [guestAvatarCropperImage, setGuestAvatarCropperImage] = useState<string | null>(null);
  const documentFileInputRef = useRef<HTMLInputElement | null>(null);
  if (!guest || !form) return null;
  const attachedDocumentIds = new Set((guest.documents || []).map((document) => document.id));
  const availableDocumentOptions = documents.filter((document) => !attachedDocumentIds.has(document.id));
  const setField = <K extends keyof GuestEditState>(key: K, value: GuestEditState[K]) => {
    setForm((current) => current ? { ...current, [key]: value } : current);
  };
  const handleClose = () => {
    setGuestAvatarCropperImage(null);
    onClose();
  };

  return (
    <>
      <Modal
        isOpen
        onClose={handleClose}
        closeOnEsc={!guestAvatarCropperImage}
        title={`Гость #${guest.id}`}
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <button type="button" onClick={handleClose} className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium">Отмена</button>
            <button type="button" onClick={() => void onSubmit()} disabled={busy} className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60">
              {busy ? <Loader2 className="animate-spin" size={15} /> : null}
              Сохранить
            </button>
          </div>
        }
      >
        <div className="grid gap-3 md:grid-cols-2">
          <GuestAvatarPicker
            name={[form.last_name, form.first_name].filter(Boolean).join(" ") || guestName(guest)}
            value={form.avatar}
            onSelectImage={setGuestAvatarCropperImage}
          />
          <TextField label="Фамилия" value={form.last_name} onChange={(value) => setField("last_name", value)} />
          <TextField label="Имя" value={form.first_name} onChange={(value) => setField("first_name", value)} />
          <TextField label="Отчество" value={form.patronymic} onChange={(value) => setField("patronymic", value)} />
          <TextField label="Дата рождения" value={form.birth_date || ""} onChange={(value) => setField("birth_date", value)} type="date" />
          <TextField label="Телефон" value={form.phone} onChange={(value) => setField("phone", value)} />
          <TextField label="Email" value={form.email} onChange={(value) => setField("email", value)} type="email" />
          <TextField label="Организация" value={form.organization} onChange={(value) => setField("organization", value)} />
          <TextField label="Должность" value={form.position} onChange={(value) => setField("position", value)} />
        </div>

        <section className="app-surface-muted mt-4 rounded-xl p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <FileText size={16} className="app-text-muted" />
              <h3 className="text-sm font-semibold text-[var(--foreground)]">Документы</h3>
            </div>
            <button
              type="button"
              onClick={() => documentFileInputRef.current?.click()}
              className="app-link-accent inline-flex items-center gap-1 text-xs font-medium"
            >
              <Plus size={12} /> Загрузить файл
            </button>
            <input
              ref={documentFileInputRef}
              type="file"
              multiple
              hidden
              tabIndex={-1}
              onChange={(event) => {
                Array.from(event.target.files || []).forEach((file) => {
                  void onUploadDocument(guest, file);
                });
                event.target.value = "";
              }}
            />
          </div>

          <div className="mb-3 flex gap-2">
            <div className="min-w-0 flex-1">
              <SearchableSelectSingle
                label="Выбрать существующий"
                items={availableDocumentOptions}
                selectedId={null}
                onSelect={(id) => {
                  if (id) void onAttachDocument(guest, id);
                }}
                placeholder="Найти документ"
              />
            </div>
            <button
              type="button"
              onClick={() => void onReloadDocuments()}
              className="app-action-secondary mt-5 h-10 rounded-lg px-3"
              title="Обновить документы"
            >
              {documentsLoading ? <Loader2 className="animate-spin" size={15} /> : <Search size={15} />}
            </button>
          </div>

          <div className="space-y-2">
            {(guest.documents || []).map((document) => (
              <div key={document.id} className="flex items-center gap-2">
                {document.file_url ? (
                  <a
                    href={resolveMediaUrl(document.file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="app-input min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-sm transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
                    title={document.title || document.file_name || `Документ #${document.id}`}
                  >
                    {document.title || document.file_name || `Документ #${document.id}`}
                  </a>
                ) : (
                  <input
                    readOnly
                    value={document.title || document.file_name || `Документ #${document.id}`}
                    className="app-input min-w-0 flex-1 rounded-lg px-3 py-2 text-sm"
                  />
                )}
                <button
                  type="button"
                  onClick={() => void onRemoveDocument(guest, document.id)}
                  disabled={busyKey === `guest-remove-doc-${document.id}`}
                  className="app-action-secondary inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg disabled:opacity-60"
                  title="Убрать документ"
                >
                  <XCircle size={13} />
                </button>
              </div>
            ))}
            {guest.documents?.length ? null : (
              <p className="app-text-muted text-xs">
                Документы можно выбрать из реестра или загрузить новым файлом.
              </p>
            )}
          </div>
        </section>
      </Modal>

      {guestAvatarCropperImage ? (
        <AvatarCropper
          initialImage={guestAvatarCropperImage}
          onCropComplete={(croppedImage) => {
            setField("avatar", croppedImage);
            setGuestAvatarCropperImage(null);
          }}
          onCancel={() => setGuestAvatarCropperImage(null)}
        />
      ) : null}
    </>
  );
}

function TextField({
  label,
  value,
  onChange,
  required = false,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
}) {
  return (
    <label className="min-w-0">
      <span className="app-text-muted mb-1 block text-xs font-medium">{label}{required ? " *" : ""}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="app-input h-10 w-full min-w-0 rounded-lg px-3 text-sm"
      />
    </label>
  );
}

function InfoBlock({ children, icon, title }: { children: React.ReactNode; icon: React.ReactNode; title: string }) {
  return (
    <section className="app-surface-muted rounded-xl p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="app-text-muted">{icon}</span>
        <h3 className="text-sm font-semibold text-[var(--foreground)]">{title}</h3>
      </div>
      <div className="space-y-1.5">{children}</div>
    </section>
  );
}

function InfoLine({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-2 text-xs">
      <span className="app-text-muted">{label}</span>
      <span className="min-w-0 break-words text-[var(--foreground)]">{value || "—"}</span>
    </div>
  );
}
