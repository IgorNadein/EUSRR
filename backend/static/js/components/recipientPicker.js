/**
 * RecipientPicker - компонент для выбора получателей заявления в стиле email-клиента
 * Использует Token/Chip input с autocomplete для удобного выбора получателей
 * 
 * Особенности:
 * - Autocomplete с поиском по имени/email
 * - Chip-based UI (как в Gmail)
 * - Разделение To/CC (как в почтовых клиентах)
 * - Выбор отделов через dropdown
 * - Опция "Всем сотрудникам отделов"
 */

export class RecipientPicker {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      apiUsersUrl: '/api/v1/employees/',
      apiDepartmentsUrl: '/api/v1/departments/',
      placeholder: 'Начните вводить имя или выберите из списка...',
      showCC: true,
      showDepartments: true,
      onChange: null,
      ...options
    };

    this.state = {
      departments: [],
      recipients: [],
      ccUsers: [],
      sendToAllDepartment: false,
      showCC: false,
      showDepartments: false,  // Новый флаг для показа строки отделов
      loading: false,
      searchQuery: '',
      searchQueryCC: '',
      showDropdown: false,
      showDropdownCC: false
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
      <div class="recipient-picker-email">
        
        <!-- Отделы (показываются по кнопке) -->
        ${this.state.showDepartments ? `
          <div class="recipient-row">
            <label class="recipient-label">
              <i class="bi-building"></i>
              <span>Отделы:</span>
            </label>
            <div class="recipient-field">
              <div class="recipient-chips" id="departmentChips">
                ${this.renderDepartmentChips()}
              </div>
              <div class="dropdown d-inline-block">
                <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                        data-bs-toggle="dropdown">
                  Выбрать отдел
                </button>
                <div class="dropdown-menu" id="departmentDropdown">
                  ${this.departments.map(dept => `
                    <div class="dropdown-item" data-action="toggle-dept" data-dept-id="${dept.id}">
                      <input type="checkbox" class="form-check-input me-2" 
                             ${this.state.departments.includes(dept.id) ? 'checked' : ''}>
                      ${dept.name}
                    </div>
                  `).join('')}
                </div>
              </div>
              
              <!-- Флаг: всем в отделе (только если выбран хотя бы 1 отдел) -->
              ${this.state.departments.length > 0 ? `
                <div class="form-check form-check-inline ms-3">
                  <input class="form-check-input" type="checkbox" id="sendToAllDept"
                         ${this.state.sendToAllDepartment ? 'checked' : ''}>
                  <label class="form-check-label text-muted small" for="sendToAllDept">
                    <i class="bi-people-fill"></i> Всем в отделе${this.state.departments.length > 1 ? 'ах' : ''}
                  </label>
                </div>
              ` : ''}
            </div>
          </div>
        ` : ''}

        <!-- Основные получатели (To:) -->
        <div class="recipient-row">
          <label class="recipient-label">
            <i class="bi-person-check"></i>
            <span>Кому:</span>
          </label>
          <div class="recipient-field">
            <div class="recipient-input-wrapper" id="recipientsWrapper">
              ${this.renderUserChips(this.state.recipients)}
              <input type="text" 
                     class="recipient-input" 
                     id="recipientInput"
                     placeholder="${this.options.placeholder}"
                     autocomplete="off">
              <div class="recipient-dropdown" id="recipientDropdown" style="display: none;">
                ${this.renderUserDropdown(this.state.recipients, 'recipient')}
              </div>
            </div>
            <div class="d-flex gap-2 ms-2">
              ${!this.state.showCC && this.options.showCC ? `
                <button type="button" class="btn btn-sm btn-link text-decoration-none p-0" 
                        id="showCCBtn">
                  + Копия
                </button>
              ` : ''}
              ${!this.state.showDepartments && this.options.showDepartments ? `
                <button type="button" class="btn btn-sm btn-link text-decoration-none p-0" 
                        id="showDepartmentsBtn">
                  + Отделы
                </button>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Копия (CC:) -->
        ${this.state.showCC && this.options.showCC ? `
          <div class="recipient-row">
            <label class="recipient-label">
              <i class="bi-person-plus"></i>
              <span>Копия:</span>
            </label>
            <div class="recipient-field">
              <div class="recipient-input-wrapper" id="ccWrapper">
                ${this.renderUserChips(this.state.ccUsers, true)}
                <input type="text" 
                       class="recipient-input" 
                       id="ccInput"
                       placeholder="Добавить в копию..."
                       autocomplete="off">
                <div class="recipient-dropdown" id="ccDropdown" style="display: none;">
                  ${this.renderUserDropdown(this.state.ccUsers, 'cc')}
                </div>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Подсказка -->
        ${this.state.sendToAllDepartment && this.state.departments.length > 0 ? `
          <div class="alert alert-info alert-sm">
            <i class="bi-info-circle"></i>
            <small>
              Заявление будет отправлено всем сотрудникам выбранных отделов
              ${this.state.recipients.length > 0 ? ' + указанным получателям' : ''}.
            </small>
          </div>
        ` : ''}
      </div>
    `;
  }

  renderDepartmentChips() {
    if (this.state.departments.length === 0) {
      return '<span class="text-muted small">Не выбрано</span>';
    }

    return this.state.departments.map(id => {
      const dept = this.departments.find(d => d.id === id);
      if (!dept) return '';

      return `
        <span class="recipient-chip">
          ${dept.name}
          <button type="button" class="chip-remove" data-action="remove-dept" data-dept-id="${id}">
            <i class="bi-x"></i>
          </button>
        </span>
      `;
    }).join('');
  }

  renderUserChips(userIds, isCC = false) {
    return userIds.map(id => {
      const user = this.users.find(u => u.id === id);
      if (!user) return '';

      const displayName = `${user.last_name} ${user.first_name}`;
      
      return `
        <span class="recipient-chip ${isCC ? 'chip-cc' : ''}">
          ${displayName}
          <button type="button" class="chip-remove" 
                  data-action="remove-${isCC ? 'cc' : 'recipient'}" 
                  data-user-id="${id}">
            <i class="bi-x"></i>
          </button>
        </span>
      `;
    }).join('');
  }

  renderUserDropdown(excludeIds, type) {
    const query = type === 'cc' ? this.state.searchQueryCC : this.state.searchQuery;
    const allExcludeIds = [...this.state.recipients, ...this.state.ccUsers];
    
    let filteredUsers = this.users.filter(u => !allExcludeIds.includes(u.id));

    // Фильтрация по запросу
    if (query) {
      const lowerQuery = query.toLowerCase();
      filteredUsers = filteredUsers.filter(u => {
        const fullName = `${u.last_name} ${u.first_name} ${u.patronymic || ''}`.toLowerCase();
        const email = (u.email || '').toLowerCase();
        return fullName.includes(lowerQuery) || email.includes(lowerQuery);
      });
    }

    if (filteredUsers.length === 0) {
      return '<div class="dropdown-item-empty">Никого не найдено</div>';
    }

    // Ограничиваем до 10 результатов
    return filteredUsers.slice(0, 10).map(user => {
      const displayName = `${user.last_name} ${user.first_name}`;
      const subtitle = user.position || user.email || '';
      
      return `
        <div class="dropdown-item-user" data-action="add-${type}" data-user-id="${user.id}">
          <div class="user-avatar-small">${this.getInitials(user)}</div>
          <div class="user-info">
            <div class="user-name">${displayName}</div>
            ${subtitle ? `<div class="user-subtitle">${subtitle}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  getInitials(user) {
    const first = (user.first_name || '').charAt(0).toUpperCase();
    const last = (user.last_name || '').charAt(0).toUpperCase();
    return first + last || '?';
  }

  attachEvents() {
    // Показать CC
    const showCCBtn = this.container.querySelector('#showCCBtn');
    if (showCCBtn) {
      showCCBtn.addEventListener('click', () => {
        this.state.showCC = true;
        this.render();
        this.attachEvents();
        // Фокус на CC input
        setTimeout(() => {
          this.container.querySelector('#ccInput')?.focus();
        }, 100);
      });
    }

    // Показать Отделы
    const showDepartmentsBtn = this.container.querySelector('#showDepartmentsBtn');
    if (showDepartmentsBtn) {
      showDepartmentsBtn.addEventListener('click', () => {
        this.state.showDepartments = true;
        this.render();
        this.attachEvents();
      });
    }

    // Флаг "всем сотрудникам"
    const sendToAllCheckbox = this.container.querySelector('#sendToAllDept');
    if (sendToAllCheckbox) {
      sendToAllCheckbox.addEventListener('change', (e) => {
        this.state.sendToAllDepartment = e.target.checked;
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    }

    // Toggle отделов через dropdown
    this.container.querySelectorAll('[data-action="toggle-dept"]').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const deptId = parseInt(e.currentTarget.dataset.deptId);
        
        if (this.state.departments.includes(deptId)) {
          this.state.departments = this.state.departments.filter(id => id !== deptId);
        } else {
          this.state.departments.push(deptId);
        }
        
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    });

    // Удаление отдела через chip
    this.container.querySelectorAll('[data-action="remove-dept"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const deptId = parseInt(e.currentTarget.dataset.deptId);
        this.state.departments = this.state.departments.filter(id => id !== deptId);
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    });

    // Input для получателей с autocomplete
    const recipientInput = this.container.querySelector('#recipientInput');
    if (recipientInput) {
      recipientInput.addEventListener('input', (e) => {
        this.state.searchQuery = e.target.value;
        const dropdown = this.container.querySelector('#recipientDropdown');
        
        if (this.state.searchQuery.length > 0) {
          dropdown.innerHTML = this.renderUserDropdown(this.state.recipients, 'recipient');
          dropdown.style.display = 'block';
          this.state.showDropdown = true;
        } else {
          dropdown.style.display = 'none';
          this.state.showDropdown = false;
        }
        
        this.attachDropdownEvents();
      });

      // Показать dropdown при фокусе
      recipientInput.addEventListener('focus', () => {
        const dropdown = this.container.querySelector('#recipientDropdown');
        dropdown.innerHTML = this.renderUserDropdown(this.state.recipients, 'recipient');
        dropdown.style.display = 'block';
        this.state.showDropdown = true;
        this.attachDropdownEvents();
      });

      // Скрыть dropdown при потере фокуса (с задержкой для клика)
      recipientInput.addEventListener('blur', () => {
        setTimeout(() => {
          const dropdown = this.container.querySelector('#recipientDropdown');
          if (dropdown) {
            dropdown.style.display = 'none';
            this.state.showDropdown = false;
          }
        }, 200);
      });
    }

    // Input для CC с autocomplete
    const ccInput = this.container.querySelector('#ccInput');
    if (ccInput) {
      ccInput.addEventListener('input', (e) => {
        this.state.searchQueryCC = e.target.value;
        const dropdown = this.container.querySelector('#ccDropdown');
        
        if (this.state.searchQueryCC.length > 0) {
          dropdown.innerHTML = this.renderUserDropdown(this.state.ccUsers, 'cc');
          dropdown.style.display = 'block';
          this.state.showDropdownCC = true;
        } else {
          dropdown.style.display = 'none';
          this.state.showDropdownCC = false;
        }
        
        this.attachDropdownEvents();
      });

      ccInput.addEventListener('focus', () => {
        const dropdown = this.container.querySelector('#ccDropdown');
        dropdown.innerHTML = this.renderUserDropdown(this.state.ccUsers, 'cc');
        dropdown.style.display = 'block';
        this.state.showDropdownCC = true;
        this.attachDropdownEvents();
      });

      ccInput.addEventListener('blur', () => {
        setTimeout(() => {
          const dropdown = this.container.querySelector('#ccDropdown');
          if (dropdown) {
            dropdown.style.display = 'none';
            this.state.showDropdownCC = false;
          }
        }, 200);
      });
    }

    // Удаление получателей через chip
    this.container.querySelectorAll('[data-action="remove-recipient"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const userId = parseInt(e.currentTarget.dataset.userId);
        this.state.recipients = this.state.recipients.filter(id => id !== userId);
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    });

    // Удаление CC через chip
    this.container.querySelectorAll('[data-action="remove-cc"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const userId = parseInt(e.currentTarget.dataset.userId);
        this.state.ccUsers = this.state.ccUsers.filter(id => id !== userId);
        this.render();
        this.attachEvents();
        this.triggerChange();
      });
    });
  }

  attachDropdownEvents() {
    // Добавление получателя из dropdown
    this.container.querySelectorAll('[data-action="add-recipient"]').forEach(item => {
      item.addEventListener('click', () => {
        const userId = parseInt(item.dataset.userId);
        if (!this.state.recipients.includes(userId)) {
          this.state.recipients.push(userId);
          this.state.searchQuery = '';
          
          const input = this.container.querySelector('#recipientInput');
          if (input) input.value = '';
          
          this.render();
          this.attachEvents();
          this.triggerChange();
          
          // Возвращаем фокус
          setTimeout(() => {
            this.container.querySelector('#recipientInput')?.focus();
          }, 100);
        }
      });
    });

    // Добавление CC из dropdown
    this.container.querySelectorAll('[data-action="add-cc"]').forEach(item => {
      item.addEventListener('click', () => {
        const userId = parseInt(item.dataset.userId);
        if (!this.state.ccUsers.includes(userId)) {
          this.state.ccUsers.push(userId);
          this.state.searchQueryCC = '';
          
          const input = this.container.querySelector('#ccInput');
          if (input) input.value = '';
          
          this.render();
          this.attachEvents();
          this.triggerChange();
          
          // Возвращаем фокус
          setTimeout(() => {
            this.container.querySelector('#ccInput')?.focus();
          }, 100);
        }
      });
    });
  }

  triggerChange() {
    // Очищаем ошибку при любом изменении
    this.clearError();
    
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

  /**
   * Проверяет, заполнены ли получатели
   * @returns {boolean} true если есть получатели или отделы
   */
  validate() {
    const hasDepartments = this.state.departments.length > 0;
    const hasRecipients = this.state.recipients.length > 0;
    const isValid = hasDepartments || hasRecipients;
    
    if (!isValid) {
      this.setError('Укажите хотя бы одного получателя или отдел');
    } else {
      this.clearError();
    }
    
    return isValid;
  }

  /**
   * Устанавливает сообщение об ошибке
   * @param {string} message - Текст ошибки
   */
  setError(message) {
    this.clearError();
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback d-block';
    errorDiv.textContent = message;
    errorDiv.id = 'recipientPickerError';
    this.container.appendChild(errorDiv);
    this.container.classList.add('is-invalid');
  }

  /**
   * Убирает сообщение об ошибке
   */
  clearError() {
    const errorDiv = this.container.querySelector('#recipientPickerError');
    if (errorDiv) {
      errorDiv.remove();
    }
    this.container.classList.remove('is-invalid');
  }

  setValues(data) {
    if (data.department_ids) {
      this.state.departments = Array.isArray(data.department_ids) 
        ? data.department_ids 
        : [data.department_ids];
      // Если есть отделы - показываем строку отделов
      if (this.state.departments.length > 0) {
        this.state.showDepartments = true;
      }
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
      // Если есть CC - показываем строку CC
      if (this.state.ccUsers.length > 0) {
        this.state.showCC = true;
      }
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
    this.state.showCC = false;
    this.state.showDepartments = false;
    this.render();
    this.attachEvents();
  }

  destroy() {
    this.container.innerHTML = '';
  }
}
