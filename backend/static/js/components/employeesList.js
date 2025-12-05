/**
 * Модуль для загрузки и отображения списка сотрудников
 * Использует API для получения данных с корректными глобальными URL
 */

export class EmployeesList {
  constructor(options = {}) {
    this.containerId = options.containerId || 'empList';
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      console.warn(`Container #${this.containerId} not found`);
      return;
    }
    
    this.apiUrl = '/api/v1/employees/';
    this.employees = [];
    this.loading = false;
    this.hasMore = true;
    this.nextUrl = null;
    this.totalCount = 0;
    
    // Параметры из URL (без page - используем бесконечную прокрутку)
    const urlParams = new URLSearchParams(window.location.search);
    this.params = {
      ordering: urlParams.get('o') || 'last_name',
      search: urlParams.get('q') || '',
      department: urlParams.get('department') || '',
      position: urlParams.get('position') || '',
      is_active: urlParams.get('is_active') || ''
    };
    
    // Intersection Observer для бесконечной прокрутки
    this.observerTarget = null;
    this.observer = null;
  }

  /**
   * Инициализация - загрузка и рендеринг
   */
  async init() {
    if (!this.container) return;
    
    // Устанавливаем hasMore в true перед первой загрузкой
    this.hasMore = true;
    
    try {
      await this.loadEmployees(false); // append = false
      this.render(false); // append = false
      this.updateCount();
      this.setupInfiniteScroll();
    } catch (error) {
      console.error('Failed to load employees:', error);
      this.renderError();
    }
  }
  
  /**
   * Обновление счетчика сотрудников в заголовке страницы
   */
  updateCount() {
    const countElement = document.querySelector('.count-value');
    if (countElement && this.totalCount !== undefined) {
      countElement.textContent = this.totalCount;
    }
  }
  
  /**
   * Настройка Intersection Observer для бесконечной прокрутки
   */
  setupInfiniteScroll() {
    if (!this.observerTarget) return;
    
    // Создаем observer
    this.observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting && this.hasMore && !this.loading) {
            this.loadMore();
          }
        });
      },
      {
        root: null,
        rootMargin: '100px', // Загружаем за 100px до конца
        threshold: 0.01
      }
    );
    
    // Наблюдаем за observer target
    this.observer.observe(this.observerTarget);
  }
  
  /**
   * Загрузка следующей порции сотрудников
   */
  async loadMore() {
    try {
      await this.loadEmployees(true); // append = true
      this.render(true); // append = true
      this.updateCount();
    } catch (error) {
      console.error('Failed to load more employees:', error);
    }
  }

  /**
   * Загрузка сотрудников через API
   */
  async loadEmployees(append = false) {
    // Проверяем hasMore только при подгрузке
    if (this.loading || (append && !this.hasMore)) return;
    this.loading = true;
    
    this.showLoadingSpinner();

    try {
      // Используем nextUrl если это подгрузка, иначе строим URL с параметрами
      let url;
      if (append && this.nextUrl) {
        url = this.nextUrl;
      } else {
        const params = new URLSearchParams();
        Object.entries(this.params).forEach(([key, value]) => {
          if (value) params.append(key, value);
        });
        url = `${this.apiUrl}?${params}`;
      }

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const newEmployees = data.results || data;
      
      // Сохраняем метаданные
      this.totalCount = data.count || newEmployees.length;
      this.nextUrl = data.next || null;
      this.hasMore = !!this.nextUrl;
      
      if (append) {
        // Добавляем к существующим
        this.employees = [...this.employees, ...newEmployees];
      } else {
        // Заменяем
        this.employees = newEmployees;
      }
      
      this.loading = false;
      this.hideLoadingSpinner();
    } catch (error) {
      this.loading = false;
      this.hideLoadingSpinner();
      throw error;
    }
  }
  
  /**
   * Показать спиннер загрузки
   */
  showLoadingSpinner() {
    const existing = this.container.querySelector('.loading-spinner');
    if (existing) return;
    
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner text-center py-4';
    spinner.innerHTML = `
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    `;
    this.container.appendChild(spinner);
  }
  
  /**
   * Скрыть спиннер загрузки
   */
  hideLoadingSpinner() {
    const spinner = this.container.querySelector('.loading-spinner');
    if (spinner) {
      spinner.remove();
    }
  }

  /**
   * Рендеринг списка сотрудников
   */
  render(append = false) {
    if (this.employees.length === 0 && !append) {
      this.container.innerHTML = '<div class="alert alert-info shadow-sm">Нет сотрудников.</div>';
      return;
    }

    const itemsHtml = this.employees.map(emp => this.createEmployeeCard(emp)).join('');
    
    if (append) {
      // Удаляем observer target перед добавлением
      if (this.observerTarget && this.observerTarget.parentNode) {
        this.observerTarget.remove();
      }
      // Добавляем новые карточки
      this.container.insertAdjacentHTML('beforeend', itemsHtml);
      // Возвращаем observer target обратно
      if (this.observerTarget) {
        this.container.appendChild(this.observerTarget);
      }
    } else {
      this.container.innerHTML = itemsHtml;
      // Создаем observer target при первой загрузке
      if (this.hasMore && !this.observerTarget) {
        this.observerTarget = document.createElement('div');
        this.observerTarget.className = 'load-more-trigger';
        this.observerTarget.style.height = '1px';
        this.container.appendChild(this.observerTarget);
      }
    }
  }

  /**
   * Создание карточки сотрудника
   */
  createEmployeeCard(emp) {
    const fullName = this.getFullName(emp);
    const position = this.getPosition(emp);
    const departments = this.getDepartments(emp);
    const avatar = this.getAvatarHtml(emp);
    
    return `
      <article class="emp-row list-row"
               data-name="${this.escapeHtml(fullName + ' ' + position)}"
               data-depts="${this.escapeHtml(departments)}">
        <header class="card-header">
          <div class="card-icon">
            ${avatar}
          </div>

          <div class="card-meta flex-grow-1">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              ${emp.id ? 
                `<a href="/employees/${emp.id}/" class="card-title text-decoration-none">${this.escapeHtml(fullName)}</a>` :
                `<span class="card-title">${this.escapeHtml(fullName)}</span>`
              }
              ${position ? `<span class="emp-pos">— ${this.escapeHtml(position)}</span>` : ''}
            </div>
            ${departments ? `<div class="card-subtitle">${departments}</div>` : ''}
          </div>

          <div class="ms-auto d-flex align-items-center gap-2">
            ${this.getActionButtons(emp)}
          </div>
        </header>

        <div class="card-body"></div>
      </article>
    `;
  }

  /**
   * Получение полного имени
   */
  getFullName(emp) {
    let name = `${emp.last_name || ''} ${emp.first_name || ''}`.trim();
    if (emp.patronymic) {
      name += ` ${emp.patronymic}`;
    }
    return name || 'Сотрудник';
  }

  /**
   * Получение должности
   */
  getPosition(emp) {
    if (emp.position?.name) {
      return emp.position.name;
    } else if (emp.position_label) {
      return emp.position_label;
    } else if (emp.position) {
      return `Должность #${emp.position}`;
    }
    return '';
  }

  /**
   * Получение отделов
   */
  getDepartments(emp) {
    if (!emp.departments || emp.departments.length === 0) {
      return '';
    }
    
    return emp.departments
      .filter(d => d.name)
      .map(d => {
        if (d.id) {
          return `<a href="/employees/departments/${d.id}/">${this.escapeHtml(d.name)}</a>`;
        }
        return this.escapeHtml(d.name);
      })
      .join(', ');
  }

  /**
   * Получение HTML аватара
   */
  getAvatarHtml(emp) {
    if (emp.avatar) {
      return `<img src="${emp.avatar}" alt="${this.escapeHtml(this.getFullName(emp))}">`;
    } else {
      return '<i class="bi-person"></i>';
    }
  }

  /**
   * Получение кнопок действий
   */
  getActionButtons(emp) {
    if (!emp.id) return '';
    
    // Получаем ID текущего пользователя из глобальной переменной или data-атрибута
    const currentUserId = window.currentUserId || document.body.dataset.userId;
    if (currentUserId && String(currentUserId) === String(emp.id)) {
      return ''; // Не показываем кнопки для себя
    }

    return `
      <a href="/communications/chats/private/${emp.id}/"
         class="btn btn-ghost action-btn" title="Чат">
        <i class="bi-chat-dots"></i><span class="d-none d-sm-inline ms-1">Чат</span>
      </a>
    `;
  }

  /**
   * Экранирование HTML
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Рендеринг ошибки
   */
  renderError() {
    this.container.innerHTML = `
      <div class="alert alert-danger shadow-sm">
        Не удалось загрузить список сотрудников. Попробуйте обновить страницу.
      </div>
    `;
  }
}

/**
 * Инициализация списка сотрудников
 */
export function initEmployeesList(options) {
  const list = new EmployeesList(options);
  list.init();
  return list;
}
