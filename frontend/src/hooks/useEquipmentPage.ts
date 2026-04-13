"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";
import { canManageEquipment, canManageEquipmentCategories } from "@/lib/permissions";
import { displayUserName as sharedDisplayUserName, extractNextPage, formatDate, formatMoney, loadAllPages } from "@/lib/shared";
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

type PaginatedLike<T> = {
  results?: T[];
  next?: string | null;
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

const createInitialMaintenanceForm = (): MaintenanceFormState => ({
  type: "repair",
  description: "",
  cost: "",
  date: new Date().toISOString().slice(0, 10),
});

const getPaginatedResults = <T,>(response: unknown): T[] => {
  if (Array.isArray(response)) {
    return response as T[];
  }

  if (response && typeof response === "object") {
    const results = (response as PaginatedLike<T>).results;
    if (Array.isArray(results)) {
      return results;
    }
  }

  return [];
};

const getPaginatedNext = (response: unknown): number | null => {
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    return null;
  }

  return extractNextPage((response as PaginatedLike<unknown>).next ?? null);
};

const getReadableError = (error: unknown, fallback: string): string => {
  const raw = String((error as Error)?.message || fallback);

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return Object.entries(parsed)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
      .join(". ");
  } catch {
    return raw;
  }
};

export function useEquipmentPage(user: User | null) {
  const canManage = canManageEquipment(user);
  const canManageCategories = canManageEquipmentCategories(user);
  const auth = user?.auth;

  const [items, setItems] = useState<Equipment[]>([]);
  const [detailsMap, setDetailsMap] = useState<Record<number, Equipment>>({});
  const [transferHistoryMap, setTransferHistoryMap] = useState<Record<number, EquipmentTransferHistoryEntry[]>>({});
  const [maintenanceMap, setMaintenanceMap] = useState<Record<number, MaintenanceRecord[]>>({});
  const [employees, setEmployees] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [categories, setCategories] = useState<EquipmentCategory[]>([]);
  const [createOptions, setCreateOptions] = useState<EquipmentCreateOptions | null>(null);
  const [previewInventoryNumber, setPreviewInventoryNumber] = useState("");
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
  const [maintenanceForm, setMaintenanceForm] = useState<MaintenanceFormState>(createInitialMaintenanceForm);

  const [searchQuery, setSearchQuery] = useState("");
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

  const isCreateMode = createOpen && editingId === null;

  const displayUserName = useCallback((person?: User | null) => sharedDisplayUserName(person), []);

  const buildParams = useCallback(
    (page: number): Record<string, string | number> => {
      const params: Record<string, string | number> = { page };
      if (deferredSearchQuery.trim()) params.search = deferredSearchQuery.trim();
      if (ordering) params.ordering = ordering;
      if (statusFilter) params.status = statusFilter;
      if (categoryFilter) params.category = categoryFilter;
      if (departmentFilter) params.department = departmentFilter;
      if (responsibleFilter) params.responsible_person = responsibleFilter;
      if (dateFromFilter) params.purchase_date__gte = dateFromFilter;
      if (dateToFilter) params.purchase_date__lte = dateToFilter;
      return params;
    },
    [categoryFilter, dateFromFilter, dateToFilter, deferredSearchQuery, departmentFilter, ordering, responsibleFilter, statusFilter],
  );

  const fetchEquipmentPage = useCallback(
    async (page: number): Promise<unknown> => {
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
    },
    [buildParams, listMode],
  );

  const reloadEquipmentList = useCallback(async () => {
    const response = await fetchEquipmentPage(1);
    setItems(getPaginatedResults<Equipment>(response));
    setNextPage(getPaginatedNext(response));
  }, [fetchEquipmentPage]);

  const getCategoryName = useCallback(
    (equipment: Equipment): string => {
      if (equipment.category_name) return equipment.category_name;
      const category = categories.find((item) => item.id === Number(equipment.category));
      return category?.name || "—";
    },
    [categories],
  );

  const getDepartmentName = useCallback(
    (equipment: Equipment): string => {
      if (equipment.department_name) return equipment.department_name;
      const department = departments.find((item) => item.id === Number(equipment.department));
      return department?.name || "—";
    },
    [departments],
  );

  const getResponsibleName = useCallback(
    (equipment: Equipment): string => {
      if (equipment.responsible_name) return equipment.responsible_name;
      if (equipment.responsible_person && typeof equipment.responsible_person === "number") {
        const employee = employees.find((item) => item.id === equipment.responsible_person);
        return employee ? displayUserName(employee) : "—";
      }
      return "—";
    },
    [displayUserName, employees],
  );

  const getResponsibleLink = useCallback(
    (equipment: Equipment): string => {
      if (!equipment.responsible_person || typeof equipment.responsible_person !== "number") return "";
      if (equipment.responsible_person === user?.id) return "/profile";
      return `/users/${equipment.responsible_person}`;
    },
    [user?.id],
  );

  const getEquipmentMeta = useCallback(
    (equipment: Equipment) => ([
      { label: "Категория", value: getCategoryName(equipment) },
      { label: "Отдел", value: getDepartmentName(equipment) },
      { label: "Ответственный", value: getResponsibleName(equipment) },
      { label: "Серийный номер", value: equipment.serial_number || "—" },
      { label: "Расположение", value: equipment.location || "—" },
      { label: "Гарантия до", value: formatDate(equipment.warranty_until) || "—" },
      { label: "Обслуживаний", value: String(equipment.maintenance_count ?? "—") },
      { label: "Стоимость", value: formatMoney(equipment.purchase_cost) },
      { label: "Добавлено", value: formatDate(equipment.created_at) || "—" },
    ]),
    [getCategoryName, getDepartmentName, getResponsibleName],
  );

  const filteredDepartmentsForForm = useMemo(() => {
    if (!createOptions || !isCreateMode || createOptions.allowed_departments.length === 0) {
      return departments;
    }

    const allowedIds = new Set(createOptions.allowed_departments.map((department) => department.id));
    return departments.filter((department) => allowedIds.has(department.id));
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

  const applyCreateDefaults = useCallback((options: EquipmentCreateOptions | null) => {
    if (!options) return;

    setForm((previous) => {
      const nextDepartment = options.can_choose_department
        ? previous.department
        : options.allowed_departments[0]?.id ?? previous.department;
      const nextResponsible = options.can_choose_responsible
        ? previous.responsible_person
        : options.default_responsible?.id ?? previous.responsible_person;

      return {
        ...previous,
        department: nextDepartment,
        responsible_person: nextResponsible,
      };
    });
  }, []);

  const loadRowDetails = useCallback(async (equipmentId: number) => {
    if (loadingRowDetails[equipmentId]) return;

    try {
      setLoadingRowDetails((previous) => ({ ...previous, [equipmentId]: true }));
      const results = await Promise.allSettled([
        detailsMap[equipmentId] ? Promise.resolve(detailsMap[equipmentId]) : apiClient.getEquipmentDetail(equipmentId),
        transferHistoryMap[equipmentId] ? Promise.resolve(transferHistoryMap[equipmentId]) : apiClient.getEquipmentTransferHistory(equipmentId),
        maintenanceMap[equipmentId] ? Promise.resolve(maintenanceMap[equipmentId]) : apiClient.getMaintenanceRecords({ equipment: equipmentId }),
      ]);

      const [detailResult, transferResult, maintenanceResult] = results;

      if (detailResult.status === "fulfilled") {
        setDetailsMap((previous) => ({ ...previous, [equipmentId]: detailResult.value as Equipment }));
      }

      if (transferResult.status === "fulfilled") {
        setTransferHistoryMap((previous) => ({
          ...previous,
          [equipmentId]: getPaginatedResults<EquipmentTransferHistoryEntry>(transferResult.value),
        }));
      }

      if (maintenanceResult.status === "fulfilled") {
        setMaintenanceMap((previous) => ({
          ...previous,
          [equipmentId]: getPaginatedResults<MaintenanceRecord>(maintenanceResult.value),
        }));
      }
    } catch (loadError) {
      console.error("Ошибка загрузки деталей оборудования:", loadError);
    } finally {
      setLoadingRowDetails((previous) => ({ ...previous, [equipmentId]: false }));
    }
  }, [detailsMap, loadingRowDetails, maintenanceMap, transferHistoryMap]);

  const resetForm = useCallback(() => {
    setForm(emptyForm);
  }, []);

  const openCreateModal = useCallback(async () => {
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
    } catch (loadError) {
      console.error("Ошибка загрузки опций создания оборудования:", loadError);
    }
  }, [applyCreateDefaults, resetForm]);

  const openEdit = useCallback((equipment: Equipment) => {
    setEditingId(equipment.id);
    setCreateOpen(false);
    setActionError(null);
    setActionSuccess(null);
    setPreviewInventoryNumber(equipment.inventory_number || "");
    setForm({
      name: equipment.name || "",
      notes: equipment.notes || "",
      category: equipment.category ?? null,
      department: equipment.department ?? null,
      responsible_person: typeof equipment.responsible_person === "number" ? equipment.responsible_person : null,
      quantity: 1,
      serial_number: equipment.serial_number || "",
      purchase_date: equipment.purchase_date || "",
      purchase_cost: String(equipment.purchase_cost || ""),
      location: equipment.location || "",
    });
  }, []);

  const openOperationModal = useCallback((type: Exclude<OperationModal, null>, equipment: Equipment) => {
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
      setMaintenanceForm(createInitialMaintenanceForm());
    }
  }, []);

  const closeOperationModal = useCallback(() => {
    setOperationModal(null);
    setSelectedEquipment(null);
    setWriteOffReason("");
    setTransferForm({ to_department: null, to_person: null, reason: "" });
    setMaintenanceForm(createInitialMaintenanceForm());
  }, []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetchEquipmentPage(1);
        if (cancelled) return;
        setItems(getPaginatedResults<Equipment>(response));
        setNextPage(getPaginatedNext(response));
      } catch (loadError) {
        if (cancelled) return;
        console.error("Ошибка загрузки оборудования:", loadError);
        setError("Не удалось загрузить оборудование");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fetchEquipmentPage]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const [allEmployees, allDepartments, allCategories] = await Promise.all([
          loadAllPages<User>((page) => apiClient.getEmployees(page)),
          loadAllPages<Department>((page) => apiClient.getDepartments(page)),
          loadAllPages<EquipmentCategory>((page) => apiClient.getEquipmentCategories(page)),
        ]);

        if (cancelled) return;
        setEmployees(allEmployees);
        setDepartments(allDepartments);
        setCategories(allCategories);
      } catch (loadError) {
        if (!cancelled) {
          console.error("Ошибка загрузки справочников:", loadError);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const options = await apiClient.getEquipmentCreateOptions();
        if (!cancelled) {
          setCreateOptions(options);
        }
      } catch (loadError) {
        if (!cancelled) {
          console.error("Ошибка загрузки create options:", loadError);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const sortItemsLocally = useCallback((source: Equipment[]) => {
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
  }, [ordering]);

  const filteredItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
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
    if (!query) return sorted;

    return sorted.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const notes = (item.notes || "").toLowerCase();
      const serialNumber = (item.serial_number || "").toLowerCase();
      const inventoryNumber = (item.inventory_number || "").toLowerCase();
      const responsible = getResponsibleName(item).toLowerCase();
      const category = getCategoryName(item).toLowerCase();

      return (
        name.includes(query)
        || notes.includes(query)
        || serialNumber.includes(query)
        || inventoryNumber.includes(query)
        || responsible.includes(query)
        || category.includes(query)
      );
    });
  }, [
    categoryFilter,
    dateFromFilter,
    dateToFilter,
    departmentFilter,
    getCategoryName,
    getResponsibleName,
    items,
    listMode,
    responsibleFilter,
    searchQuery,
    sortItemsLocally,
    statusFilter,
  ]);

  const handleSave = useCallback(async (mode: "create" | "edit") => {
    try {
      setBusyKey(`${mode}-save`);
      setActionError(null);
      setActionSuccess(null);

      if (!form.name.trim()) {
        setActionError("Укажите название оборудования.");
        return;
      }
      if (!form.category) {
        setActionError("Выберите категорию.");
        return;
      }
      if (!form.department) {
        setActionError("Выберите отдел.");
        return;
      }
      if (!form.purchase_date) {
        setActionError("Укажите дату покупки.");
        return;
      }
      if (!form.purchase_cost) {
        setActionError("Укажите стоимость.");
        return;
      }

      const payload: Record<string, unknown> = {
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
    } catch (saveError) {
      setActionError(getReadableError(saveError, "Не удалось сохранить"));
    } finally {
      setBusyKey(null);
    }
  }, [editingId, form, reloadEquipmentList, resetForm]);

  const handleCreateCategory = useCallback(async (name: string) => {
    const normalizedName = name.trim();
    if (!normalizedName) {
      setActionError("Укажите название категории.");
      return null;
    }

    const existing = categories.find(
      (category) => category.name.trim().toLowerCase() === normalizedName.toLowerCase(),
    );
    if (existing) {
      setForm((previous) => ({ ...previous, category: existing.id }));
      setActionSuccess(`Категория "${existing.name}" уже существует и выбрана.`);
      setActionError(null);
      return existing;
    }

    try {
      setBusyKey("create-category");
      setActionError(null);
      setActionSuccess(null);

      const created = await apiClient.createEquipmentCategory({ name: normalizedName }) as EquipmentCategory;

      setCategories((previous) => (
        [...previous, created].sort((left, right) => left.name.localeCompare(right.name, "ru"))
      ));
      setForm((previous) => ({ ...previous, category: created.id }));
      setActionSuccess(`Категория "${created.name}" создана.`);
      return created;
    } catch (categoryError) {
      setActionError(getReadableError(categoryError, "Не удалось создать категорию"));
      return null;
    } finally {
      setBusyKey(null);
    }
  }, [categories]);

  const handleLoadMore = useCallback(async () => {
    if (!nextPage || loadingMore) return;

    try {
      setLoadingMore(true);
      const response = await fetchEquipmentPage(nextPage);
      const chunk = getPaginatedResults<Equipment>(response);
      setItems((previous) => {
        const known = new Set(previous.map((item) => item.id));
        return [...previous, ...chunk.filter((item) => !known.has(item.id))];
      });
      setNextPage(getPaginatedNext(response));
    } catch {
      setError("Не удалось загрузить ещё");
    } finally {
      setLoadingMore(false);
    }
  }, [fetchEquipmentPage, loadingMore, nextPage]);

  const handleDelete = useCallback(async (id: number) => {
    if (!window.confirm("Удалить это оборудование?")) return;

    try {
      setBusyKey(`delete-${id}`);
      await apiClient.deleteEquipment(id);
      setItems((previous) => previous.filter((item) => item.id !== id));
    } catch {
      setActionError("Не удалось удалить");
    } finally {
      setBusyKey(null);
    }
  }, []);

  const toggleRow = useCallback((equipmentId: number) => {
    const nextOpen = !expandedRows[equipmentId];
    setExpandedRows((previous) => ({ ...previous, [equipmentId]: nextOpen }));
    if (nextOpen) {
      void loadRowDetails(equipmentId);
    }
  }, [expandedRows, loadRowDetails]);

  const handleTransfer = useCallback(async () => {
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
    } catch (transferError) {
      setActionError(String((transferError as Error)?.message || "Не удалось выполнить перевод"));
    } finally {
      setBusyKey(null);
    }
  }, [closeOperationModal, loadRowDetails, reloadEquipmentList, selectedEquipment, transferForm]);

  const handleWriteOff = useCallback(async () => {
    if (!selectedEquipment) return;

    try {
      setBusyKey(`writeoff-${selectedEquipment.id}`);
      await apiClient.writeOffEquipment(selectedEquipment.id, writeOffReason);
      setActionSuccess("Оборудование списано.");
      closeOperationModal();
      await reloadEquipmentList();
      await loadRowDetails(selectedEquipment.id);
    } catch (writeOffError) {
      setActionError(String((writeOffError as Error)?.message || "Не удалось списать оборудование"));
    } finally {
      setBusyKey(null);
    }
  }, [closeOperationModal, loadRowDetails, reloadEquipmentList, selectedEquipment, writeOffReason]);

  const handleMaintenance = useCallback(async () => {
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
    } catch (maintenanceError) {
      setActionError(String((maintenanceError as Error)?.message || "Не удалось добавить обслуживание"));
    } finally {
      setBusyKey(null);
    }
  }, [closeOperationModal, loadRowDetails, maintenanceForm, selectedEquipment]);

  const openEquipmentById = useCallback(async (equipmentId: number, options?: { expand?: boolean }) => {
    if (options?.expand !== false) {
      setExpandedRows((previous) => ({ ...previous, [equipmentId]: true }));
    }

    const existing = detailsMap[equipmentId] || items.find((item) => item.id === equipmentId);
    if (!existing) {
      try {
        const detail = (await apiClient.getEquipmentDetail(equipmentId)) as Equipment;
        setItems((previous) =>
          previous.some((item) => item.id === equipmentId)
            ? previous
            : [detail, ...previous]
        );
        setDetailsMap((previous) => ({ ...previous, [equipmentId]: detail }));
      } catch (loadError) {
        setActionError(String((loadError as Error)?.message || "Не удалось открыть оборудование"));
        return;
      }
    }

    await loadRowDetails(equipmentId);
  }, [detailsMap, items, loadRowDetails]);

  const toggleComments = useCallback(async (equipmentId: number) => {
    const isOpen = Boolean(expandedComments[equipmentId]);
    setExpandedComments((previous) => ({ ...previous, [equipmentId]: !isOpen }));

    if (!isOpen && !commentsMap[equipmentId]) {
      try {
        const response = await apiClient.getEquipmentComments(equipmentId);
        setCommentsMap((previous) => ({
          ...previous,
          [equipmentId]: getPaginatedResults<EquipmentComment>(response),
        }));
      } catch {
        setCommentsMap((previous) => ({ ...previous, [equipmentId]: [] }));
      }
    }
  }, [commentsMap, expandedComments]);

  const handleAddComment = useCallback(async (equipmentId: number) => {
    const text = (commentDrafts[equipmentId] || "").trim();
    if (!text) return;

    try {
      setBusyKey(`comment-${equipmentId}`);
      const saved = await apiClient.addEquipmentComment(equipmentId, text);
      setCommentsMap((previous) => ({ ...previous, [equipmentId]: [...(previous[equipmentId] || []), saved as EquipmentComment] }));
      setCommentDrafts((previous) => ({ ...previous, [equipmentId]: "" }));
    } catch {
      setActionError("Не удалось добавить комментарий");
    } finally {
      setBusyKey(null);
    }
  }, [commentDrafts]);

  const handleDeleteComment = useCallback(async (equipmentId: number, commentId: number) => {
    try {
      setBusyKey(`comment-delete-${commentId}`);
      await apiClient.deleteEquipmentComment(equipmentId, commentId);
      setCommentsMap((previous) => ({
        ...previous,
        [equipmentId]: (previous[equipmentId] || []).filter((comment) => comment.id !== commentId),
      }));
    } catch {
      setActionError("Не удалось удалить комментарий");
    } finally {
      setBusyKey(null);
    }
  }, []);

  const modalMode: "create" | "edit" = editingId ? "edit" : "create";
  const isModalOpen = createOpen || editingId !== null;

  const closeModal = useCallback(() => {
    setCreateOpen(false);
    setEditingId(null);
    resetForm();
    setActionError(null);
  }, [resetForm]);

  const activeFilterCount = [statusFilter, categoryFilter, departmentFilter, responsibleFilter, dateFromFilter, dateToFilter].filter(Boolean).length;

  return {
    auth,
    actionError,
    actionSuccess,
    activeFilterCount,
    busyKey,
    canManage,
    canManageCategories,
    categories,
    categoryFilter,
    closeModal,
    closeOperationModal,
    commentDrafts,
    commentsMap,
    createOptions,
    dateFromFilter,
    dateToFilter,
    departmentFilter,
    departments,
    detailsMap,
    displayUserName,
    editingId,
    employees,
    error,
    expandedComments,
    expandedRows,
    filteredDepartmentsForForm,
    filteredEmployeesForForm,
    filteredItems,
    filtersOpen,
    form,
    getEquipmentMeta,
    getResponsibleLink,
    getResponsibleName,
    handleAddComment,
    handleCreateCategory,
    handleDelete,
    handleDeleteComment,
    handleLoadMore,
    handleMaintenance,
    handleSave,
    handleTransfer,
    handleWriteOff,
    openEquipmentById,
    isCreateMode,
    isModalOpen,
    listMode,
    loading,
    loadingMore,
    loadingRowDetails,
    maintenanceForm,
    maintenanceMap,
    modalMode,
    nextPage,
    openCreateModal,
    openEdit,
    openOperationModal,
    operationModal,
    ordering,
    previewInventoryNumber,
    responsibleFilter,
    searchQuery,
    selectedEquipment,
    setCategoryFilter,
    setCommentDrafts,
    setDateFromFilter,
    setDateToFilter,
    setDepartmentFilter,
    setFiltersOpen,
    setForm,
    setListMode,
    setMaintenanceForm,
    setOrdering,
    setResponsibleFilter,
    setSearchQuery,
    setStatusFilter,
    setTransferForm,
    setWriteOffReason,
    statusFilter,
    transferForm,
    transferHistoryMap,
    toggleComments,
    toggleRow,
    writeOffReason,
  };
}
