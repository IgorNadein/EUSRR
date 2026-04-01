"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { canManageEquipment } from "@/lib/permissions";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type {
  Department,
  Equipment,
  EquipmentCategory,
  EquipmentComment,
  EquipmentCreateOptions,
  EquipmentTransferHistoryEntry,
  MaintenanceRecord,
  User,
} from "@/types/api";
import { Archive, ArrowRightLeft, ArrowUpDown, ChevronDown, Filter, MessageSquare, Monitor, Pencil, Plus, QrCode, Search, Shield, Trash2, Wrench, X } from "lucide-react";
import { SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import { formatDate as sharedFormatDate, formatMoney as sharedFormatMoney, displayUserName as sharedDisplayUserName, extractNextPage as sharedExtractNextPage, loadAllPages } from "@/lib/shared";

/* ──── form state ──── */
type EquipmentFormState = {
  name: string;
  notes: string;
  category: number | null;
  department: number | null;
  responsible_person: number | null;
  quantity: number;
  serial_number: string;
  purchase_date: string;
  purchase_cost: string;
  location: string;
};

const emptyForm: EquipmentFormState = {
  name: "",
  notes: "",
  category: null,
  department: null,
  responsible_person: null,
  quantity: 1,
  serial_number: "",
  purchase_date: "",
  purchase_cost: "",
  location: "",
};

type EquipmentListMode = "all" | "mine" | "warranty";

type OperationModal = "transfer" | "writeoff" | "maintenance" | null;

type TransferFormState = {
  to_department: number | null;
  to_person: number | null;
  reason: string;
};

type MaintenanceFormState = {
  type: string;
  description: string;
  cost: string;
  date: string;
};

const listModeMeta: Array<{ value: EquipmentListMode; label: string }> = [
  { value: "all", label: "Весь реестр" },
  { value: "mine", label: "Мое оборудование" },
  { value: "warranty", label: "Истекает гарантия" },
];

const orderingOptions = [
  { value: "-created_at", label: "Сначала новые" },
  { value: "created_at", label: "Сначала старые" },
  { value: "name", label: "По названию" },
  { value: "purchase_date", label: "По дате покупки ↑" },
  { value: "-purchase_date", label: "По дате покупки ↓" },
];

/* ──── status badges ──── */
const statusMeta: Record<string, { label: string; className: string; accentClass: string; surfaceClass: string }> = {
  available: {
    label: "Доступно",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    accentClass: "bg-emerald-500",
    surfaceClass: "border-emerald-100",
  },
  in_use: {
    label: "В использовании",
    className: "bg-sky-50 text-sky-700 ring-sky-100",
    accentClass: "bg-sky-500",
    surfaceClass: "border-sky-100",
  },
  maintenance: {
    label: "На обслуживании",
    className: "bg-amber-50 text-amber-700 ring-amber-100",
    accentClass: "bg-amber-500",
    surfaceClass: "border-amber-100",
  },
  retired: {
    label: "Списано",
    className: "bg-gray-100 text-gray-700 ring-gray-200",
    accentClass: "bg-gray-400",
    surfaceClass: "border-gray-200",
  },
  broken: {
    label: "Сломано",
    className: "bg-rose-50 text-rose-700 ring-rose-100",
    accentClass: "bg-rose-500",
    surfaceClass: "border-rose-100",
  },
};

const defaultStatusMeta = {
  label: "—",
  className: "bg-gray-50 text-gray-700 ring-gray-200",
  accentClass: "bg-gray-300",
  surfaceClass: "border-gray-200",
};

const formatDate = sharedFormatDate;
const formatMoney = sharedFormatMoney;

/* ──── main page ──── */
export default function EquipmentPage() {
  const { user } = useUser();
  const [items, setItems] = useState<Equipment[]>([]);
  const [detailsMap, setDetailsMap] = useState<Record<number, Equipment>>({});
  const [transferHistoryMap, setTransferHistoryMap] = useState<Record<number, EquipmentTransferHistoryEntry[]>>({});
  const [maintenanceMap, setMaintenanceMap] = useState<Record<number, MaintenanceRecord[]>>({});
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [categories, setCategories] = useState<EquipmentCategory[]>([]);
  const [createOptions, setCreateOptions] = useState<EquipmentCreateOptions | null>(null);
  const [previewInventoryNumber, setPreviewInventoryNumber] = useState<string>("");
  const [commentsMap, setCommentsMap] = useState<Record<number, EquipmentComment[]>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [expandedComments, setExpandedComments] = useState<Record<number, boolean>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});
  const [loadingRowDetails, setLoadingRowDetails] = useState<Record<number, boolean>>({});

  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<EquipmentFormState>(emptyForm);
  const [listMode, setListMode] = useState<EquipmentListMode>("all");
  const [ordering, setOrdering] = useState("-created_at");
  const [operationModal, setOperationModal] = useState<OperationModal>(null);
  const [selectedEquipment, setSelectedEquipment] = useState<Equipment | null>(null);
  const [writeOffReason, setWriteOffReason] = useState("");
  const [transferForm, setTransferForm] = useState<TransferFormState>({ to_department: null, to_person: null, reason: "" });
  const [maintenanceForm, setMaintenanceForm] = useState<MaintenanceFormState>({
    type: "repair",
    description: "",
    cost: "",
    date: new Date().toISOString().slice(0, 10),
  });

  const [searchQuery, setSearch] = useState("");
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [responsibleFilter, setResponsibleFilter] = useState("");
  const [dateFromFilter, setDateFromFilter] = useState("");
  const [dateToFilter, setDateToFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [nextPage, setNextPage] = useState<number | null>(null);

  const auth = user?.auth;
  const canManage = canManageEquipment(user);
  const isCreateMode = createOpen && editingId === null;

  /* ──── helpers ──── */
  const displayUserName = (person?: User | null) => sharedDisplayUserName(person);

  const extractNextPage = sharedExtractNextPage;

  const buildParams = (page: number): Record<string, string | number> => {
    const p: Record<string, string | number> = { page };
    if (deferredSearchQuery.trim()) p.search = deferredSearchQuery.trim();
    if (ordering) p.ordering = ordering;
    if (statusFilter) p.status = statusFilter;
    if (categoryFilter) p.category = categoryFilter;
    if (departmentFilter) p.department = departmentFilter;
    if (responsibleFilter) p.responsible_person = responsibleFilter;
    if (dateFromFilter) p.purchase_date__gte = dateFromFilter;
    if (dateToFilter) p.purchase_date__lte = dateToFilter;
    return p;
  };

  const getCategoryName = (eq: Equipment): string => {
    if (eq.category_name) return eq.category_name;
    const cat = categories.find((c) => c.id === Number(eq.category));
    return cat?.name || "—";
  };

  const getDepartmentName = (eq: Equipment): string => {
    if (eq.department_name) return eq.department_name;
    const dep = departments.find((d) => d.id === Number(eq.department));
    return dep?.name || "—";
  };

  const getResponsibleName = (eq: Equipment): string => {
    if (eq.responsible_name) return eq.responsible_name;
    if (eq.responsible_person && typeof eq.responsible_person === "number") {
      const emp = employees.find((e) => e.id === eq.responsible_person);
      return emp ? displayUserName(emp) : "—";
    }
    return "—";
  };

  const getResponsibleLink = (eq: Equipment): string => {
    if (!eq.responsible_person || typeof eq.responsible_person !== "number") return "";
    if (eq.responsible_person === user?.id) return "/profile";
    return `/users/${eq.responsible_person}`;
  };

  const getEquipmentMeta = (eq: Equipment) => {
    return [
      { label: "Категория", value: getCategoryName(eq) },
      { label: "Отдел", value: getDepartmentName(eq) },
      { label: "Ответственный", value: getResponsibleName(eq) },
      { label: "Серийный номер", value: eq.serial_number || "—" },
      { label: "Расположение", value: eq.location || "—" },
      { label: "Гарантия до", value: formatDate(eq.warranty_until) || "—" },
      { label: "Обслуживаний", value: String(eq.maintenance_count ?? "—") },
      { label: "Стоимость", value: formatMoney(eq.purchase_cost) },
      { label: "Добавлено", value: formatDate(eq.created_at) || "—" },
    ];
  };

  const filteredDepartmentsForForm = useMemo(() => {
    if (!createOptions || !isCreateMode || createOptions.allowed_departments.length === 0) {
      return departments;
    }
    const allowedIds = new Set(createOptions.allowed_departments.map((dept) => dept.id));
    return departments.filter((dept) => allowedIds.has(dept.id));
  }, [createOptions, departments, isCreateMode]);

  const filteredEmployeesForForm = useMemo(() => {
    if (!isCreateMode || !createOptions || createOptions.can_choose_responsible) {
      return employees;
    }
    if (!createOptions.default_responsible) {
      return [];
    }
    return employees.filter((employee) => employee.id === createOptions.default_responsible?.id);
  }, [createOptions, employees, isCreateMode]);

  const applyCreateDefaults = (options: EquipmentCreateOptions | null) => {
    if (!options) return;

    setForm((prev) => {
      const nextDepartment = options.can_choose_department
        ? prev.department
        : options.allowed_departments[0]?.id ?? prev.department;
      const nextResponsible = options.can_choose_responsible
        ? prev.responsible_person
        : options.default_responsible?.id ?? prev.responsible_person;

      return {
        ...prev,
        department: nextDepartment,
        responsible_person: nextResponsible,
      };
    });
  };

  const loadRowDetails = async (equipmentId: number) => {
    if (loadingRowDetails[equipmentId]) return;

    try {
      setLoadingRowDetails((prev) => ({ ...prev, [equipmentId]: true }));
      const results = await Promise.allSettled([
        detailsMap[equipmentId] ? Promise.resolve(detailsMap[equipmentId]) : apiClient.getEquipmentDetail(equipmentId),
        transferHistoryMap[equipmentId] ? Promise.resolve(transferHistoryMap[equipmentId]) : apiClient.getEquipmentTransferHistory(equipmentId),
        maintenanceMap[equipmentId] ? Promise.resolve(maintenanceMap[equipmentId]) : apiClient.getMaintenanceRecords({ equipment: equipmentId }),
      ]);

      const [detailResult, transferResult, maintenanceResult] = results;

      if (detailResult.status === "fulfilled") {
        setDetailsMap((prev) => ({ ...prev, [equipmentId]: detailResult.value }));
      }

      if (transferResult.status === "fulfilled") {
        setTransferHistoryMap((prev) => ({ ...prev, [equipmentId]: Array.isArray(transferResult.value) ? transferResult.value : transferResult.value.results || [] }));
      }

      if (maintenanceResult.status === "fulfilled") {
        setMaintenanceMap((prev) => ({
          ...prev,
          [equipmentId]: Array.isArray(maintenanceResult.value) ? maintenanceResult.value : maintenanceResult.value.results || [],
        }));
      }
    } catch (error) {
      console.error("Ошибка загрузки деталей оборудования:", error);
    } finally {
      setLoadingRowDetails((prev) => ({ ...prev, [equipmentId]: false }));
    }
  };

  const openCreateModal = async () => {
    setEditingId(null);
    resetForm();
    setActionError(null);
    setActionSuccess(null);
    setCreateOpen(true);

    try {
      const [options, inventoryPreview] = await Promise.all([
        apiClient.getEquipmentCreateOptions(),
        apiClient.generateEquipmentInventoryNumber(),
      ]);
      setCreateOptions(options);
      setPreviewInventoryNumber(inventoryPreview.inventory_number || "");
      applyCreateDefaults(options);
    } catch (error) {
      console.error("Ошибка загрузки опций создания оборудования:", error);
    }
  };

  const openOperationModal = (type: Exclude<OperationModal, null>, equipment: Equipment) => {
    setSelectedEquipment(equipment);
    setOperationModal(type);
    setActionError(null);

    if (type === "transfer") {
      setTransferForm({
        to_department: equipment.department ?? null,
        to_person: typeof equipment.responsible_person === "number" ? equipment.responsible_person : null,
        reason: "",
      });
    }

    if (type === "writeoff") {
      setWriteOffReason("");
    }

    if (type === "maintenance") {
      setMaintenanceForm({
        type: "repair",
        description: "",
        cost: "",
        date: new Date().toISOString().slice(0, 10),
      });
    }
  };

  const closeOperationModal = () => {
    setOperationModal(null);
    setSelectedEquipment(null);
    setWriteOffReason("");
    setTransferForm({ to_department: null, to_person: null, reason: "" });
    setMaintenanceForm({ type: "repair", description: "", cost: "", date: new Date().toISOString().slice(0, 10) });
  };

  /* ──── load data ──── */
  const fetchEquipmentPage = async (page: number) => {
    if (listMode === "mine") {
      return apiClient.getMyEquipment({ page });
    }

    if (listMode === "warranty") {
      if (page > 1) {
        return { results: [], next: null };
      }
      return apiClient.getWarrantyExpiringEquipment();
    }

    return apiClient.getEquipment(buildParams(page));
  };

  const reloadEquipmentList = async () => {
    const res = await fetchEquipmentPage(1);
    const results = Array.isArray(res) ? res : (res.results || []);
    setItems(results);
    setNextPage(extractNextPage((res as { next?: string | null }).next));
  };

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetchEquipmentPage(1);
        const results = Array.isArray(res) ? res : (res.results || []);
        setItems(results);
        setNextPage(extractNextPage(res.next));
      } catch (e: any) {
        console.error("Ошибка загрузки оборудования:", e);
        setError("Не удалось загрузить оборудование");
      } finally {
        setLoading(false);
      }
    })();
  }, [
    listMode,
    deferredSearchQuery,
    ordering,
    statusFilter,
    categoryFilter,
    departmentFilter,
    responsibleFilter,
    dateFromFilter,
    dateToFilter,
  ]);

  useEffect(() => {
    (async () => {
      try {
        const [allEmployees, allDepartments, allCategories] = await Promise.all([
          loadAllPages<User>((p) => apiClient.getEmployees(p)),
          loadAllPages<Department>((p) => apiClient.getDepartments(p)),
          loadAllPages<EquipmentCategory>((p) => apiClient.getEquipmentCategories(p)),
        ]);
        setEmployees(allEmployees);
        setDepartments(allDepartments);
        setCategories(allCategories);
      } catch (e) {
        console.error("Ошибка загрузки справочников:", e);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const options = await apiClient.getEquipmentCreateOptions();
        setCreateOptions(options);
      } catch (error) {
        console.error("Ошибка загрузки create options:", error);
      }
    })();
  }, []);

  /* ──── filtered ──── */
  const sortItemsLocally = (source: Equipment[]) => {
    const sorted = [...source];

    sorted.sort((left, right) => {
      switch (ordering) {
        case "name":
          return (left.name || "").localeCompare(right.name || "", "ru");
        case "purchase_date":
          return new Date(left.purchase_date || 0).getTime() - new Date(right.purchase_date || 0).getTime();
        case "-purchase_date":
          return new Date(right.purchase_date || 0).getTime() - new Date(left.purchase_date || 0).getTime();
        case "created_at":
          return new Date(left.created_at || 0).getTime() - new Date(right.created_at || 0).getTime();
        case "-created_at":
        default:
          return new Date(right.created_at || 0).getTime() - new Date(left.created_at || 0).getTime();
      }
    });

    return sorted;
  };

  const filteredItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    let scopedItems = [...items];

    if (listMode !== "all") {
      scopedItems = scopedItems.filter((item) => {
        const itemDate = item.purchase_date || "";
        if (statusFilter && item.status !== statusFilter) return false;
        if (categoryFilter && Number(item.category) !== Number(categoryFilter)) return false;
        if (departmentFilter && Number(item.department) !== Number(departmentFilter)) return false;
        if (responsibleFilter && Number(item.responsible_person) !== Number(responsibleFilter)) return false;
        if (dateFromFilter && itemDate && itemDate < dateFromFilter) return false;
        if (dateToFilter && itemDate && itemDate > dateToFilter) return false;
        return true;
      });
    }

    const sorted = listMode === "all" ? items : sortItemsLocally(scopedItems);
    if (!q) return sorted;
    return sorted.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const notes = (item.notes || "").toLowerCase();
      const sn = (item.serial_number || "").toLowerCase();
      const inv = (item.inventory_number || "").toLowerCase();
      const responsible = getResponsibleName(item).toLowerCase();
      const cat = getCategoryName(item).toLowerCase();
      return name.includes(q) || notes.includes(q) || sn.includes(q) || inv.includes(q) || responsible.includes(q) || cat.includes(q);
    });
  }, [
    items,
    listMode,
    ordering,
    searchQuery,
    statusFilter,
    categoryFilter,
    departmentFilter,
    responsibleFilter,
    dateFromFilter,
    dateToFilter,
    employees,
    categories,
    departments,
  ]);

  /* ──── form ──── */
  const resetForm = () => setForm(emptyForm);

  const openEdit = (eq: Equipment) => {
    setEditingId(eq.id);
    setCreateOpen(false);
    setActionError(null);
    setActionSuccess(null);
    setPreviewInventoryNumber(eq.inventory_number || "");
    setForm({
      name: eq.name || "",
      notes: eq.notes || "",
      category: eq.category ?? null,
      department: eq.department ?? null,
      responsible_person: typeof eq.responsible_person === "number" ? eq.responsible_person : null,
      quantity: 1,
      serial_number: eq.serial_number || "",
      purchase_date: eq.purchase_date || "",
      purchase_cost: String(eq.purchase_cost || ""),
      location: eq.location || "",
    });
  };

  const handleSave = async (mode: "create" | "edit") => {
    try {
      setBusyKey(`${mode}-save`);
      setActionError(null);
      setActionSuccess(null);

      if (!form.name.trim()) { setActionError("Укажите название оборудования."); return; }
      if (!form.category) { setActionError("Выберите категорию."); return; }
      if (!form.department) { setActionError("Выберите отдел."); return; }
      if (!form.purchase_date) { setActionError("Укажите дату покупки."); return; }
      if (!form.purchase_cost) { setActionError("Укажите стоимость."); return; }

      const payload: Record<string, any> = {
        name: form.name,
        notes: form.notes,
        category: form.category,
        department: form.department,
        purchase_date: form.purchase_date,
        purchase_cost: form.purchase_cost,
      };

      if (form.responsible_person) payload.responsible_person = form.responsible_person;
      if (mode === "create" && form.quantity > 1) payload.quantity = form.quantity;
      if (form.serial_number) payload.serial_number = form.serial_number;
      if (form.location) payload.location = form.location;

      if (mode === "create") {
        await apiClient.createEquipment(payload);
        setActionSuccess("Оборудование добавлено.");
        setCreateOpen(false);
      } else if (editingId) {
        await apiClient.updateEquipment(editingId, payload);
        setActionSuccess("Оборудование обновлено.");
        setEditingId(null);
      }

      resetForm();
      await reloadEquipmentList();
    } catch (e: any) {
      const raw = String(e?.message || "Не удалось сохранить");
      let readable = raw;
      try {
        const parsed = JSON.parse(raw);
        readable = Object.entries(parsed).map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(", ") : val}`).join(". ");
      } catch {}
      setActionError(readable);
    } finally {
      setBusyKey(null);
    }
  };

  const handleLoadMore = async () => {
    if (!nextPage || loadingMore) return;
    try {
      setLoadingMore(true);
      const res = await fetchEquipmentPage(nextPage);
      const chunk = Array.isArray(res) ? res : (res.results || []);
      setItems((prev) => {
        const known = new Set(prev.map((r) => r.id));
        return [...prev, ...chunk.filter((r: Equipment) => !known.has(r.id))];
      });
      setNextPage(extractNextPage(res.next));
    } catch {
      setError("Не удалось загрузить ещё");
    } finally {
      setLoadingMore(false);
    }
  };

  /* ──── actions ──── */
  const handleDelete = async (id: number) => {
    if (!confirm("Удалить это оборудование?")) return;
    try { setBusyKey(`delete-${id}`); await apiClient.deleteEquipment(id); setItems((p) => p.filter((r) => r.id !== id)); } catch { setActionError("Не удалось удалить"); } finally { setBusyKey(null); } };

  const toggleRow = (equipmentId: number) => {
    setExpandedRows((prev) => {
      const nextOpen = !prev[equipmentId];
      if (nextOpen) {
        void loadRowDetails(equipmentId);
      }
      return { ...prev, [equipmentId]: nextOpen };
    });
  };

  const handleTransfer = async () => {
    if (!selectedEquipment) return;
    try {
      setBusyKey(`transfer-${selectedEquipment.id}`);
      await apiClient.transferEquipment(selectedEquipment.id, {
        to_department: transferForm.to_department,
        to_person: transferForm.to_person,
        reason: transferForm.reason,
      });
      setActionSuccess("Оборудование переведено.");
      closeOperationModal();
      await reloadEquipmentList();
      await loadRowDetails(selectedEquipment.id);
    } catch (error: any) {
      setActionError(String(error?.message || "Не удалось выполнить перевод"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleWriteOff = async () => {
    if (!selectedEquipment) return;
    try {
      setBusyKey(`writeoff-${selectedEquipment.id}`);
      await apiClient.writeOffEquipment(selectedEquipment.id, writeOffReason);
      setActionSuccess("Оборудование списано.");
      closeOperationModal();
      await reloadEquipmentList();
      await loadRowDetails(selectedEquipment.id);
    } catch (error: any) {
      setActionError(String(error?.message || "Не удалось списать оборудование"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleMaintenance = async () => {
    if (!selectedEquipment) return;
    try {
      setBusyKey(`maintenance-${selectedEquipment.id}`);
      await apiClient.addEquipmentMaintenance(selectedEquipment.id, {
        type: maintenanceForm.type,
        description: maintenanceForm.description,
        cost: maintenanceForm.cost || undefined,
        date: maintenanceForm.date,
      });
      setActionSuccess("Запись обслуживания добавлена.");
      closeOperationModal();
      await loadRowDetails(selectedEquipment.id);
    } catch (error: any) {
      setActionError(String(error?.message || "Не удалось добавить обслуживание"));
    } finally {
      setBusyKey(null);
    }
  };

  const handleOpenQr = async (equipmentId: number) => {
    try {
      setBusyKey(`qr-${equipmentId}`);
      const blobUrl = await apiClient.getEquipmentQrCodeBlobUrl(equipmentId);
      window.open(blobUrl, "_blank", "noopener,noreferrer");
    } catch (error: any) {
      setActionError(String(error?.message || "Не удалось получить QR-код"));
    } finally {
      setBusyKey(null);
    }
  };

  const toggleComments = async (eqId: number) => {
    const isOpen = Boolean(expandedComments[eqId]);
    setExpandedComments((p) => ({ ...p, [eqId]: !isOpen }));
    if (!isOpen && !commentsMap[eqId]) {
      try {
        const c = await apiClient.getEquipmentComments(eqId);
        setCommentsMap((p) => ({ ...p, [eqId]: Array.isArray(c) ? c : c.results || [] }));
      } catch {
        setCommentsMap((p) => ({ ...p, [eqId]: [] }));
      }
    }
  };

  const handleAddComment = async (eqId: number) => {
    const text = (commentDrafts[eqId] || "").trim();
    if (!text) return;
    try {
      setBusyKey(`comment-${eqId}`);
      const saved = await apiClient.addEquipmentComment(eqId, text);
      setCommentsMap((p) => ({ ...p, [eqId]: [...(p[eqId] || []), saved] }));
      setCommentDrafts((p) => ({ ...p, [eqId]: "" }));
    } catch {
      setActionError("Не удалось добавить комментарий");
    } finally {
      setBusyKey(null);
    }
  };

  const handleDeleteComment = async (eqId: number, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      await apiClient.deleteEquipmentComment(eqId, commentId);
      setCommentsMap((p) => ({ ...p, [eqId]: (p[eqId] || []).filter((c) => c.id !== commentId) }));
    } catch {
      setActionError("Не удалось удалить комментарий");
    } finally {
      setBusyKey(null);
    }
  };

  const modalMode: "create" | "edit" = editingId ? "edit" : "create";
  const isModalOpen = createOpen || editingId !== null;

  const closeModal = () => {
    setCreateOpen(false);
    setEditingId(null);
    resetForm();
    setActionError(null);
  };

  const activeFilterCount = [statusFilter, categoryFilter, departmentFilter, responsibleFilter, dateFromFilter, dateToFilter].filter(Boolean).length;
  /* ──── render ──── */
  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка оборудования...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          {/* Header */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Оборудование</p>
            <button
              type="button"
              onClick={() => { void openCreateModal(); }}
              className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600"
            >
              <Plus size={14} /> Добавить оборудование
            </button>
          </div>

          {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {actionSuccess && <p className="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{actionSuccess}</p>}

          {/* Search + filter toggle */}
          <div className="mb-4 flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQuery}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по оборудованию"
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <button
              type="button"
              title="Фильтры"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${filtersOpen ? "border-sky-400 bg-sky-50 text-sky-600" : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"}`}
            >
              <Filter size={16} />
              {activeFilterCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <div className="relative w-[148px] shrink-0">
              <ArrowUpDown size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <select
                value={ordering}
                onChange={(e) => setOrdering(e.target.value)}
                className="w-full appearance-none rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-8 text-xs font-medium text-gray-700 transition hover:bg-gray-100 focus:border-sky-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                aria-label="Сортировка списка оборудования"
              >
                {orderingOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" />
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {listModeMeta.map((mode) => (
              <button
                key={mode.value}
                type="button"
                onClick={() => setListMode(mode.value)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  listMode === mode.value
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                <span>{mode.label}</span>
              </button>
            ))}
          </div>

          {/* Filters panel */}
          {filtersOpen && (
            <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все статусы</option>
                  {Object.entries(statusMeta).map(([key, meta]) => (
                    <option key={key} value={key}>{meta.label}</option>
                  ))}
                </select>
                <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все категории</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все отделы</option>
                  {departments.map((dep) => (
                    <option key={dep.id} value={dep.id}>{dep.name}</option>
                  ))}
                </select>
                <select value={responsibleFilter} onChange={(e) => setResponsibleFilter(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                  <option value="">Все сотрудники</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>{displayUserName(emp)}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="shrink-0 text-xs text-gray-500">Дата покупки:</span>
                <input type="date" value={dateFromFilter} onChange={(e) => setDateFromFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" placeholder="С" />
                <span className="text-xs text-gray-400">—</span>
                <input type="date" value={dateToFilter} onChange={(e) => setDateToFilter(e.target.value)} className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800" placeholder="По" />
              </div>
              {activeFilterCount > 0 && (
                <button type="button" onClick={() => { setStatusFilter(""); setCategoryFilter(""); setDepartmentFilter(""); setResponsibleFilter(""); setDateFromFilter(""); setDateToFilter(""); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100">
                  Очистить фильтры
                </button>
              )}
            </div>
          )}

          {/* Items list */}
          <div className="space-y-2">
            {filteredItems.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <Monitor size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Записи об оборудовании не найдены</p>
              </div>
            ) : (
              <>
                <div className="hidden grid-cols-[minmax(0,2.3fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto_auto] items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500 xl:grid">
                  <span>Оборудование</span>
                  <span>Ответственный</span>
                  <span>Статус</span>
                  <span>Стоимость</span>
                  <span>Дата покупки</span>
                  <span className="text-right">Действия</span>
                </div>

                {filteredItems.map((item) => {
                const responsibleName = getResponsibleName(item);
                const responsibleId = typeof item.responsible_person === "number" ? item.responsible_person : null;
                const responsibleLink = getResponsibleLink(item);
                const statusKey = String(item.status || "").toLowerCase();
                const st = statusMeta[statusKey] ?? defaultStatusMeta;
                const canEditThis = canManage;
                const canDeleteThis = canManage;
                const comments = commentsMap[item.id] || [];
                const rowOpen = Boolean(expandedRows[item.id]);
                const commentsOpen = Boolean(expandedComments[item.id]);
                const commentsTotal = item.comments_count ?? comments.length;
                const detailItem = detailsMap[item.id] || item;
                const metaItems = getEquipmentMeta(detailItem);
                const transferHistory = transferHistoryMap[item.id] || [];
                const maintenanceRecords = maintenanceMap[item.id] || [];
                const rowLoading = Boolean(loadingRowDetails[item.id]);

                return (
                  <article key={item.id} className="overflow-hidden rounded-xl border border-gray-200 bg-white transition hover:border-gray-300">
                    <div className="px-4 py-3 xl:hidden">
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={() => toggleRow(item.id)}
                          aria-label={rowOpen ? "Свернуть детали" : "Развернуть детали"}
                          className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"
                        >
                          <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className={`h-2 w-2 shrink-0 rounded-full ${st.accentClass}`} />
                                <h3 className="truncate text-sm font-semibold text-gray-900">{item.name || "Без названия"}</h3>
                              </div>
                              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                                <span className="font-medium text-gray-700">{item.inventory_number || "Без инв. номера"}</span>
                                {item.serial_number && <span>SN: {item.serial_number}</span>}
                              </div>
                            </div>

                            <div className="flex shrink-0 items-center gap-1.5">
                              <button type="button" title={`Комментарии (${commentsTotal})`} onClick={() => toggleComments(item.id)} className="relative inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 transition hover:border-sky-200 hover:bg-sky-50 hover:text-sky-700">
                                <MessageSquare size={15} />
                                {commentsTotal > 0 && (
                                  <span className="absolute -right-1 -top-1 inline-flex min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 py-0.5 text-[10px] font-bold text-white">{commentsTotal}</span>
                                )}
                              </button>
                              {canEditThis && (
                                <button type="button" title="Редактировать" onClick={() => openEdit(item)} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50">
                                  <Pencil size={15} />
                                </button>
                              )}
                              {canDeleteThis && (
                                <button type="button" title="Удалить" onClick={() => handleDelete(item.id)} disabled={busyKey === `delete-${item.id}`} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-rose-200 bg-rose-50 text-rose-600 transition hover:bg-rose-100 disabled:opacity-60">
                                  <Trash2 size={15} />
                                </button>
                              )}
                            </div>
                          </div>

                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            {statusKey && <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${st.className}`}>{st.label}</span>}
                            {item.is_under_warranty && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200" title="На гарантии">
                                <Shield size={11} /> Гарантия
                              </span>
                            )}
                          </div>

                          <div className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs text-gray-500 sm:grid-cols-2">
                            <div>
                              <span className="text-gray-400">Стоимость:</span>{" "}
                              <span className="font-medium text-gray-700">{formatMoney(item.purchase_cost)}</span>
                            </div>
                            <div>
                              <span className="text-gray-400">Покупка:</span>{" "}
                              <span className="font-medium text-gray-700">{formatDate(item.purchase_date) || "—"}</span>
                            </div>
                            {responsibleId ? (
                              <div className="col-span-2 min-w-0">
                                <span className="text-gray-400">Ответственный:</span>{" "}
                                <Link href={responsibleLink} className="font-medium text-sky-700 hover:text-sky-800">
                                  {responsibleName}
                                </Link>
                              </div>
                            ) : (
                              <div className="col-span-2 text-gray-400">Ответственный не назначен</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="hidden gap-3 px-4 py-3 xl:grid xl:grid-cols-[minmax(0,2.3fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto_auto] xl:items-center">
                      <div className="min-w-0">
                        <div className="flex items-start gap-3">
                          <button
                            type="button"
                            onClick={() => toggleRow(item.id)}
                            aria-label={rowOpen ? "Свернуть детали" : "Развернуть детали"}
                            className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-500 transition hover:bg-gray-100"
                          >
                            <ChevronDown size={15} className={`transition ${rowOpen ? "rotate-180" : ""}`} />
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={`h-2 w-2 shrink-0 rounded-full ${st.accentClass}`} />
                              <h3 className="truncate text-sm font-semibold text-gray-900">{item.name || "Без названия"}</h3>
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                              <span className="font-medium text-gray-700">{item.inventory_number || "Без инв. номера"}</span>
                              {item.serial_number && <span>SN: {item.serial_number}</span>}
                              {item.location && <span>{item.location}</span>}
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="min-w-0 text-sm">
                        {responsibleId ? (
                          <Link href={responsibleLink} className="group inline-flex max-w-full items-center gap-2 text-sm font-medium text-gray-700 transition hover:text-sky-700">
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-100 text-[11px] font-semibold text-sky-700 ring-1 ring-sky-200">
                              {responsibleName[0]?.toUpperCase() || "?"}
                            </span>
                            <span className="truncate">{responsibleName}</span>
                          </Link>
                        ) : (
                          <span className="text-sm text-gray-400">Не назначен</span>
                        )}
                      </div>

                      <div>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {statusKey && <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${st.className}`}>{st.label}</span>}
                          {item.is_under_warranty && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-700 ring-1 ring-gray-200" title="На гарантии">
                              <Shield size={11} /> Гарантия
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <p className="text-sm font-medium text-gray-700">{formatMoney(item.purchase_cost)}</p>
                      </div>

                      <div>
                        <p className="text-sm text-gray-600">{formatDate(item.purchase_date) || "—"}</p>
                      </div>

                      <div className="flex items-center justify-end gap-2 lg:justify-self-end">
                        <button type="button" title={`Комментарии (${commentsTotal})`} onClick={() => toggleComments(item.id)} className="relative inline-flex items-center justify-center rounded-lg border border-gray-200 bg-white p-2 text-gray-600 transition hover:border-sky-200 hover:bg-sky-50 hover:text-sky-700">
                          <MessageSquare size={15} />
                          {commentsTotal > 0 && (
                            <span className="absolute -right-1 -top-1 inline-flex min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 py-0.5 text-[10px] font-bold text-white">{commentsTotal}</span>
                          )}
                        </button>
                        {canEditThis && (
                          <button type="button" title="Редактировать" onClick={() => openEdit(item)} className="inline-flex items-center justify-center rounded-lg border border-gray-200 bg-white p-2 text-gray-600 transition hover:bg-gray-50">
                            <Pencil size={15} />
                          </button>
                        )}
                        {canDeleteThis && (
                          <button type="button" title="Удалить" onClick={() => handleDelete(item.id)} disabled={busyKey === `delete-${item.id}`} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-2 text-rose-600 transition hover:bg-rose-100 disabled:opacity-60">
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </div>

                    {(rowOpen || commentsOpen) && (
                      <div className="border-t border-gray-100 bg-gray-50/70 px-4 py-4">
                        {commentsOpen && (
                          <div className="rounded-xl border border-gray-200 bg-white p-3">
                            <div className="space-y-2">
                              {comments.length === 0 ? (
                                <p className="text-xs text-gray-500">Комментариев пока нет</p>
                              ) : (
                                comments.map((c) => {
                                  const canDel = Boolean(c.author?.id && (user?.id === c.author.id || auth?.is_staff || auth?.is_superuser));
                                  return (
                                    <div key={c.id} className="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 ring-1 ring-gray-100">
                                      <div className="mb-1 flex items-center justify-between gap-2">
                                        <span className="font-medium">{displayUserName(c.author)}</span>
                                        <div className="flex items-center gap-2">
                                          <span className="text-gray-500">{formatDate(c.created_at)}</span>
                                          {canDel && <button type="button" onClick={() => handleDeleteComment(item.id, c.id)} className="text-rose-600 hover:text-rose-700">удалить</button>}
                                        </div>
                                      </div>
                                      <p>{c.text}</p>
                                    </div>
                                  );
                                })
                              )}
                            </div>
                            <div className="mt-2 flex items-center gap-2">
                              <input value={commentDrafts[item.id] || ""} onChange={(e) => setCommentDrafts((p) => ({ ...p, [item.id]: e.target.value }))} placeholder="Добавить комментарий" className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-xs" />
                              <button type="button" onClick={() => handleAddComment(item.id)} disabled={busyKey === `comment-${item.id}`} className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-medium text-white hover:bg-sky-600 disabled:opacity-60">Отправить</button>
                            </div>
                          </div>
                        )}

                        {rowOpen && (
                          <>
                            {rowLoading && (
                              <div className={`${commentsOpen ? "mt-3 " : ""}mb-3 rounded-xl border border-sky-100 bg-sky-50 px-3 py-2 text-sm text-sky-700`}>
                                Загружаем детали оборудования...
                              </div>
                            )}

                            <div className={`${commentsOpen ? "mt-3 " : ""}mb-3 flex flex-wrap gap-2`}>
                              <button type="button" onClick={() => openOperationModal("transfer", detailItem)} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">
                                <ArrowRightLeft size={15} /> Перевести
                              </button>
                              <button type="button" onClick={() => openOperationModal("maintenance", detailItem)} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">
                                <Wrench size={15} /> Обслуживание
                              </button>
                              <button type="button" onClick={() => handleOpenQr(item.id)} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50">
                                <QrCode size={15} /> QR-код
                              </button>
                              {item.status !== "retired" && (
                                <button type="button" onClick={() => openOperationModal("writeoff", detailItem)} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-100">
                                  <Archive size={15} /> Списать
                                </button>
                              )}
                            </div>

                            {detailItem.notes && (
                              <div className="mb-3 rounded-xl bg-white px-3 py-2.5 ring-1 ring-gray-100">
                                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Заметки</p>
                                <p className="mt-1 text-sm leading-6 text-gray-700">{detailItem.notes}</p>
                              </div>
                            )}

                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                              {metaItems.map((meta) => (
                                <div key={meta.label} className="rounded-xl border border-gray-100 bg-white px-3 py-2">
                                  <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400">{meta.label}</p>
                                  <p className="mt-1 text-sm font-medium text-gray-700">{meta.value}</p>
                                </div>
                              ))}
                            </div>

                            <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
                              <div className="rounded-xl border border-gray-200 bg-white p-3">
                                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">История переводов</p>
                                {transferHistory.length === 0 ? (
                                  <p className="text-sm text-gray-500">Переводы пока не выполнялись</p>
                                ) : (
                                  <div className="space-y-2">
                                    {transferHistory.map((entry) => (
                                      <div key={entry.id} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                                        <div className="flex items-center justify-between gap-3">
                                          <span className="font-medium">{formatDate(entry.date)}</span>
                                          <span className="text-xs text-gray-500">{entry.created_by || "—"}</span>
                                        </div>
                                        <p className="mt-1 text-xs text-gray-600">{entry.from_department || "—"} → {entry.to_department || "—"}</p>
                                        {(entry.from_person || entry.to_person) && <p className="mt-1 text-xs text-gray-500">{entry.from_person || "—"} → {entry.to_person || "—"}</p>}
                                        {entry.reason && <p className="mt-1 text-xs text-gray-500">Причина: {entry.reason}</p>}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              <div className="rounded-xl border border-gray-200 bg-white p-3">
                                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">История обслуживания</p>
                                {maintenanceRecords.length === 0 ? (
                                  <p className="text-sm text-gray-500">Записей обслуживания пока нет</p>
                                ) : (
                                  <div className="space-y-2">
                                    {maintenanceRecords.map((record) => (
                                      <div key={record.id} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                                        <div className="flex items-center justify-between gap-3">
                                          <span className="font-medium">{record.type_display || record.type}</span>
                                          <span className="text-xs text-gray-500">{formatDate(record.date)}</span>
                                        </div>
                                        {record.description && <p className="mt-1 text-xs text-gray-600">{record.description}</p>}
                                        <div className="mt-1 flex items-center justify-between gap-3 text-xs text-gray-500">
                                          <span>{record.performed_by_name || "—"}</span>
                                          <span>{formatMoney(record.cost)}</span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </>
                        )}

                      </div>
                    )}
                  </article>
                );
              })}
              </>
            )}
          </div>

          {/* Load more */}
          {nextPage && (
            <div className="mt-4 flex justify-center">
              <button type="button" onClick={handleLoadMore} disabled={loadingMore} className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60">
                {loadingMore ? "Загружаем..." : "Загрузить ещё"}
              </button>
            </div>
          )}
        </section>
      )}

      {/* ===== Modal create/edit ===== */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
          <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">{modalMode === "create" ? "Добавить оборудование" : "Редактировать оборудование"}</h2>
              <button type="button" onClick={closeModal} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"><X size={18} /></button>
            </div>

            {actionError && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}

            <div className="flex flex-col gap-3">
              {/* Название */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Название оборудования *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Ноутбук Lenovo ThinkPad X1..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Категория */}
              <SearchableSelectSingle
                label="Категория *"
                placeholder="Выберите категорию..."
                items={categories.map((c) => ({ id: c.id, name: c.name }))}
                selectedId={form.category}
                onSelect={(id) => setForm((p) => ({ ...p, category: id }))}
              />

              {isCreateMode && previewInventoryNumber && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
                  Следующий инвентарный номер: <span className="font-semibold text-gray-900">{previewInventoryNumber}</span>
                </div>
              )}

              {/* Отдел */}
              <SearchableSelectSingle
                label="Отдел *"
                placeholder="Выберите отдел..."
                items={filteredDepartmentsForForm.map((d) => ({ id: d.id, name: d.name }))}
                selectedId={form.department}
                onSelect={(id) => setForm((p) => ({ ...p, department: id }))}
                disabled={Boolean(isCreateMode && createOptions && !createOptions.can_choose_department)}
              />

              {/* Ответственный */}
              <SearchableSelectSingle
                label="Ответственный"
                placeholder="Выберите сотрудника..."
                items={filteredEmployeesForForm.map((emp) => ({ id: emp.id, name: displayUserName(emp) }))}
                selectedId={form.responsible_person}
                onSelect={(id) => setForm((p) => ({ ...p, responsible_person: id }))}
                disabled={Boolean(isCreateMode && createOptions && !createOptions.can_choose_responsible)}
              />

              {modalMode === "create" && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Количество</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={form.quantity}
                    onChange={(e) => setForm((p) => ({ ...p, quantity: Math.max(1, Math.min(100, Number(e.target.value) || 1)) }))}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              )}

              {/* Дата покупки + стоимость */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Дата покупки *</label>
                  <input
                    type="date"
                    value={form.purchase_date}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_date: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Стоимость (₽) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.purchase_cost}
                    onChange={(e) => setForm((p) => ({ ...p, purchase_cost: e.target.value }))}
                    placeholder="0.00"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              </div>

              {/* Серийный номер */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Серийный номер</label>
                <input
                  value={form.serial_number}
                  onChange={(e) => setForm((p) => ({ ...p, serial_number: e.target.value }))}
                  placeholder="SN-XXXXX"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Расположение */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Расположение</label>
                <input
                  value={form.location}
                  onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
                  placeholder="Офис 305, стол 2..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>

              {/* Заметки */}
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Заметки</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
                  placeholder="Заметки об оборудовании..."
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100"
                />
              </div>
            </div>

            {/* Buttons */}
            <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t border-gray-100 pt-4">
              <button type="button" onClick={closeModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={() => handleSave(modalMode)} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">
                {modalMode === "create" ? "Добавить" : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}

      {operationModal && selectedEquipment && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4" onClick={(e) => { if (e.target === e.currentTarget) closeOperationModal(); }}>
          <div className="relative w-full max-w-lg rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900">
                {operationModal === "transfer" && "Перевод оборудования"}
                {operationModal === "writeoff" && "Списание оборудования"}
                {operationModal === "maintenance" && "Добавить обслуживание"}
              </h3>
              <button type="button" onClick={closeOperationModal} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"><X size={18} /></button>
            </div>

            {operationModal === "transfer" && (
              <div className="space-y-3">
                <SearchableSelectSingle
                  label="Новый отдел"
                  placeholder="Выберите отдел..."
                  items={departments.map((dept) => ({ id: dept.id, name: dept.name }))}
                  selectedId={transferForm.to_department}
                  onSelect={(id) => setTransferForm((prev) => ({ ...prev, to_department: id }))}
                />
                <SearchableSelectSingle
                  label="Новый ответственный"
                  placeholder="Выберите сотрудника..."
                  items={employees.map((employee) => ({ id: employee.id, name: displayUserName(employee) }))}
                  selectedId={transferForm.to_person}
                  onSelect={(id) => setTransferForm((prev) => ({ ...prev, to_person: id }))}
                />
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Причина</label>
                  <textarea value={transferForm.reason} onChange={(e) => setTransferForm((prev) => ({ ...prev, reason: e.target.value }))} rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                </div>
              </div>
            )}

            {operationModal === "writeoff" && (
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">Причина списания</label>
                <textarea value={writeOffReason} onChange={(e) => setWriteOffReason(e.target.value)} rows={4} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
              </div>
            )}

            {operationModal === "maintenance" && (
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Тип обслуживания</label>
                  <select value={maintenanceForm.type} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, type: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-800 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100">
                    <option value="repair">Ремонт</option>
                    <option value="maintenance">Обслуживание</option>
                    <option value="inspection">Осмотр</option>
                    <option value="upgrade">Модернизация</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-500">Дата</label>
                    <input type="date" value={maintenanceForm.date} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, date: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-500">Стоимость</label>
                    <input type="number" step="0.01" value={maintenanceForm.cost} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, cost: e.target.value }))} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500">Описание</label>
                  <textarea value={maintenanceForm.description} onChange={(e) => setMaintenanceForm((prev) => ({ ...prev, description: e.target.value }))} rows={4} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-100" />
                </div>
              </div>
            )}

            <div className="mt-5 flex items-center justify-end gap-2 border-t border-gray-100 pt-4">
              <button type="button" onClick={closeOperationModal} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              {operationModal === "transfer" && <button type="button" onClick={() => { void handleTransfer(); }} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">Перевести</button>}
              {operationModal === "writeoff" && <button type="button" onClick={() => { void handleWriteOff(); }} disabled={busyKey !== null} className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-60">Списать</button>}
              {operationModal === "maintenance" && <button type="button" onClick={() => { void handleMaintenance(); }} disabled={busyKey !== null} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">Добавить</button>}
            </div>
          </div>
        </div>
      )}

      {/* ===== Attachment preview removed (no attachment fields in model) ===== */}
    </AppShell>
  );
}
