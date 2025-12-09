/**
 * Equipment List Handler
 * Обработчик для списка оборудования
 */

export class EquipmentListHandler {
  constructor(options = {}) {
    this.apiBase = options.apiBase || '/api/procurement';
    this.container = options.container || '#equipmentList';
    this.filterForm = options.filterForm || '#filterForm';
    this.searchInput = options.searchInput || '#searchInput';
    
    this.currentPage = 1;
    this.pageSize = 24;
    this.filters = {};
    
    this.init();
  }
  
  init() {
    this.bindEvents();
    this.loadEquipment();
    this.loadCategories();
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
          this.loadEquipment();
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
    
    // Кнопки быстрых фильтров по статусу
    document.querySelectorAll('[data-status-filter]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[data-status-filter]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        const status = btn.dataset.statusFilter;
        if (status === 'all') {
          delete this.filters.status;
        } else {
          this.filters.status = status;
        }
        this.currentPage = 1;
        this.loadEquipment();
      });
    });
    
    // Переключение вида
    document.querySelectorAll('[data-view]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('[data-view]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        const view = btn.dataset.view;
        const container = document.querySelector(this.container);
        if (container) {
          container.classList.toggle('list-view', view === 'list');
          container.classList.toggle('grid-view', view === 'grid');
        }
      });
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
    this.loadEquipment();
  }
  
  async loadCategories() {
    try {
      const resp = await fetch(`${this.apiBase}/categories/`);
      if (!resp.ok) return;
      
      const categories = await resp.json();
      const select = document.querySelector('#categoryFilter');
      
      if (select && categories.length) {
        select.innerHTML = '<option value="">Все категории</option>' +
          categories.map(cat => `<option value="${cat.id}">${this.escapeHtml(cat.name)}</option>`).join('');
      }
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  }
  
  async loadEquipment() {
    const container = document.querySelector(this.container);
    if (!container) return;
    
    container.innerHTML = `
      <div class="text-center py-5 col-12">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Загрузка...</span>
        </div>
      </div>
    `;
    
    try {
      let url = `${this.apiBase}/equipment/?page=${this.currentPage}&page_size=${this.pageSize}`;
      
      Object.entries(this.filters).forEach(([key, value]) => {
        url += `&${key}=${encodeURIComponent(value)}`;
      });
      
      const resp = await fetch(url);
      if (!resp.ok) throw new Error('Failed to load equipment');
      
      const data = await resp.json();
      const equipment = data.results || data;
      
      this.renderEquipment(equipment, data.count || equipment.length);
      
    } catch (error) {
      console.error('Error loading equipment:', error);
      container.innerHTML = `
        <div class="col-12">
          <div class="alert alert-danger">
            <i class="bi-exclamation-triangle me-2"></i>
            Ошибка загрузки оборудования
          </div>
        </div>
      `;
    }
  }
  
  renderEquipment(equipment, totalCount) {
    const container = document.querySelector(this.container);
    if (!container) return;
    
    // Сохраняем классы вида
    const isListView = container.classList.contains('list-view');
    
    if (equipment.length === 0) {
      container.innerHTML = `
        <div class="col-12 text-center py-5 text-muted">
          <i class="bi-inbox fs-1 d-block mb-3"></i>
          <h5>Оборудование не найдено</h5>
          <p class="mb-0">Попробуйте изменить параметры поиска</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = equipment.map(eq => this.renderEquipmentCard(eq)).join('');
    
    if (isListView) {
      container.classList.add('list-view');
    }
    
    // Pagination
    if (totalCount > this.pageSize) {
      const paginationWrapper = document.createElement('div');
      paginationWrapper.className = 'col-12';
      paginationWrapper.innerHTML = this.renderPagination(totalCount);
      container.appendChild(paginationWrapper);
      this.bindPaginationEvents();
    }
    
    // QR modals
    this.bindQRModals();
  }
  
  renderEquipmentCard(eq) {
    const icon = this.getEquipmentIcon(eq.name, eq.category_name);
    
    return `
      <div class="col-md-6 col-lg-4 col-xl-3">
        <div class="proc-equipment-card h-100">
          <div class="card-body">
            <div class="proc-equipment-icon mb-3">
              ${icon}
            </div>
            <h6 class="mb-1">${this.escapeHtml(eq.name)}</h6>
            <div class="mb-2">
              <code class="small">${eq.inventory_number}</code>
            </div>
            <div class="d-flex justify-content-between align-items-center">
              <span class="proc-eq-status ${this.getStatusClass(eq.status)}">
                ${this.getStatusLabel(eq.status)}
              </span>
              <small class="text-muted">${eq.category_name || ''}</small>
            </div>
          </div>
          <div class="card-footer bg-transparent border-top-0 pt-0">
            <div class="d-flex gap-2">
              <a href="/procurement/equipment/${eq.id}/" class="btn btn-outline-primary btn-sm flex-grow-1">
                <i class="bi-eye me-1"></i>Подробнее
              </a>
              <button class="btn btn-outline-secondary btn-sm" 
                      data-qr-url="/api/procurement/equipment/${eq.id}/qr_code/"
                      data-qr-name="${this.escapeHtml(eq.name)}"
                      title="QR-код">
                <i class="bi-qr-code"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getEquipmentIcon(name, category) {
    const text = (name + ' ' + (category || '')).toLowerCase();
    
    if (text.includes('ноутбук') || text.includes('laptop')) {
      return '<i class="bi-laptop"></i>';
    } else if (text.includes('монитор') || text.includes('display')) {
      return '<i class="bi-display"></i>';
    } else if (text.includes('принтер') || text.includes('printer')) {
      return '<i class="bi-printer"></i>';
    } else if (text.includes('телефон') || text.includes('phone')) {
      return '<i class="bi-phone"></i>';
    } else if (text.includes('сервер') || text.includes('server')) {
      return '<i class="bi-hdd-rack"></i>';
    } else if (text.includes('клавиатур') || text.includes('keyboard')) {
      return '<i class="bi-keyboard"></i>';
    } else if (text.includes('мышь') || text.includes('mouse')) {
      return '<i class="bi-mouse"></i>';
    } else if (text.includes('роутер') || text.includes('router') || text.includes('свитч') || text.includes('switch')) {
      return '<i class="bi-router"></i>';
    }
    return '<i class="bi-pc-display-horizontal"></i>';
  }
  
  bindQRModals() {
    document.querySelectorAll('[data-qr-url]').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = btn.dataset.qrUrl;
        const name = btn.dataset.qrName;
        this.showQRModal(url, name);
      });
    });
  }
  
  showQRModal(qrUrl, name) {
    // Удаляем существующую модалку
    document.querySelector('#qrModal')?.remove();
    
    const modal = document.createElement('div');
    modal.id = 'qrModal';
    modal.className = 'modal fade';
    modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered modal-sm">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">QR-код</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body text-center">
            <img src="${qrUrl}" alt="QR Code" class="img-fluid mb-2" style="max-width: 200px;">
            <p class="small text-muted mb-0">${name}</p>
          </div>
          <div class="modal-footer justify-content-center">
            <a href="${qrUrl}" download class="btn btn-outline-primary btn-sm">
              <i class="bi-download me-1"></i>Скачать
            </a>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
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
          this.loadEquipment();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });
    });
  }
  
  /**
   * Вспомогательные методы
   */
  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }
  
  getStatusClass(status) {
    const classes = {
      'in_stock': 'in-stock',
      'in_use': 'in-use',
      'maintenance': 'maintenance',
      'retired': 'retired'
    };
    return classes[status] || '';
  }
  
  getStatusLabel(status) {
    const labels = {
      'in_stock': 'На складе',
      'in_use': 'В использовании',
      'maintenance': 'Обслуживание',
      'retired': 'Списано'
    };
    return labels[status] || status;
  }
}

// Автоматическая инициализация
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('#equipmentList')) {
    window.equipmentList = new EquipmentListHandler();
  }
});

export default EquipmentListHandler;
