/**
 * Procurement Dashboard Handler
 * Обработчик для главной страницы модуля закупок
 */

export class ProcurementDashboardHandler {
  constructor(options = {}) {
    this.apiBase = options.apiBase || '/api/procurement';
    this.statsContainer = options.statsContainer || '#procDashboardStats';
    this.recentRequestsContainer = options.recentRequestsContainer || '#recentRequests';
    this.recentEquipmentContainer = options.recentEquipmentContainer || '#recentEquipment';
    
    this.init();
  }
  
  async init() {
    await Promise.all([
      this.loadStats(),
      this.loadRecentRequests(),
      this.loadRecentEquipment()
    ]);
  }
  
  /**
   * Загрузка статистики
   */
  async loadStats() {
    try {
      const [requestsResp, equipmentResp] = await Promise.all([
        fetch(`${this.apiBase}/requests/?page_size=1000`),
        fetch(`${this.apiBase}/equipment/?page_size=1000`)
      ]);
      
      if (!requestsResp.ok || !equipmentResp.ok) return;
      
      const requestsData = await requestsResp.json();
      const equipmentData = await equipmentResp.json();
      
      const requests = requestsData.results || requestsData;
      const equipment = equipmentData.results || equipmentData;
      
      // Подсчёт статистики
      const stats = {
        totalRequests: requests.length,
        pendingRequests: requests.filter(r => r.status === 'pending_approval').length,
        approvedRequests: requests.filter(r => ['approved', 'ordered', 'delivered'].includes(r.status)).length,
        totalEquipment: equipment.length,
        inUseEquipment: equipment.filter(e => e.status === 'in_use').length,
        totalBudget: requests.reduce((sum, r) => sum + parseFloat(r.total_cost || 0), 0)
      };
      
      this.updateStatsDisplay(stats);
    } catch (error) {
      console.error('Error loading dashboard stats:', error);
    }
  }
  
  /**
   * Обновление отображения статистики
   */
  updateStatsDisplay(stats) {
    const container = document.querySelector(this.statsContainer);
    if (!container) return;
    
    const statsElements = {
      'totalRequests': stats.totalRequests,
      'pendingRequests': stats.pendingRequests,
      'approvedRequests': stats.approvedRequests,
      'totalEquipment': stats.totalEquipment,
      'inUseEquipment': stats.inUseEquipment,
      'totalBudget': this.formatCurrency(stats.totalBudget)
    };
    
    Object.entries(statsElements).forEach(([id, value]) => {
      const el = container.querySelector(`[data-stat="${id}"]`);
      if (el) el.textContent = value;
    });
  }
  
  /**
   * Загрузка последних заявок
   */
  async loadRecentRequests() {
    const container = document.querySelector(this.recentRequestsContainer);
    if (!container) return;
    
    try {
      const resp = await fetch(`${this.apiBase}/requests/?ordering=-created_at&page_size=5`);
      if (!resp.ok) return;
      
      const data = await resp.json();
      const requests = data.results || data;
      
      if (requests.length === 0) {
        container.innerHTML = `
          <div class="text-center py-4 text-muted">
            <i class="bi-inbox fs-3 d-block mb-2"></i>
            <p class="mb-0">Заявок пока нет</p>
          </div>
        `;
        return;
      }
      
      container.innerHTML = requests.map(req => `
        <a href="/procurement/requests/${req.id}/" class="list-group-item list-group-item-action">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <h6 class="mb-1">${this.escapeHtml(req.title)}</h6>
              <small class="text-muted">
                ${req.requester_name || 'Неизвестно'} • 
                ${this.formatDate(req.created_at)}
              </small>
            </div>
            <span class="proc-status ${this.getStatusClass(req.status)}">
              ${this.getStatusLabel(req.status)}
            </span>
          </div>
        </a>
      `).join('');
      
    } catch (error) {
      console.error('Error loading recent requests:', error);
    }
  }
  
  /**
   * Загрузка последнего оборудования
   */
  async loadRecentEquipment() {
    const container = document.querySelector(this.recentEquipmentContainer);
    if (!container) return;
    
    try {
      const resp = await fetch(`${this.apiBase}/equipment/?ordering=-id&page_size=5`);
      if (!resp.ok) return;
      
      const data = await resp.json();
      const equipment = data.results || data;
      
      if (equipment.length === 0) {
        container.innerHTML = `
          <div class="text-center py-4 text-muted">
            <i class="bi-inbox fs-3 d-block mb-2"></i>
            <p class="mb-0">Оборудования пока нет</p>
          </div>
        `;
        return;
      }
      
      container.innerHTML = equipment.map(eq => `
        <a href="/procurement/equipment/${eq.id}/" class="list-group-item list-group-item-action">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <h6 class="mb-1">${this.escapeHtml(eq.name)}</h6>
              <small class="text-muted">
                <code>${eq.inventory_number}</code> • 
                ${eq.category_name || 'Без категории'}
              </small>
            </div>
            <span class="proc-eq-status ${this.getEquipmentStatusClass(eq.status)}">
              ${this.getEquipmentStatusLabel(eq.status)}
            </span>
          </div>
        </a>
      `).join('');
      
    } catch (error) {
      console.error('Error loading recent equipment:', error);
    }
  }
  
  /**
   * Вспомогательные методы
   */
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
  
  getEquipmentStatusClass(status) {
    const classes = {
      'in_stock': 'in-stock',
      'in_use': 'in-use',
      'maintenance': 'maintenance',
      'retired': 'retired'
    };
    return classes[status] || '';
  }
  
  getEquipmentStatusLabel(status) {
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
  if (document.querySelector('#procDashboardStats, #recentRequests, #recentEquipment')) {
    window.procurementDashboard = new ProcurementDashboardHandler();
  }
});

export default ProcurementDashboardHandler;
