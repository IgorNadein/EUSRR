/**
 * feedList.js
 * Загрузка и рендеринг ленты новостей через API
 */

export class FeedList {
  constructor(options = {}) {
    this.containerId = options.containerId || 'feedList';
    this.apiUrl = options.apiUrl || '/api/v1/posts/';
    this.params = options.params || { type: 'company' };
    this.currentPage = 1;
    this.isLoading = false;
    this.hasMore = true;
    this.posts = [];
    
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      console.error(`Container #${this.containerId} not found`);
      return;
    }
    
    this.init();
  }
  
  init() {
    this.loadPosts();
    this.attachScrollHandler();
  }
  
  /**
   * Загрузка постов с API
   */
  async loadPosts(page = 1) {
    if (this.isLoading) return;
    
    this.isLoading = true;
    this.showLoader();
    
    const params = new URLSearchParams({
      ...this.params,
      page: page
    });
    
    try {
      const response = await fetch(`${this.apiUrl}?${params}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // API возвращает paginated response
      const newPosts = data.results || [];
      
      if (page === 1) {
        this.posts = newPosts;
        this.renderPosts();
      } else {
        this.posts = [...this.posts, ...newPosts];
        this.appendPosts(newPosts);
      }
      
      this.currentPage = page;
      this.hasMore = !!data.next;
      
    } catch (error) {
      console.error('Error loading posts:', error);
      this.showError('Не удалось загрузить публикации');
    } finally {
      this.isLoading = false;
      this.hideLoader();
    }
  }
  
  /**
   * Полный рендеринг списка постов
   */
  renderPosts() {
    this.container.innerHTML = '';
    
    if (this.posts.length === 0) {
      this.container.innerHTML = `
        <div class="alert alert-info shadow-sm mt-2">
          Пока нет новостей.
        </div>
      `;
      return;
    }
    
    this.posts.forEach(post => {
      this.container.appendChild(this.createPostCard(post));
    });
  }
  
  /**
   * Добавление новых постов в конец списка
   */
  appendPosts(posts) {
    posts.forEach(post => {
      this.container.appendChild(this.createPostCard(post));
    });
  }
  
  /**
   * Создание карточки поста
   */
  createPostCard(post) {
    const article = document.createElement('article');
    article.className = 'feed-post';
    article.id = `post-${post.id}`;
    article.dataset.postCard = '';
    article.dataset.searchtitle = post.title || 'Без названия';
    article.dataset.searchauthor = post.author?.full_name || 'Автор';
    article.dataset.searchbody = (post.body || 'Без содержания').substring(0, 200);
    
    // Header
    const header = this.createPostHeader(post);
    article.appendChild(header);
    
    // Image
    if (post.image) {
      const imageDiv = this.createPostImage(post);
      article.appendChild(imageDiv);
    }
    
    // Body
    const body = this.createPostBody(post);
    article.appendChild(body);
    
    // Footer
    const footer = this.createPostFooter(post);
    article.appendChild(footer);
    
    // Collapse block for comments (пустой пока)
    if (post.comments_count > 0) {
      const collapseDiv = this.createCommentsCollapse(post);
      article.appendChild(collapseDiv);
    }
    
    return article;
  }
  
  /**
   * Создание заголовка поста
   */
  createPostHeader(post) {
    const header = document.createElement('header');
    header.className = 'card-header';
    
    // Avatar
    const iconDiv = document.createElement('div');
    iconDiv.className = 'card-icon d-flex align-items-center justify-content-center';
    
    if (post.author?.avatar) {
      const img = document.createElement('img');
      img.src = post.author.avatar;
      img.alt = '';
      img.loading = 'lazy';
      iconDiv.appendChild(img);
    } else {
      const icon = document.createElement('i');
      icon.className = 'bi-person';
      iconDiv.appendChild(icon);
    }
    
    header.appendChild(iconDiv);
    
    // Meta
    const metaDiv = document.createElement('div');
    metaDiv.className = 'card-meta';
    
    const titleDiv = document.createElement('div');
    titleDiv.className = 'card-title';
    
    if (post.author?.id) {
      const authorLink = document.createElement('a');
      authorLink.href = `/employees/${post.author.id}/`;
      authorLink.className = 'text-decoration-none';
      authorLink.textContent = post.author.full_name || 'Сотрудник';
      titleDiv.appendChild(authorLink);
    } else {
      titleDiv.textContent = 'Автор не указан';
    }
    
    metaDiv.appendChild(titleDiv);
    
    // Subtitle
    const subtitleDiv = document.createElement('div');
    subtitleDiv.className = 'card-subtitle';
    subtitleDiv.textContent = post.created_at_display || '';
    
    if (post.type === 'department' && post.department?.name) {
      subtitleDiv.textContent += ` · ${post.department.name}`;
    }
    
    metaDiv.appendChild(subtitleDiv);
    header.appendChild(metaDiv);
    
    // Pin indicator
    if (post.pinned) {
      const pin = document.createElement('span');
      pin.className = 'feed-pin';
      pin.innerHTML = '<i class="bi-pin-angle"></i>';
      header.appendChild(pin);
    }
    
    return header;
  }
  
  /**
   * Создание блока изображения
   */
  createPostImage(post) {
    const div = document.createElement('div');
    div.className = 'feed-img';
    
    const link = document.createElement('a');
    link.href = '#';
    link.dataset.postLink = '';
    link.dataset.postId = post.id;
    link.className = 'stretched-link';
    
    const img = document.createElement('img');
    img.src = post.image;
    img.alt = post.title || 'Публикация';
    img.loading = 'lazy';
    img.decoding = 'async';
    
    div.appendChild(link);
    div.appendChild(img);
    
    return div;
  }
  
  /**
   * Создание тела поста
   */
  createPostBody(post) {
    const div = document.createElement('div');
    div.className = 'card-body';
    
    // Title
    const title = document.createElement('h3');
    title.className = 'feed-title mb-1';
    
    const titleLink = document.createElement('a');
    titleLink.href = '#';
    titleLink.dataset.postLink = '';
    titleLink.dataset.postId = post.id;
    titleLink.className = 'text-decoration-none stretched-link';
    titleLink.textContent = post.title || 'Без названия';
    
    title.appendChild(titleLink);
    div.appendChild(title);
    
    // Body text (truncated)
    if (post.body) {
      const textDiv = document.createElement('div');
      textDiv.className = 'feed-text mb-1';
      
      const words = post.body.split(/\s+/);
      if (words.length > 42) {
        textDiv.textContent = words.slice(0, 42).join(' ') + '...';
      } else {
        textDiv.innerHTML = post.body.replace(/\n/g, '<br>');
      }
      
      div.appendChild(textDiv);
    }
    
    return div;
  }
  
  /**
   * Создание футера поста
   */
  createPostFooter(post) {
    const footer = document.createElement('footer');
    footer.className = 'card-actions border-0';
    
    // Comments button (collapse toggle)
    if (post.comments_count > 0) {
      const commentBtn = document.createElement('button');
      commentBtn.className = 'btn btn-ghost d-inline-flex align-items-center gap-1';
      commentBtn.type = 'button';
      commentBtn.dataset.bsToggle = 'collapse';
      commentBtn.dataset.bsTarget = `#ccoll-${post.id}`;
      commentBtn.setAttribute('aria-controls', `ccoll-${post.id}`);
      commentBtn.setAttribute('aria-expanded', 'false');
      
      const commentIcon = document.createElement('i');
      commentIcon.className = 'bi-chat-dots';
      
      const commentCount = document.createElement('span');
      commentCount.className = 'txt-open';
      commentCount.textContent = post.comments_count || 0;
      
      const hideText = document.createElement('span');
      hideText.className = 'txt-close';
      hideText.textContent = 'Скрыть';
      
      commentBtn.appendChild(commentIcon);
      commentBtn.appendChild(commentCount);
      commentBtn.appendChild(hideText);
      
      footer.appendChild(commentBtn);
    }
    
    // Attachment button
    if (post.attachment) {
      const attachBtn = document.createElement('a');
      attachBtn.href = post.attachment;
      attachBtn.className = 'btn btn-ghost d-inline-flex align-items-center gap-1';
      
      const attachIcon = document.createElement('i');
      attachIcon.className = 'bi-paperclip';
      
      const attachText = document.createElement('span');
      attachText.textContent = 'Вложение';
      
      attachBtn.appendChild(attachIcon);
      attachBtn.appendChild(attachText);
      
      footer.appendChild(attachBtn);
    }
    
    // Spacer - pushes like button to the right
    const spacer = document.createElement('span');
    spacer.className = 'ms-auto';
    footer.appendChild(spacer);
    
    // Like button - на правой стороне
    const likeBtn = document.createElement('button');
    likeBtn.type = 'button';
    likeBtn.className = 'btn btn-ghost d-inline-flex align-items-center gap-1 like-btn-card';
    likeBtn.dataset.postId = post.id;
    likeBtn.dataset.liked = post.is_liked ? 'true' : 'false';
    
    const likeIcon = document.createElement('i');
    likeIcon.className = post.is_liked ? 'bi-heart-fill text-danger' : 'bi-heart';
    
    const likeCount = document.createElement('span');
    likeCount.className = 'like-count';
    likeCount.textContent = post.likes_count || 0;
    
    likeBtn.appendChild(likeIcon);
    likeBtn.appendChild(likeCount);
    
    footer.appendChild(likeBtn);
    
    return footer;
  }
  
  /**
   * Создание collapse блока с комментариями
   */
  createCommentsCollapse(post) {
    const collapseDiv = document.createElement('div');
    collapseDiv.id = `ccoll-${post.id}`;
    collapseDiv.className = 'collapse';
    
    // Заглушка - показываем кнопку "Показать все комментарии"
    const contentDiv = document.createElement('div');
    contentDiv.className = 'px-3 pt-2';
    
    const linkContainer = document.createElement('div');
    linkContainer.className = 'd-flex justify-content-between align-items-center mb-2';
    
    const showAllLink = document.createElement('a');
    showAllLink.className = 'small text-primary text-decoration-none';
    showAllLink.href = '#';
    showAllLink.dataset.postLink = '';
    showAllLink.dataset.postId = post.id;
    showAllLink.textContent = `Показать все комментарии записи (${post.comments_count})`;
    
    linkContainer.appendChild(showAllLink);
    contentDiv.appendChild(linkContainer);
    collapseDiv.appendChild(contentDiv);
    
    return collapseDiv;
  }
  
  /**
   * Показать лоадер
   */
  showLoader() {
    let loader = document.getElementById('feedLoader');
    if (!loader) {
      loader = document.createElement('div');
      loader.id = 'feedLoader';
      loader.className = 'text-center py-4';
      loader.innerHTML = `
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Загрузка...</span>
        </div>
      `;
      this.container.parentElement.appendChild(loader);
    }
    loader.style.display = 'block';
  }
  
  /**
   * Скрыть лоадер
   */
  hideLoader() {
    const loader = document.getElementById('feedLoader');
    if (loader) {
      loader.style.display = 'none';
    }
  }
  
  /**
   * Показать ошибку
   */
  showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger shadow-sm mt-2';
    alert.textContent = message;
    this.container.innerHTML = '';
    this.container.appendChild(alert);
  }
  
  /**
   * Обработчик прокрутки для бесконечной загрузки
   */
  attachScrollHandler() {
    let ticking = false;
    
    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          this.checkScrollPosition();
          ticking = false;
        });
        ticking = true;
      }
    });
  }
  
  /**
   * Проверка позиции прокрутки
   */
  checkScrollPosition() {
    if (this.isLoading || !this.hasMore) return;
    
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;
    
    // Загружаем следующую страницу за 500px до конца
    if (scrollTop + windowHeight >= documentHeight - 500) {
      this.loadPosts(this.currentPage + 1);
    }
  }
  
  /**
   * Обновление ленты
   */
  refresh() {
    this.currentPage = 1;
    this.hasMore = true;
    this.posts = [];
    this.loadPosts(1);
  }
}
