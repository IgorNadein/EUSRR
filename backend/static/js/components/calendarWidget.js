/**
 * calendarWidget.js
 * Модуль управления календарём событий с FullCalendar
 * Поддерживает: компания + отделы пользователя, повторяющиеся события, недельный список
 *
 * @module calendarWidget
 * @version 2.0.0
 */

import {
  getCalendarEvents,
  invalidateCalendarEvents,
} from "../api/calendarApi.js";
import { getCalendar } from "../api/calendarsApi.js";
import { getMyDepartments } from "../api/departmentsApi.js";
import {
  getAccessToken,
  authHeaders as getAuthHeaders,
  getCookie,
} from "../utils/authUtils.js";
import { formatDate, ymdLocal, fmtDate, fmtTime } from "../utils/dateUtils.js";
import {
  CALENDAR_TYPES,
  CALENDAR_COLORS,
  createLegacyDeptId,
} from "../constants/calendarTypes.js";
import { API_URLS } from "../constants/apiUrls.js";
import { resolveEventPayload } from "../utils/calendarTypeResolver.js";
import {
  extractNumericPk,
  eventsUrl,
  addRange,
  isDateOnly,
  toDate,
  pick,
  startOfWeek,
  endOfWeek,
  overlaps,
  truncate,
  setWeekdaysFromMask,
  fmtWhen,
  DIGITS_RE,
  dayMs,
  hourMs,
} from "./calendarWidget/helpers.js";
import { fetchJSON, apiGet, apiDelete } from "./calendarWidget/apiClient.js";
import {
  renderVertical,
  updateWeekLists as updateWeekListsRenderer,
} from "./calendarWidget/weekListRenderer.js";

/**
 * Инициализация виджета календаря
 * @param {Object} options - Параметры инициализации
 * @param {string} options.deskContainerId - ID контейнера десктопного календаря (по умолчанию 'calendarRight')
 * @param {string} options.mobContainerId - ID контейнера мобильного календаря (по умолчанию 'calendarRightMobile')
 * @param {string} options.apiEventsUrl - URL API событий (по умолчанию '/api/v1/calendar/events/')
 * @param {string} options.apiMyDeptsUrl - URL API отделов пользователя (по умолчанию '/api/v1/departments/my-departments/')
 * @param {string} options.defaultColor - Цвет событий по умолчанию (по умолчанию '#0d6efd')
 * @returns {Object} API виджета { updateWeekLists, refetchEvents, getDepartments }
 */
