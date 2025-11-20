/**
 * navbar-mobile-search.js
 * Управление мобильным поиском в navbar
 */

(function() {
    'use strict';

    // Элементы
    const searchToggle = document.querySelector('.mobile-search-toggle');
    const searchInput = document.querySelector('.mobile-search-input');
    const searchForm = document.querySelector('.mobile-search-form');
    const navbarIcons = document.querySelectorAll('.navbar-icon');
    const navbarBrand = document.querySelector('.navbar-brand-item');
    const navbarRight = document.querySelector('.navbar-right');

    if (!searchToggle || !searchInput) return;

    let isSearchOpen = false;
    let searchOverlay = null;

    // Создать оверлей
    function createOverlay() {
        if (!searchOverlay) {
            searchOverlay = document.createElement('div');
            searchOverlay.className = 'mobile-search-overlay';
            document.body.appendChild(searchOverlay);
        }
    }

    // Показать оверлей
    function showOverlay() {
        createOverlay();
        setTimeout(() => {
            searchOverlay.classList.add('active');
        }, 10);
    }

    // Скрыть оверлей
    function hideOverlay() {
        if (searchOverlay) {
            searchOverlay.classList.remove('active');
        }
    }

    // Открыть/закрыть поиск
    function toggleMobileSearch() {
        isSearchOpen = !isSearchOpen;

        if (isSearchOpen) {
            // Открыть поиск
            searchToggle.classList.add('d-none');
            searchInput.classList.remove('d-none');
            searchInput.classList.add('d-flex');
            
            // Показать оверлей
            showOverlay();
            
            // Скрыть остальные элементы на мобильном
            navbarIcons.forEach(icon => {
                if (window.innerWidth < 768) {
                    icon.classList.add('d-none');
                }
            });
            
            if (window.innerWidth < 768) {
                if (navbarBrand) navbarBrand.classList.add('d-none');
                if (navbarRight) navbarRight.classList.add('d-none');
            }

            // Фокус на инпут
            const input = searchInput.querySelector('input');
            if (input) {
                setTimeout(() => input.focus(), 100);
            }
        } else {
            // Закрыть поиск
            closeMobileSearch();
        }
    }

    function closeMobileSearch() {
        isSearchOpen = false;
        searchToggle.classList.remove('d-none');
        searchInput.classList.add('d-none');
        searchInput.classList.remove('d-flex');

        // Скрыть оверлей
        hideOverlay();

        // Показать остальные элементы
        navbarIcons.forEach(icon => icon.classList.remove('d-none'));
        if (navbarBrand) navbarBrand.classList.remove('d-none');
        if (navbarRight) navbarRight.classList.remove('d-none');
    }

    // Клик на иконку поиска
    searchToggle.addEventListener('click', toggleMobileSearch);

    // Закрыть при клике вне поиска
    document.addEventListener('click', (e) => {
        if (!isSearchOpen) return;
        
        // Проверяем, был ли клик вне формы поиска (или на оверлей)
        if (!searchForm.contains(e.target) || e.target === searchOverlay) {
            closeMobileSearch();
        }
    });

    // Закрыть при нажатии Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isSearchOpen) {
            closeMobileSearch();
        }
    });

    // Отправка формы - отключаем неактивный input
    searchForm.addEventListener('submit', (e) => {
        const mobileInput = document.getElementById('mobileSearchInput');
        const desktopInput = document.getElementById('desktopSearchInput');
        
        // Определяем какой input активен
        const isMobile = window.innerWidth < 768;
        
        if (isMobile) {
            // На мобильном отключаем десктопный
            if (desktopInput) desktopInput.disabled = true;
            
            // Проверяем что мобильный не пустой
            if (!mobileInput || !mobileInput.value.trim()) {
                e.preventDefault();
                if (desktopInput) desktopInput.disabled = false;
                return;
            }
        } else {
            // На десктопе отключаем мобильный
            if (mobileInput) mobileInput.disabled = true;
            
            // Проверяем что десктопный не пустой
            if (!desktopInput || !desktopInput.value.trim()) {
                e.preventDefault();
                if (mobileInput) mobileInput.disabled = false;
                return;
            }
        }
        
        // Форма отправится с одним активным полем
    });

    // Закрыть при изменении размера окна на десктоп
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 768 && isSearchOpen) {
            closeMobileSearch();
        }
    });
})();
