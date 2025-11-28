/**
 * calendarWidget.js
 * Модуль управления календарём событий с FullCalendar
 * Поддерживает: компания + отделы пользователя, повторяющиеся события, недельный список
 * 
 * @module calendarWidget
 * @version 2.0.0
 */

import { getCalendarEvents, invalidateCalendarEvents } from '../api/calendarApi.js';
import { getMyDepartments } from '../api/departmentsApi.js';

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
    deskContainerId: options.deskContainerId || 'calendarRight',
    mobContainerId: options.mobContainerId || 'calendarRightMobile',
    apiEventsUrl: options.apiEventsUrl || '/api/v1/calendar/events/',
    apiMyDeptsUrl: options.apiMyDeptsUrl || '/api/v1/departments/my-departments/',
    defaultColor: options.defaultColor || '#0d6efd',
  };

  const API_EVENTS = config.apiEventsUrl;
  const API_MY_DEPTS = config.apiMyDeptsUrl;
  const DEFAULT_EVENT_COLOR = config.defaultColor;
  const holder = document.querySelector('.rightbar-card') || document.querySelector('#rightbarOffcanvas');

  /* ===== Регулярки и константы ===== */
  const DIGITS_RE = /^\d+$/;
  const dayMs = 86400000;
  const hourMs = 3600000;

  /* ===== Токен из meta ===== */
  function getAccessToken() {
    const meta = document.querySelector('meta[name="api-access"]');
    const m = (meta && meta.getAttribute('content')) || '';
    if (m) return m.trim();
    try {
      return localStorage.getItem('api.access') || '';
    } catch (_) {
      return '';
    }
  }

  // Сохраняем токен глобально при загрузке, чтобы избежать timing issues
  const globalToken = getAccessToken();

  function authHeaders() {
    return globalToken ? { Authorization: 'Bearer ' + globalToken } : {};
  }

  /* ===== Только ЧИСЛОВОЙ PK отдела ===== */
  function extractNumericPk(d) {
    const cands = [d?.pk, d?.id, d?.department_id];
    for (const v of cands) {
      const s = String(v ?? '').trim();
      if (s && DIGITS_RE.test(s)) return s;
    }
    return null;
  }

  // YYYY-MM-DD в ЛОКАЛИ (без TZ-сдвига)
  function ymdLocal(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  // Базовый URL событий: для отдела добавляем department_id
  const eventsUrl = (deptId = null) => {
    const u = new URL(API_EVENTS, location.origin);
    if (deptId != null) u.searchParams.set('department_id', String(deptId));
    return u.pathname + (u.search ? '?' + u.searchParams.toString() : '');
  };

  // Корректно вешаем диапазон дат на любой URL
  function addRange(url, start, end) {
    const u = new URL(url, location.origin);
    u.searchParams.set('start', ymdLocal(start));
    u.searchParams.set('end', ymdLocal(end));
    return u.pathname + '?' + u.searchParams.toString();
  }

  // Обратная совместимость: data-dept-id="1,2,3"
  const legacyDeptIds = (holder?.dataset.deptId || '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => DIGITS_RE.test(s));

  /* ===== Элементы UI ===== */
  const chooserBtn = document.getElementById('calendarChooserBtn');
  const chooserMenu = document.getElementById('calendarChooserMenu');
  const chooserBtnMobile = document.getElementById('calendarChooserBtnMobile');
  const chooserMenuMobile = document.getElementById('calendarChooserMenuMobile');
  const eventTargetLabel = document.getElementById('eventTargetLabel');

  // Поля модала для переключений
  const allDayChk = document.getElementById('allDayChk');
  const recurrenceSelect = document.getElementById('recurrenceSelect');
  const weeklyBlock = document.getElementById('weeklyBlock');
  const recurrenceInterval = document.getElementById('recurrenceInterval');
  const recurrenceUntil = document.getElementById('recurrenceUntil');
  const recurrenceCount = document.getElementById('recurrenceCount');

  /* ===== Состояние ===== */
  let departments = []; // [{id, name}] где id — всегда числовой PK
  const state = { type: 'company', deptId: null };
  // Защита от гонок при загрузке отделов
  let deptsLoadSeq = 0;

  /* ===== Utils ===== */
  const isDateOnly = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v);

  const toDate = (v) => {
    if (!v) return null;
    if (v instanceof Date) return v;
    if (typeof v === 'number') return new Date(v);
    if (typeof v === 'string') {
      const s = v.trim();
      if (isDateOnly(s)) {
        const [y, m, d] = s.split('-').map(Number);
        return new Date(y, m - 1, d);
      }
      const t = Date.parse(s);
      if (!isNaN(t)) return new Date(t);
    }
    return null;
  };

  const pick = (o, ks) => {
    for (const k of ks) if (o && o[k] != null && o[k] !== '') return o[k];
    return null;
  };

  const startOfWeek = (d) => {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const day = (x.getDay() + 6) % 7;
    x.setDate(x.getDate() - day);
    x.setHours(0, 0, 0, 0);
    return x;
  };

  const endOfWeek = (d) => {
    const s = startOfWeek(d);
    const e = new Date(s);
    e.setDate(s.getDate() + 7);
    return e;
  };

  const overlaps = (ev, ws, we) => ev.start < we && ev.end > ws;

  const truncate = (s, n = 20) => {
    const t = (s ?? '').toString();
    return t.length > n ? t.slice(0, n - 1) + '…' : t;
  };

  async function fetchJSON(url, opts = {}) {
    const headers = { Accept: 'application/json', ...authHeaders(), ...(opts.headers || {}) };
    const r = await fetch(url, { headers, ...opts });
    if (r.status === 401) {
      console.warn('401 от API — нужен валидный access токен');
      return [];
    }
    if (!r.ok) {
      let text = await r.text();
      try {
        text = JSON.parse(text);
      } catch {}
      throw { status: r.status, data: text };
    }
    const data = await r.json();
    return Array.isArray(data) ? data : data.results || data.items || data.events || [];
  }

  function setWeekdaysFromMask(mask) {
    try {
      const m = Number(mask) || 0;
      for (let i = 0; i <= 6; i++) {
        const el = document.getElementById('wd' + i);
        if (el) el.checked = !!(m & (1 << i));
      }
    } catch (_) {}
  }

  /* ===== Helpers для форматирования и API детальной карточки ===== */
  function pad(n) {
    return (n < 10 ? '0' : '') + n;
  }

  function fmtDate(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function fmtTime(d) {
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function fmtWhen(ev) {
    if (!ev) return '—';
    const allDay = !!ev.all_day;
    // Аккуратно парсим дату/дату-время (без UTC-сдвигов на простых датах)
    const sd = toDate(ev.start || ev.start_date);
    const ed = ev.end || ev.end_date ? toDate(ev.end || ev.end_date) : null;
    if (allDay) {
      if (ed && fmtDate(sd) !== fmtDate(ed)) return `${fmtDate(sd)} — ${fmtDate(ed)} (весь день)`;
      return `${fmtDate(sd)} (весь день)`;
    }
    if (ed) return `${fmtDate(sd)} ${fmtTime(sd)} — ${fmtDate(ed)} ${fmtTime(ed)}`;
    return `${fmtDate(sd)} ${fmtTime(sd)}`;
  }

  async function apiGet(url) {
    const r = await fetch(url, { headers: { Accept: 'application/json', ...authHeaders() } });
    const data = await r.json().catch(() => null);
    if (!r.ok) {
      const err = new Error('GET failed');
      err.status = r.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function apiDelete(url) {
    const r = await fetch(url, { method: 'DELETE', headers: { ...authHeaders() } });
    if (!r.ok) {
      const data = await r.json().catch(() => null);
      const err = new Error('DELETE failed');
      err.status = r.status;
      err.data = data;
      throw err;
    }
  }

  // Узлы модала (если разметка подключена)
  const detailsModalEl = document.getElementById('eventDetailsModal');
  // Вынесем модал в <body>, иначе позиционирование ломается, если родитель с transform
  if (detailsModalEl && detailsModalEl.parentElement !== document.body) {
    document.body.appendChild(detailsModalEl);
  }
  // Гарантируем вертикальное центрирование (если в HTML забыли класс)
  detailsModalEl?.querySelector('.modal-dialog')?.classList.add('modal-dialog-centered');

  const detailsModal = detailsModalEl ? new bootstrap.Modal(detailsModalEl) : null;

  const $dt = {
    title: document.getElementById('detailTitle'),
    when: document.getElementById('detailWhen'),
    loc: document.getElementById('detailLocation'),
    desc: document.getElementById('detailDescription'),
    scope: document.getElementById('detailScope'),
    rec: document.getElementById('detailRecurrence'),
    dot: document.getElementById('detailColorDot'),
    btnEdit: document.getElementById('btnEditEvent'),
    btnDel: document.getElementById('btnDeleteEvent'),
  };

  let currentDetail = null;

  function fillDetails(ev) {
    if (!$dt.title) return; // Модала нет — тихо выходим
    $dt.title.textContent = ev.title || 'Событие';
    $dt.when.textContent = fmtWhen(ev);
    $dt.loc.textContent = ev.location || '—';
    $dt.desc.textContent = ev.description || '—';
    $dt.scope.textContent = ev.department
      ? `Отдел: ${ev.department.name || ev.department}`
      : 'Компания';
    $dt.rec.textContent = ev.recurrence_interval
      ? `${ev.recurrence} ×${ev.recurrence_interval}`
      : ev.recurrence || '—';
    const col = ev.color || DEFAULT_EVENT_COLOR;
    if ($dt.dot) $dt.dot.style.backgroundColor = col;
  }

  async function openEventDetailsById(eventId) {
    try {
      const data = await apiGet(`${API_EVENTS}${eventId}/`);
      currentDetail = data;
      fillDetails(data);
      detailsModal && detailsModal.show();
    } catch (err) {
      console.error('Load details error', err);
      if (err.status === 403) alert('Недостаточно прав для просмотра деталей события.');
      else alert('Не удалось загрузить событие.');
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
      console.error('[CalendarWidget] Failed to load departments:', e);
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
      mapped = legacyDeptIds.map((pk) => ({ id: String(pk), name: `Отдел #${pk}` }));
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
      if (menu) menu.querySelectorAll('[data-cal="dept"]').forEach((n) => n.closest('li')?.remove());
    });

    if (!departments.length) {
      setChooserLabel();
      return departments;
    }

    // Заполнение dropdown отделами (десктоп и мобильный)
    [chooserMenu, chooserMenuMobile].forEach((menu) => {
      if (!menu) return;

      // Убедимся, что есть разделитель
      menu.querySelector('.dropdown-divider') ||
        (() => {
          const li = document.createElement('li');
          li.innerHTML = '<hr class="dropdown-divider">';
          menu.appendChild(li);
        })();

      // Вставка пунктов
      const frag = document.createDocumentFragment();
      departments.forEach((d) => {
        const li = document.createElement('li');
        li.innerHTML = `<button class="dropdown-item" type="button" data-cal="dept" data-id="${d.id}">${d.name}</button>`;
        frag.appendChild(li);
      });
      menu.appendChild(frag);
    });

    // Валидация текущего выбора
    if (state.type === 'dept' && !departments.some((d) => String(d.id) === String(state.deptId))) {
      state.type = 'company';
      state.deptId = null;
    }
    setChooserLabel();
    return departments;
  }

  function currentDeptLabel() {
    if (state.type !== 'dept') return 'Компания';
    const d = departments.find((x) => String(x.id) === String(state.deptId));
    return d?.name || `Отдел #${state.deptId}`;
  }

  function setChooserLabel() {
    const label = state.type === 'company' ? 'Компания' : currentDeptLabel();
    if (chooserBtn) chooserBtn.textContent = label;
    if (chooserBtnMobile) chooserBtnMobile.textContent = label;
    if (eventTargetLabel) eventTargetLabel.textContent = label;
  }

  /* ===== Обработчик выбора из дропдауна (десктоп и мобильный) ===== */
  function handleChooserClick(e) {
    const btn = e.target.closest('[data-cal]');
    if (!btn) return;
    const type = btn.dataset.cal;
    if (type === 'company') {
      state.type = 'company';
      state.deptId = null;
    } else {
      const id = btn.dataset.id;
      if (!DIGITS_RE.test(String(id || ''))) {
        alert('Некорректный идентификатор отдела');
        return;
      }
      state.type = 'dept';
      state.deptId = id;
    }
    setChooserLabel();
    [deskCalendar, mobCalendar].forEach((cal) => cal?.refetchEvents());
    updateWeekLists();
  }

  if (chooserMenu) chooserMenu.addEventListener('click', handleChooserClick);
  if (chooserMenuMobile) chooserMenuMobile.addEventListener('click', handleChooserClick);

  /* ===== Комбинированная загрузка событий (occurrences) ===== */
  // События для текущего контекста (используется календарём)
  async function fetchEventsCombined(start, end) {
    try {
      const params = {
        start: ymdLocal(start),
        end: ymdLocal(end)
      };
      
      // Добавляем department_id если нужно
      if (state.type === 'dept' && state.deptId) {
        params.department_id = state.deptId;
      }
      
      // Используем кешированный API
      return await getCalendarEvents(params);
    } catch (e) {
      console.error('[CalendarWidget] Fetch events failed', e);
      return [];
    }
  }

  // ✅ ВСЕ доступные календари: компания + все отделы пользователя
  async function fetchEventsAllCalendars(start, end) {
    // При первом вызове убедимся, что отделы загружены
    if (!departments || departments.length === 0) {
      try {
        await loadDepartments();
      } catch (_) {}
    }
    
    const startStr = ymdLocal(start);
    const endStr = ymdLocal(end);
    
    // Формируем список источников с подписью
    const sources = [
      { params: { start: startStr, end: endStr }, label: 'Компания', type: 'company', id: null },
      ...departments.map((d) => ({
        params: { start: startStr, end: endStr, department_id: d.id },
        label: d.name,
        type: 'dept',
        id: d.id,
      })),
    ];
    
    // Загружаем все источники параллельно (с кешированием!)
    const chunks = await Promise.all(
      sources.map((s) =>
        getCalendarEvents(s.params)
          .then((arr) =>
            (arr || []).map((ev) => ({
              ...ev,
              __source: { label: s.label, type: s.type, id: s.id },
            }))
          )
          .catch((err) => {
            console.error(`[CalendarWidget] Failed to load events for ${s.label}:`, err);
            return [];
          })
      )
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
    const title = pick(ev, ['title', 'name', 'summary', 'text']) || '';
    const rs = pick(ev, ['start', 'start_date', 'date_start', 'date', 'date_from']);
    const re = pick(ev, ['end', 'end_date', 'date_end', 'date_to']);
    const allDay =
      'allDay' in ev
        ? !!ev.allDay
        : 'all_day' in ev
        ? !!ev.all_day
        : isDateOnly(rs) && (!re || isDateOnly(re));
    const s = toDate(rs);
    let e = toDate(re);
    if (!s) return null;
    if (!e) e = new Date(s.getTime() + (allDay ? dayMs : hourMs));
    const color = ev.color || ev.bgColor || null;
    const recurrence = ev.recurrence || ev.recurrence_display || null;
    const location = ev.location || ev.place || '';
    const description = ev.description || ev.details || ev.note || '';
    const sourceLabel = ev.__source?.label || (ev.department?.name ?? ev.department) || 'Компания';
    return { title, start: s, end: e, allDay, color, recurrence, location, description, sourceLabel };
  }

  function renderVertical(container, rangeLabel, events, ws, we) {
    if (!container) return;
    container.innerHTML = '';
    if (rangeLabel) {
      const df = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'long' });
      rangeLabel.textContent = `${df.format(ws)} — ${df.format(new Date(we.getTime() - dayMs))}`;
    }
    const dfDow = new Intl.DateTimeFormat('ru-RU', { weekday: 'short' });
    const dfMD = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit' });

    const list = events
      .map(normalizeEvent)
      .filter(Boolean)
      .filter((ev) => overlaps(ev, ws, we))
      .sort((a, b) => a.start - b.start);

    if (!list.length) {
      const e = document.createElement('div');
      e.className = 'week-vertical empty';
      e.textContent = 'Нет событий на этой неделе';
      container.appendChild(e);
      return;
    }

    list.forEach((ev) => {
      const row = document.createElement('div');
      row.className = 'week-row';
      // Цветовая точка слева от заголовка
      const dot = document.createElement('span');
      dot.className = 'color-dot';
      dot.style.backgroundColor = ev.color || DEFAULT_EVENT_COLOR;
      const badge = document.createElement('div');
      badge.className = 'date-badge';
      const dow = dfDow.format(ev.start),
        md = dfMD.format(ev.start);
      badge.innerHTML = `<div class="dow">${dow}</div><div class="md">${md}</div>`;
      const cont = document.createElement('div');
      cont.className = 'content';
      const title = document.createElement('div');
      title.className = 'title';
      title.textContent = ev.title || 'Без названия';
      title.title = ev.title || '';
      // Строка с источником, локацией и кратким описанием
      const meta = document.createElement('div');
      meta.className = 'meta';
      const dateSpan =
        ev.end - ev.start > dayMs
          ? `${dfMD.format(ev.start)} — ${dfMD.format(new Date(ev.end - 1))}`
          : `${md}`;
      const parts = [ev.sourceLabel || '—'];
      if (ev.location) parts.push(ev.location);
      if (ev.description) parts.push(truncate(ev.description, 20));
      meta.textContent = `${dateSpan} • ${parts.join(' • ')}`;
      const head = document.createElement('div');
      head.style.display = 'flex';
      head.style.alignItems = 'center';
      head.style.gap = '8px';
      head.append(dot, title);
      cont.append(head, meta);
      row.append(badge, cont);
      container.appendChild(row);
    });
  }

  async function updateWeekLists() {
    const now = new Date();
    const ws = startOfWeek(now),
      we = endOfWeek(now);
    const from = new Date(ws.getTime() - 3 * dayMs),
      to = new Date(we.getTime() + 3 * dayMs);
    const items = await fetchEventsAllCalendars(from, to);
    renderVertical(
      document.getElementById('weekList'),
      document.getElementById('weekRange'),
      items,
      ws,
      we
    );
    renderVertical(
      document.getElementById('weekListMobile'),
      document.getElementById('weekRangeMobile'),
      items,
      ws,
      we
    );
  }

  /* ===== Offcanvas header height fix ===== */
  const oc = document.getElementById('rightbarOffcanvas');
  const setHeadH = () => {
    const h = oc?.querySelector('.offcanvas-header')?.offsetHeight || 56;
    if (oc) oc.style.setProperty('--rb-offcanvas-head', h + 'px');
  };
  setHeadH();
  window.addEventListener('resize', setHeadH);
  oc?.addEventListener('shown.bs.offcanvas', () => {
    setHeadH();
    mobCalendar?.updateSize();
  });

  /* ===== FullCalendar init ===== */
  const fcOpts = {
    locale: 'ru',
    initialView: 'dayGridMonth',
    headerToolbar: { left: 'prev,next today', center: 'title', right: '' },
    height: 'auto',
    displayEventTime: false,
    events: async (info, success, failure) => {
      try {
        const raw = await fetchEventsCombined(info.start, info.end);
        // Нормализуем id и цвет для FullCalendar
        const mapped = (Array.isArray(raw) ? raw : []).map((ev) => {
          const id = ev.id ?? ev.pk ?? ev.uuid ?? ev.slug ?? ev._id;
          const color = ev.color || ev.bgColor || null;
          return {
            ...ev,
            ...(id != null ? { id } : {}),
            ...(color ? { backgroundColor: color, borderColor: color } : {}),
          };
        });
        success(mapped);
      } catch (e) {
        console.error('Calendar fetch error:', e);
        failure(e);
      }
    },
    eventContent: (arg) => {
      const el = document.createElement('div');
      el.className = 'fc-event-main';
      el.textContent = arg.event.title || '';
      el.title = arg.event.title || '';
      return { domNodes: [el] };
    },
    eventDidMount: (info) => {
      const col = info.event.backgroundColor || info.event.extendedProps?.color;
      if (col) {
        info.el.style.backgroundColor = col;
        info.el.style.borderColor = col;
        info.el.style.color = 'var(--bs-body-bg)';
      }
      if (info.event.extendedProps?.recurrence === 'annual') {
        info.el.style.outline = '1px dashed currentColor';
        info.el.style.outlineOffset = '-2px';
      }
      const t = info.el.querySelector('.fc-event-main, .fc-event-title');
      if (t) {
        const s = t.style;
        s.fontSize = '10px';
        s.lineHeight = '1.02';
        s.letterSpacing = '-0.2px';
        s.display = '-webkit-box';
        s.webkitLineClamp = '3';
        s.webkitBoxOrient = 'vertical';
        s.overflow = 'hidden';
        s.whiteSpace = 'normal';
        s.textOverflow = 'ellipsis';
        s.fontWeight = '600';
        s.fontFamily =
          '"Arial Narrow","Roboto Condensed",system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif';
      }
    },
  };

  let deskCalendar = null,
    mobCalendar = null;
  const desk = document.getElementById(config.deskContainerId);
  if (desk) {
    deskCalendar = new FullCalendar.Calendar(desk, fcOpts);
    deskCalendar.on('loading', (l) => {
      if (!l) updateWeekLists();
    });
    deskCalendar.on('eventClick', (info) => {
      info.jsEvent?.preventDefault?.();
      const eid = info.event.id || info.event.extendedProps?.id;
      if (eid) openEventDetailsById(eid);
    });
    deskCalendar.render();
  }
  const mob = document.getElementById(config.mobContainerId);
  if (mob) {
    mobCalendar = new FullCalendar.Calendar(mob, fcOpts);
    mobCalendar.on('loading', (l) => {
      if (!l) updateWeekLists();
    });
    mobCalendar.on('eventClick', (info) => {
      info.jsEvent?.preventDefault?.();
      const eid = info.event.id || info.event.extendedProps?.id;
      if (eid) openEventDetailsById(eid);
    });
    mobCalendar.render();
  }

  // Загрузим отделы и обновим подпись селектора
  loadDepartments().then(() => setChooserLabel());

  setTimeout(() => updateWeekLists(), 100);
  [deskCalendar, mobCalendar].forEach((cal) => cal?.on('datesSet', () => updateWeekLists()));

  /* ===== UX: переключалки формы ===== */
  function syncByRecurrence() {
    const r = recurrenceSelect?.value || 'one_time';
    // Weekly block
    if (r === 'weekly') {
      weeklyBlock?.classList.remove('d-none');
    } else {
      weeklyBlock?.classList.add('d-none');
    }
    // Hourly требует времени → снимаем all-day и блокируем чекбокс
    if (r === 'hourly') {
      allDayChk.checked = false;
      allDayChk.disabled = true;
    } else {
      allDayChk.disabled = false;
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
      recurrenceCount.value = '';
      recurrenceCount.disabled = true;
    } else {
      recurrenceCount.disabled = false;
    }
  }

  recurrenceSelect?.addEventListener('change', syncByRecurrence);
  allDayChk?.addEventListener('change', syncByAllDay);
  recurrenceUntil?.addEventListener('change', syncUntilCount);
  syncByRecurrence();
  syncByAllDay();
  syncUntilCount();

  /* ===== Кнопки модала: редактирование/удаление ===== */
  $dt?.btnEdit?.addEventListener?.('click', () => {
    if (!currentDetail) return;
    const form = document.getElementById('eventForm');
    if (!form) {
      detailsModal?.hide();
      return;
    }
    form.dataset.mode = 'edit';
    form.dataset.eventId = currentDetail.id;

    // Базовые поля
    form.querySelector('[name="title"]').value = currentDetail.title || '';
    form.querySelector('[name="location"]').value = currentDetail.location || '';
    form.querySelector('[name="color"]').value = currentDetail.color || DEFAULT_EVENT_COLOR;
    form.querySelector('[name="all_day"]').checked = !!currentDetail.all_day;

    // Описание
    const descEl = form.querySelector('[name="description"]');
    if (descEl) descEl.value = currentDetail.description || '';

    // Дата/время
    const startIso =
      currentDetail.start ||
      (currentDetail.start_date
        ? `${currentDetail.start_date}T${(currentDetail.start_time || '00:00').slice(0, 5)}`
        : '');
    const endIso =
      currentDetail.end ||
      (currentDetail.end_date
        ? `${currentDetail.end_date}T${(currentDetail.end_time || '00:00').slice(0, 5)}`
        : '');
    const startEl = form.querySelector('[name="start"]');
    const endEl = form.querySelector('[name="end"]');
    if (startEl) startEl.value = (startIso || '').slice(0, 16);
    if (endEl) endEl.value = (endIso || '').slice(0, 16);

    // Повторы
    const recSel = form.querySelector('[name="recurrence"]');
    if (recSel) recSel.value = currentDetail.recurrence || 'one_time';
    const recInt = form.querySelector('[name="recurrence_interval"]');
    if (recInt) recInt.value = currentDetail.recurrence_interval || 1;

    // Until / count
    const untilEl = form.querySelector('[name="recurrence_until"]');
    if (untilEl) untilEl.value = (currentDetail.recurrence_until || '').slice(0, 10);
    const countEl = form.querySelector('[name="recurrence_count"]');
    if (countEl) countEl.value = currentDetail.recurrence_count ?? '';

    // Weekly дни из маски
    if (currentDetail.weekdays_mask != null) setWeekdaysFromMask(currentDetail.weekdays_mask);

    // Синхронизация UI
    try {
      typeof syncByRecurrence === 'function' && syncByRecurrence();
    } catch (_) {}

    // Отдел (если есть select)
    const deptSel = form.querySelector('[name="department_id"]');
    if (deptSel && currentDetail.department) {
      const val = currentDetail.department.id ?? currentDetail.department;
      if (val != null) deptSel.value = String(val);
    }

    // Открываем форму редактирования
    detailsModal?.hide();
    setTimeout(() => {
      const createModalEl = document.getElementById('eventCreateModal');
      if (createModalEl) {
        const createModal = bootstrap.Modal.getOrCreateInstance(createModalEl);
        createModal.show();
      } else {
        const offcanvasEl = document.getElementById('rightbarOffcanvas');
        if (offcanvasEl) bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl).show();
      }
      form.querySelector('[name="title"]')?.focus();
    }, 150);
  });

  $dt?.btnDel?.addEventListener?.('click', async () => {
    if (!currentDetail) return;
    if (!confirm('Удалить это событие без возможности восстановления?')) return;
    try {
      await apiDelete(`${API_EVENTS}${currentDetail.id}/`);
      detailsModal?.hide();
      try {
        deskCalendar?.refetchEvents?.();
        mobCalendar?.refetchEvents?.();
      } catch (_) {}
      updateWeekLists();
    } catch (err) {
      console.error('Delete event error', err);
      alert(
        err.status === 403 ? 'Недостаточно прав для удаления.' : 'Не удалось удалить событие.'
      );
    }
  });

  /* ===== Цвет: палитра и синхронизация с input[type=color] ===== */
  function initColorPicker() {
    const form = document.getElementById('eventForm');
    if (!form) return;
    const colorInput = form.querySelector('input[name="color"]');
    const palette = document.getElementById('colorPalette');
    if (!colorInput || !palette) return;

    // Значение по умолчанию
    if (!colorInput.value) colorInput.value = DEFAULT_EVENT_COLOR;

    function highlightActive() {
      const val = (colorInput.value || '').toLowerCase();
      palette.querySelectorAll('[data-color]').forEach((btn) => {
        btn.classList.toggle('active', (btn.dataset.color || '').toLowerCase() === val);
      });
    }
    palette.querySelectorAll('[data-color]').forEach((btn) => {
      btn.addEventListener('click', () => {
        colorInput.value = btn.dataset.color || DEFAULT_EVENT_COLOR;
        colorInput.dispatchEvent(new Event('input', { bubbles: true }));
        highlightActive();
      });
    });
    colorInput.addEventListener('input', highlightActive);
    highlightActive();
  }

  /* ===== Создание/редактирование события (POST/PATCH только с Bearer) ===== */
  const form = document.getElementById('eventForm');
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const title = (fd.get('title') || '').toString().trim();
    let start = fd.get('start')?.toString() || '';
    let end = fd.get('end')?.toString() || '';
    const allDay = !!fd.get('all_day');

    if (!title) {
      alert('Укажите заголовок');
      return;
    }

    // Разбираем datetime-local → даты/время
    const nowIso = new Date().toISOString().slice(0, 16);
    const sDate = (start || nowIso).slice(0, 10);
    const eDate = (end && end.trim() ? end : start || '').slice(0, 10) || sDate;
    const sTime = start && start.length >= 16 ? start.slice(11, 16) : '';
    const eTime = end && end.length >= 16 ? end.slice(11, 16) : '';

    // Повторяемость
    const recurrence = (fd.get('recurrence') || 'one_time').toString();
    const recurrence_interval = Math.max(1, parseInt(fd.get('recurrence_interval') || '1', 10));
    const recurrence_until = (fd.get('recurrence_until') || '').toString().trim();
    const recurrence_count_raw = (fd.get('recurrence_count') || '').toString().trim();
    const recurrence_count = recurrence_count_raw
      ? Math.max(1, parseInt(recurrence_count_raw, 10))
      : null;

    // Weekly weekdays → массив чисел
    const weekdays = Array.from(document.querySelectorAll('input[name="weekdays"]:checked')).map(
      (el) => parseInt(el.value, 10)
    );

    const colorVal = (fd.get('color') || '').toString().trim() || DEFAULT_EVENT_COLOR;
    // Базовый payload
    const payload = {
      title,
      start_date: sDate,
      end_date: eDate,
      all_day: allDay,
      recurrence,
      recurrence_interval,
      color: colorVal,
      location: (fd.get('location') || '').toString().trim() || '',
      description: (fd.get('description') || '').toString().trim() || '',
    };

    // Время (если all_day=false ИЛИ пользователь указал оба времени)
    if (!allDay || (sTime && eTime)) {
      if (sTime && eTime) {
        payload.start_time = sTime; // "HH:MM"
        payload.end_time = eTime; // "HH:MM"
        payload.all_day = false;
      } else if (recurrence === 'hourly') {
        alert('Ежечасное событие требует и время начала, и время окончания.');
        return;
      }
    }

    // Ограничители серии
    if (recurrence_until && recurrence_count) {
      alert('Нельзя одновременно задавать "Повторять до" и "Кол-во повторов". Укажите что-то одно.');
      return;
    }
    if (recurrence_until) payload.recurrence_until = recurrence_until;
    if (recurrence_count) payload.recurrence_count = recurrence_count;

    // Weekly: передаём weekdays если выбраны
    if (recurrence === 'weekly' && weekdays.length) {
      payload.weekdays = weekdays;
    }

    // Область — компания/отдел
    if (state.type === 'dept') {
      if (!DIGITS_RE.test(String(state.deptId))) {
        alert('Некорректный отдел');
        return;
      }
      payload.department_id = Number(state.deptId);
    }

    const postHeaders = { 'Content-Type': 'application/json', ...authHeaders() };
    // Проверка токена
    if (!globalToken) {
      alert('Требуется авторизация. Войдите заново.');
      return;
    }

    try {
      const isEdit = form.dataset.mode === 'edit' && form.dataset.eventId;
      const url = isEdit ? API_EVENTS + String(form.dataset.eventId) + '/' : API_EVENTS;
      const method = isEdit ? 'PATCH' : 'POST';
      await fetchJSON(url, {
        method,
        headers: postHeaders,
        body: JSON.stringify(payload),
      });

      document.querySelector('#eventCreateModal .btn-close')?.click();
      form.reset();
      delete form.dataset.mode;
      delete form.dataset.eventId;
      syncByRecurrence();
      syncByAllDay();
      syncUntilCount();
      [deskCalendar, mobCalendar].forEach((cal) => cal?.refetchEvents());
      updateWeekLists();
    } catch (err) {
      console.error('Create event error', err);
      if (err && err.status === 403) {
        const where = state?.type === 'dept' ? `отделе «${currentDeptLabel()}»` : 'компании';
        alert(
          'Недостаточно прав для создания события в ' +
            where +
            '.\n' +
            'Попросите руководителя назначить вам роль «Управлять календарём отдела».'
        );
      } else {
        const detail =
          err?.data?.detail || (typeof err?.data === 'string' ? err.data : '');
        alert('Не удалось создать событие: ' + (detail || JSON.stringify(err?.data || {})));
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
  };
}

// Автоинициализация при загрузке DOM
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.calendarWidget = initCalendarWidget();
  });
}