export function initCalendarWidget(options = {}) {
  if (!window.FullCalendar) {
    return null; // Тихий выход, если FullCalendar не загружен
  }

  // Инициализация цветовой палитры
  initColorPicker();

  /* ===== Конфигурация ===== */
  const config = {
    deskContainerId: options.deskContainerId || "calendarRight",
    mobContainerId: options.mobContainerId || "calendarRightMobile",
    apiEventsUrl: options.apiEventsUrl || API_URLS.EVENTS,
    apiMyDeptsUrl: options.apiMyDeptsUrl || API_URLS.MY_DEPARTMENTS,
    defaultColor: options.defaultColor || CALENDAR_COLORS.DEFAULT,
  };

  const API_EVENTS = config.apiEventsUrl;
  const API_MY_DEPTS = config.apiMyDeptsUrl;
  const DEFAULT_EVENT_COLOR = config.defaultColor;
  const holder =
    document.querySelector(".rightbar-card") ||
    document.querySelector("#rightbarOffcanvas");

  // Используем утилиты авторизации из authUtils
  const globalToken = getAccessToken();

  function authHeaders() {
    return getAuthHeaders();
  }

  // Используем ymdLocal, eventsUrl, addRange, extractNumericPk из helpers.js
  // Используем DIGITS_RE, dayMs, hourMs из helpers.js

  // Обратная совместимость: data-dept-id="1,2,3"
  const legacyDeptIds = (holder?.dataset.deptId || "")
    .split(",")
    .map((s) => s.trim())
    .filter((s) => DIGITS_RE.test(s));

  /* ===== Элементы UI ===== */
  const chooserBtn = document.getElementById("calendarChooserBtn");
  const chooserMenu = document.getElementById("calendarChooserMenu");
  const chooserBtnMobile = document.getElementById("calendarChooserBtnMobile");
  const chooserMenuMobile = document.getElementById(
    "calendarChooserMenuMobile",
  );
  const eventTargetLabel = document.getElementById("eventTargetLabel");

  // Поля модала для переключений
  const allDayChk = document.getElementById("allDayChk");
  const recurrenceSelect = document.getElementById("recurrenceSelect");
  const weeklyBlock = document.getElementById("weeklyBlock");
  const recurrenceInterval = document.getElementById("recurrenceInterval");
  const recurrenceUntil = document.getElementById("recurrenceUntil");
  const recurrenceCount = document.getElementById("recurrenceCount");

  /* ===== Состояние ===== */
  let departments = []; // [{id, name}] где id — всегда числовой PK
  const state = { type: "company", deptId: null, employeeId: null };
  // Защита от гонок при загрузке отделов
  let deptsLoadSeq = 0;

  // Используем isDateOnly, toDate, pick, startOfWeek, endOfWeek, overlaps, truncate из helpers.js
  // Используем fetchJSON из apiClient.js
  // Используем setWeekdaysFromMask, fmtWhen из helpers.js
  // Используем apiGet, apiDelete из apiClient.js

  // Узлы модала (если разметка подключена)
  const detailsModalEl = document.getElementById("eventDetailsModal");
  // Вынесем модал в <body>, иначе позиционирование ломается, если родитель с transform
  if (detailsModalEl && detailsModalEl.parentElement !== document.body) {
    document.body.appendChild(detailsModalEl);
  }
  // Гарантируем вертикальное центрирование (если в HTML забыли класс)
  detailsModalEl
    ?.querySelector(".modal-dialog")
    ?.classList.add("modal-dialog-centered");

  const detailsModal = detailsModalEl
    ? new bootstrap.Modal(detailsModalEl)
    : null;

  const $dt = {
    title: document.getElementById("detailTitle"),
    when: document.getElementById("detailWhen"),
    loc: document.getElementById("detailLocation"),
    locWrapper: document.getElementById("detailLocationWrapper"),
    desc: document.getElementById("detailDescription"),
    descWrapper: document.getElementById("detailDescriptionWrapper"),
    calendar: document.getElementById("detailCalendar"),
    scope: document.getElementById("detailScope"),
    scopeWrapper: document.getElementById("detailScopeWrapper"),
    rec: document.getElementById("detailRecurrence"),
    recWrapper: document.getElementById("detailRecurrenceWrapper"),
    createdBy: document.getElementById("detailCreatedBy"),
    createdByWrapper: document.getElementById("detailCreatedByWrapper"),
    createdAt: document.getElementById("detailCreatedAt"),
    createdAtWrapper: document.getElementById("detailCreatedAtWrapper"),
    dot: document.getElementById("detailColorDot"),
    btnEdit: document.getElementById("btnEditEvent"),
    btnDel: document.getElementById("btnDeleteEvent"),
  };

  let currentDetail = null;

  /**
   * Утилита для показа/скрытия элементов с контентом
   */
  function toggleElement(element, wrapper, content, isEmpty = false) {
    if (!element || !wrapper) return;

    if (isEmpty || !content || content === "—" || content.trim() === "") {
      wrapper.style.display = "none";
    } else {
      wrapper.style.removeProperty("display");
      element.textContent = content;
    }
  }

  /**
   * Форматирование даты для отображения
   */
  function formatDateTime(dateString) {
    if (!dateString) return null;
    try {
      const date = new Date(dateString);
      return date.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  }

  function fillDetails(ev) {
    if (!$dt.title) return; // Модала нет — тихо выходим

    // Заголовок
    $dt.title.textContent = ev.title || "Событие";

    // Цвет
    const col = ev.color || DEFAULT_EVENT_COLOR;
    if ($dt.dot) $dt.dot.style.backgroundColor = col;

    // Время
    $dt.when.textContent = fmtWhen(ev);

    // Место (скрываем если пусто)
    toggleElement($dt.loc, $dt.locWrapper, ev.location);

    // Описание (скрываем если пусто)
    toggleElement($dt.desc, $dt.descWrapper, ev.description);

    // Календарь
    let calendarName = "—";
    let calendarContext = null; // Контекст отдельно: тип и владелец

    // Приоритет: __calendar объект (полные данные)
    if (ev.__calendar) {
      const cal = ev.__calendar;
      calendarName = cal.title || cal.name || `Календарь #${cal.id}`;

      // Определяем контекст на основе owner_user / owner_department
      if (cal.is_personal || cal.owner_user || cal.owner_user_id) {
        calendarContext = "👤 Личный";
        if (cal.owner_user_name) {
          calendarContext += ` (${cal.owner_user_name})`;
        }
      } else if (
        cal.is_department ||
        cal.owner_department ||
        cal.owner_department_id
      ) {
        calendarContext = "🏢 Отдел";
        if (cal.owner_department_name) {
          calendarContext += ` (${cal.owner_department_name})`;
        }
      } else if (cal.is_global) {
        calendarContext = "📅 Компания";
      }
    }
    // Fallback: если нет __calendar, используем старые поля
    else if (ev.calendar) {
      if (typeof ev.calendar === "object") {
        calendarName =
          ev.calendar.title ||
          ev.calendar.name ||
          `Календарь #${ev.calendar.id}`;
      } else {
        calendarName = `Календарь #${ev.calendar}`;
      }
    } else if (ev.calendar_id) {
      calendarName = `Календарь #${ev.calendar_id}`;
    } else if (ev.employee_id) {
      calendarName = "Личный календарь";
      calendarContext = "👤 Личное событие";
    } else if (ev.department_id || ev.department) {
      const deptName = ev.department?.name || `Отдел #${ev.department_id}`;
      calendarName = `Календарь отдела`;
      calendarContext = `🏢 ${deptName}`;
    } else {
      calendarName = "Компания (общие события)";
      calendarContext = "📅 Общий календарь";
    }

    // Календарь - только название
    $dt.calendar.textContent = calendarName;

    // Повторение (скрываем если нет)
    let recText = null;
    if (ev.recurrence && ev.recurrence !== "one_time") {
      const recNames = {
        hourly: "Ежечасно",
        daily: "Ежедневно",
        weekly: "Еженедельно",
        monthly: "Ежемесячно",
        annual: "Ежегодно",
      };
      recText = recNames[ev.recurrence] || ev.recurrence;
      if (ev.recurrence_interval && ev.recurrence_interval > 1) {
        recText += ` (каждые ${ev.recurrence_interval})`;
      }
      if (ev.recurrence_until) {
        recText += ` до ${ev.recurrence_until}`;
      } else if (ev.recurrence_count) {
        recText += ` (${ev.recurrence_count} раз)`;
      }
    }
    toggleElement($dt.rec, $dt.recWrapper, recText);

    // Автор (скрываем если нет)
    let createdByText = null;
    if (ev.created_by_name) {
      // Используем готовое имя из бэкенда
      createdByText = ev.created_by_name;
    } else if (ev.created_by) {
      // Fallback на старую логику для совместимости
      if (typeof ev.created_by === "object") {
        createdByText =
          ev.created_by.username ||
          ev.created_by.email ||
          ev.created_by.full_name ||
          `ID: ${ev.created_by.id}`;
      } else {
        createdByText = `ID: ${ev.created_by}`;
      }
    }
    toggleElement($dt.createdBy, $dt.createdByWrapper, createdByText);

    // Дата создания (скрываем если нет)
    const createdAtText = ev.created_at ? formatDateTime(ev.created_at) : null;
    toggleElement($dt.createdAt, $dt.createdAtWrapper, createdAtText);

    // Контекст - тип и владелец календаря (из переменной выше)
    toggleElement($dt.scope, $dt.scopeWrapper, calendarContext);

    // Кнопки действий (пока скрываем, потом добавим проверку прав)
    if ($dt.btnEdit) $dt.btnEdit.style.display = "none";
    if ($dt.btnDel) $dt.btnDel.style.display = "none";
  }

  async function openEventDetailsById(eventId) {
    try {
      const url = `${API_EVENTS}${eventId}/`;
      const data = await apiGet(url);

      // Если нет __calendar объекта, но есть calendar ID - загружаем данные календаря
      if (!data.__calendar && data.calendar) {
        const calendarId =
          typeof data.calendar === "object" ? data.calendar.id : data.calendar;
        if (calendarId) {
          try {
            const calendarData = await getCalendar(calendarId);
            data.__calendar = calendarData;
          } catch (calErr) {
            console.warn(
              "[CalendarWidget] Failed to load calendar data:",
              calErr,
            );
          }
        }
      }

      currentDetail = data;
      fillDetails(data);
      if (detailsModal) {
        detailsModal.show();
      } else {
        console.error("[CalendarWidget] detailsModal is not initialized!");
      }
    } catch (err) {
      console.error("[CalendarWidget] Load details error:", err);
      if (err.status === 404) {
        alert("Событие не найдено. Возможно, оно было удалено.");
        // Очистить параметр event_id из URL, если он есть
        const url = new URL(window.location);
        if (url.searchParams.has("event_id")) {
          url.searchParams.delete("event_id");
          window.history.replaceState({}, "", url);
        }
      } else if (err.status === 403) {
        alert("Недостаточно прав для просмотра деталей события.");
      } else {
        alert("Не удалось загрузить событие.");
      }
    }
  }

  /* ===== Загрузка отделов (только числовой PK) ===== */
  async function loadDepartments() {
    const mySeq = ++deptsLoadSeq; // Метка версии вызова

    let raw = [];
    try {
      // Используем кешированный API вместо прямого fetch
      raw = await getMyDepartments();
    } catch (e) {
      console.error("[CalendarWidget] Failed to load departments:", e);
      raw = [];
    }

    // Маппинг → {id, name}
    let mapped = (Array.isArray(raw) ? raw : [])
      .map((d) => {
        const pk = extractNumericPk(d);
        if (!pk) return null;
        const name = d.name ?? d.title ?? d.code ?? `Отдел #${pk}`;
        return { id: String(pk), name };
      })
      .filter(Boolean);

    // Если API вернул пусто — fallback к data-dept-id
    if (!mapped.length && legacyDeptIds.length) {
      mapped = legacyDeptIds.map((pk) => ({
        id: String(pk),
        name: `Отдел #${pk}`,
      }));
    }

    // ✅ Дедуп по id
    const uniq = new Map();
    for (const d of mapped) {
      const key = String(d.id);
      if (!uniq.has(key)) uniq.set(key, d);
    }
    const nextDepartments = Array.from(uniq.values());

    // Если наш вызов устарел (есть более поздний) — не трогаем DOM
    if (mySeq !== deptsLoadSeq) return departments;

    departments = nextDepartments;

    // Очистка пунктов отделов в обоих dropdown (десктоп и мобильный)
    [chooserMenu, chooserMenuMobile].forEach((menu) => {
      if (menu)
        menu
          .querySelectorAll('[data-cal="dept"]')
          .forEach((n) => n.closest("li")?.remove());
    });

    if (!departments.length) {
      setChooserLabel();
      return departments;
    }

    // Заполнение dropdown отделами (десктоп и мобильный)
    [chooserMenu, chooserMenuMobile].forEach((menu) => {
      if (!menu) return;

      // Убедимся, что есть разделитель
      menu.querySelector(".dropdown-divider") ||
        (() => {
          const li = document.createElement("li");
          li.innerHTML = '<hr class="dropdown-divider">';
          menu.appendChild(li);
        })();

      // Вставка пунктов
      const frag = document.createDocumentFragment();
      departments.forEach((d) => {
        const li = document.createElement("li");
        li.innerHTML = `<button class="dropdown-item" type="button" data-cal="dept" data-id="${d.id}">${d.name}</button>`;
        frag.appendChild(li);
      });
      menu.appendChild(frag);
    });

    // Валидация текущего выбора
    if (
      state.type === "dept" &&
      !departments.some((d) => String(d.id) === String(state.deptId))
    ) {
      state.type = "company";
      state.deptId = null;
    }
    setChooserLabel();
    return departments;
  }

  function currentDeptLabel() {
    if (state.type === "personal") return "Личный";
    if (state.type !== "dept") return "Компания";
    const d = departments.find((x) => String(x.id) === String(state.deptId));
    return d?.name || `Отдел #${state.deptId}`;
  }

  function setChooserLabel() {
    let label = "Компания";
    if (state.type === "personal") {
      label = "Личный";
    } else if (state.type === "dept") {
      label = currentDeptLabel();
    }
    if (chooserBtn) chooserBtn.textContent = label;
    if (chooserBtnMobile) chooserBtnMobile.textContent = label;
    if (eventTargetLabel) eventTargetLabel.textContent = label;
  }

  /* ===== Обработчик выбора из дропдауна (десктоп и мобильный) ===== */
  function handleChooserClick(e) {
    const btn = e.target.closest("[data-cal]");
    if (!btn) return;
    const type = btn.dataset.cal;
    if (type === "company") {
      state.type = "company";
      state.deptId = null;
      state.employeeId = null;
    } else if (type === "personal") {
      state.type = "personal";
      state.deptId = null;
      // Получаем employee_id из meta-тега или атрибута
      const userMeta = document.querySelector('meta[name="user-id"]');
      state.employeeId = userMeta ? userMeta.content : null;
      if (!state.employeeId) {
        alert("Не удалось определить ID пользователя");
        state.type = "company";
        return;
      }
    } else {
      const id = btn.dataset.id;
      if (!DIGITS_RE.test(String(id || ""))) {
        alert("Некорректный идентификатор отдела");
        return;
      }
      state.type = "dept";
      state.deptId = id;
      state.employeeId = null;
    }
    setChooserLabel();
    [deskCalendar, mobCalendar].forEach((cal) => cal?.refetchEvents());
    updateWeekLists();
  }

  if (chooserMenu) chooserMenu.addEventListener("click", handleChooserClick);
  if (chooserMenuMobile)
    chooserMenuMobile.addEventListener("click", handleChooserClick);

  /* ===== Комбинированная загрузка событий (occurrences) ===== */
  // События для текущего контекста (используется календарём)
  async function fetchEventsCombined(start, end) {
    try {
      const params = {
        start: ymdLocal(start),
        end: ymdLocal(end),
      };

      // Добавляем employee_id для личного календаря
      if (state.type === "personal" && state.employeeId) {
        params.employee_id = state.employeeId;
      }
      // Добавляем department_id для отдела
      else if (state.type === "dept" && state.deptId) {
        params.department_id = state.deptId;
      }

      // Используем кешированный API
      return await getCalendarEvents(params);
    } catch (e) {
      console.error("[CalendarWidget] Fetch events failed", e);
      return [];
    }
  }

  // ✅ ВСЕ доступные календари: компания + все отделы пользователя + личный
  async function fetchEventsAllCalendars(start, end) {
    // При первом вызове убедимся, что отделы загружены
    if (!departments || departments.length === 0) {
      try {
        await loadDepartments();
      } catch (_) {}
    }

    const startStr = ymdLocal(start);
    const endStr = ymdLocal(end);

    // Получаем employee_id текущего пользователя
    const userMeta = document.querySelector('meta[name="user-id"]');
    const currentEmployeeId = userMeta ? userMeta.content : null;

    // Формируем список источников с подписью и цветом
    const sources = [
      {
        params: { start: startStr, end: endStr },
        label: "Компания",
        type: "company",
        id: null,
        color: CALENDAR_COLORS.COMPANY, // Цвет компании
      },
      ...departments.map((d) => ({
        params: { start: startStr, end: endStr, department_id: d.id },
        label: d.name,
        type: "dept",
        id: d.id,
        color: CALENDAR_COLORS.DEPARTMENT, // Цвет отдела
      })),
    ];

    // Добавляем личный календарь, если есть employee_id
    if (currentEmployeeId) {
      sources.push({
        params: {
          start: startStr,
          end: endStr,
          employee_id: currentEmployeeId,
        },
        label: "Личный",
        type: "personal",
        id: currentEmployeeId,
        color: CALENDAR_COLORS.PERSONAL, // Цвет личного календаря
      });
    }

    // Загружаем все источники параллельно (с кешированием!)
    const chunks = await Promise.all(
      sources.map((s) =>
        getCalendarEvents(s.params)
          .then((arr) =>
            (arr || []).map((ev) => ({
              ...ev,
              __source: { label: s.label, type: s.type, id: s.id },
              __calendar: { color: s.color }, // Добавляем цвет календаря
            })),
          )
          .catch((err) => {
            console.error(
              `[CalendarWidget] Failed to load events for ${s.label}:`,
              err,
            );
            return [];
          }),
      ),
    );

    const merged = chunks.flat();
    // Дедуп по устойчивому ключу
    const seen = new Set();
    const out = [];
    for (const ev of merged) {
      const key = ev.id ?? ev.pk ?? ev.uuid ?? ev.slug ?? ev._id ?? null;
      const sk = key != null ? String(key) : null;
      if (!sk || !seen.has(sk)) {
        if (sk) seen.add(sk);
        out.push(ev);
      }
    }
    return out;
  }

  function normalizeEvent(ev) {
    const id = ev.id ?? ev.pk ?? ev.uuid ?? ev.slug ?? ev._id;
    const title = pick(ev, ["title", "name", "summary", "text"]) || "";
    const rs = pick(ev, [
      "start",
      "start_date",
      "date_start",
      "date",
      "date_from",
    ]);
    const re = pick(ev, ["end", "end_date", "date_end", "date_to"]);
    const allDay =
      "allDay" in ev
        ? !!ev.allDay
        : "all_day" in ev
          ? !!ev.all_day
          : isDateOnly(rs) && (!re || isDateOnly(re));
    const s = toDate(rs);
    let e = toDate(re);
    if (!s) return null;
    if (!e) e = new Date(s.getTime() + (allDay ? dayMs : hourMs));
    const color = ev.color || ev.bgColor || null;
    const recurrence = ev.recurrence || ev.recurrence_display || null;
    const location = ev.location || ev.place || "";
    const description = ev.description || ev.details || ev.note || "";
    const sourceLabel =
      ev.__source?.label ||
      (ev.department?.name ?? ev.department) ||
      "Компания";
    return {
      id,
      title,
      start: s,
      end: e,
      allDay,
      color,
      recurrence,
      location,
      description,
      sourceLabel,
    };
  }

  // Используем renderVertical и updateWeekLists из weekListRenderer.js

  // Обёртка для updateWeekLists с передачей нужных параметров
  async function updateWeekLists() {
    await updateWeekListsRenderer(
      fetchEventsAllCalendars,
      normalizeEvent,
      openEventDetailsById,
      DEFAULT_EVENT_COLOR,
    );
  }

  /* ===== Контекстное меню для событий ===== */
  const contextMenu = document.getElementById("calendarContextMenu");
  const contextMenuView = document.getElementById("contextMenuView");
  const contextMenuEdit = document.getElementById("contextMenuEdit");
  const contextMenuDelete = document.getElementById("contextMenuDelete");

  let contextMenuEventId = null;
  let contextMenuLongPressTimer = null;

  // Функция показа контекстного меню
  function showContextMenu(x, y, eventId) {
    if (!contextMenu) return;

    contextMenuEventId = eventId;

    // Проверяем права доступа
    checkEventPermissions(eventId).then((perms) => {
      // Показываем/скрываем кнопки в зависимости от прав
      if (contextMenuEdit) {
        contextMenuEdit.classList.toggle("d-none", !perms.can_edit);
      }
      if (contextMenuDelete) {
        contextMenuDelete.classList.toggle("d-none", !perms.can_delete);
      }

      // Скрываем разделитель если нет прав на удаление
      const divider = contextMenu.querySelector(
        '.dropdown-divider[data-requires-permission="delete"]',
      );
      if (divider) {
        divider.classList.toggle("d-none", !perms.can_delete);
      }

      // Сначала показываем меню для получения его размеров
      contextMenu.style.display = "block";
      contextMenu.style.visibility = "hidden";

      // Получаем размеры меню и окна
      const menuRect = contextMenu.getBoundingClientRect();
      const menuWidth = menuRect.width;
      const menuHeight = menuRect.height;
      const windowWidth = window.innerWidth;
      const windowHeight = window.innerHeight;

      // Корректируем позицию по горизонтали
      let finalX = x;
      if (x + menuWidth > windowWidth) {
        // Меню выходит за правый край - сдвигаем влево
        finalX = windowWidth - menuWidth - 10; // 10px отступ от края
      }
      if (finalX < 10) {
        finalX = 10; // Минимальный отступ слева
      }

      // Корректируем позицию по вертикали
      let finalY = y;
      if (y + menuHeight > windowHeight) {
        // Меню выходит за нижний край - показываем выше курсора
        finalY = y - menuHeight;
        // Если и сверху не помещается, прижимаем к нижнему краю
        if (finalY < 10) {
          finalY = windowHeight - menuHeight - 10;
        }
      }
      if (finalY < 10) {
        finalY = 10; // Минимальный отступ сверху
      }

      // Применяем скорректированную позицию
      contextMenu.style.left = finalX + "px";
      contextMenu.style.top = finalY + "px";
      contextMenu.style.visibility = "visible";
    });
  }

  // Функция скрытия контекстного меню
  function hideContextMenu() {
    if (contextMenu) {
      contextMenu.style.display = "none";
    }
    contextMenuEventId = null;
  }

  // Проверка прав на событие
  async function checkEventPermissions(eventId) {
    try {
      const response = await fetch(`${API_EVENTS}${eventId}/permissions/`, {
        headers: authHeaders(),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (e) {
      console.error("Failed to check permissions:", e);
    }
    return { can_view: true, can_edit: false, can_delete: false };
  }

  // Обработчики кнопок контекстного меню
  if (contextMenuView) {
    contextMenuView.addEventListener("click", () => {
      if (contextMenuEventId) {
        openEventDetailsById(contextMenuEventId);
      }
      hideContextMenu();
    });
  }

  if (contextMenuEdit) {
    contextMenuEdit.addEventListener("click", async () => {
      if (contextMenuEventId) {
        try {
          const data = await apiGet(`${API_EVENTS}${contextMenuEventId}/`);
          currentDetail = data;
          // Переиспользуем логику редактирования из старой кнопки "Редактировать"
          editEvent(data);
        } catch (err) {
          console.error("Load event for edit error", err);
          alert("Не удалось загрузить событие для редактирования.");
        }
      }
      hideContextMenu();
    });
  }

  if (contextMenuDelete) {
    contextMenuDelete.addEventListener("click", async () => {
      if (contextMenuEventId) {
        if (!confirm("Удалить это событие без возможности восстановления?")) {
          hideContextMenu();
          return;
        }
        try {
          await apiDelete(`${API_EVENTS}${contextMenuEventId}/`);
          invalidateCalendarEvents();
          try {
            deskCalendar?.refetchEvents?.();
            mobCalendar?.refetchEvents?.();
          } catch (_) {}
          updateWeekLists();
        } catch (err) {
          console.error("Delete event error", err);
          alert(
            err.status === 403
              ? "Недостаточно прав для удаления."
              : "Не удалось удалить событие.",
          );
        }
      }
      hideContextMenu();
    });
  }

  // Закрытие контекстного меню при клике вне его
  document.addEventListener("click", (e) => {
    if (contextMenu && !contextMenu.contains(e.target)) {
      hideContextMenu();
    }
  });

  // Функция редактирования события (вынесена из обработчика кнопки)
  function editEvent(data) {
    const form = document.getElementById("eventForm");
    if (!form) return;

    form.dataset.mode = "edit";
    form.dataset.eventId = data.id;

    // Базовые поля
    form.querySelector('[name="title"]').value = data.title || "";
    form.querySelector('[name="location"]').value = data.location || "";
    form.querySelector('[name="color"]').value =
      data.color || DEFAULT_EVENT_COLOR;
    form.querySelector('[name="all_day"]').checked = !!data.all_day;

    // Описание
    const descEl = form.querySelector('[name="description"]');
    if (descEl) descEl.value = data.description || "";

    // Дата/время
    const startIso =
      data.start ||
      (data.start_date
        ? `${data.start_date}T${(data.start_time || "00:00").slice(0, 5)}`
        : "");
    const endIso =
      data.end ||
      (data.end_date
        ? `${data.end_date}T${(data.end_time || "00:00").slice(0, 5)}`
        : "");
    const startEl = form.querySelector('[name="start"]');
    const endEl = form.querySelector('[name="end"]');
    if (startEl) startEl.value = (startIso || "").slice(0, 16);
    if (endEl) endEl.value = (endIso || "").slice(0, 16);

    // Повторы
    const recSel = form.querySelector('[name="recurrence"]');
    if (recSel) recSel.value = data.recurrence || "one_time";
    const recInt = form.querySelector('[name="recurrence_interval"]');
    if (recInt) recInt.value = data.recurrence_interval || 1;

    // Until / count
    const untilEl = form.querySelector('[name="recurrence_until"]');
    if (untilEl) untilEl.value = (data.recurrence_until || "").slice(0, 10);
    const countEl = form.querySelector('[name="recurrence_count"]');
    if (countEl) countEl.value = data.recurrence_count ?? "";

    // Weekly дни из маски
    if (data.weekdays_mask != null) setWeekdaysFromMask(data.weekdays_mask);

    // Синхронизация UI
    try {
      typeof syncByRecurrence === "function" && syncByRecurrence();
    } catch (_) {}

    // Отдел (если есть select)
    const deptSel = form.querySelector('[name="department_id"]');
    if (deptSel && data.department) {
      const val = data.department.id ?? data.department;
      if (val != null) deptSel.value = String(val);
    }

    // Заполняем dropdown календарей
    populateCalendarSelect();

    // При редактировании выбираем текущий календарь события
    const select = document.querySelector('select[name="target_calendar"]');
    if (select && data) {
      // Определяем текущий календарь
      let targetValue = null;

      console.log("[CalendarWidget] Event data for calendar select:", {
        calendar_id: data.calendar_id,
        calendar: data.calendar,
        calendar_type: typeof data.calendar,
        employee_id: data.employee_id,
        department_id: data.department_id,
        department: data.department,
      });

      // Сначала проверяем новые календари
      if (data.calendar_id) {
        // Прямое поле calendar_id
        targetValue = String(data.calendar_id);
      } else if (data.calendar) {
        // Поле calendar может быть:
        // 1. Числом (ID календаря)
        // 2. Объектом с полем id
        if (
          typeof data.calendar === "number" ||
          typeof data.calendar === "string"
        ) {
          targetValue = String(data.calendar);
        } else if (data.calendar?.id) {
          targetValue = String(data.calendar.id);
        }
      }
      // Затем legacy календари
      if (!targetValue) {
        if (data.employee_id) {
          targetValue = "legacy-personal";
        } else if (data.department_id || data.department) {
          const deptId =
            data.department_id || data.department?.id || data.department;
          targetValue = `legacy-dept-${deptId}`;
        } else {
          // По умолчанию - глобальный legacy календарь
          targetValue = "legacy-company";
        }
      }

      console.log("[CalendarWidget] Setting calendar select to:", targetValue);
      console.log(
        "[CalendarWidget] Available options:",
        Array.from(select.options).map((opt) => ({
          value: opt.value,
          text: opt.textContent,
        })),
      );

      // Устанавливаем значение в dropdown
      select.value = targetValue;

      // Если значение не установилось (нет такой опции), пробуем найти похожее
      if (select.value !== targetValue) {
        console.warn("[CalendarWidget] Value not found, trying fallback");

        // Для новых календарей пробуем найти по ID
        if (data.calendar_id || data.calendar?.id) {
          const calId = data.calendar_id || data.calendar?.id;
          const found = Array.from(select.options).find(
            (opt) => opt.value == calId || opt.value == String(calId),
          );
          if (found) {
            select.value = found.value;
          }
        }
      }

      console.log(
        "[CalendarWidget] Calendar select value after set:",
        select.value,
      );

      // Если все еще не установилось - предупреждение
      if (select.value !== targetValue && select.value === "") {
        console.error(
          "[CalendarWidget] Failed to set calendar select! Event may be from unavailable calendar.",
        );
      }
    }

    // Открываем форму редактирования
    const createModalEl = document.getElementById("eventCreateModal");
    if (createModalEl) {
      const createModal = bootstrap.Modal.getOrCreateInstance(createModalEl);
      createModal.show();
    } else {
      const offcanvasEl = document.getElementById("rightbarOffcanvas");
      if (offcanvasEl)
        bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl).show();
    }
    form.querySelector('[name="title"]')?.focus();
  }

  /* ===== Функция заполнения dropdown календарей ===== */
  function populateCalendarSelect() {
    const select = document.getElementById("targetCalendarSelect");
    if (!select) return;

    // Очищаем select (кроме первого placeholder option)
    while (select.options.length > 1) {
      select.remove(1);
    }

    // Получаем календари из calendarIntegration
    let allCalendars = [];

    if (
      window.calendarIntegration &&
      typeof window.calendarIntegration.getCalendars === "function"
    ) {
      allCalendars = window.calendarIntegration.getCalendars();
      console.log(
        "[CalendarWidget] Loading calendars for modal:",
        allCalendars.length,
      );
    }

    if (allCalendars.length === 0) {
      console.warn("[CalendarWidget] No calendars found, using fallback");
      // Fallback: базовые календари
      const opt1 = document.createElement("option");
      opt1.value = CALENDAR_TYPES.COMPANY;
      opt1.textContent = "📅 Компания (общие события)";
      opt1.selected = true;
      select.appendChild(opt1);

      const opt2 = document.createElement("option");
      opt2.value = CALENDAR_TYPES.PERSONAL;
      opt2.textContent = "👤 Личный календарь";
      select.appendChild(opt2);
      return;
    }

    // Разделяем на legacy и новые календари
    const legacyCalendars = allCalendars.filter((cal) =>
      String(cal.id).startsWith("legacy-"),
    );
    const newCalendars = allCalendars.filter(
      (cal) => !String(cal.id).startsWith("legacy-"),
    );

    console.log("[CalendarWidget] Calendar breakdown:", {
      total: allCalendars.length,
      legacy: legacyCalendars.length,
      new: newCalendars.length,
    });

    // Добавляем legacy календари
    legacyCalendars.forEach((cal, index) => {
      const opt = document.createElement("option");
      opt.value = cal.id;

      // Иконки для распознавания типа календаря
      let icon = "📅";
      if (cal.id === CALENDAR_TYPES.LEGACY_PERSONAL) icon = "👤";
      else if (String(cal.id).includes("dept-")) icon = "🏢";

      opt.textContent = `${icon} ${cal.title || cal.name}`;
      opt.selected = index === 0; // Первый legacy календарь выбран по умолчанию
      select.appendChild(opt);
    });

    // Добавляем новые календари с вложенной структурой (папки)
    if (newCalendars.length > 0) {
      // Группируем календари по папкам (владельцу)
      const folders = {
        global: [], // Глобальные (is_global = true)
        personal: [], // Личные (is_personal = true)
        departments: {}, // Отделы (is_department = true, по owner_department_id)
      };

      newCalendars.forEach((cal) => {
        if (cal.is_global) {
          folders.global.push(cal);
        } else if (cal.is_personal) {
          folders.personal.push(cal);
        } else if (cal.is_department && cal.owner_department_id) {
          const deptId = cal.owner_department_id;
          if (!folders.departments[deptId]) {
            folders.departments[deptId] = {
              name: cal.owner_department_name || `Отдел ${deptId}`,
              calendars: [],
            };
          }
          folders.departments[deptId].calendars.push(cal);
        }
      });

      console.log("[CalendarWidget] Grouped calendars into folders:", {
        global: folders.global.length,
        personal: folders.personal.length,
        departments: Object.keys(folders.departments).length,
        folderDetails: {
          global: folders.global.map((c) => c.title),
          personal: folders.personal.map((c) => c.title),
          departments: Object.entries(folders.departments).map(
            ([id, dept]) => ({
              id,
              name: dept.name,
              calendars: dept.calendars.map((c) => c.title),
            }),
          ),
        },
      });

      // Добавляем глобальные календари
      if (folders.global.length > 0) {
        const optgroup = document.createElement("optgroup");
        optgroup.label = "📂 Компания";
        folders.global.forEach((cal) => {
          const opt = document.createElement("option");
          opt.value = String(cal.id); // Явно конвертируем в строку
          opt.textContent = `  🗓️ ${cal.title || cal.name}`;
          optgroup.appendChild(opt);
        });
        select.appendChild(optgroup);
      }

      // Добавляем личные календари
      if (folders.personal.length > 0) {
        const optgroup = document.createElement("optgroup");
        optgroup.label = "📂 Личные";
        folders.personal.forEach((cal) => {
          const opt = document.createElement("option");
          opt.value = String(cal.id); // Явно конвертируем в строку
          opt.textContent = `  🗓️ ${cal.title || cal.name}`;
          optgroup.appendChild(opt);
        });
        select.appendChild(optgroup);
      }

      // Добавляем календари отделов
      Object.keys(folders.departments).forEach((deptId) => {
        const dept = folders.departments[deptId];
        const optgroup = document.createElement("optgroup");
        optgroup.label = `📂 ${dept.name}`;
        dept.calendars.forEach((cal) => {
          const opt = document.createElement("option");
          opt.value = String(cal.id); // Явно конвертируем в строку
          opt.textContent = `  🗓️ ${cal.title || cal.name}`;
          optgroup.appendChild(opt);
        });
        select.appendChild(optgroup);
      });
    }
  }

  /* ===== Обработчики событий календаря ===== */
  const oc = document.getElementById("rightbarOffcanvas");
  const setHeadH = () => {
    const h = oc?.querySelector(".offcanvas-header")?.offsetHeight || 56;
    if (oc) oc.style.setProperty("--rb-offcanvas-head", h + "px");
  };
  setHeadH();
  window.addEventListener("resize", setHeadH);
  oc?.addEventListener("shown.bs.offcanvas", () => {
    setHeadH();
    mobCalendar?.updateSize();
  });

  /* ===== FullCalendar init ===== */
  const fcOpts = {
    locale: "ru",
    initialView: "dayGridMonth",
    headerToolbar: { left: "prev,next today", center: "title", right: "" },
    height: "auto",
    displayEventTime: false,
    selectable: true, // Позволяет выбирать даты

    // Улучшенное отображение накладывающихся событий
    dayMaxEvents: 5, // Максимум 5 событий видимых в ячейке (остальные в "+N еще")
    dayMaxEventRows: 5, // Максимум 5 рядов событий (включая многодневные)
    moreLinkClick: "popover", // Показывать popover при клике на "+N еще"
    eventOverlap: false, // ВАЖНО: false заставляет FullCalendar размещать события в разные ряды
    slotEventOverlap: false, // Дополнительно для timeGrid

    // Улучшенный порядок событий
    eventOrder: ["start", "-duration", "title"], // Сортировка: раньше начало, длиннее, по алфавиту

    // Настройки отображения
    eventDisplay: "block", // block для dayGrid (не auto!)
    eventTimeFormat: {
      hour: "2-digit",
      minute: "2-digit",
      meridiem: false,
    },

    // Отладка: проверяем, что FullCalendar получает
    eventDidMount: (info) => {
      const ev = info.event;
      if (ev.allDay && ev.end && ev.start) {
        const days = Math.round((ev.end - ev.start) / (1000 * 60 * 60 * 24));
        if (days > 1) {
          console.log("EVENT MOUNTED:", {
            title: ev.title,
            allDay: ev.allDay,
            days: days,
            element_top: info.el.style.top,
            element_classes: info.el.className,
          });
        }
      }
    },

    events: async (info, success, failure) => {
      try {
        let raw;

        // Используем новую систему множественных календарей, если доступна
        if (window.calendarIntegration?.fetchEventsForVisibleCalendars) {
          console.log(
            "[CalendarWidget] Using calendar integration for event loading",
          );
          raw = await window.calendarIntegration.fetchEventsForVisibleCalendars(
            info.start,
            info.end,
          );
        } else {
          // Fallback на старую систему
          console.log("[CalendarWidget] Using legacy fetchEventsCombined");
          raw = await fetchEventsCombined(info.start, info.end);
        }

        // 🔍 DEBUG: Анализируем события
        window.lastEvents = raw;
        const multiDay =
          raw?.filter((ev) => {
            const start = new Date(ev.start);
            const end = new Date(ev.end);
            const days = Math.round((end - start) / (1000 * 60 * 60 * 24));
            return days > 1;
          }) || [];

        console.log("🔍 EVENTS ANALYSIS:", {
          total: raw?.length || 0,
          multiDay: multiDay.length,
          multiDayDetails: multiDay.map((ev) => ({
            title: ev.title,
            start: ev.start,
            end: ev.end,
            allDay: ev.allDay,
            days: Math.round(
              (new Date(ev.end) - new Date(ev.start)) / (1000 * 60 * 60 * 24),
            ),
          })),
        });

        if (multiDay.length > 0 && multiDay.some((ev) => !ev.allDay)) {
          console.warn(
            "⚠️ ПРОБЛЕМА: Найдены многодневные события с allDay=false!",
          );
          console.log(
            "Эти события НЕ БУДУТ растягиваться в dayGridMonth виде:",
          );
          console.table(
            multiDay
              .filter((ev) => !ev.allDay)
              .map((ev) => ({
                title: ev.title,
                start: ev.start,
                end: ev.end,
                allDay: ev.allDay,
              })),
          );
          console.log(
            "� РЕШЕНИЕ: Отредактируйте эти события и уберите время (сделайте целодневными)",
          );
        }

        // Нормализуем id, даты и цвет для FullCalendar
        const mapped = (Array.isArray(raw) ? raw : []).map((ev) => {
          const id = ev.id ?? ev.pk ?? ev.uuid ?? ev.slug ?? ev._id;
          const eventColor = ev.color || ev.bgColor || null;
          const calendarColor = ev.__calendar?.color || null;
          const calendarTitle =
            ev.__calendar?.title || ev.__calendar?.name || null;

          // Преобразуем строковые даты в Date объекты для FullCalendar
          const start = ev.start ? toDate(ev.start) : null;
          const end = ev.end ? toDate(ev.end) : null;

          // � FIX: Многодневные события с временем автоматически делаем allDay
          // для корректного отображения в dayGridMonth виде
          let allDay = ev.allDay;
          if (start && end) {
            const durationDays = Math.round(
              (end - start) / (1000 * 60 * 60 * 24),
            );
            if (durationDays > 1 && !allDay) {
              console.log(
                `� Конвертирую "${ev.title}" в allDay (длительность: ${durationDays} дней)`,
              );
              allDay = true;
            }
          }

          return {
            ...ev,
            ...(id != null ? { id } : {}),
            ...(start ? { start } : {}), // Используем преобразованную дату
            ...(end ? { end } : {}), // Используем преобразованную дату
            allDay, // Используем вычисленное значение allDay (может быть изменено для многодневных)
            ...(eventColor
              ? { backgroundColor: eventColor, borderColor: eventColor }
              : {}),
            extendedProps: {
              ...(ev.extendedProps || {}),
              ...ev, // Копируем все свойства события
              calendar_color: calendarColor, // Добавляем цвет календаря
              calendar_title: calendarTitle, // Добавляем название календаря
            },
          };
        });

        // 🔍 DEBUG: Проверяем финальные события после конвертации
        console.log("🔍 FINAL MAPPED EVENTS:", {
          total: mapped.length,
          multiDayAllDay: mapped.filter((ev) => {
            const durationDays = Math.round(
              (new Date(ev.end) - new Date(ev.start)) / (1000 * 60 * 60 * 24),
            );
            return durationDays > 1 && ev.allDay;
          }).length,
          multiDayNotAllDay: mapped.filter((ev) => {
            const durationDays = Math.round(
              (new Date(ev.end) - new Date(ev.start)) / (1000 * 60 * 60 * 24),
            );
            return durationDays > 1 && !ev.allDay;
          }).length,
        });

        success(mapped);
      } catch (e) {
        console.error("Calendar fetch error:", e);
        failure(e);
      }
    },
    eventContent: (arg) => {
      const el = document.createElement("div");
      el.className = "fc-event-main";
      el.textContent = arg.event.title || "";
      el.title = arg.event.title || "";
      return { domNodes: [el] };
    },
    eventDidMount: (info) => {
      // Получаем цвет события и цвет календаря
      const eventColor =
        info.event.backgroundColor ||
        info.event.extendedProps?.color ||
        "#0d6efd";
      const calendarColor = info.event.extendedProps?.calendar_color || null;
      const recurrence = info.event.extendedProps?.recurrence || null;

      // Применяем современный стиль с двойным цветом
      const eventEl = info.el;

      // Проверяем, является ли событие многодневным
      const isMultiDay =
        !info.event.allDay &&
        info.event.start &&
        info.event.end &&
        (info.event.end.getDate() !== info.event.start.getDate() ||
          info.event.end.getMonth() !== info.event.start.getMonth() ||
          info.event.end.getFullYear() !== info.event.start.getFullYear());

      // Проверяем тип сегмента многодневного события
      const isStart = info.isStart;
      const isEnd = info.isEnd;

      if (calendarColor) {
        // Если есть цвет календаря - показываем оба цвета
        eventEl.setAttribute("data-has-calendar-color", "true");
        eventEl.style.borderLeft = `4px solid ${calendarColor}`; // Левая граница = цвет календаря
        eventEl.style.backgroundColor = eventColor + "CC"; // 80% прозрачности, фон = цвет события
        eventEl.style.borderColor = eventColor;
      } else {
        // Если нет цвета календаря - используем только цвет события
        eventEl.style.backgroundColor = eventColor;
        eventEl.style.borderColor = eventColor;
        eventEl.style.borderLeft = `3px solid ${eventColor}`;
      }

      // Улучшаем читаемость текста
      eventEl.style.color = "#ffffff";
      eventEl.style.textShadow = "0 1px 2px rgba(0,0,0,0.2)";

      // Особый стиль для ежегодных событий
      if (recurrence === "annual") {
        eventEl.setAttribute("data-recurrence", "annual");
      }

      // Hover эффект (только если не применяются автоматически)
      if (!eventEl.classList.contains("fc-event")) {
        eventEl.addEventListener("mouseenter", () => {
          eventEl.style.transform = "translateY(-1px)";
          eventEl.style.transition = "all 0.2s ease";
          eventEl.style.zIndex = "100";
        });

        eventEl.addEventListener("mouseleave", () => {
          eventEl.style.transform = "translateY(0)";
          eventEl.style.transition = "all 0.2s ease";
        });
      }

      // Добавляем обработчик правой кнопки мыши
      info.el.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        const eid = info.event.id || info.event.extendedProps?.id;
        if (eid) {
          showContextMenu(e.pageX, e.pageY, eid);
        }
      });

      // Добавляем обработчик долгого нажатия для мобильных устройств
      info.el.addEventListener("touchstart", (e) => {
        contextMenuLongPressTimer = setTimeout(() => {
          const eid = info.event.id || info.event.extendedProps?.id;
          if (eid) {
            const touch = e.touches[0];
            showContextMenu(touch.pageX, touch.pageY, eid);
          }
        }, 500); // 500ms для долгого нажатия
      });

      info.el.addEventListener("touchend", () => {
        if (contextMenuLongPressTimer) {
          clearTimeout(contextMenuLongPressTimer);
          contextMenuLongPressTimer = null;
        }
      });

      info.el.addEventListener("touchmove", () => {
        if (contextMenuLongPressTimer) {
          clearTimeout(contextMenuLongPressTimer);
          contextMenuLongPressTimer = null;
        }
      });
    },
    // Обработчик клика по дате для создания нового события
    dateClick: (info) => {
      // Открываем модал создания события
      const form = document.getElementById("eventForm");
      if (!form) return;

      // Очищаем форму
      form.reset();
      form.dataset.mode = "create";
      delete form.dataset.eventId;

      // Устанавливаем выбранную дату
      const clickedDate = info.dateStr; // YYYY-MM-DD
      const startEl = form.querySelector('[name="start"]');
      const endEl = form.querySelector('[name="end"]');

      if (startEl) {
        // Устанавливаем дату начала (с текущим временем)
        const now = new Date();
        const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
        startEl.value = `${clickedDate}T${timeStr}`;
      }

      if (endEl) {
        // Устанавливаем дату окончания (на час позже)
        const now = new Date();
        now.setHours(now.getHours() + 1);
        const timeStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
        endEl.value = `${clickedDate}T${timeStr}`;
      }

      // Синхронизируем UI
      try {
        typeof syncByRecurrence === "function" && syncByRecurrence();
        typeof syncByAllDay === "function" && syncByAllDay();
        typeof syncUntilCount === "function" && syncUntilCount();
      } catch (_) {}

      // Заполняем чекбоксы календарей
      populateCalendarSelect();

      // Открываем модал
      const createModalEl = document.getElementById("eventCreateModal");
      if (createModalEl) {
        const createModal = bootstrap.Modal.getOrCreateInstance(createModalEl);
        createModal.show();
      }
    },
  };

  let deskCalendar = null,
    mobCalendar = null;
  const desk = document.getElementById(config.deskContainerId);
  if (desk) {
    deskCalendar = new FullCalendar.Calendar(desk, fcOpts);
    deskCalendar.on("loading", (l) => {
      if (!l) updateWeekLists();
    });
    deskCalendar.on("eventClick", (info) => {
      info.jsEvent?.preventDefault?.();
      const eid = info.event.id || info.event.extendedProps?.id;
      if (eid) openEventDetailsById(eid);
    });
    deskCalendar.render();
  }
  const mob = document.getElementById(config.mobContainerId);
  if (mob) {
    mobCalendar = new FullCalendar.Calendar(mob, fcOpts);
    mobCalendar.on("loading", (l) => {
      if (!l) updateWeekLists();
    });
    mobCalendar.on("eventClick", (info) => {
      info.jsEvent?.preventDefault?.();
      const eid = info.event.id || info.event.extendedProps?.id;
      if (eid) openEventDetailsById(eid);
    });
    mobCalendar.render();
  }

  // Загрузим отделы и обновим подпись селектора
  loadDepartments().then(() => setChooserLabel());

  setTimeout(() => updateWeekLists(), 100);
  [deskCalendar, mobCalendar].forEach((cal) =>
    cal?.on("datesSet", () => updateWeekLists()),
  );

  /* ===== UX: переключалки формы ===== */
  function syncByRecurrence() {
    const r = recurrenceSelect?.value || "one_time";

    // Weekly block - показываем только для weekly
    if (r === "weekly") {
      weeklyBlock?.classList.remove("d-none");
    } else {
      weeklyBlock?.classList.add("d-none");
    }

    // Recurrence end block - показываем если не one_time
    const recurrenceEndBlock = document.getElementById("recurrenceEndBlock");
    if (r !== "one_time") {
      if (recurrenceEndBlock) recurrenceEndBlock.style.display = "block";
      if (recurrenceInterval) recurrenceInterval.disabled = false;
    } else {
      if (recurrenceEndBlock) recurrenceEndBlock.style.display = "none";
      if (recurrenceInterval) {
        recurrenceInterval.value = "1";
        recurrenceInterval.disabled = true;
      }
    }
  }

  function syncByAllDay() {
    const isAllDay = allDayChk?.checked;
    const startEl = document.querySelector('input[name="start"]');
    const endEl = document.querySelector('input[name="end"]');
    if (!startEl || !endEl) return;
    // Если all-day — время можно не указывать, но поля не блокируем
  }

  function syncUntilCount() {
    const hasUntil = !!recurrenceUntil?.value;
    if (hasUntil) {
      recurrenceCount.value = "";
      recurrenceCount.disabled = true;
    } else {
      recurrenceCount.disabled = false;
    }
  }

  recurrenceSelect?.addEventListener("change", syncByRecurrence);
  allDayChk?.addEventListener("change", syncByAllDay);
  recurrenceUntil?.addEventListener("change", syncUntilCount);
  syncByRecurrence();
  syncByAllDay();
  syncUntilCount();

  /* ===== Цвет: палитра и синхронизация с input[type=color] ===== */
  function initColorPicker() {
    const form = document.getElementById("eventForm");
    if (!form) return;
    const colorInput = form.querySelector('input[name="color"]');
    const palette = document.getElementById("colorPalette");
    if (!colorInput || !palette) return;

    // Значение по умолчанию
    if (!colorInput.value) colorInput.value = DEFAULT_EVENT_COLOR;

    function highlightActive() {
      const val = (colorInput.value || "").toLowerCase();
      palette.querySelectorAll("[data-color]").forEach((btn) => {
        btn.classList.toggle(
          "active",
          (btn.dataset.color || "").toLowerCase() === val,
        );
      });
    }
    palette.querySelectorAll("[data-color]").forEach((btn) => {
      btn.addEventListener("click", () => {
        colorInput.value = btn.dataset.color || DEFAULT_EVENT_COLOR;
        colorInput.dispatchEvent(new Event("input", { bubbles: true }));
        highlightActive();
      });
    });
    colorInput.addEventListener("input", highlightActive);
    highlightActive();
  }

  /* ===== Создание/редактирование события (POST/PATCH только с Bearer) ===== */
  const form = document.getElementById("eventForm");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const title = (fd.get("title") || "").toString().trim();
    let start = fd.get("start")?.toString() || "";
    let end = fd.get("end")?.toString() || "";
    const allDay = !!fd.get("all_day");

    if (!title) {
      alert("Укажите заголовок");
      return;
    }

    // Разбираем datetime-local → даты/время
    const nowIso = new Date().toISOString().slice(0, 16);
    const sDate = (start || nowIso).slice(0, 10);
    const eDate = (end && end.trim() ? end : start || "").slice(0, 10) || sDate;
    const sTime = start && start.length >= 16 ? start.slice(11, 16) : "";
    const eTime = end && end.length >= 16 ? end.slice(11, 16) : "";

    // Повторяемость
    const recurrence = (fd.get("recurrence") || "one_time").toString();
    const recurrence_interval = Math.max(
      1,
      parseInt(fd.get("recurrence_interval") || "1", 10),
    );
    const recurrence_until = (fd.get("recurrence_until") || "")
      .toString()
      .trim();
    const recurrence_count_raw = (fd.get("recurrence_count") || "")
      .toString()
      .trim();
    const recurrence_count = recurrence_count_raw
      ? Math.max(1, parseInt(recurrence_count_raw, 10))
      : null;

    // Weekly weekdays → массив чисел
    const weekdays = Array.from(
      document.querySelectorAll('input[name="weekdays"]:checked'),
    ).map((el) => parseInt(el.value, 10));

    const colorVal =
      (fd.get("color") || "").toString().trim() || DEFAULT_EVENT_COLOR;
    // Базовый payload
    const payload = {
      title,
      start_date: sDate,
      end_date: eDate,
      all_day: allDay,
      recurrence,
      recurrence_interval,
      color: colorVal,
      location: (fd.get("location") || "").toString().trim() || "",
      description: (fd.get("description") || "").toString().trim() || "",
    };

    // Время (если all_day=false ИЛИ пользователь указал оба времени)
    if (!allDay || (sTime && eTime)) {
      if (sTime && eTime) {
        payload.start_time = sTime; // "HH:MM"
        payload.end_time = eTime; // "HH:MM"
        payload.all_day = false;
      } else if (recurrence === "hourly") {
        alert("Ежечасное событие требует и время начала, и время окончания.");
        return;
      }
    }

    // Ограничители серии
    if (recurrence_until && recurrence_count) {
      alert(
        'Нельзя одновременно задавать "Повторять до" и "Кол-во повторов". Укажите что-то одно.',
      );
      return;
    }
    if (recurrence_until) payload.recurrence_until = recurrence_until;
    if (recurrence_count) payload.recurrence_count = recurrence_count;

    // Weekly: передаём weekdays если выбраны
    if (recurrence === "weekly" && weekdays.length) {
      payload.weekdays = weekdays;
    }

    // Получаем выбранный календарь из dropdown
    const selectEl = document.querySelector('select[name="target_calendar"]');
    let targetCalendar = selectEl?.value;

    if (!targetCalendar) {
      alert("Выберите календарь для создания события");
      return;
    }

    // Парсим в число, если это новый календарь (numeric ID)
    // Legacy календари остаются строками ("company", "personal", "dept-X")
    const parsedId = parseInt(targetCalendar, 10);
    if (!isNaN(parsedId) && parsedId > 0) {
      targetCalendar = parsedId;
    }

    console.log("[CalendarWidget] Selected calendar:", {
      raw: selectEl?.value,
      parsed: targetCalendar,
      type: typeof targetCalendar,
    });

    const postHeaders = {
      "Content-Type": "application/json",
      ...authHeaders(),
    };
    // Проверка токена
    if (!globalToken) {
      alert("Требуется авторизация. Войдите заново.");
      return;
    }

    try {
      const isEdit = form.dataset.mode === "edit" && form.dataset.eventId;

      // Используем утилиту для определения payload
      const eventPayload = resolveEventPayload(targetCalendar, payload);

      if (isEdit) {
        // При редактировании - обновляем событие
        const url = API_EVENTS + String(form.dataset.eventId) + "/";
        await fetchJSON(url, {
          method: "PATCH",
          headers: postHeaders,
          body: JSON.stringify(eventPayload),
        });
      } else {
        // При создании - создаем новое событие
        await fetchJSON(API_EVENTS, {
          method: "POST",
          headers: postHeaders,
          body: JSON.stringify(eventPayload),
        });
      }

      document.querySelector("#eventCreateModal .btn-close")?.click();
      form.reset();
      delete form.dataset.mode;
      delete form.dataset.eventId;
      syncByRecurrence();
      syncByAllDay();
      syncUntilCount();
      invalidateCalendarEvents();
      [deskCalendar, mobCalendar].forEach((cal) => cal?.refetchEvents());
      updateWeekLists();
    } catch (err) {
      console.error("Create event error", err);
      console.error("Payload sent:", payload);
      console.error("Response data:", err?.data);

      if (err && err.status === 403) {
        const where =
          state?.type === "dept"
            ? `отделе «${currentDeptLabel()}»`
            : "компании";
        alert(
          "Недостаточно прав для создания события в " +
            where +
            ".\n" +
            "Попросите руководителя назначить вам роль «Управлять календарём отдела».",
        );
      } else if (err && err.status === 400) {
        // Детальная информация о валидации
        const errors = err?.data?.errors || err?.data;
        const detail = err?.data?.detail || "";
        let errorMsg = "Ошибка валидации события:\n\n";

        if (detail) {
          errorMsg += detail + "\n\n";
        }

        if (typeof errors === "object" && errors !== null) {
          for (const [field, messages] of Object.entries(errors)) {
            const msgs = Array.isArray(messages) ? messages : [messages];
            errorMsg += `${field}: ${msgs.join(", ")}\n`;
          }
        }

        alert(
          errorMsg ||
            "Не удалось сохранить событие. Проверьте введенные данные.",
        );
      } else {
        const detail =
          err?.data?.detail || (typeof err?.data === "string" ? err.data : "");
        alert(
          "Не удалось создать событие: " +
            (detail || JSON.stringify(err?.data || {})),
        );
      }
    }
  });

  // API возвращаем для внешнего использования
  return {
    updateWeekLists,
    refetchEvents: () => {
      deskCalendar?.refetchEvents();
      mobCalendar?.refetchEvents();
    },
    getDepartments: () => departments,
    getState: () => ({ ...state }),
    openEventById: (eventId) => openEventDetailsById(eventId),
  };
}

// Автоинициализация при загрузке DOM
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    window.calendarWidget = initCalendarWidget();

    // Обработчик кнопки "Больше опций" - меняем текст при раскрытии
    const moreOptionsBtn = document.querySelector(
      '[data-bs-target="#moreOptions"]',
    );
    const moreOptionsCollapse = document.getElementById("moreOptions");
    if (moreOptionsBtn && moreOptionsCollapse) {
      moreOptionsCollapse.addEventListener("show.bs.collapse", () => {
        moreOptionsBtn.querySelector("span").textContent = "Меньше опций";
      });
      moreOptionsCollapse.addEventListener("hide.bs.collapse", () => {
        moreOptionsBtn.querySelector("span").textContent = "Больше опций";
      });
    }

    // Проверяем URL на наличие параметра event_id для открытия модала
    const urlParams = new URLSearchParams(window.location.search);
    const eventIdFromUrl = urlParams.get("event_id");
    if (eventIdFromUrl && window.calendarWidget) {
      // Небольшая задержка, чтобы календарь успел загрузиться
      setTimeout(() => {
        window.calendarWidget.openEventById(eventIdFromUrl);
      }, 500);
    }
  });
}
