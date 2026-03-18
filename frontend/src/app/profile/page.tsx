"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import { Camera, Pencil, Save, X } from "lucide-react";

function formatDate(value?: string): string {
	if (!value) return "";
	const d = new Date(value);
	if (Number.isNaN(d.getTime())) return "";
	return d.toLocaleString("ru-RU", {
		day: "2-digit",
		month: "2-digit",
		year: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

export default function ProfilePage() {
	const { user, loading, refreshUser } = useUser();
	const avatarInputRef = useRef<HTMLInputElement | null>(null);
	const [editProfileOpen, setEditProfileOpen] = useState(false);
	const [editContactsOpen, setEditContactsOpen] = useState(false);
	const [savingProfile, setSavingProfile] = useState(false);
	const [savingContacts, setSavingContacts] = useState(false);
	const [profileError, setProfileError] = useState<string | null>(null);
	const [contactsError, setContactsError] = useState<string | null>(null);
	const [avatarFile, setAvatarFile] = useState<File | null>(null);
	const [profileForm, setProfileForm] = useState({
		last_name: "",
		first_name: "",
		patronymic: "",
		birth_date: "",
	});
	const [contactsForm, setContactsForm] = useState({
		email: "",
		phone_number: "",
		telegram: "",
		whatsapp: "",
		wechat: "",
	});

	const fullName = useMemo(() => {
		if (!user) return "";
		return `${user.last_name || ""} ${user.first_name || ""} ${user.patronymic || ""}`.trim() || "Пользователь";
	}, [user]);

	const initials = useMemo(() => {
		if (!user) return "П";
		const s = `${user.last_name?.[0] || ""}${user.first_name?.[0] || ""}`.trim();
		return s || "П";
	}, [user]);

	const departments = user?.departments || [];
	const skills = user?.skills || [];
	const actions = user?.actions || [];

	const birthDateLabel = useMemo(() => {
		if (!user?.birth_date) return "—";
		const d = new Date(user.birth_date);
		if (Number.isNaN(d.getTime())) return user.birth_date;
		return d.toLocaleDateString("ru-RU", {
			day: "2-digit",
			month: "2-digit",
			year: "numeric",
		});
	}, [user?.birth_date]);

	useEffect(() => {
		if (!user) return;
		setProfileForm({
			last_name: user.last_name || "",
			first_name: user.first_name || "",
			patronymic: user.patronymic || "",
			birth_date: user.birth_date || "",
		});
		setContactsForm({
			email: user.email || "",
			phone_number: user.phone_number || "",
			telegram: user.telegram || "",
			whatsapp: user.whatsapp || "",
			wechat: user.wechat || "",
		});
	}, [user]);

	const handleSaveProfile = async () => {
		try {
			setSavingProfile(true);
			setProfileError(null);

			await apiClient.updateCurrentUserProfile({
				last_name: profileForm.last_name.trim(),
				first_name: profileForm.first_name.trim(),
				patronymic: profileForm.patronymic.trim(),
				birth_date: profileForm.birth_date.trim() || null,
				avatar: avatarFile || undefined,
			});

			await refreshUser();
			setAvatarFile(null);
			setEditProfileOpen(false);
		} catch (e: any) {
			setProfileError(String(e?.message || "Не удалось сохранить профиль"));
		} finally {
			setSavingProfile(false);
		}
	};

	const handleSaveContacts = async () => {
		try {
			setSavingContacts(true);
			setContactsError(null);

			await apiClient.updateCurrentUserProfile({
				email: contactsForm.email.trim(),
				phone_number: contactsForm.phone_number.trim(),
				telegram: contactsForm.telegram.trim(),
				whatsapp: contactsForm.whatsapp.trim(),
				wechat: contactsForm.wechat.trim(),
			});

			await refreshUser();
			setEditContactsOpen(false);
		} catch (e: any) {
			setContactsError(String(e?.message || "Не удалось сохранить контакты"));
		} finally {
			setSavingContacts(false);
		}
	};

	if (loading) {
		return (
			<AppShell>
				<div className="flex items-center justify-center py-12">
					<div className="text-center">
						<div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
						<p className="text-sm text-gray-500">Загрузка профиля...</p>
					</div>
				</div>
			</AppShell>
		);
	}

	if (!user) {
		return null;
	}

	const normalizeTelegram = (value: string) => {
		const v = value.trim();
		if (!v) return "";
		if (/^https?:\/\//i.test(v)) return v;
		return `https://t.me/${v.replace(/^@/, "")}`;
	};

	const normalizeWhatsApp = (value: string) => {
		const v = value.trim();
		if (!v) return "";
		if (/^https?:\/\//i.test(v)) return v;
		const digits = v.replace(/[^\d]/g, "");
		return digits ? `https://wa.me/${digits}` : "";
	};

	const contactItems = [
		{ label: "Телефон", value: user.phone_number?.trim() || "", href: user.phone_number?.trim() ? `tel:${user.phone_number.trim().replace(/\s+/g, "")}` : "", external: false },
		{ label: "Почта", value: user.email?.trim() || "", href: user.email?.trim() ? `mailto:${user.email.trim()}` : "", external: false },
		{ label: "Telegram", value: user.telegram?.trim() || "", href: normalizeTelegram(user.telegram || ""), external: true },
		{ label: "WhatsApp", value: user.whatsapp?.trim() || "", href: normalizeWhatsApp(user.whatsapp || ""), external: true },
		{ label: "WeChat", value: user.wechat?.trim() || "", href: "", external: false },
	].filter((item) => item.value);

	const editableContactItems = [
		{ label: "Телефон", key: "phone_number" as const },
		{ label: "Почта", key: "email" as const },
		{ label: "Telegram", key: "telegram" as const },
		{ label: "WhatsApp", key: "whatsapp" as const },
		{ label: "WeChat", key: "wechat" as const },
	];

	return (
		<AppShell>
			<div className="space-y-4">
				<section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
					<div className="flex items-start gap-4">
						<div className="shrink-0">
							<div className="relative h-16 w-16">
								{user.avatar ? (
									<a href={resolveMediaUrl(user.avatar)} target="_blank" rel="noreferrer" title="Открыть фото" className="block h-16 w-16 overflow-hidden rounded-full bg-sky-400">
										<Image
											src={resolveMediaUrl(user.avatar)}
											alt={fullName}
											width={64}
											height={64}
											className="h-full w-full object-cover"
											unoptimized
										/>
									</a>
								) : (
									<div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-lg font-semibold text-white">{initials}</div>
								)}
							</div>
							<input
								ref={avatarInputRef}
								type="file"
								accept="image/*"
								onChange={(e) => {
									setAvatarFile(e.target.files?.[0] || null);
									setEditProfileOpen(true);
								}}
								className="hidden"
							/>
							{editProfileOpen ? (
								<button
									type="button"
									onClick={() => avatarInputRef.current?.click()}
									className="mt-2 inline-flex w-full items-center justify-center rounded-md border border-gray-200 px-2 py-1 text-gray-700 hover:bg-gray-50"
									title="Заменить фото"
								>
									<Camera size={14} />
								</button>
							) : null}
						</div>

						<div className="min-w-0 flex-1">
							<div className="flex items-start justify-between gap-3">
								{editProfileOpen ? (
									<div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-3">
										<input value={profileForm.last_name} onChange={(e) => setProfileForm((p) => ({ ...p, last_name: e.target.value }))} placeholder="Фамилия" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
										<input value={profileForm.first_name} onChange={(e) => setProfileForm((p) => ({ ...p, first_name: e.target.value }))} placeholder="Имя" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
										<input value={profileForm.patronymic} onChange={(e) => setProfileForm((p) => ({ ...p, patronymic: e.target.value }))} placeholder="Отчество" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
									</div>
								) : (
									<p className="truncate text-xl font-semibold text-gray-900">{fullName}</p>
								)}
								<button
									type="button"
									onClick={() => {
										setEditProfileOpen((v) => !v);
										setProfileError(null);
									}}
									className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50"
									title="Редактировать профиль"
								>
									<Pencil size={14} />
								</button>
							</div>
							{editProfileOpen ? (
								<div className="mt-2 flex items-center gap-2 text-sm text-gray-600">
									<span>Дата рождения:</span>
									<input type="date" value={profileForm.birth_date} onChange={(e) => setProfileForm((p) => ({ ...p, birth_date: e.target.value }))} className="rounded-lg border border-gray-300 px-2 py-1 text-sm" />
								</div>
							) : (
								<p className="mt-1 text-sm text-gray-600">Дата рождения: {birthDateLabel}</p>
							)}
							<p className="mt-1 text-sm text-gray-600">Должность: {user.position?.name || "—"}</p>

							<div className="mt-3 space-y-2">
								{departments.length === 0 ? (
									<p className="text-sm text-gray-500">Отделы не указаны</p>
								) : (
									departments.map((d, index) => {
										const deptId = Number((d as any).id ?? (d as any).department_id);
										const isValidDeptId = Number.isFinite(deptId) && deptId > 0;

										return isValidDeptId ? (
											<Link key={deptId} href={`/departments/${deptId}`} className="flex items-center justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-800 transition hover:bg-gray-100">
												<div className="min-w-0">
													<p className="truncate font-medium">{d.name}</p>
													{d.role_name ? <p className="truncate text-xs text-gray-500">{d.role_name}</p> : null}
												</div>
												{d.is_head ? <span className="shrink-0 rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-700">Руководитель</span> : null}
											</Link>
										) : (
											<div key={`${d.name || "dept"}-${index}`} className="flex items-center justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-800">
												<div className="min-w-0">
													<p className="truncate font-medium">{d.name}</p>
													{d.role_name ? <p className="truncate text-xs text-gray-500">{d.role_name}</p> : null}
												</div>
												{d.is_head ? <span className="shrink-0 rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-700">Руководитель</span> : null}
											</div>
										);
									})
								)}
							</div>
						</div>
					</div>

					{editProfileOpen ? (
						<div className="mt-4 border-t border-gray-100 pt-4">
							{profileError ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{profileError}</p> : null}
							{avatarFile ? <p className="mb-3 text-xs text-gray-500">Выбран файл: {avatarFile.name}</p> : null}
							<div className="mt-3 flex items-center justify-end gap-2">
								<button
									type="button"
									onClick={() => {
										setEditProfileOpen(false);
										setProfileError(null);
										setAvatarFile(null);
									}}
									className="inline-flex items-center gap-1 rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
								>
									<X size={14} /> Отмена
								</button>
								<button
									type="button"
									onClick={handleSaveProfile}
									disabled={savingProfile}
									className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60"
								>
									<Save size={14} /> {savingProfile ? "Сохраняем..." : "Сохранить"}
								</button>
							</div>
						</div>
					) : null}
				</section>

				<article className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
					<div className="mb-3 flex items-start justify-between gap-3">
						<h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Контакты</h3>
						<button
							type="button"
							onClick={() => {
								setEditContactsOpen((v) => !v);
								setContactsError(null);
							}}
							className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50"
							title="Редактировать контакты"
						>
							<Pencil size={14} />
						</button>
					</div>

					{editContactsOpen ? (
						<>
							{contactsError ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{contactsError}</p> : null}
							<ul className="space-y-2">
								{editableContactItems.map((item) => (
									<li key={item.key} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-800">
										<label className="mb-1 block font-medium">{item.label}</label>
										<input
											value={contactsForm[item.key]}
											onChange={(e) => setContactsForm((p) => ({ ...p, [item.key]: e.target.value }))}
											placeholder={item.label}
											className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
										/>
									</li>
								))}
							</ul>

							<div className="mt-3 flex items-center justify-end gap-2">
								<button
									type="button"
									onClick={() => {
										setEditContactsOpen(false);
										setContactsError(null);
									}}
									className="inline-flex items-center gap-1 rounded-lg bg-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
								>
									<X size={14} /> Отмена
								</button>
								<button
									type="button"
									onClick={handleSaveContacts}
									disabled={savingContacts}
									className="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-3 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-60"
								>
									<Save size={14} /> {savingContacts ? "Сохраняем..." : "Сохранить"}
								</button>
							</div>
						</>
					) : contactItems.length === 0 ? (
						<p className="text-sm text-gray-500">Контакты не указаны</p>
					) : (
						<ul className="space-y-2">
							{contactItems.map((item) => (
								<li key={item.label} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-800">
									<span className="font-medium">{item.label}:</span>{" "}
									{item.href ? (
										<a href={item.href} target={item.external ? "_blank" : undefined} rel={item.external ? "noreferrer" : undefined} className="text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-800">
											{item.value}
										</a>
									) : (
										<span>{item.value}</span>
									)}
								</li>
							))}
						</ul>
					)}
				</article>

				<article className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
					<h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Навыки</h3>
					{skills.length === 0 ? (
						<p className="text-sm text-gray-500">Навыки не указаны</p>
					) : (
						<div className="flex flex-wrap gap-2">
							{skills.map((s) => (
								<span key={s.id} className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
									{s.name}
								</span>
							))}
						</div>
					)}
				</article>

				<article className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
					<h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Кадровые события</h3>
					{actions.length === 0 ? (
						<p className="text-sm text-gray-500">Событий нет</p>
					) : (
						<div className="space-y-2">
							{actions.map((a) => (
								<div key={a.id} className="rounded-lg bg-gray-50 px-3 py-2">
									<p className="text-sm font-medium text-gray-900">{a.action_type}</p>
									{a.description ? <p className="text-xs text-gray-600">{a.description}</p> : null}
									<p className="mt-1 text-xs text-gray-500">{formatDate(a.date || a.created_at)}</p>
								</div>
							))}
						</div>
					)}
				</article>
			</div>
		</AppShell>
	);
}
