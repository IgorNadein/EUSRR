/**
 * avatarCropperHandler.js
 * Компонент для обрезки аватара с требованиями FaceID
 * 
 * Требования для FaceID:
 * - Лицо должно занимать 70-80% кадра
 * - Центрирование лица в кадре
 * - Минимальный размер: 600x600px
 * - Соотношение сторон: 1:1 (квадрат)
 * - Формат: JPEG (оптимизированный для распознавания)
 * 
 * Зависимости: Cropper.js (https://github.com/fengyuanchen/cropperjs)
 */

const DEFAULT_CONFIG = {
  // Селекторы
  fileInputSelector: 'input[type="file"][name="avatar"]',
  modalId: 'avatarCropperModal',
  previewImageId: 'avatarPreview',
  placeholderId: 'avatarPlaceholder',
  
  // Настройки Cropper.js
  cropperOptions: {
    aspectRatio: 1, // Квадратное фото
    viewMode: 2, // Ограничить canvas областью контейнера
    dragMode: 'move', // Перемещение изображения
    autoCropArea: 0.8, // Начальный размер области обрезки (80%)
    restore: false,
    guides: true,
    center: true,
    highlight: true,
    cropBoxMovable: true,
    cropBoxResizable: true,
    toggleDragModeOnDblclick: false,
    minCropBoxWidth: 200,
    minCropBoxHeight: 200,
  },
  
  // Требования для FaceID
  minOutputSize: 600, // Минимальный размер выходного изображения
  outputSize: 800, // Рекомендуемый размер выходного изображения
  outputQuality: 0.92, // Качество JPEG (0.0 - 1.0)
  outputFormat: 'image/jpeg', // Формат выходного файла
  
  // Тексты для UI
  texts: {
    modalTitle: 'Обрезка фото для FaceID',
    instructions: `
      <div class="alert alert-info mb-3">
        <h6 class="mb-2"><i class="bi-info-circle me-2"></i>Требования для системы распознавания лиц:</h6>
        <ul class="mb-0 small">
          <li>Лицо должно занимать 70-80% кадра</li>
          <li>Расположите лицо в центре рамки</li>
          <li>Избегайте теней и бликов</li>
          <li>Смотрите прямо в камеру</li>
          <li>Нейтральное выражение лица</li>
        </ul>
      </div>
    `,
    cropButton: 'Применить обрезку',
    cancelButton: 'Отмена',
    errorTooSmall: 'Изображение слишком маленькое. Минимальный размер: ',
    errorInvalidFormat: 'Неподдерживаемый формат. Используйте JPG, PNG или GIF.',
    errorFileSize: 'Файл слишком большой. Максимум 10 МБ.',
  }
};

/**
 * Создает и управляет модальным окном для обрезки аватара
 */
export class AvatarCropper {
  constructor(config = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.cropper = null;
    this.currentFile = null;
    this.croppedBlob = null;
    
    this.init();
  }
  
  /**
   * Инициализация компонента
   */
  init() {
    this.createModal();
    this.attachEventListeners();
  }
  
