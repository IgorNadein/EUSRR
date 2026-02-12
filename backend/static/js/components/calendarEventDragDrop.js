/**
 * @fileoverview Calendar Event Drag & Drop - перемещение событий между календарями
 * @module components/calendarEventDragDrop
 */

import { authHeaders as getAuthHeaders } from "../utils/authUtils.js";
import { API_URLS } from "../constants/apiUrls.js";
import {
  CALENDAR_TYPES,
  isLegacyCalendar,
  getLegacyCalendarType,
  extractDepartmentId,
} from "../constants/calendarTypes.js";

/**
 * Класс для управления состоянием переноса событий
 */
class DragDropState {
  constructor() {
    this.sourceCalendarId = null;
    this.targetCalendarId = null;
  }

  setSource(id) {
    this.sourceCalendarId = id;
  }

  setTarget(id) {
    this.targetCalendarId = id;
  }

  reset() {
    this.sourceCalendarId = null;
    this.targetCalendarId = null;
  }

  isValid() {
    return (
      this.sourceCalendarId &&
      this.targetCalendarId &&
      this.sourceCalendarId !== this.targetCalendarId
    );
  }
}

/**
 * Утилиты для работы с календарями
 */
class CalendarUtils {
  static getCalendarName(calendarId) {
    if (isLegacyCalendar(calendarId)) {
      const type = getLegacyCalendarType(calendarId);

      if (type === CALENDAR_TYPES.COMPANY) {
        return "📅 Календарь компании";
      }

      if (type === CALENDAR_TYPES.DEPARTMENT) {
        const deptId = extractDepartmentId(calendarId);
        const folderEl = document.querySelector(`[data-folder-id="legacy-dept-${deptId}"]`);
        if (folderEl) {
          const titleEl = folderEl.querySelector(".calendar-folder-title");
          if (titleEl) return `🏢 ${titleEl.textContent.trim()}`;
        }
        return `🏢 Календарь отдела #${deptId}`;
      }

      if (type === CALENDAR_TYPES.PERSONAL) {
        return "👤 Мой календарь";
      }
    }

    const calEl = document.querySelector(`[data-calendar-id="${calendarId}"]`);
    if (calEl) {
      const titleEl = calEl.querySelector(".calendar-title");
      if (titleEl) return `📆 ${titleEl.textContent.trim()}`;
    }

    return `📆 Календарь #${calendarId}`;
  }

  static buildMovePayload(targetCalendarId) {
    if (isLegacyCalendar(targetCalendarId)) {
      const type = getLegacyCalendarType(targetCalendarId);

      if (type === CALENDAR_TYPES.COMPANY) {
        return { calendar_id: null, department_id: null, employee_id: null };
      }

      if (type === CALENDAR_TYPES.DEPARTMENT) {
        const deptId = extractDepartmentId(targetCalendarId);
        return { calendar_id: null, department_id: deptId, employee_id: null };
      }

      if (type === CALENDAR_TYPES.PERSONAL) {
        const employeeId = window.currentUserId;
        if (!employeeId) throw new Error("User ID not found");
        return { calendar_id: null, department_id: null, employee_id: employeeId };
      }
    }

    return {
      calendar_id: parseInt(targetCalendarId),
      department_id: null,
      employee_id: null,
    };
  }

  static buildEventsUrl(calendarId) {
    const url = new URL(`${API_URLS.EVENTS}list_raw/`, window.location.origin);

    if (isLegacyCalendar(calendarId)) {
      const type = getLegacyCalendarType(calendarId);

      if (type === CALENDAR_TYPES.COMPANY) {
        return url.toString();
      }

      if (type === CALENDAR_TYPES.DEPARTMENT) {
        const deptId = extractDepartmentId(calendarId);
        if (deptId) url.searchParams.set("department_id", String(deptId));
      } else if (type === CALENDAR_TYPES.PERSONAL) {
        const userId = window.currentUserId;
        if (userId) url.searchParams.set("employee_id", String(userId));
      }
    } else {
      url.searchParams.set("calendar_id", String(calendarId));
    }

    return url.toString();
  }
}

/**
 * Инициализация drag & drop
 */
