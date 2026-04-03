"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import type { ProcurementSupplier } from "@/types/api";
import { Pencil, Plus, Star, Trash2 } from "lucide-react";
import { Modal } from "@/components/ui";

type Props = {
  canManage: boolean;
};

type SupplierForm = {
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  address: string;
  website: string;
  inn: string;
  rating: string;
  is_active: boolean;
  notes: string;
};

const emptyForm: SupplierForm = {
  name: "",
  contact_person: "",
  phone: "",
  email: "",
  address: "",
  website: "",
  inn: "",
  rating: "",
  is_active: true,
  notes: "",
};

export default function ProcurementSuppliersPanel({ canManage }: Props) {
  const [items, setItems] = useState<ProcurementSupplier[]>([]);
  const [topRated, setTopRated] = useState<ProcurementSupplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeOnly, setActiveOnly] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ProcurementSupplier | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<SupplierForm>(emptyForm);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [list, best] = await Promise.all([
        apiClient.getProcurementSuppliers({ ...(search ? { search } : {}), ...(activeOnly ? { is_active: activeOnly } : {}) }),
        apiClient.getTopRatedProcurementSuppliers(),
      ]);
      setItems(Array.isArray(list) ? list : list.results || []);
      setTopRated(Array.isArray(best) ? best : best.results || []);
    } catch (e: any) {
      setError(String(e?.message || "Не удалось загрузить поставщиков"));
      setItems([]);
      setTopRated([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [search, activeOnly]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEdit = (item: ProcurementSupplier) => {
    setEditing(item);
    setForm({
      name: item.name || "",
      contact_person: item.contact_person || "",
      phone: item.phone || "",
      email: item.email || "",
      address: item.address || "",
      website: item.website || "",
      inn: item.inn || "",
      rating: item.rating !== null && item.rating !== undefined ? String(item.rating) : "",
      is_active: Boolean(item.is_active),
      notes: item.notes || "",
    });
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditing(null);
    setForm(emptyForm);
  };

  const handleSave = async () => {
    try {
      setBusy(true);
      setError(null);
      const payload = {
        ...form,
        rating: form.rating === "" ? null : Number(form.rating),
      };
      if (editing) {
        await apiClient.updateProcurementSupplier(editing.id, payload);
      } else {
        await apiClient.createProcurementSupplier(payload);
      }
      closeForm();
      await load();
    } catch (e: any) {
      setError(String(e?.message || "Не удалось сохранить поставщика"));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Удалить поставщика?")) return;
    try {
      setBusy(true);
      setError(null);
      await apiClient.deleteProcurementSupplier(id);
      await load();
    } catch (e: any) {
      setError(String(e?.message || "Не удалось удалить поставщика"));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="rounded-xl bg-gray-50 p-8 text-center text-sm text-gray-500">Загрузка поставщиков...</div>;
  }

  return (
    <div className="space-y-4">
      {error && <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="rounded-xl border border-gray-200 bg-white p-4 ring-1 ring-gray-100">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Поиск по поставщикам" className="w-64 rounded-lg border border-gray-200 px-3 py-2 text-sm" />
            <select value={activeOnly} onChange={(e) => setActiveOnly(e.target.value)} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700">
              <option value="">Все</option>
              <option value="true">Только активные</option>
              <option value="false">Только неактивные</option>
            </select>
          </div>
          {canManage && (
            <button type="button" onClick={openCreate} className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600">
              <Plus size={14} /> Новый поставщик
            </button>
          )}
        </div>

        {topRated.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {topRated.map((supplier) => (
              <span key={supplier.id} className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-100">
                <Star size={12} /> {supplier.name} · {supplier.rating ?? "—"}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white ring-1 ring-gray-100">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
            <tr>
              <th className="px-4 py-3 font-medium">Поставщик</th>
              <th className="px-4 py-3 font-medium">Контакт</th>
              <th className="px-4 py-3 font-medium">ИНН</th>
              <th className="px-4 py-3 font-medium text-right">Рейтинг</th>
              <th className="px-4 py-3 font-medium text-right">Статус</th>
              {canManage && <th className="px-4 py-3 font-medium text-right">Действия</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((item) => (
              <tr key={item.id}>
                <td className="px-4 py-3">
                  <div>
                    <p className="font-medium text-gray-900">{item.name}</p>
                    {item.website && <p className="text-xs text-sky-600">{item.website}</p>}
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-700">
                  <div>{item.contact_person || "—"}</div>
                  <div className="text-xs text-gray-500">{item.email || item.phone || "—"}</div>
                </td>
                <td className="px-4 py-3 text-gray-700">{item.inn || "—"}</td>
                <td className="px-4 py-3 text-right text-gray-700">{item.rating ?? "—"}</td>
                <td className="px-4 py-3 text-right">
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${item.is_active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600"}`}>
                    {item.is_active ? "Активен" : "Неактивен"}
                  </span>
                </td>
                {canManage && (
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button type="button" onClick={() => openEdit(item)} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white p-2 text-gray-600 hover:bg-gray-50"><Pencil size={14} /></button>
                      <button type="button" onClick={() => handleDelete(item.id)} className="inline-flex items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-2 text-rose-600 hover:bg-rose-100"><Trash2 size={14} /></button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal isOpen={formOpen && canManage} onClose={closeForm} title={editing ? "Редактировать поставщика" : "Новый поставщик"} size="md" footer={
            <div className="flex justify-end gap-2">
              <button type="button" onClick={closeForm} className="rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300">Отмена</button>
              <button type="button" onClick={handleSave} disabled={busy} className="rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60">Сохранить</button>
            </div>
      }>
            <div className="grid gap-3">
              <input value={form.name} onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))} placeholder="Название *" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              <div className="grid grid-cols-2 gap-3">
                <input value={form.contact_person} onChange={(e) => setForm((prev) => ({ ...prev, contact_person: e.target.value }))} placeholder="Контактное лицо" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
                <input value={form.inn} onChange={(e) => setForm((prev) => ({ ...prev, inn: e.target.value }))} placeholder="ИНН" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input value={form.phone} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} placeholder="Телефон" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
                <input value={form.email} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} placeholder="Email" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input value={form.website} onChange={(e) => setForm((prev) => ({ ...prev, website: e.target.value }))} placeholder="Сайт" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
                <input value={form.rating} onChange={(e) => setForm((prev) => ({ ...prev, rating: e.target.value }))} placeholder="Рейтинг" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <input value={form.address} onChange={(e) => setForm((prev) => ({ ...prev, address: e.target.value }))} placeholder="Адрес" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              <textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} rows={3} placeholder="Заметки" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.checked }))} /> Активный поставщик
              </label>
            </div>
      </Modal>
    </div>
  );
}
