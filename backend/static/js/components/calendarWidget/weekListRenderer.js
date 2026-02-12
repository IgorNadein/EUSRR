/**
 * weekListRenderer.js
 * Рендеринг бокового списка событий по неделям
 * @module calendarWidget/weekListRenderer
 */

import {
  startOfWeek,
  endOfWeek,
  overlaps,
  truncate,
  dayMs,
} from "./helpers.js";

/**
 * Отрендерить вертикальный список событий недели
 * @param {HTMLElement} container - Контейнер для списка
 * @param {HTMLElement} rangeLabel - Элемент для отображения диапазона дат
 * @param {Array} events - Массив событий
 * @param {Date} ws - Начало недели
 * @param {Date} we - Конец недели
 * @param {Function} normalizeEvent - Функция нормализации события
 * @param {Function} openEventDetailsById - Функция открытия детальной карточки
 * @param {string} defaultColor - Цвет по умолчанию
 */
export function renderVertical(
  container,
  rangeLabel,
  events,
  ws,
  we,
  normalizeEvent,
  openEventDetailsById,
  defaultColor,
) {
  if (!container) return;
  container.innerHTML = "";
  if (rangeLabel) {
    const df = new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "long",
    });
    rangeLabel.textContent = `${df.format(ws)} — ${df.format(new Date(we.getTime() - dayMs))}`;
  }
  const dfDow = new Intl.DateTimeFormat("ru-RU", { weekday: "short" });
  const dfMD = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
  });

  const list = events
    .map(normalizeEvent)
    .filter(Boolean)
    .filter((ev) => overlaps(ev, ws, we))
    .sort((a, b) => a.start - b.start);

  if (!list.length) {
    const e = document.createElement("div");
    e.className = "week-vertical empty";
    e.textContent = "Нет событий на этой неделе";
    container.appendChild(e);
    return;
  }

  list.forEach((ev) => {
    const row = document.createElement("div");
    row.className = "week-row";

    // Сохраняем ID события для обработчика клика (уже нормализовано в ev.id)
    if (ev.id) {
      row.dataset.eventId = String(ev.id);
      row.style.cursor = "pointer";
      row.addEventListener("click", () => {
        console.log("[CalendarWidget] Opening event details:", ev.id);
        openEventDetailsById(ev.id);
      });
    }

    // Цветовая точка слева от заголовка
    const dot = document.createElement("span");
    dot.className = "color-dot";
    dot.style.backgroundColor = ev.color || defaultColor;
    const badge = document.createElement("div");
    badge.className = "date-badge";
    const dow = dfDow.format(ev.start),
      md = dfMD.format(ev.start);
    badge.innerHTML = `<div class="dow">${dow}</div><div class="md">${md}</div>`;
    const cont = document.createElement("div");
    cont.className = "content";
    const title = document.createElement("div");
    title.className = "title";
    title.textContent = ev.title || "Без названия";
    title.title = ev.title || "";
    // Строка с источником, локацией и кратким описанием
    const meta = document.createElement("div");
    meta.className = "meta";
    const dateSpan =
      ev.end - ev.start > dayMs
        ? `${dfMD.format(ev.start)} — ${dfMD.format(new Date(ev.end - 1))}`
        : `${md}`;
    const parts = [ev.sourceLabel || "—"];
    if (ev.location) parts.push(ev.location);
    if (ev.description) parts.push(truncate(ev.description, 20));
    meta.textContent = `${dateSpan} • ${parts.join(" • ")}`;
    const head = document.createElement("div");
    head.style.display = "flex";
    head.style.alignItems = "center";
    head.style.gap = "8px";
    head.append(dot, title);
    cont.append(head, meta);
    row.append(badge, cont);
    container.appendChild(row);
  });
}

/**
 * Обновить списки событий текущей недели (десктоп и мобильная версии)
 * @param {Function} fetchEventsAllCalendars - Функция загрузки событий
 * @param {Function} normalizeEvent - Функция нормализации события
 * @param {Function} openEventDetailsById - Функция открытия детальной карточки
 * @param {string} defaultColor - Цвет по умолчанию
 */
export async function updateWeekLists(
  fetchEventsAllCalendars,
  normalizeEvent,
  openEventDetailsById,
  defaultColor,
) {
  const now = new Date();
  const ws = startOfWeek(now),
    we = endOfWeek(now);
  const from = new Date(ws.getTime() - 3 * dayMs),
    to = new Date(we.getTime() + 3 * dayMs);
  const items = await fetchEventsAllCalendars(from, to);
  renderVertical(
    document.getElementById("weekList"),
    document.getElementById("weekRange"),
    items,
    ws,
    we,
    normalizeEvent,
    openEventDetailsById,
    defaultColor,
  );
  renderVertical(
    document.getElementById("weekListMobile"),
    document.getElementById("weekRangeMobile"),
    items,
    ws,
    we,
    normalizeEvent,
    openEventDetailsById,
    defaultColor,
  );
}
