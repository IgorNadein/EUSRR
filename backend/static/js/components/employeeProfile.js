/**
 * Модуль для загрузки и отображения профиля сотрудника
 * Использует API для получения данных с корректными глобальными URL
 */

export class EmployeeProfile {
  constructor(employeeId, options = {}) {
    this.employeeId = employeeId;
    this.apiUrl = `/api/v1/employees/${employeeId}/`;
    this.postsApiUrl = '/api/v1/posts/';
    
    // Селекторы контейнеров
    this.avatarContainer = options.avatarContainer || '#employeeAvatar';
    this.nameContainer = options.nameContainer || '#employeeName';
    this.postsContainer = options.postsContainer || '#employeePosts';
  }

  /**
   * Инициализация - загрузка и рендеринг
   */
  async init() {
    try {
      // Загружаем данные сотрудника
      const employee = await this.fetchEmployee();
      if (employee) {
        this.renderAvatar(employee);
        this.renderName(employee);
      }
      
      // Загружаем посты сотрудника
      await this.loadPosts();
    } catch (error) {
      console.error('Failed to load employee profile:', error);
    }
  }

  /**
   * Загрузка данных сотрудника через API
   */
  async fetchEmployee() {
    const response = await fetch(this.apiUrl);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  }

  /**
   * Рендеринг аватара
   */
  renderAvatar(employee) {
    const container = document.querySelector(this.avatarContainer);
    if (!container) return;

    const avatarHtml = this.createAvatarHtml(employee);
    container.innerHTML = avatarHtml;
  }

  /**
   * Создание HTML аватара
   */
  createAvatarHtml(employee) {
    if (employee.avatar) {
      return `
        <img src="${employee.avatar}"
             alt="Аватар ${employee.last_name} ${employee.first_name}"
             class="ios-ava" 
             style="object-fit:cover; cursor: pointer;"
             data-bs-toggle="modal"
             data-bs-target="#avatarModal"
             data-avatar-url="${employee.avatar}">
      `;
    } else {
      const initial = (employee.first_name || employee.last_name || '?').charAt(0).toUpperCase();
      return `
        <div class="ios-ava--ph">
          ${initial}
        </div>
      `;
    }
  }

  /**
   * Рендеринг имени (опционально, если нужно обновить)
   */
  renderName(employee) {
    const container = document.querySelector(this.nameContainer);
    if (!container) return;

    let fullName = `${employee.last_name} ${employee.first_name}`;
    if (employee.patronymic) {
      fullName += ` ${employee.patronymic}`;
    }
    container.textContent = fullName;
  }

  /**
   * Загрузка постов сотрудника
   */
  async loadPosts() {
    const container = document.querySelector(this.postsContainer);
    if (!container) return;

    try {
      // Динамический импорт FeedList
      const { FeedList } = await import('/static/js/components/feedList.js');
      
      // Создаем экземпляр FeedList для постов сотрудника
      const feedList = new FeedList({
        containerId: this.postsContainer.replace('#', ''),
        apiUrl: this.postsApiUrl,
        params: { 
          author: this.employeeId,
          ordering: '-created_at'
        },
        showLoadMore: false, // Не показываем кнопку "загрузить еще"
        postsPerPage: 10
      });
      
      await feedList.init();
      
      // Если постов нет, показываем сообщение
      if (feedList.posts.length === 0) {
        container.innerHTML = '<div class="text-secondary small">Публикаций пока нет.</div>';
      }
    } catch (error) {
      console.error('Failed to load employee posts:', error);
      container.innerHTML = '<div class="text-danger small">Не удалось загрузить публикации.</div>';
    }
  }
}

/**
 * Инициализация профиля сотрудника
 */
export function initEmployeeProfile(employeeId, options) {
  const profile = new EmployeeProfile(employeeId, options);
  profile.init();
  return profile;
}
