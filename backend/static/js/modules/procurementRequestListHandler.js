/**
 * Procurement Request List Handler
 * Обработчик для списка заявок на закупку
 */

export class ProcurementRequestListHandler {
  constructor(options = {}) {
    this.apiBase = options.apiBase || '/api/procurement';
    this.container = options.container || '#requestsList';
    this.filterForm = options.filterForm || '#filterForm';
    this.searchInput = options.searchInput || '#searchInput';
    this.createForm = options.createForm || '#createRequestForm';
    this.scope = options.scope || 'all'; // 'all', 'my', 'pending'
    
    this.currentPage = 1;
    this.pageSize = 20;
    this.filters = {};
    
    this.init();
  }
  
  init() {
    this.bindEvents();
    this.loadRequests();
  }
  
  bindEvents() {
    // Поиск
    const searchInput = document.querySelector(this.searchInput);
    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          this.filters.search = e.target.value;
          this.currentPage = 1;
          this.loadRequests();
        }, 300);
      });
    }
    
    // Фильтры
    const filterForm = document.querySelector(this.filterForm);
    if (filterForm) {
      filterForm.addEventListener('change', () => {
        this.applyFilters();
      });
    }
    
    // Табы scope
    document.querySelectorAll('[data-scope]').forEach(tab => {
      tab.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[data-scope]').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.scope = tab.dataset.scope;
        this.currentPage = 1;
        this.loadRequests();
      });
    });
    
    // Форма создания заявки
    const createForm = document.querySelector(this.createForm);
    if (createForm) {
      createForm.addEventListener('submit', (e) => this.handleCreate(e));
    }
    
    // Кнопка добавления позиции
    document.querySelector('#addItemBtn')?.addEventListener('click', () => {
      this.addItemRow();
    });
  }
  
  applyFilters() {
    const form = document.querySelector(this.filterForm);
    if (!form) return;
    
    const formData = new FormData(form);
    this.filters = {};
    
    for (const [key, value] of formData.entries()) {
      if (value) {
        this.filters[key] = value;
      }
    }
    
    this.currentPage = 1;
    this.loadRequests();
  }
  
  async loadRequests() {
    const container = document.querySelector(this.container);
    if (!container) return;
    
    container.innerHTML = `
      <div class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Загрузка...</span>
        </div>
      </div>
    `;
    
    try {
      let url = `${this.apiBase}/requests/?page=${this.currentPage}&page_size=${this.pageSize}`;
      
      // Scope filters
      if (this.scope === 'my') {
        url += '&requester=me';
      } else if (this.scope === 'pending') {
        url += '&status=pending_approval';
      }
      
      // Additional filters
      Object.entries(this.filters).forEach(([key, value]) => {
        url += `&${key}=${encodeURIComponent(value)}`;
      });
      
      const resp = await fetch(url);
      if (!resp.ok) throw new Error('Failed to load requests');
      
      const data = await resp.json();
      const requests = data.results || data;
      
      this.renderRequests(requests, data.count || requests.length);
      
    } catch (error) {
      console.error('Error loading requests:', error);
      container.innerHTML = `
        <div class="alert alert-danger">
          <i class="bi-exclamation-triangle me-2"></i>
          Ошибка загрузки заявок
        </div>
      `;
    }
  }
  
  renderRequests(requests, totalCount) {
    const container = document.querySelector(this.container);
    if (!container) return;
    
    if (requests.length === 0) {
      container.innerHTML = `
        <div class="text-center py-5 text-muted">
          <i class="bi-inbox fs-1 d-block mb-3"></i>
          <h5>Заявок не найдено</h5>
          <p class="mb-0">Создайте новую заявку на закупку</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = requests.map(req => this.renderRequestCard(req)).join('');
    
    // Pagination
    if (totalCount > this.pageSize) {
      container.innerHTML += this.renderPagination(totalCount);
      this.bindPaginationEvents();
    }
  }
  
  renderRequestCard(req) {
    const urgencyClass = req.is_urgent ? 'border-danger' : '';
    const urgencyBadge = req.is_urgent ? 
      '<span class="badge bg-danger me-2"><i class="bi-lightning-fill"></i> Срочно</span>' : '';
    
    return `
      <a href="/procurement/requests/${req.id}/" class="proc-request-card ${urgencyClass}">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-start">
            <div class="flex-grow-1">
              <h5 class="mb-1">
                ${urgencyBadge}
                ${this.escapeHtml(req.title)}
              </h5>
              <p class="text-muted mb-2 small">
                <i class="bi-person me-1"></i>${req.requester_name || 'Неизвестно'}
                <span class="mx-2">•</span>
                <i class="bi-calendar me-1"></i>${this.formatDate(req.created_at)}
                ${req.items_count ? `<span class="mx-2">•</span><i class="bi-list me-1"></i>${req.items_count} поз.` : ''}
              </p>
              ${req.description ? `<p class="mb-0 small text-truncate" style="max-width: 400px;">${this.escapeHtml(req.description)}</p>` : ''}
            </div>
            <div class="text-end">
              <span class="proc-status ${this.getStatusClass(req.status)} mb-2 d-inline-block">
                ${this.getStatusLabel(req.status)}
              </span>
              ${req.total_cost ? `<div class="fw-bold">${this.formatCurrency(req.total_cost)}</div>` : ''}
            </div>
          </div>
        </div>
      </a>
    `;
  }
  
  renderPagination(totalCount) {
    const totalPages = Math.ceil(totalCount / this.pageSize);
    let html = '<nav class="mt-4"><ul class="pagination justify-content-center">';
    
    // Previous
    html += `
      <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${this.currentPage - 1}">
          <i class="bi-chevron-left"></i>
        </a>
      </li>
    `;
    
    // Pages
    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
        html += `
          <li class="page-item ${i === this.currentPage ? 'active' : ''}">
            <a class="page-link" href="#" data-page="${i}">${i}</a>
          </li>
        `;
      } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
        html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
      }
    }
    
    // Next
    html += `
      <li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${this.currentPage + 1}">
          <i class="bi-chevron-right"></i>
        </a>
      </li>
    `;
    
    html += '</ul></nav>';
    return html;
  }
  
  bindPaginationEvents() {
    document.querySelectorAll('.pagination .page-link[data-page]').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = parseInt(link.dataset.page);
        if (page && page !== this.currentPage) {
          this.currentPage = page;
          this.loadRequests();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });
    });
  }
  
  async handleCreate(e) {
    e.preventDefault();
    
    const form = e.target;
    const submitBtn = form.querySelector('[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Сохранение...';
    
    try {
      // Собираем данные
      const formData = {
        title: form.querySelector('[name="title"]').value,
        description: form.querySelector('[name="description"]')?.value || '',
        is_urgent: form.querySelector('[name="is_urgent"]')?.checked || false,
        items: this.collectItems(form)
      };
      
      const resp = await fetch(`${this.apiBase}/requests/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCsrfToken()
        },
        body: JSON.stringify(formData)
      });
      
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || JSON.stringify(err));
      }
      
      const request = await resp.json();
      
      // Закрыть модалку и перейти к заявке
      const modal = bootstrap.Modal.getInstance(document.querySelector('#createModal'));
      modal?.hide();
      
      window.location.href = `/procurement/requests/${request.id}/`;
      
    } catch (error) {
      console.error('Error creating request:', error);
      alert('Ошибка создания заявки: ' + error.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalText;
    }
  }
  
  collectItems(form) {
    const items = [];
    form.querySelectorAll('.item-row').forEach(row => {
      const name = row.querySelector('[name="item_name"]')?.value;
      const quantity = parseInt(row.querySelector('[name="item_quantity"]')?.value) || 1;
      const price = parseFloat(row.querySelector('[name="item_price"]')?.value) || 0;
      
      if (name) {
        items.push({ name, quantity, estimated_price: price });
      }
    });
    return items;
  }
  
  addItemRow() {
    const container = document.querySelector('#itemsContainer');
    if (!container) return;
    
    const index = container.querySelectorAll('.item-row').length;
    const row = document.createElement('div');
    row.className = 'item-row row g-2 mb-2';
    row.innerHTML = `
      <div class="col-6">
        <input type="text" name="item_name" class="form-control form-control-sm" 
               placeholder="Наименование" required>
      </div>
      <div class="col-2">
        <input type="number" name="item_quantity" class="form-control form-control-sm" 
               value="1" min="1" placeholder="Кол-во">
      </div>
      <div class="col-3">
        <input type="number" name="item_price" class="form-control form-control-sm" 
               min="0" step="0.01" placeholder="Цена">
      </div>
      <div class="col-1">
        <button type="button" class="btn btn-outline-danger btn-sm w-100" onclick="this.closest('.item-row').remove()">
          <i class="bi-x"></i>
        </button>
      </div>
    `;
    container.appendChild(row);
  }
  
  /**
   * Вспомогательные методы
   */
  getCsrfToken() {
    return document.querySelector('[name="csrfmiddlewaretoken"]')?.value || 
           document.querySelector('meta[name="csrf-token"]')?.content || '';
  }
  
  formatCurrency(amount) {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      minimumFractionDigits: 0
    }).format(amount);
  }
  
  formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('ru-RU');
  }
  
  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }
  
  getStatusClass(status) {
    const classes = {
      'draft': 'draft',
      'pending_approval': 'pending',
      'approved': 'approved',
      'rejected': 'rejected',
      'ordered': 'ordered',
      'delivered': 'delivered'
    };
    return classes[status] || '';
  }
  
  getStatusLabel(status) {
    const labels = {
      'draft': 'Черновик',
      'pending_approval': 'На согласовании',
      'approved': 'Одобрена',
      'rejected': 'Отклонена',
      'ordered': 'Заказано',
      'delivered': 'Получено'
    };
    return labels[status] || status;
  }
}

// Автоматическая инициализация
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('#requestsList')) {
    const scopeTab = document.querySelector('[data-scope].active');
    window.procurementRequestList = new ProcurementRequestListHandler({
      scope: scopeTab?.dataset.scope || 'all'
    });
  }
});

export default ProcurementRequestListHandler;
