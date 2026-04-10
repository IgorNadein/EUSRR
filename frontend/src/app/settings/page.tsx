"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
	ArrowRight,
	Bell,
	BellRing,
	CalendarClock,
	CheckCircle2,
	ChevronRight,
	CircleAlert,
	Clock3,
	Lock,
	LogOut,
	Mail,
	MoonStar,
	Phone,
	Save,
	ShieldCheck,
	Smartphone,
	UserRound,
	Users,
} from "lucide-react";
import { toast } from "sonner";
import { AppShell, PageHeader } from "@/components/AppShell";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { useWebPush } from "@/hooks/useWebPush";
import { getVerbName } from "@/lib/verbTranslations";
import { resolveMediaUrl } from "@/lib/url";

type SectionId = "account" | "contacts" | "notifications" | "access";

type NotificationPreferences = {
	web_enabled: boolean;
	email_enabled: boolean;
	email_frequency: "instant" | "daily" | "weekly" | "never";
	push_enabled: boolean;
	dnd_enabled: boolean;
	dnd_start_time: string | null;
	dnd_end_time: string | null;
	disabled_verbs: string[];
};

type VerbType = {
	verb: string;
	name: string;
	total: number;
	unread: number;
};

const sectionMeta: Array<{ id: SectionId; label: string; description: string }> = [
	{ id: "account", label: "Профиль", description: "Имя, фото и основная информация" },
	{ id: "contacts", label: "Контакты", description: "Почта, телефон и мессенджеры" },
	{ id: "notifications", label: "Уведомления", description: "Каналы, DND и типы событий" },
	{ id: "access", label: "Доступ", description: "Сессия и быстрые переходы" },
];

const defaultPreferences: NotificationPreferences = {
	web_enabled: true,
	email_enabled: false,
	email_frequency: "instant",
	push_enabled: false,
	dnd_enabled: false,
	dnd_start_time: null,
	dnd_end_time: null,
	disabled_verbs: [],
};

function preferencesSignature(value: NotificationPreferences | null) {
	if (!value) return "";
	return JSON.stringify({
		...value,
		disabled_verbs: [...value.disabled_verbs].sort(),
		dnd_start_time: value.dnd_start_time || null,
		dnd_end_time: value.dnd_end_time || null,
	});
}

