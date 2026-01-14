/**
 * Менеджер уведомлений - подключение к WebSocket и управление
 */

import {
  getNotifications,
  invalidateNotifications,
} from "../api/notificationsApi.js";

class NotificationManager {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.isConnected = false;
    this.notificationPermission = "default";
    this.soundEnabled = this.loadSoundPreference();

    this.init();
  }

  /**
   * Загрузить настройку звука из localStorage
   */
  loadSoundPreference() {
    const saved = localStorage.getItem("notificationSoundEnabled");
    return saved === null ? true : saved === "true";
  }

  /**
   * Сохранить настройку звука
   */
  saveSoundPreference(enabled) {
    this.soundEnabled = enabled;
    localStorage.setItem("notificationSoundEnabled", enabled.toString());
  }

  /**
   * Воспроизвести звук уведомления
   * Приоритет: 1) MP3 файл, 2) Web Audio API (fallback)
   */
  playNotificationSound() {
    if (!this.soundEnabled) {
      console.log("[Notifications] Sound disabled");
      return;
    }

    try {
      // Попытка воспроизвести MP3 файл
      const audio = new Audio("/static/sounds/notification.mp3");
      audio.volume = 0.3;
      console.log("[Notifications] Playing MP3 sound");
      audio
        .play()
        .then(() => {
          console.log("[Notifications] MP3 sound played successfully");
        })
        .catch((err) => {
          console.warn(
            "[Notifications] MP3 playback failed, using fallback:",
            err
          );
          // Fallback на Web Audio API если MP3 недоступен
          this.playFallbackSound();
        });
    } catch (error) {
      console.warn(
        "[Notifications] MP3 loading failed, using fallback:",
        error
      );
      // Fallback на Web Audio API
      this.playFallbackSound();
    }
  }

  /**
   * Резервный метод: синтетический звук через Web Audio API
   */
  playFallbackSound() {
    console.log("[Notifications] Playing fallback Web Audio API sound");
    try {
      const audioContext = new (window.AudioContext ||
        window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800; // Частота звука
      oscillator.type = "sine";

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(
        0.01,
        audioContext.currentTime + 0.3
      );

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.3);
      console.log("[Notifications] Fallback sound completed");
    } catch (error) {
      console.warn("[Notifications] Sound playback failed:", error);
    }
  }

  init() {
    this.requestNotificationPermission();
    this.connectWebSocket();
    this.loadInitialNotifications();
    this.setupDropdown();
  }

  /**
   * Запросить разрешение на показ браузерных уведомлений
   */
  async requestNotificationPermission() {
    if (!("Notification" in window)) {
      console.warn("[Notifications] Browser does not support notifications");
      return;
    }

    if (Notification.permission === "granted") {
      this.notificationPermission = "granted";
      console.log("[Notifications] Permission already granted");
      return;
    }

    if (Notification.permission !== "denied") {
      try {
        const permission = await Notification.requestPermission();
        this.notificationPermission = permission;
        console.log("[Notifications] Permission:", permission);
      } catch (error) {
        console.error("[Notifications] Error requesting permission:", error);
      }
    }
  }

  connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // Используем универсальный WebSocket endpoint (realtime architecture)
    const wsUrl = `${protocol}//${window.location.host}/ws/`;

    console.log("[Notifications] Connecting to:", wsUrl);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[Notifications] WebSocket connected");
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.updateConnectionStatus(true);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.ws.onclose = () => {
        console.log("[Notifications] WebSocket disconnected");
        this.isConnected = false;
        this.updateConnectionStatus(false);
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("[Notifications] WebSocket error:", error);
      };
    } catch (error) {
      console.error("[Notifications] Failed to create WebSocket:", error);
      this.attemptReconnect();
    }
  }

  handleMessage(event) {
    try {
      const data = JSON.parse(event.data);

      // Игнорируем ping сообщения для keepalive (не логируем)
      if (data.type === "ping") {
        return;
      }

      // Игнорируем list_update - это для списка чатов, не для уведомлений
      if (data.type === "list_update") {
        return;
      }

      // Игнорируем чат-события - они обрабатываются userWebSocket
      if (["message_edited", "reaction_added", "reaction_removed"].includes(data.type)) {
        return;
      }

      console.log("[Notifications] Received:", data);

      switch (data.type) {
        case "unread_count":
          this.updateBadge(data.count);
          break;

        case "notification": // UserConsumer использует "notification"
          this.showNewNotification(data.notification);
          // Инвалидируем кеш при получении нового уведомления
          invalidateNotifications();
          break;

        case "new_notification": // Backwards compatibility
          this.showNewNotification(data.notification);
          this.updateBadge(data.notification.unread_count);
          // Инвалидируем кеш при получении нового уведомления
          invalidateNotifications();
          break;

        case "count_update":
          this.updateBadge(data.count);
          // Инвалидируем кеш при изменении счетчика
          invalidateNotifications();
          break;

        default:
          console.warn("[Notifications] Unknown message type:", data.type);
      }
    } catch (error) {
      console.error("[Notifications] Error parsing message:", error);
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * this.reconnectAttempts;

      console.log(
        `[Notifications] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
      );

      setTimeout(() => {
        this.connectWebSocket();
      }, delay);
    } else {
      console.error("[Notifications] Max reconnect attempts reached");
    }
  }

  updateConnectionStatus(connected) {
    // Визуальная индикация статуса подключения (опционально)
    const badge = document.getElementById("notificationBadge");
    if (badge) {
      if (!connected) {
        badge.style.backgroundColor = "#dc3545"; // красный при отключении
      } else {
        badge.style.backgroundColor = ""; // вернуть стандартный цвет
      }
    }
  }

  updateBadge(count) {
    const badge = document.getElementById("notificationBadge");
    if (badge) {
      const oldCount = parseInt(badge.textContent) || 0;
      if (count > 0) {
        badge.textContent = count > 99 ? "99+" : count;
        badge.style.display = '';
        // Анимация pulse при увеличении
        if (count > oldCount) {
          badge.classList.add('pulse');
          setTimeout(() => badge.classList.remove('pulse'), 600);
        }
      } else {
        badge.style.display = 'none';
        badge.classList.remove('pulse');
      }
    }
  }

  async loadInitialNotifications() {
    try {
      // Используем кешированный API вместо прямого fetch
      const data = await getNotifications({
        page: 1,
        page_size: 5,
        unread_only: true,
      });

      console.log("[Notifications] Loaded data:", data);
      this.renderNotifications(data.notifications || []);
      this.updateBadge(data.total || 0);
    } catch (error) {
      console.error("[Notifications] Error loading notifications:", error);
      // Показываем заглушку при ошибке
      const list = document.getElementById("notificationList");
      if (list) {
        list.innerHTML = `
                    <div class="notification-empty-state">
                        <i class="bi-exclamation-triangle"></i>
                        <div>Ошибка загрузки уведомлений</div>
                    </div>
                `;
      }
    }
  }

  renderNotifications(notifications) {
    const listElement = document.getElementById("notificationList");
    if (!listElement) return;

    if (notifications.length === 0) {
      listElement.innerHTML = `
                <div class="notification-empty-state">
                    <i class="bi-bell-slash"></i>
                    <div>Нет новых уведомлений</div>
                </div>
            `;
      return;
    }

    listElement.innerHTML = notifications
      .map((n) => this.renderNotificationItem(n))
      .join("");

    // Добавить обработчики событий
    listElement.querySelectorAll("[data-notification-id]").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        const notificationId = item.dataset.notificationId;
        const actionUrl = item.dataset.actionUrl;

        this.markAsRead(notificationId).then(() => {
          this.closeDropdown(); // Закрыть dropdown
          if (actionUrl) {
            window.location.href = actionUrl;
          }
        });
      });
    });
  }

  renderNotificationItem(notification) {
    const iconColorClass = `text-${notification.color}`;
    const timeAgo = this.getTimeAgo(notification.created_at);

    return `
            <div class="notification-item ${
              !notification.is_read ? "unread" : ""
            }"
                data-notification-id="${notification.id}"
                data-action-url="${notification.action_url || ""}">
                <div class="notification-icon">
                    <i class="${notification.icon} ${iconColorClass}"></i>
                </div>
                <div class="notification-content">
                    <div class="notification-title">${this.escapeHtml(
                      notification.title
                    )}</div>
                    <div class="notification-message">${this.escapeHtml(
                      notification.message
                    )}</div>
                    <div class="notification-time">${timeAgo}</div>
                </div>
                ${
                  !notification.is_read
                    ? '<div class="notification-unread-badge"></div>'
                    : ""
                }
            </div>
        `;
  }

  showNewNotification(notification) {
    // Показать нативное браузерное уведомление
    this.showBrowserNotification(notification);

    // Обновить список в dropdown
    this.loadInitialNotifications();

    // Воспроизвести звук (опционально)
    this.playNotificationSound();
  }

  /**
   * Показать нативное браузерное уведомление
   */
  showBrowserNotification(notification) {
    if (!("Notification" in window)) {
      console.warn("[Notifications] Browser notifications not supported");
      // Fallback to toast
      this.showToast(notification);
      return;
    }

    if (Notification.permission !== "granted") {
      console.warn("[Notifications] Permission not granted");
      // Fallback to toast
      this.showToast(notification);
      return;
    }

    // Определить иконку по категории
    const iconMap = {
      communications: "💬",
      documents: "📄",
      requests: "📋",
      calendar: "📅",
      department: "👥",
      profile: "👤",
      feed: "📰",
      system: "⚙️",
    };

    const options = {
      body: notification.message,
      icon: "/static/img/logo.png", // Можно заменить на специальную иконку
      badge: "/static/img/favicon-32.png",
      tag: `notification-${notification.id}`,
      requireInteraction: notification.priority === "urgent",
      silent: false,
      data: {
        notificationId: notification.id,
        actionUrl: notification.action_url,
      },
    };

    try {
      const browserNotification = new Notification(
        `${iconMap[notification.category] || "🔔"} ${notification.title}`,
        options
      );

      // Обработать клик по уведомлению
      browserNotification.onclick = (event) => {
        event.preventDefault();
        window.focus();

        // Отметить как прочитанное
        this.markAsRead(notification.id);

        // Перейти по ссылке ТОЛЬКО если это не текущая страница
        // (избегаем ненужной перезагрузки при клике на уведомление о решении заявления)
        if (notification.action_url) {
          const currentPath = window.location.pathname;
          const notificationPath = new URL(
            notification.action_url,
            window.location.origin
          ).pathname;

          // Если это уже текущая страница, просто закрываем уведомление
          if (currentPath !== notificationPath) {
            window.location.href = notification.action_url;
          }
        }

        browserNotification.close();
      };

      // Автозакрытие через 10 секунд (если не urgent)
      if (notification.priority !== "urgent") {
        setTimeout(() => {
          browserNotification.close();
        }, 10000);
      }

      console.log(
        "[Notifications] Browser notification shown:",
        notification.title
      );
    } catch (error) {
      console.error(
        "[Notifications] Error showing browser notification:",
        error
      );
      // Fallback to toast
      this.showToast(notification);
    }
  }

  showToast(notification) {
    // Создать toast элемент
    const toastHtml = `
            <div class="toast align-items-center border-0 bg-${
              notification.color
            } text-white" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="${notification.icon} me-2"></i>
                        <strong>${this.escapeHtml(notification.title)}</strong>
                        <div class="small">${this.escapeHtml(
                          notification.message
                        )}</div>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

    // Добавить в контейнер
    let toastContainer = document.getElementById("toastContainer");
    if (!toastContainer) {
      toastContainer = document.createElement("div");
      toastContainer.id = "toastContainer";
      toastContainer.className =
        "toast-container position-fixed top-0 end-0 p-3";
      toastContainer.style.zIndex = "9999";
      document.body.appendChild(toastContainer);
    }

    toastContainer.insertAdjacentHTML("beforeend", toastHtml);

    // Показать toast
    const toastElement = toastContainer.lastElementChild;
    const toast = new bootstrap.Toast(toastElement, {
      autohide: true,
      delay: 5000,
    });
    toast.show();

    // Удалить после скрытия
    toastElement.addEventListener("hidden.bs.toast", () => {
      toastElement.remove();
    });
  }

  async markAsRead(notificationId) {
    try {
      const response = await fetch(
        `/api/v1/notifications/${notificationId}/read/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.getCsrfToken(),
          },
        }
      );

      if (response.ok) {
        console.log("[Notifications] Marked as read:", notificationId);
      }
    } catch (error) {
      console.error("[Notifications] Error marking as read:", error);
    }
  }

  async markAllAsRead() {
    try {
      const response = await fetch("/api/v1/notifications/read-all/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.getCsrfToken(),
        },
      });

      if (response.ok) {
        console.log("[Notifications] All marked as read");
        this.loadInitialNotifications();
      }
    } catch (error) {
      console.error("[Notifications] Error marking all as read:", error);
    }
  }

  getTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return "только что";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} мин назад`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч назад`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)} дн назад`;

    return date.toLocaleDateString("ru-RU");
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  getCsrfToken() {
    return (
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      document.cookie.match(/csrftoken=([^;]+)/)?.[1] ||
      ""
    );
  }

  /**
   * Управление dropdown меню
   */
  setupDropdown() {
    const toggle = document.getElementById("notificationToggle");
    const dropdown = document.getElementById("notificationDropdown");

    if (!toggle || !dropdown) return;

    // Клик по кнопке
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggleDropdown();
    });

    // Клик вне dropdown - закрыть
    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target) && !toggle.contains(e.target)) {
        this.closeDropdown();
      }
    });

    // Позиционирование при открытии
    this.positionDropdown();
    window.addEventListener("resize", () => this.positionDropdown());
    window.addEventListener("scroll", () => this.positionDropdown());
  }

  toggleDropdown() {
    const dropdown = document.getElementById("notificationDropdown");
    if (dropdown.style.display === "none" || !dropdown.style.display) {
      this.openDropdown();
    } else {
      this.closeDropdown();
    }
  }

  openDropdown() {
    const dropdown = document.getElementById("notificationDropdown");
    dropdown.style.display = "flex";
    this.positionDropdown();
  }

  closeDropdown() {
    const dropdown = document.getElementById("notificationDropdown");
    dropdown.style.display = "none";
  }

  positionDropdown() {
    const toggle = document.getElementById("notificationToggle");
    const dropdown = document.getElementById("notificationDropdown");

    if (!toggle || !dropdown || dropdown.style.display === "none") return;

    const rect = toggle.getBoundingClientRect();
    const dropdownWidth = 360;
    const margin = 16; // отступ от края экрана

    // Позиция по вертикали
    dropdown.style.top = `${rect.bottom + 8}px`;

    // Позиция по горизонтали - адаптивная
    const isMobile = window.innerWidth < 768;

    if (isMobile) {
      // На мобильных - центрируем с отступами от краёв
      dropdown.style.left = `${margin}px`;
      dropdown.style.right = `${margin}px`;
      dropdown.style.width = "auto";
    } else {
      // На десктопе - справа от кнопки
      const rightPosition = window.innerWidth - rect.right;

      // Проверяем, не выходит ли за левый край
      if (rect.right - dropdownWidth < margin) {
        // Если выходит - выравниваем по левому краю с отступом
        dropdown.style.left = `${margin}px`;
        dropdown.style.right = "auto";
      } else {
        // Обычное выравнивание по правому краю кнопки
        dropdown.style.right = `${rightPosition}px`;
        dropdown.style.left = "auto";
      }
      dropdown.style.width = `${dropdownWidth}px`;
    }
  }
}

// Инициализация при загрузке страницы
document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("notificationBell")) {
    window.notificationManager = new NotificationManager();
    console.log("[Notifications] Manager initialized");
  }
});
