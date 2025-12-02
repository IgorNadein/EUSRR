/**
 * RecipientPicker - компонент для выбора получателей заявления
 * Поддерживает выбор:
 * - Нескольких отделов
 * - Основных получателей (recipients)
 * - Пользователей в копии (CC)
 * - Флаг "Отправить всем сотрудникам отделов"
 */

export class RecipientPicker {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      apiUsersUrl: '/api/v1/employees/',
      apiDepartmentsUrl: '/api/v1/departments/',
      onChange: null,
      ...options
    };

    this.state = {
      departments: [],
      recipients: [],
      ccUsers: [],
      sendToAllDepartment: false,
      loading: false
    };

    this.users = [];
    this.departments = [];
    
    this.init();
  }

  async init() {
    await this.loadData();
    this.render();
    this.attachEvents();
  }

  async loadData() {
    this.state.loading = true;
    try {
      const [usersRes, deptsRes] = await Promise.all([
        fetch(this.options.apiUsersUrl),
        fetch(this.options.apiDepartmentsUrl)
      ]);

      if (usersRes.ok) {
        const usersData = await usersRes.json();
        this.users = usersData.results || usersData;
      }

      if (deptsRes.ok) {
        const deptsData = await deptsRes.json();
        this.departments = deptsData.results || deptsData;
      }
    } catch (error) {
      console.error('RecipientPicker: Failed to load data', error);
    } finally {
      this.state.loading = false;
    }
  }

  render() {
    this.container.innerHTML = `
      <div class="recipient-picker">
        <!-- Отделы -->
        <div class="mb-3">
          <label class="form-label">
            <i class="bi-building"></i> Отделы
            <span class="text-muted small">(можно выбрать несколько)</span>
          </label>
          <select class="form-select" id="recipientDepts" multiple size="3">
            ${this.departments.map(dept => `
              <option value="${dept.id}" ${this.state.departments.includes(dept.id) ? 'selected' : ''}>
                ${dept.name}
              </option>
            `).join('')}
          </select>
          <div class="form-text">
            Заявление будет видно сотрудникам отделов с правами обработки
          </div>
        </div>

        <!-- Флаг: всем сотрудникам -->
        <div class="mb-3">
          <div class="form-check">
            <input class="form-check-input" type="checkbox" id="sendToAllDept"
                   ${this.state.sendToAllDepartment ? 'checked' : ''}>
            <label class="form-check-label" for="sendToAllDept">
              <i class="bi-people-fill"></i> Отправить всем сотрудникам выбранных отделов
            </label>
          </div>
          <div class="form-text ms-4">
            Все активные сотрудники выбранных отделов получат уведомление и доступ к заявлению
          </div>
        </div>

        <!-- Основные получатели -->
        <div class="mb-3" id="recipientsBlock">
          <label class="form-label">
            <i class="bi-person-check"></i> Основные получатели
            <span class="text-muted small">(опционально)</span>
          </label>
          <div class="recipient-list mb-2" id="recipientsList">
            ${this.renderSelectedUsers(this.state.recipients, 'recipient')}
          </div>
          <select class="form-select" id="recipientsSelect">
            <option value="">Добавить получателя...</option>
            ${this.getAvailableUsers('recipients').map(user => `
              <option value="${user.id}">
                ${user.last_name} ${user.first_name}${user.patronymic ? ' ' + user.patronymic : ''}
                ${user.position ? ` - ${user.position}` : ''}
              </option>
            `).join('')}
          </select>
          <div class="form-text">
            Получат уведомление и смогут работать с заявлением
          </div>
        </div>

        <!-- Пользователи в копии -->
        <div class="mb-3">
          <label class="form-label">
            <i class="bi-person-plus"></i> В копии (CC)
            <span class="text-muted small">(опционально)</span>
          </label>
          <div class="recipient-list mb-2" id="ccList">
            ${this.renderSelectedUsers(this.state.ccUsers, 'cc')}
          </div>
          <select class="form-select" id="ccSelect">
            <option value="">Добавить в копию...</option>
            ${this.getAvailableUsers('cc').map(user => `
              <option value="${user.id}">
                ${user.last_name} ${user.first_name}${user.patronymic ? ' ' + user.patronymic : ''}
                ${user.position ? ` - ${user.position}` : ''}
              </option>
            `).join('')}
          </select>
          <div class="form-text">
            Получат уведомление, но не смогут изменять статус заявления
          </div>
        </div>

        ${this.state.sendToAllDepartment && this.state.recipients.length > 0 ? `
          <div class="alert alert-warning small">
            <i class="bi-exclamation-triangle"></i>
            Указаны и конкретные получатели, и флаг "всем сотрудникам". 
            Уведомления получат все сотрудники отделов + дополнительные получатели.
          </div>
        ` : ''}
      </div>
    `;
  }

  renderSelectedUsers(userIds, type) {
    if (!userIds || userIds.length === 0) {
      return '<div class="text-muted small">Не выбрано</div>';
    }

    return userIds.map(id => {
      const user = this.users.find(u => u.id === id);
      if (!user) return '';

      return `
        <div class="badge bg-primary-subtle text-primary-emphasis border border-primary-subtle me-1 mb-1">
          ${user.last_name} ${user.first_name}
          <button type="button" class="btn-close btn-close-sm ms-1" 
                  data-action="remove-${type}" data-user-id="${id}" 
                  aria-label="Удалить" style="font-size: 0.7em;"></button>
        </div>
      `;
    }).join('');
  }

  getAvailableUsers(type) {
    // Исключаем уже выбранных пользователей
    const excludeIds = [
      ...this.state.recipients,
      ...this.state.ccUsers
    ];

    return this.users.filter(u => !excludeIds.includes(u.id));
  }

  attachEvents() {
    // Выбор отделов
    const deptsSelect = this.container.querySelector('#recipientDepts');
    if (deptsSelect) {
      deptsSelect.addEventListener('change', (e) => {
        this.state.departments = Array.from(e.target.selectedOptions).map(o => parseInt(o.value));
        this.triggerChange();
      });
    }

    // Флаг "всем сотрудникам"
    const sendToAllCheckbox = this.container.querySelector('#sendToAllDept');
    if (sendToAllCheckbox) {
      sendToAllCheckbox.addEventListener('change', (e) => {
        this.state.sendToAllDepartment = e.target.checked;
        
        // Если включен флаг, отключаем возможность выбора конкретных получателей
        const recipientsBlock = this.container.querySelector('#recipientsBlock');
        if (recipientsBlock) {
          if (e.target.checked) {
            recipientsBlock.style.opacity = '0.6';
          } else {
            recipientsBlock.style.opacity = '1';
          }
        }
        
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    }

    // Добавление основного получателя
    const recipientsSelect = this.container.querySelector('#recipientsSelect');
    if (recipientsSelect) {
      recipientsSelect.addEventListener('change', (e) => {
        const userId = parseInt(e.target.value);
        if (userId && !this.state.recipients.includes(userId)) {
          this.state.recipients.push(userId);
          this.render();
          this.attachEvents();
          this.triggerChange();
        }
      });
    }

    // Добавление в копию
    const ccSelect = this.container.querySelector('#ccSelect');
    if (ccSelect) {
      ccSelect.addEventListener('change', (e) => {
        const userId = parseInt(e.target.value);
        if (userId && !this.state.ccUsers.includes(userId)) {
          this.state.ccUsers.push(userId);
          this.render();
          this.attachEvents();
          this.triggerChange();
        }
      });
    }

    // Удаление получателя
    this.container.querySelectorAll('[data-action="remove-recipient"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const userId = parseInt(e.target.dataset.userId);
        this.state.recipients = this.state.recipients.filter(id => id !== userId);
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    });

    // Удаление CC
    this.container.querySelectorAll('[data-action="remove-cc"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const userId = parseInt(e.target.dataset.userId);
        this.state.ccUsers = this.state.ccUsers.filter(id => id !== userId);
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    });
  }

  triggerChange() {
    if (this.options.onChange) {
      this.options.onChange(this.getValues());
    }
  }

  getValues() {
    return {
      department_ids: this.state.departments,
      recipient_ids: this.state.recipients,
      cc_user_ids: this.state.ccUsers,
      sent_to_all_department: this.state.sendToAllDepartment
    };
  }

  setValues(data) {
    if (data.department_ids) {
      this.state.departments = Array.isArray(data.department_ids) 
        ? data.department_ids 
        : [data.department_ids];
    }
    if (data.recipient_ids) {
      this.state.recipients = Array.isArray(data.recipient_ids)
        ? data.recipient_ids
        : [data.recipient_ids];
    }
    if (data.cc_user_ids) {
      this.state.ccUsers = Array.isArray(data.cc_user_ids)
        ? data.cc_user_ids
        : [data.cc_user_ids];
    }
    if (data.sent_to_all_department !== undefined) {
      this.state.sendToAllDepartment = data.sent_to_all_department;
    }

    this.render();
    this.attachEvents();
  }

  reset() {
    this.state.departments = [];
    this.state.recipients = [];
    this.state.ccUsers = [];
    this.state.sendToAllDepartment = false;
    this.render();
    this.attachEvents();
  }

  destroy() {
    this.container.innerHTML = '';
  }
}