function formatDateTime(value?: string) {
	if (!value) return "Не указано";
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return value;
	return date.toLocaleString("ru-RU", {
		day: "2-digit",
		month: "2-digit",
		year: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function initials(firstName?: string, lastName?: string) {
	return `${lastName?.[0] || ""}${firstName?.[0] || ""}`.trim() || "П";
}

function SectionCard({
	id,
	title,
	description,
	children,
	action,
}: {
	id: string;
	title: string;
	description: string;
	children: React.ReactNode;
	action?: React.ReactNode;
}) {
	return (
		<section id={id} className="scroll-mt-24 rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
			<div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
				<div>
					<h2 className="text-xl font-semibold text-slate-900">{title}</h2>
					<p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p>
				</div>
				{action ? <div className="shrink-0">{action}</div> : null}
			</div>
			{children}
		</section>
	);
}

function Toggle({
	checked,
	onChange,
	disabled,
}: {
	checked: boolean;
	onChange: (checked: boolean) => void;
	disabled?: boolean;
}) {
	return (
		<label className="relative inline-flex cursor-pointer items-center">
			<input
				type="checkbox"
				checked={checked}
				onChange={(e) => onChange(e.target.checked)}
				disabled={disabled}
				className="peer sr-only"
			/>
			<div className="peer h-6 w-11 rounded-full bg-slate-200 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow-sm after:transition-all after:content-[''] peer-checked:bg-sky-600 peer-checked:after:translate-x-full peer-disabled:cursor-not-allowed peer-disabled:opacity-50" />
		</label>
	);
}

export default function SettingsPage() {
	const { user, loading, refreshUser, logout } = useUser();
	const avatarInputRef = useRef<HTMLInputElement | null>(null);
	const pushSyncedRef = useRef(false);

	const [profileForm, setProfileForm] = useState({
		first_name: "",
		last_name: "",
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
	const [avatarFile, setAvatarFile] = useState<File | null>(null);
	const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
	const [savingProfile, setSavingProfile] = useState(false);
	const [savingContacts, setSavingContacts] = useState(false);

	const [preferences, setPreferences] = useState<NotificationPreferences>(defaultPreferences);
	const [savedPreferences, setSavedPreferences] = useState<NotificationPreferences | null>(null);
	const [verbTypes, setVerbTypes] = useState<VerbType[]>([]);
	const [preferencesLoading, setPreferencesLoading] = useState(true);
	const [savingPreferences, setSavingPreferences] = useState(false);

	const {
		isSupported,
		isSubscribed,
		permission,
		isLoading: pushLoading,
		subscribe,
		unsubscribe,
	} = useWebPush();

	useEffect(() => {
		if (!user) return;
		setProfileForm({
			first_name: user.first_name || "",
			last_name: user.last_name || "",
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

	useEffect(() => {
		let mounted = true;
		async function loadNotificationSettings() {
			try {
				setPreferencesLoading(true);
				const [prefsResponse, verbsResponse] = await Promise.all([
					apiClient.getNotificationPreferences(),
					apiClient.getVerbTypes(),
				]);
				if (!mounted) return;
				const normalized: NotificationPreferences = {
					...defaultPreferences,
					...prefsResponse,
					email_frequency:
						prefsResponse.email_frequency === "disabled"
							? "never"
							: prefsResponse.email_frequency,
				};
				setPreferences(normalized);
				setSavedPreferences(normalized);
				setVerbTypes(verbsResponse.verb_types || []);
			} catch (error) {
				console.error("Failed to load settings", error);
				toast.error("Не удалось загрузить настройки уведомлений");
			} finally {
				if (mounted) {
					setPreferencesLoading(false);
				}
			}
		}

		loadNotificationSettings();
		return () => {
			mounted = false;
		};
	}, []);

	useEffect(() => {
		if (!savedPreferences || pushLoading || pushSyncedRef.current) return;
		if (!isSupported) {
			pushSyncedRef.current = true;
			return;
		}
		pushSyncedRef.current = true;
		setPreferences((prev) => ({ ...prev, push_enabled: isSubscribed }));
		setSavedPreferences((prev) => (prev ? { ...prev, push_enabled: isSubscribed } : prev));
	}, [isSubscribed, isSupported, pushLoading, savedPreferences]);

	useEffect(() => {
		const section = new URLSearchParams(window.location.search).get("section") as SectionId | null;
		if (!section) return;
		const element = document.getElementById(section);
		if (element) {
			requestAnimationFrame(() => {
				element.scrollIntoView({ behavior: "smooth", block: "start" });
			});
		}
	}, []);

	const fullName = useMemo(() => {
		if (!user) return "Пользователь";
		return `${user.last_name || ""} ${user.first_name || ""} ${user.patronymic || ""}`.trim() || "Пользователь";
	}, [user]);

	const profileDirty = useMemo(() => {
		if (!user) return false;
		return (
			profileForm.first_name !== (user.first_name || "") ||
			profileForm.last_name !== (user.last_name || "") ||
			profileForm.patronymic !== (user.patronymic || "") ||
			profileForm.birth_date !== (user.birth_date || "") ||
			Boolean(avatarFile)
		);
	}, [avatarFile, profileForm, user]);

	const contactsDirty = useMemo(() => {
		if (!user) return false;
		return (
			contactsForm.email !== (user.email || "") ||
			contactsForm.phone_number !== (user.phone_number || "") ||
			contactsForm.telegram !== (user.telegram || "") ||
			contactsForm.whatsapp !== (user.whatsapp || "") ||
			contactsForm.wechat !== (user.wechat || "")
		);
	}, [contactsForm, user]);

	const notificationDirty = useMemo(() => {
		return preferencesSignature(preferences) !== preferencesSignature(savedPreferences);
	}, [preferences, savedPreferences]);

	const activeVerbCount = useMemo(
		() => verbTypes.filter((item) => !preferences.disabled_verbs.includes(item.verb)).length,
		[preferences.disabled_verbs, verbTypes],
	);

	const unreadVerbCount = useMemo(
		() => verbTypes.reduce((sum, item) => sum + item.unread, 0),
		[verbTypes],
	);

	const handleAvatarChange = (file: File | null) => {
		if (!file) return;
		if (!file.type.startsWith("image/")) {
			toast.error("Можно загрузить только изображение");
			return;
		}
		if (file.size > 5 * 1024 * 1024) {
			toast.error("Максимальный размер файла 5 МБ");
			return;
		}
		setAvatarFile(file);
		const reader = new FileReader();
		reader.onload = () => {
			setAvatarPreview(typeof reader.result === "string" ? reader.result : null);
		};
		reader.readAsDataURL(file);
	};

	const saveProfile = async () => {
		if (!profileDirty) return;
		try {
			setSavingProfile(true);
			await apiClient.updateCurrentUserProfile({
				first_name: profileForm.first_name.trim(),
				last_name: profileForm.last_name.trim(),
				patronymic: profileForm.patronymic.trim(),
				birth_date: profileForm.birth_date.trim() || null,
				avatar: avatarFile || undefined,
			});
			await refreshUser();
			setAvatarFile(null);
			setAvatarPreview(null);
			toast.success("Профиль обновлен");
		} catch (error) {
			console.error(error);
			toast.error("Не удалось сохранить профиль");
		} finally {
			setSavingProfile(false);
		}
	};

	const saveContacts = async () => {
		if (!contactsDirty) return;
		try {
			setSavingContacts(true);
			await apiClient.updateCurrentUserProfile({
				email: contactsForm.email.trim(),
				phone_number: contactsForm.phone_number.trim(),
				telegram: contactsForm.telegram.trim(),
				whatsapp: contactsForm.whatsapp.trim(),
				wechat: contactsForm.wechat.trim(),
			});
			await refreshUser();
			toast.success("Контакты обновлены");
		} catch (error) {
			console.error(error);
			toast.error("Не удалось сохранить контакты");
		} finally {
			setSavingContacts(false);
		}
	};

	const savePreferences = async () => {
		if (!notificationDirty) return;
		try {
			setSavingPreferences(true);

			if (preferences.push_enabled !== isSubscribed) {
				if (preferences.push_enabled) {
					const success = await subscribe();
					if (!success) {
						throw new Error("Push subscription failed");
					}
				} else {
					const success = await unsubscribe();
					if (!success && isSubscribed) {
						throw new Error("Push unsubscribe failed");
					}
				}
			}

			const payload = {
				...preferences,
				email_frequency: preferences.email_frequency,
				dnd_start_time: preferences.dnd_start_time || undefined,
				dnd_end_time: preferences.dnd_end_time || undefined,
			};
			await apiClient.updateNotificationPreferences(payload);
			setSavedPreferences(preferences);
			toast.success("Настройки уведомлений сохранены");
		} catch (error) {
			console.error(error);
			toast.error("Не удалось сохранить настройки уведомлений");
		} finally {
			setSavingPreferences(false);
		}
	};

	if (loading || !user) {
		return (
			<AppShell>
				<div className="flex items-center justify-center py-16">
					<div className="text-center">
						<div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-sky-300 border-t-transparent" />
						<p className="text-sm text-slate-500">Загрузка настроек...</p>
					</div>
				</div>
			</AppShell>
		);
	}

	const summaryAvatar = avatarPreview || (user.avatar ? resolveMediaUrl(user.avatar) : null);

	return (
		<AppShell>
			<div className="space-y-6">
				<PageHeader
					title="Настройки"
					eyebrow="Личный кабинет"
					subtitle="Единая точка для профиля, контактов и правил доставки уведомлений без прыжков по разным экранам."
					badge={`${sectionMeta.length} раздела`}
				/>

				<div className="grid gap-6 xl:grid-cols-[320px,minmax(0,1fr)]">
					<aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
						<div className="overflow-hidden rounded-3xl bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.18),_transparent_42%),linear-gradient(180deg,_#ffffff_0%,_#f8fbff_100%)] p-5 shadow-sm ring-1 ring-sky-100">
							<div className="flex items-start gap-4">
								<div className="relative h-16 w-16 overflow-hidden rounded-2xl bg-sky-500 text-white shadow-sm">
									{summaryAvatar ? (
										<Image src={summaryAvatar} alt={fullName} fill className="object-cover" unoptimized />
									) : (
										<div className="flex h-full w-full items-center justify-center text-lg font-semibold">
											{initials(user.first_name, user.last_name)}
										</div>
									)}
								</div>
								<div className="min-w-0">
									<p className="truncate text-lg font-semibold text-slate-900">{fullName}</p>
									<p className="truncate text-sm text-slate-500">{user.email || "Почта не указана"}</p>
									<div className="mt-2 flex flex-wrap gap-2">
										<span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-100">
											{user.is_active ? "Активный сотрудник" : "Неактивный профиль"}
										</span>
										<span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
											{user.departments?.length || 0} отделов
										</span>
									</div>
								</div>
							</div>

							<div className="mt-5 grid grid-cols-2 gap-3">
								<div className="rounded-2xl bg-white/80 p-3 ring-1 ring-slate-100">
									<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Навыки</p>
									<p className="mt-2 text-2xl font-semibold text-slate-900">{user.skills?.length || 0}</p>
								</div>
								<div className="rounded-2xl bg-white/80 p-3 ring-1 ring-slate-100">
									<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Непрочитано</p>
									<p className="mt-2 text-2xl font-semibold text-slate-900">{unreadVerbCount}</p>
								</div>
							</div>
						</div>

						<div className="rounded-3xl bg-white p-3 shadow-sm ring-1 ring-slate-100">
							<p className="px-2 pb-3 pt-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
								Разделы
							</p>
							<div className="space-y-1">
								{sectionMeta.map((section) => (
									<button
										key={section.id}
										type="button"
										onClick={() => document.getElementById(section.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}
										className="flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left transition hover:bg-sky-50"
									>
										<div>
											<p className="text-sm font-medium text-slate-800">{section.label}</p>
											<p className="mt-0.5 text-xs text-slate-500">{section.description}</p>
										</div>
										<ChevronRight size={16} className="text-slate-300" />
									</button>
								))}
							</div>
						</div>
					</aside>

					<div className="space-y-6">
						<SectionCard
							id="account"
							title="Профиль"
							description="Основные данные сотрудника. Изменения сохраняются отдельно, чтобы не смешивать контактные поля и карточку профиля."
							action={
								<button
									type="button"
									onClick={saveProfile}
									disabled={!profileDirty || savingProfile}
									className="inline-flex items-center gap-2 rounded-full bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
								>
									<Save size={16} />
									{savingProfile ? "Сохраняем..." : "Сохранить профиль"}
								</button>
							}
						>
							<div className="grid gap-6 lg:grid-cols-[220px,minmax(0,1fr)]">
								<div className="space-y-3">
									<div className="relative mx-auto h-40 w-40 overflow-hidden rounded-[2rem] bg-slate-100 shadow-sm ring-1 ring-slate-100">
										{summaryAvatar ? (
											<Image src={summaryAvatar} alt={fullName} fill className="object-cover" unoptimized />
										) : (
											<div className="flex h-full w-full items-center justify-center bg-sky-500 text-4xl font-semibold text-white">
												{initials(user.first_name, user.last_name)}
											</div>
										)}
									</div>
									<input
										ref={avatarInputRef}
										type="file"
										accept="image/*"
										className="hidden"
										onChange={(e) => handleAvatarChange(e.target.files?.[0] || null)}
									/>
									<button
										type="button"
										onClick={() => avatarInputRef.current?.click()}
										className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
									>
										Загрузить новое фото
									</button>
									<p className="text-xs text-slate-500">PNG, JPG или WEBP до 5 МБ.</p>
								</div>

								<div className="grid gap-4 sm:grid-cols-2">
									<label className="space-y-2">
										<span className="text-sm font-medium text-slate-700">Имя</span>
										<input
											value={profileForm.first_name}
											onChange={(e) => setProfileForm((prev) => ({ ...prev, first_name: e.target.value }))}
											className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
										/>
									</label>
									<label className="space-y-2">
										<span className="text-sm font-medium text-slate-700">Фамилия</span>
										<input
											value={profileForm.last_name}
											onChange={(e) => setProfileForm((prev) => ({ ...prev, last_name: e.target.value }))}
											className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
										/>
									</label>
									<label className="space-y-2">
										<span className="text-sm font-medium text-slate-700">Отчество</span>
										<input
											value={profileForm.patronymic}
											onChange={(e) => setProfileForm((prev) => ({ ...prev, patronymic: e.target.value }))}
											className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
										/>
									</label>
									<label className="space-y-2">
										<span className="text-sm font-medium text-slate-700">Дата рождения</span>
										<input
											type="date"
											value={profileForm.birth_date}
											onChange={(e) => setProfileForm((prev) => ({ ...prev, birth_date: e.target.value }))}
											className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
										/>
									</label>

									<div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100 sm:col-span-2">
										<div className="grid gap-4 sm:grid-cols-2">
											<div>
												<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Последний вход</p>
												<p className="mt-2 text-sm text-slate-700">{formatDateTime(user.last_login)}</p>
											</div>
											<div>
												<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Профиль создан</p>
												<p className="mt-2 text-sm text-slate-700">{formatDateTime(user.date_joined || user.created_at)}</p>
											</div>
										</div>
									</div>
								</div>
							</div>
						</SectionCard>

						<SectionCard
							id="contacts"
							title="Контакты"
							description="Рабочие каналы связи пользователя. Эти поля используются в карточках сотрудников и при некоторых типах уведомлений."
							action={
								<button
									type="button"
									onClick={saveContacts}
									disabled={!contactsDirty || savingContacts}
									className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
								>
									<Save size={16} />
									{savingContacts ? "Сохраняем..." : "Сохранить контакты"}
								</button>
							}
						>
							<div className="grid gap-4 sm:grid-cols-2">
								<label className="space-y-2">
									<span className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
										<Mail size={15} className="text-slate-400" />
										Email
									</span>
									<input
										type="email"
										value={contactsForm.email}
										onChange={(e) => setContactsForm((prev) => ({ ...prev, email: e.target.value }))}
										className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
									/>
								</label>
								<label className="space-y-2">
									<span className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
										<Phone size={15} className="text-slate-400" />
										Телефон
									</span>
									<input
										value={contactsForm.phone_number}
										onChange={(e) => setContactsForm((prev) => ({ ...prev, phone_number: e.target.value }))}
										className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
									/>
								</label>
								<label className="space-y-2">
									<span className="text-sm font-medium text-slate-700">Telegram</span>
									<input
										value={contactsForm.telegram}
										onChange={(e) => setContactsForm((prev) => ({ ...prev, telegram: e.target.value }))}
										className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
									/>
								</label>
								<label className="space-y-2">
									<span className="text-sm font-medium text-slate-700">WhatsApp</span>
									<input
										value={contactsForm.whatsapp}
										onChange={(e) => setContactsForm((prev) => ({ ...prev, whatsapp: e.target.value }))}
										className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
									/>
								</label>
								<label className="space-y-2 sm:col-span-2">
									<span className="text-sm font-medium text-slate-700">WeChat</span>
									<input
										value={contactsForm.wechat}
										onChange={(e) => setContactsForm((prev) => ({ ...prev, wechat: e.target.value }))}
										className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
									/>
								</label>
							</div>

							<div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
								<div className="flex flex-wrap items-center gap-3">
									<span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-200">
										<ShieldCheck size={15} className={user.email_verified ? "text-emerald-500" : "text-amber-500"} />
										{user.email_verified ? "Почта подтверждена" : "Почта не подтверждена"}
									</span>
									<span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-sm text-slate-700 ring-1 ring-slate-200">
										<Users size={15} className="text-sky-500" />
										{user.departments?.map((item) => item.name).join(", ") || "Без отдела"}
									</span>
								</div>
							</div>
						</SectionCard>

						<SectionCard
							id="notifications"
							title="Уведомления"
							description="Настройка каналов доставки, режима тишины и типов событий. Здесь нет автосохранения, чтобы каждое переключение не уходило отдельным запросом."
							action={
								<button
									type="button"
									onClick={savePreferences}
									disabled={preferencesLoading || !notificationDirty || savingPreferences}
									className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
								>
									<Save size={16} />
									{savingPreferences ? "Сохраняем..." : "Сохранить уведомления"}
								</button>
							}
						>
							{preferencesLoading ? (
								<div className="rounded-2xl bg-slate-50 p-8 text-center text-sm text-slate-500">
									Загрузка настроек уведомлений...
								</div>
							) : (
								<div className="space-y-6">
									<div className="grid gap-4 lg:grid-cols-3">
										<div className="rounded-2xl border border-slate-200 p-4">
											<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Активных типов</p>
											<p className="mt-2 text-2xl font-semibold text-slate-900">{activeVerbCount}</p>
										</div>
										<div className="rounded-2xl border border-slate-200 p-4">
											<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Email режим</p>
											<p className="mt-2 text-2xl font-semibold capitalize text-slate-900">{preferences.email_frequency}</p>
										</div>
										<div className="rounded-2xl border border-slate-200 p-4">
											<p className="text-xs uppercase tracking-[0.18em] text-slate-400">Push</p>
											<p className="mt-2 text-2xl font-semibold text-slate-900">
												{preferences.push_enabled ? "Вкл." : "Выкл."}
											</p>
										</div>
									</div>

									<div className="grid gap-4">
										<div className="rounded-2xl border border-slate-200 p-4">
											<div className="flex items-start justify-between gap-4">
												<div className="flex items-start gap-3">
													<BellRing className="mt-0.5 h-5 w-5 text-sky-600" />
													<div>
														<p className="font-medium text-slate-900">Web-уведомления</p>
														<p className="text-sm text-slate-500">Моментальная доставка внутри приложения.</p>
													</div>
												</div>
												<Toggle
													checked={preferences.web_enabled}
													onChange={(checked) => setPreferences((prev) => ({ ...prev, web_enabled: checked }))}
												/>
											</div>
										</div>

										<div className="rounded-2xl border border-slate-200 p-4">
											<div className="flex items-start justify-between gap-4">
												<div className="flex items-start gap-3">
													<Mail className="mt-0.5 h-5 w-5 text-sky-600" />
													<div>
														<p className="font-medium text-slate-900">Email-уведомления</p>
														<p className="text-sm text-slate-500">Полезно для дайджестов и событий вне рабочего окна.</p>
													</div>
												</div>
												<Toggle
													checked={preferences.email_enabled}
													onChange={(checked) => setPreferences((prev) => ({ ...prev, email_enabled: checked }))}
												/>
											</div>

											<div className="mt-4 grid gap-2 sm:max-w-xs">
												<label className="text-sm font-medium text-slate-700">Частота писем</label>
												<select
													value={preferences.email_frequency}
													onChange={(e) =>
														setPreferences((prev) => ({
															...prev,
															email_frequency: e.target.value as NotificationPreferences["email_frequency"],
														}))
													}
													className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
												>
													<option value="instant">Мгновенно</option>
													<option value="daily">Ежедневный дайджест</option>
													<option value="weekly">Еженедельный дайджест</option>
													<option value="never">Не отправлять</option>
												</select>
											</div>
										</div>

										<div className="rounded-2xl border border-slate-200 p-4">
											<div className="flex items-start justify-between gap-4">
												<div className="flex items-start gap-3">
													<Smartphone className="mt-0.5 h-5 w-5 text-sky-600" />
													<div>
														<p className="font-medium text-slate-900">Push-уведомления</p>
														<p className="text-sm text-slate-500">Системные уведомления браузера для текущего устройства.</p>
													</div>
												</div>
												<Toggle
													checked={preferences.push_enabled}
													onChange={(checked) => setPreferences((prev) => ({ ...prev, push_enabled: checked }))}
													disabled={!isSupported || permission === "denied" || pushLoading}
												/>
											</div>

											<div className="mt-4 rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
												<div className="flex items-start gap-3">
													{!isSupported || permission === "denied" ? (
														<CircleAlert className="mt-0.5 h-5 w-5 text-amber-500" />
													) : (
														<CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-500" />
													)}
													<div className="text-sm text-slate-600">
														<p className="font-medium text-slate-800">
															{!isSupported
																? "Этот браузер не поддерживает Push"
																: permission === "denied"
																	? "Разрешение на уведомления отклонено"
																	: isSubscribed
																		? "Текущее устройство уже подписано"
																		: "Подписка будет создана при сохранении"}
														</p>
														<p className="mt-1">
															{permission === "denied"
																? "Нужно разрешить уведомления в настройках браузера."
																: "Состояние браузера и серверной настройки будет синхронизировано одной операцией."}
														</p>
													</div>
												</div>
											</div>
										</div>
									</div>

									<div className="rounded-[1.75rem] border border-violet-200 bg-violet-50/60 p-5">
										<div className="flex items-start justify-between gap-4">
											<div className="flex items-start gap-3">
												<MoonStar className="mt-0.5 h-5 w-5 text-violet-600" />
												<div>
														<p className="font-medium text-slate-900">Режим &quot;Не беспокоить&quot;</p>
													<p className="text-sm text-slate-500">
														В период тишины email и push отключаются, web остаются беззвучными.
													</p>
												</div>
											</div>
											<Toggle
												checked={preferences.dnd_enabled}
												onChange={(checked) =>
													setPreferences((prev) => ({
														...prev,
														dnd_enabled: checked,
														dnd_start_time: checked ? prev.dnd_start_time || "00:00" : prev.dnd_start_time,
														dnd_end_time: checked ? prev.dnd_end_time || "23:59" : prev.dnd_end_time,
													}))
												}
											/>
										</div>

										{preferences.dnd_enabled ? (
											<div className="mt-4 grid gap-4 sm:grid-cols-2">
												<label className="space-y-2">
													<span className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
														<Clock3 size={15} className="text-violet-500" />
														Начало
													</span>
													<input
														type="time"
														value={preferences.dnd_start_time || "00:00"}
														onChange={(e) => setPreferences((prev) => ({ ...prev, dnd_start_time: e.target.value }))}
														className="w-full rounded-2xl border border-violet-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
													/>
												</label>
												<label className="space-y-2">
													<span className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
														<CalendarClock size={15} className="text-violet-500" />
														Конец
													</span>
													<input
														type="time"
														value={preferences.dnd_end_time || "23:59"}
														onChange={(e) => setPreferences((prev) => ({ ...prev, dnd_end_time: e.target.value }))}
														className="w-full rounded-2xl border border-violet-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
													/>
												</label>
											</div>
										) : null}
									</div>

									<div className="rounded-2xl border border-slate-200 p-5">
										<div className="mb-4 flex items-center justify-between gap-3">
											<div>
												<p className="font-medium text-slate-900">Типы уведомлений</p>
												<p className="text-sm text-slate-500">Отключайте только шумные категории, а не весь канал целиком.</p>
											</div>
											<span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
												{verbTypes.length} типов
											</span>
										</div>
										<div className="grid gap-3">
											{verbTypes.map((item) => {
												const enabled = !preferences.disabled_verbs.includes(item.verb);
												return (
													<label
														key={item.verb}
														className="flex cursor-pointer items-start justify-between rounded-2xl border border-slate-200 px-4 py-3 transition hover:bg-slate-50"
													>
														<div className="flex items-start gap-3">
															<input
																type="checkbox"
																checked={enabled}
																onChange={() =>
																	setPreferences((prev) => ({
																		...prev,
																		disabled_verbs: enabled
																			? prev.disabled_verbs.concat(item.verb)
																			: prev.disabled_verbs.filter((verb) => verb !== item.verb),
																	}))
																}
																className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-200"
															/>
															<div>
																<p className="font-medium text-slate-800">{getVerbName(item.verb)}</p>
																<p className="mt-1 text-xs text-slate-500">
																	{item.total} всего, {item.unread} непрочитанных
																</p>
															</div>
														</div>
														<span className={`rounded-full px-2.5 py-1 text-xs font-medium ${enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
															{enabled ? "Вкл." : "Выкл."}
														</span>
													</label>
												);
											})}
										</div>
									</div>
								</div>
							)}
						</SectionCard>

						<SectionCard
							id="access"
							title="Доступ и навигация"
							description="Быстрые переходы и действия по учетной записи. Отсюда можно уйти в детальные разделы, если нужен рабочий контекст, а не только настройки."
						>
							<div className="grid gap-4 lg:grid-cols-2">
								<Link
									href="/profile"
									className="group rounded-2xl border border-slate-200 p-5 transition hover:border-sky-200 hover:bg-sky-50"
								>
									<div className="flex items-center justify-between gap-3">
										<div>
											<p className="inline-flex items-center gap-2 text-sm font-medium text-slate-900">
												<UserRound size={16} className="text-sky-600" />
												Полная карточка профиля
											</p>
											<p className="mt-2 text-sm text-slate-500">Посмотреть отделы, навыки и историю действий пользователя.</p>
										</div>
										<ArrowRight size={18} className="text-slate-300 transition group-hover:text-sky-600" />
									</div>
								</Link>

								<Link
									href="/notifications"
									className="group rounded-2xl border border-slate-200 p-5 transition hover:border-sky-200 hover:bg-sky-50"
								>
									<div className="flex items-center justify-between gap-3">
										<div>
											<p className="inline-flex items-center gap-2 text-sm font-medium text-slate-900">
												<Bell size={16} className="text-sky-600" />
												Центр уведомлений
											</p>
											<p className="mt-2 text-sm text-slate-500">Открыть историю уведомлений и быстро прочитать новые события.</p>
										</div>
										<ArrowRight size={18} className="text-slate-300 transition group-hover:text-sky-600" />
									</div>
								</Link>
							</div>

							<div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-5">
								<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
									<div>
										<p className="inline-flex items-center gap-2 text-sm font-medium text-slate-900">
											<Lock size={16} className="text-slate-500" />
											Текущая сессия
										</p>
										<p className="mt-2 text-sm text-slate-500">
											Если устройство общее или сессия больше не нужна, выйдите из аккаунта вручную.
										</p>
									</div>
									<button
										type="button"
										onClick={logout}
										className="inline-flex items-center justify-center gap-2 rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
									>
										<LogOut size={16} />
										Выйти из аккаунта
									</button>
								</div>
							</div>
						</SectionCard>
					</div>
				</div>
			</div>
		</AppShell>
	);
}