  /**
   * Создает модальное окно для cropper
   */
  createModal() {
    // Проверяем, не существует ли уже модальное окно
    if (document.getElementById(this.config.modalId)) {
      return;
    }
    
    const modalHtml = `
      <div class="modal fade" id="${this.config.modalId}" tabindex="-1" aria-hidden="true" data-bs-backdrop="static">
        <div class="modal-dialog modal-lg modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">${this.config.texts.modalTitle}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              ${this.config.texts.instructions}
              
              <!-- Контейнер для Cropper.js -->
              <div class="cropper-container-wrapper" style="max-height: 500px; overflow: hidden;">
                <img id="cropperImage" style="max-width: 100%; display: block;">
              </div>
              
              <!-- Индикатор размера -->
              <div class="mt-3 text-center">
                <small class="text-muted" id="cropperSizeIndicator">
                  Размер обрезанного фото: <span class="fw-bold">-</span>
                </small>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                ${this.config.texts.cancelButton}
              </button>
              <button type="button" class="btn btn-primary" id="cropperApplyBtn">
                <i class="bi-check-circle me-2"></i>${this.config.texts.cropButton}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }
  
  /**
   * Навешивает обработчики событий
   */
  attachEventListeners() {
    // Обработчик выбора файла
    const fileInput = document.querySelector(this.config.fileInputSelector);
    if (fileInput) {
      fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    }
    
    // Обработчик кнопки "Применить"
    const applyBtn = document.getElementById('cropperApplyBtn');
    if (applyBtn) {
      applyBtn.addEventListener('click', () => this.applyCrop());
    }
    
    // Обработчик закрытия модального окна
    const modal = document.getElementById(this.config.modalId);
    if (modal) {
      modal.addEventListener('hidden.bs.modal', () => this.destroyCropper());
    }
    
    // Обработчик изменения области обрезки (для обновления индикатора размера)
    const cropperImage = document.getElementById('cropperImage');
    if (cropperImage) {
      cropperImage.addEventListener('crop', (e) => this.updateSizeIndicator(e.detail));
    }
  }
  
  /**
   * Обработка выбора файла
   */
  async handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Валидация формата
    if (!file.type.match(/^image\/(jpeg|jpg|png|gif)$/i)) {
      alert(this.config.texts.errorInvalidFormat);
      event.target.value = '';
      return;
    }
    
    // Валидация размера (10 МБ)
    if (file.size > 10 * 1024 * 1024) {
      alert(this.config.texts.errorFileSize);
      event.target.value = '';
      return;
    }
    
    this.currentFile = file;
    
    // Проверяем размер изображения
    const isValidSize = await this.validateImageSize(file);
    if (!isValidSize) {
      event.target.value = '';
      return;
    }
    
    // Открываем cropper
    this.openCropper(file);
  }
  
  /**
   * Проверяет размер изображения
   */
  validateImageSize(file) {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      
      img.onload = () => {
        URL.revokeObjectURL(url);
        
        const minSize = this.config.minOutputSize;
        if (img.width < minSize || img.height < minSize) {
          alert(
            `${this.config.texts.errorTooSmall}${minSize}x${minSize}px\n` +
            `Ваше изображение: ${img.width}x${img.height}px`
          );
          resolve(false);
        } else {
          resolve(true);
        }
      };
      
      img.onerror = () => {
        URL.revokeObjectURL(url);
        alert('Не удалось загрузить изображение');
        resolve(false);
      };
      
      img.src = url;
    });
  }
  
  /**
   * Открывает модальное окно с cropper
   */
  openCropper(file) {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const cropperImage = document.getElementById('cropperImage');
      cropperImage.src = e.target.result;
      
      // Показываем модальное окно
      const modal = new bootstrap.Modal(document.getElementById(this.config.modalId));
      modal.show();
      
      // Инициализируем Cropper.js после отображения модального окна
      setTimeout(() => {
        this.initCropper(cropperImage);
      }, 200);
    };
    
    reader.readAsDataURL(file);
  }
  
  /**
   * Инициализирует Cropper.js
   */
  initCropper(imageElement) {
    // Уничтожаем предыдущий экземпляр, если есть
    if (this.cropper) {
      this.cropper.destroy();
    }
    
    // Создаем новый экземпляр Cropper
    this.cropper = new Cropper(imageElement, {
      ...this.config.cropperOptions,
      ready: () => {
        console.log('[AvatarCropper] Cropper ready');
        this.updateSizeIndicator();
      },
      crop: (event) => {
        this.updateSizeIndicator(event.detail);
      }
    });
  }
  
  /**
   * Обновляет индикатор размера обрезанного изображения
   */
  updateSizeIndicator(detail) {
    if (!this.cropper) return;
    
    const data = detail || this.cropper.getData();
    const width = Math.round(data.width);
    const height = Math.round(data.height);
    
    const indicator = document.getElementById('cropperSizeIndicator');
    if (indicator) {
      const sizeSpan = indicator.querySelector('.fw-bold');
      if (sizeSpan) {
        const minSize = this.config.minOutputSize;
        const isValid = width >= minSize && height >= minSize;
        
        sizeSpan.textContent = `${width}x${height}px`;
        sizeSpan.className = isValid ? 'fw-bold text-success' : 'fw-bold text-danger';
        
        if (!isValid) {
          sizeSpan.textContent += ` (мин. ${minSize}x${minSize}px)`;
        }
      }
    }
  }
  
  /**
   * Применяет обрезку и закрывает модальное окно
   */
  async applyCrop() {
    if (!this.cropper) return;
    
    const applyBtn = document.getElementById('cropperApplyBtn');
    const originalText = applyBtn.innerHTML;
    
    try {
      // Показываем индикатор загрузки
      applyBtn.disabled = true;
      applyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Обработка...';
      
      // Получаем обрезанное изображение
      const canvas = this.cropper.getCroppedCanvas({
        width: this.config.outputSize,
        height: this.config.outputSize,
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'high',
      });
      
      // Конвертируем в Blob
      this.croppedBlob = await new Promise((resolve) => {
        canvas.toBlob(
          (blob) => resolve(blob),
          this.config.outputFormat,
          this.config.outputQuality
        );
      });
      
      // Создаем File объект из Blob
      const croppedFile = new File(
        [this.croppedBlob],
        this.currentFile.name,
        { type: this.config.outputFormat }
      );
      
      // Обновляем превью
      this.updatePreview(canvas);
      
      // Обновляем input файла
      this.updateFileInput(croppedFile);
      
      // Закрываем модальное окно
      const modal = bootstrap.Modal.getInstance(document.getElementById(this.config.modalId));
      modal.hide();
      
    } catch (error) {
      console.error('[AvatarCropper] Error applying crop:', error);
      alert('Произошла ошибка при обрезке изображения');
    } finally {
      applyBtn.disabled = false;
      applyBtn.innerHTML = originalText;
    }
  }
  
  /**
   * Обновляет превью аватара
   */
  updatePreview(canvas) {
    const previewImg = document.getElementById(this.config.previewImageId);
    const placeholder = document.getElementById(this.config.placeholderId);
    
    const dataUrl = canvas.toDataURL(this.config.outputFormat, this.config.outputQuality);
    
    if (previewImg) {
      // Если превью - это img элемент
      previewImg.src = dataUrl;
      previewImg.classList.remove('d-none');
      
      if (placeholder) {
        placeholder.classList.add('d-none');
      }
    } else if (placeholder && placeholder.tagName !== 'IMG') {
      // Если превью - это placeholder, заменяем его на img
      const img = document.createElement('img');
      img.id = this.config.previewImageId;
      img.src = dataUrl;
      img.alt = 'Фото';
      img.className = 'rounded';
      img.style.cssText = 'width: 120px; height: 120px; object-fit: cover; border: 2px solid #dee2e6;';
      placeholder.replaceWith(img);
    }
  }
  
  /**
   * Обновляет input файла с обрезанным изображением
   */
  updateFileInput(croppedFile) {
    const fileInput = document.querySelector(this.config.fileInputSelector);
    if (!fileInput) return;
    
    // Создаем новый DataTransfer объект
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(croppedFile);
    
    // Обновляем files input
    fileInput.files = dataTransfer.files;
    
    console.log('[AvatarCropper] File input updated with cropped image:', {
      name: croppedFile.name,
      size: croppedFile.size,
      type: croppedFile.type
    });
  }
  
  /**
   * Уничтожает экземпляр Cropper
   */
  destroyCropper() {
    if (this.cropper) {
      this.cropper.destroy();
      this.cropper = null;
    }
    
    // Очищаем src изображения
    const cropperImage = document.getElementById('cropperImage');
    if (cropperImage) {
      cropperImage.src = '';
    }
  }
}

/**
 * Инициализирует Avatar Cropper
 * @param {Object} config - Конфигурация
 * @returns {AvatarCropper} Экземпляр AvatarCropper
 */
export function initAvatarCropper(config = {}) {
  return new AvatarCropper(config);
}