export function initCalendarEventDragDrop(options = {}) {
  const { onEventMoved = () => {} } = options;

  const state = new DragDropState();
  let modal = null;
  let listEl = null;

  function createModal() {
    const html = `
      <div class="modal fade" id="calendarEventPickerModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
          <div class="modal-content">
            <div class="modal-header">
              <div>
                <h5 class="modal-title">
                  <i class="bi bi-arrow-left-right me-2"></i>Перемещение событий
                </h5>
                <div id="calendarTransferInfo" class="mt-2 d-flex align-items-center gap-2">
                  <span id="sourceCalendarName" class="badge bg-primary">...</span>
                  <i class="bi bi-arrow-right"></i>
                  <span id="targetCalendarName" class="badge bg-success">...</span>
                </div>
              </div>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <input type="search" class="form-control" id="eventPickerSearch" placeholder="Поиск события...">
              </div>
              <div id="eventPickerList" class="list-group"></div>
              <div id="eventPickerEmpty" class="text-center text-muted py-5 d-none">
                <i class="bi bi-inbox fs-1 mb-3 opacity-50"></i>
                <p class="mb-0">Нет событий для перемещения</p>
              </div>
              <div id="eventPickerLoading" class="text-center py-5 d-none">
                <div class="spinner-border text-primary mb-3"></div>
                <p class="text-muted mb-0">Загрузка событий...</p>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                <i class="bi bi-x-lg me-1"></i>Отмена
              </button>
              <button type="button" class="btn btn-primary" id="eventPickerMoveAll">
                <i class="bi bi-arrow-right-square me-1"></i>Переместить все
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML("beforeend", html);
    const modalEl = document.getElementById("calendarEventPickerModal");
    modal = new bootstrap.Modal(modalEl);
    listEl = document.getElementById("eventPickerList");

    modalEl.addEventListener("hidden.bs.modal", () => {
      listEl.innerHTML = "";
      document.getElementById("eventPickerSearch").value = "";
      document.getElementById("eventPickerLoading").classList.add("d-none");
      document.getElementById("eventPickerEmpty").classList.add("d-none");
      state.reset();
    });

    document.getElementById("eventPickerSearch").addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase();
      listEl.querySelectorAll(".list-group-item").forEach((item) => {
        const title = item.dataset.eventTitle?.toLowerCase() || "";
        item.style.display = title.includes(query) ? "" : "none";
      });
    });

    document.getElementById("eventPickerMoveAll").addEventListener("click", moveAllEvents);
  }

  async function showModal(sourceId, targetId) {
    if (!sourceId || !targetId || sourceId === targetId) {
      console.error("[EventDragDrop] Invalid IDs:", { sourceId, targetId });
      return;
    }

    state.setSource(sourceId);
    state.setTarget(targetId);

    const sourceName = CalendarUtils.getCalendarName(sourceId);
    const targetName = CalendarUtils.getCalendarName(targetId);

    document.getElementById("sourceCalendarName").textContent = sourceName;
    document.getElementById("targetCalendarName").textContent = targetName;

    console.log("[EventDragDrop] Transfer:", sourceName, "→", targetName);

    await loadEvents();
    modal.show();
  }

  async function loadEvents() {
    const loadingEl = document.getElementById("eventPickerLoading");
    const emptyEl = document.getElementById("eventPickerEmpty");

    loadingEl.classList.remove("d-none");
    emptyEl.classList.add("d-none");
    listEl.innerHTML = "";

    try {
      const url = CalendarUtils.buildEventsUrl(state.sourceCalendarId);
      console.log("[EventDragDrop] Loading from:", url);

      const response = await fetch(url, { headers: getAuthHeaders() });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const events = await response.json();
      console.log("[EventDragDrop] Loaded:", events.length, "events");

      loadingEl.classList.add("d-none");

      if (!events || events.length === 0) {
        emptyEl.classList.remove("d-none");
        return;
      }

      listEl.innerHTML = events
        .map((event) => {
          const date = new Date(event.start_date);
          const dateStr = date.toLocaleDateString("ru-RU");
          const timeStr = event.start_time ? event.start_time.slice(0, 5) : "";
          const dateTime = timeStr ? `${dateStr} ${timeStr}` : dateStr;

          return `
            <button type="button" class="list-group-item list-group-item-action"
                    data-event-id="${event.id}" data-event-title="${escapeHtml(event.title)}">
              <div class="d-flex justify-content-between align-items-start">
                <div>
                  <div class="fw-bold mb-1">${escapeHtml(event.title)}</div>
                  <small class="text-muted">
                    <i class="bi bi-calendar-event me-1"></i>${dateTime}
                  </small>
                </div>
                <i class="bi bi-arrow-right text-primary"></i>
              </div>
            </button>
          `;
        })
        .join("");

      listEl.querySelectorAll(".list-group-item").forEach((item) => {
        item.addEventListener("click", () => moveSingleEvent(parseInt(item.dataset.eventId)));
      });
    } catch (error) {
      console.error("[EventDragDrop] Load failed:", error);
      loadingEl.classList.add("d-none");
      emptyEl.classList.remove("d-none");
      showToast("Ошибка загрузки событий", "danger");
    }
  }

  async function moveSingleEvent(eventId) {
    if (!state.isValid()) {
      showToast("Некорректные календари", "danger");
      return;
    }

    try {
      const payload = CalendarUtils.buildMovePayload(state.targetCalendarId);
      const url = `${API_URLS.EVENTS}${eventId}/`;

      console.log("[EventDragDrop] Moving:", eventId, payload);

      const response = await fetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Server error");
      }

      console.log("[EventDragDrop] Success:", await response.json());

      modal.hide();
      await new Promise((resolve) => setTimeout(resolve, 100));
      onEventMoved();
      showToast("Событие перемещено", "success");
    } catch (error) {
      console.error("[EventDragDrop] Move failed:", error);
      showToast("Ошибка перемещения: " + error.message, "danger");
    }
  }

  async function moveAllEvents() {
    const items = Array.from(listEl.querySelectorAll(".list-group-item")).filter(
      (item) => item.style.display !== "none"
    );

    if (items.length === 0) {
      showToast("Нет событий для перемещения", "warning");
      return;
    }

    const eventIds = items.map((item) => parseInt(item.dataset.eventId));
    const sourceName = CalendarUtils.getCalendarName(state.sourceCalendarId);
    const targetName = CalendarUtils.getCalendarName(state.targetCalendarId);

    if (!confirm(`Переместить ${eventIds.length} событий из "${sourceName}" в "${targetName}"?`)) {
      return;
    }

    try {
      const payload = CalendarUtils.buildMovePayload(state.targetCalendarId);
      const btn = document.getElementById("eventPickerMoveAll");
      const originalText = btn.innerHTML;

      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Перемещение...';

      let successCount = 0;
      let failCount = 0;

      console.log("[EventDragDrop] Bulk move:", eventIds.length, payload);

      for (const eventId of eventIds) {
        try {
          const url = `${API_URLS.EVENTS}${eventId}/`;
          const response = await fetch(url, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", ...getAuthHeaders() },
            body: JSON.stringify(payload),
          });

          if (response.ok) {
            successCount++;
          } else {
            failCount++;
            console.error(`[EventDragDrop] Failed: ${eventId}`);
          }
        } catch (error) {
          failCount++;
          console.error(`[EventDragDrop] Error ${eventId}:`, error);
        }
      }

      btn.disabled = false;
      btn.innerHTML = originalText;

      console.log("[EventDragDrop] Completed:", { successCount, failCount });

      modal.hide();
      await new Promise((resolve) => setTimeout(resolve, 100));
      onEventMoved();

      if (failCount === 0) {
        showToast(`✅ Перемещено ${successCount} событий`, "success");
      } else {
        showToast(`⚠️ Перемещено ${successCount}, ошибок: ${failCount}`, "warning");
      }
    } catch (error) {
      console.error("[EventDragDrop] Bulk move failed:", error);
      showToast("Ошибка массового перемещения", "danger");
    }
  }

  function initDragDrop(element) {
    const calendarId = element.dataset.calendarId || element.dataset.folderId;
    if (!calendarId) return;

    const badge = element.querySelector(".badge.bg-secondary-subtle.text-secondary, .badge.bg-info-subtle.text-info");
    if (!badge) return;

    badge.setAttribute("draggable", "true");
    badge.style.cursor = "grab";
    badge.title = "Перетащите для перемещения событий";

    badge.addEventListener("dragstart", (e) => {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", calendarId);
      badge.style.opacity = "0.5";
      console.log("[EventDragDrop] Drag start:", calendarId);
    });

    badge.addEventListener("dragend", () => {
      badge.style.opacity = "1";
      document.querySelectorAll(".drop-target-active").forEach((el) => {
        el.classList.remove("drop-target-active");
      });
    });

    element.addEventListener("dragover", (e) => {
      const targetId = element.dataset.calendarId || element.dataset.folderId;
      const sourceId = e.dataTransfer.getData("text/plain");
      if (targetId === sourceId) return;

      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "move";
      element.classList.add("drop-target-active");
    });

    element.addEventListener("dragleave", (e) => {
      if (!element.contains(e.relatedTarget)) {
        element.classList.remove("drop-target-active");
      }
    });

    element.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      element.classList.remove("drop-target-active");

      const sourceId = e.dataTransfer.getData("text/plain");
      const targetId = element.dataset.calendarId || element.dataset.folderId;

      console.log("[EventDragDrop] Drop:", { source: sourceId, target: targetId });

      if (sourceId && targetId && sourceId !== targetId) {
        showModal(sourceId, targetId);
      }
    });
  }

  function refreshDragDrop() {
    document.querySelectorAll(".calendar-list-item").forEach(initDragDrop);
    document.querySelectorAll(".calendar-folder").forEach(initDragDrop);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function showToast(message, type = "success") {
    const icons = { success: "check-circle", danger: "exclamation-circle", warning: "exclamation-triangle" };
    const titles = { success: "Успешно", danger: "Ошибка", warning: "Внимание" };

    const html = `
      <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div class="toast show">
          <div class="toast-header bg-${type} text-white">
            <i class="bi-${icons[type]} me-2"></i>
            <strong class="me-auto">${titles[type]}</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
          </div>
          <div class="toast-body">${message}</div>
        </div>
      </div>
    `;

    document.querySelector(".toast-container")?.remove();
    document.body.insertAdjacentHTML("beforeend", html);
    setTimeout(() => document.querySelector(".toast-container")?.remove(), 5000);
  }

  createModal();

  const observer = new MutationObserver(refreshDragDrop);
  const container = document.querySelector(".calendar-list-container");
  if (container) {
    observer.observe(container, { childList: true, subtree: true });
  }

  refreshDragDrop();

  return {
    refresh: refreshDragDrop,
    destroy: () => {
      observer.disconnect();
      document.getElementById("calendarEventPickerModal")?.remove();
    },
  };
}
