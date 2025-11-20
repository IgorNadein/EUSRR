/**
 * @fileoverview Role Manager - Управление ролями и правами отделов
 * Включает:
 * - Автокомплит для выбора роли
 * - Управление правами (permissions) через чипы
 * - Создание/редактирование/удаление ролей
 * @module components/roleManager
 */

import { esc, norm } from '../utils/stringUtils.js';

/**
 * Инициализирует менеджер ролей отдела
 * @returns {Object|null} API компонента или null если элементы не найдены
 */
export function initRoleManager() {
  // Основные элементы
  const editForm = document.getElementById('roleEditForm');
  const roleNameInp = document.getElementById('role_name_text');
  const roleIdHidden = document.getElementById('role_id_hidden');
  const roleIdInput = document.getElementById('edit_role_id');
  const roleSaveBtn = document.getElementById('roleSaveBtn');
  const roleDeleteBtn = document.getElementById('roleDeleteBtn');
  const editChips = document.getElementById('edit_role_perms_chips');
  const editHidden = document.getElementById('edit_role_perms_hidden');

  const createForm = document.getElementById('roleCreateForm');
  const newRoleName = document.getElementById('new_role_name');
  const newChips = document.getElementById('new_role_perms_chips');
  const newHidden = document.getElementById('new_role_perms_hidden');

  // Если основных элементов нет, выходим
  if (!editForm || !roleNameInp) {
    return null;
  }

  /**
   * Создаёт элемент чипа для отображения прав
   */
  function makeChip(text, value) {
    const span = document.createElement('span');
    span.className = 'chip';
    span.dataset.value = value;
    span.textContent = text;
    return span;
  }

  /**
   * Строит словарь прав из списка checkbox'ов
   */
  function buildDict(listSelector) {
    const res = new Map();
    document.querySelectorAll(listSelector + ' .list-group-item').forEach(li => {
      const cb = li.querySelector('input[type=checkbox]');
      const name = li.querySelector('.flex-grow-1')?.textContent?.trim();
      const code = li.querySelector('.text-muted')?.textContent?.trim();
      res.set(cb.value, { name, code });
    });
    return res;
  }

  /**
   * Отображает чипы выбранных прав
   */
  function setChips(container, ids, dict) {
    container.innerHTML = '';
    ids.forEach(id => container.appendChild(makeChip((dict.get(id)?.name || id), id)));
  }

  /**
   * Устанавливает состояние checkbox'ов согласно списку ID
   */
  function setChecks(listSelector, ids) {
    document.querySelectorAll(listSelector + ' input[type=checkbox]').forEach(cb => {
      cb.checked = ids.includes(cb.value);
    });
  }

  /**
   * Синхронизирует скрытые input'ы для отправки формы
   */
  function syncHidden(containerEl, ids) {
    containerEl.innerHTML = '';
    ids.forEach(id => {
      const inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = 'permission_ids';
      inp.value = id;
      containerEl.appendChild(inp);
    });
  }

  /**
   * Инициализирует автокомплит для выбора роли
   */
  function initRolePicker() {
    const root = document.querySelector('[data-role-picker]');
    if (!root || !roleNameInp) return;

    const choices = JSON.parse(root.dataset.choices || '[]');

    // Создаём меню в body для правильного z-index
    const menuLayer = document.createElement('div');
    menuLayer.className = 'dropdown-menu shadow';
    menuLayer.style.position = 'fixed';
    menuLayer.style.zIndex = '2000';
    menuLayer.style.maxHeight = '240px';
    menuLayer.style.overflowY = 'auto';
    document.body.appendChild(menuLayer);

    /**
     * Позиционирует меню относительно input
     */
    function placeMenu() {
      const r = roleNameInp.getBoundingClientRect();
      menuLayer.style.left = r.left + 'px';
      menuLayer.style.top = (r.bottom) + 'px';
      menuLayer.style.width = r.width + 'px';
    }

    /**
     * Отображает список ролей
     */
    function listItems(arr) {
      if (!arr.length) {
        menuLayer.innerHTML = '<div class="dropdown-item disabled">Ничего не найдено</div>';
      } else {
        menuLayer.innerHTML = arr.map(c => `
          <button type="button" class="dropdown-item"
                  data-id="${esc(c.id)}"
                  data-name="${esc(c.name)}"
                  data-perms="${esc(c.perms || '')}">
            ${esc(c.name)}
          </button>
        `).join('');
      }
      placeMenu();
      menuLayer.classList.add('show');
      window.addEventListener('scroll', placeMenu, true);
      window.addEventListener('resize', placeMenu);
    }

    /**
     * Скрывает меню
     */
    function hideMenu() {
      menuLayer.classList.remove('show');
      window.removeEventListener('scroll', placeMenu, true);
      window.removeEventListener('resize', placeMenu);
    }

    /**
     * Фильтрует роли по запросу
     */
    function filter(q) {
      const s = norm(q);
      const res = s 
        ? choices.filter(c => norm(c.name).includes(s)).slice(0, 10)
        : choices.slice(0, 10);
      listItems(res);
    }

    // События input для ролей
    roleNameInp.addEventListener('focus', () => filter(roleNameInp.value));

    roleNameInp.addEventListener('input', () => {
      roleIdHidden.value = '';
      roleIdInput.value = '';
      roleSaveBtn.disabled = true;
      roleDeleteBtn.disabled = true;
      setChips(editChips, [], buildDict('#permListEdit'));
      syncHidden(editHidden, []);
      document.querySelectorAll('#permListEdit input[type=checkbox]').forEach(cb => cb.checked = false);
      filter(roleNameInp.value);
    });

    roleNameInp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const first = menuLayer.querySelector('.dropdown-item:not(.disabled)');
        if (menuLayer.classList.contains('show') && first) {
          e.preventDefault();
          first.click();
        }
      } else if (e.key === 'Escape') {
        hideMenu();
      }
    });

    // Выбор роли из списка
    menuLayer.addEventListener('click', (e) => {
      const btn = e.target.closest('.dropdown-item');
      if (!btn || btn.classList.contains('disabled')) return;

      const id = btn.dataset.id || '';
      const name = btn.dataset.name || '';
      const permsCsv = btn.dataset.perms || '';

      roleNameInp.value = name;
      roleIdHidden.value = id;
      roleIdInput.value = id;
      roleSaveBtn.disabled = !id;
      roleDeleteBtn.disabled = !id;

      const ids = (permsCsv ? permsCsv.split(',').map(s => s.trim()).filter(Boolean) : []);
      setChecks('#permListEdit', ids);
      setChips(editChips, ids, buildDict('#permListEdit'));
      syncHidden(editHidden, ids);

      hideMenu();
    });

    // Закрытие при клике вне
    document.addEventListener('click', (e) => {
      if (!roleNameInp.contains(e.target) && !menuLayer.contains(e.target)) {
        hideMenu();
      }
    });

    // Закрытие при открытии модалки
    document.addEventListener('show.bs.modal', hideMenu);
  }

  /**
   * Инициализирует переключатель формы создания роли
   */
  function initToggleNewRole() {
    document.addEventListener('click', function(e) {
      const btn = e.target.closest('#toggleNewRole');
      if (!btn) return;

      const targetSel = btn.getAttribute('data-toggle-target') || '#roleCreateForm';
      const frm = document.querySelector(targetSel);
      if (!frm) return;

      const willShow = frm.classList.contains('d-none');
      
      if (willShow) {
        frm.classList.remove('d-none');
        // Копируем имя роли если оно было введено в поиске
        if (roleNameInp?.value && !roleIdHidden?.value && newRoleName) {
          newRoleName.value = roleNameInp.value.trim();
        }
        newRoleName?.focus();
      } else {
        frm.classList.add('d-none');
        frm.reset?.();
        if (newChips) newChips.innerHTML = '';
        if (newHidden) newHidden.innerHTML = '';
        document.querySelectorAll('#permListCreate input[type=checkbox]')
          .forEach(cb => cb.checked = false);
      }
    });
  }

  /**
   * Инициализирует кнопку "Применить" для прав редактирования
   */
  function initApplyPermsEdit() {
    document.getElementById('applyPermsEdit')?.addEventListener('click', function() {
      const ids = Array.from(
        document.querySelectorAll('#permListEdit input[type=checkbox]:checked')
      ).map(cb => cb.value);
      
      setChips(editChips, ids, buildDict('#permListEdit'));
      syncHidden(editHidden, ids);
    });
  }

  /**
   * Инициализирует кнопку удаления роли
   */
  function initRoleDelete() {
    roleDeleteBtn?.addEventListener('click', function() {
      if (!roleIdInput.value) return;
      
      if (confirm('Удалить выбранную роль?')) {
        document.getElementById('delete_role_id').value = roleIdInput.value;
        document.getElementById('roleDeleteForm').submit();
      }
    });
  }

  /**
   * Инициализирует кнопку "Применить" для прав создания
   */
  function initApplyPermsCreate() {
    document.getElementById('applyPermsCreate')?.addEventListener('click', function() {
      const ids = Array.from(
        document.querySelectorAll('#permListCreate input[type=checkbox]:checked')
      ).map(cb => cb.value);
      
      setChips(newChips, ids, buildDict('#permListCreate'));
      syncHidden(newHidden, ids);
    });
  }

  /**
   * Инициализирует синхронизацию при отправке формы создания
   */
  function initCreateFormSubmit() {
    createForm?.addEventListener('submit', function() {
      const ids = Array.from(
        document.querySelectorAll('#permListCreate input[type=checkbox]:checked')
      ).map(cb => cb.value);
      
      syncHidden(newHidden, ids);
    });
  }

  /**
   * Инициализирует кнопку "Отмена" для формы создания
   */
  function initCancelNewRole() {
    document.addEventListener('click', function(e) {
      const btn = e.target.closest('#cancelNewRole');
      if (!btn) return;
      e.preventDefault();

      const frm = document.getElementById('roleCreateForm');
      if (!frm) return;

      frm.classList.add('d-none');
      frm.reset?.();

      if (newChips) newChips.innerHTML = '';
      if (newHidden) newHidden.innerHTML = '';

      document.querySelectorAll('#permListCreate input[type=checkbox]')
        .forEach(cb => cb.checked = false);
    });
  }

  /**
   * Перемещает модалки в body для правильного z-index
   */
  function fixModals() {
    document.querySelectorAll('.modal').forEach(m => {
      if (m.parentElement !== document.body) {
        document.body.appendChild(m);
      }
    });
  }

  // Инициализируем все компоненты
  initRolePicker();
  initToggleNewRole();
  initApplyPermsEdit();
  initRoleDelete();
  initApplyPermsCreate();
  initCreateFormSubmit();
  initCancelNewRole();
  fixModals();

  return {
    /**
     * Переинициализирует компонент
     */
    refresh: () => {
      initRoleManager();
    },

    /**
     * Получить выбранную роль
     */
    getSelectedRole: () => ({
      id: roleIdInput?.value || '',
      name: roleNameInp?.value || ''
    }),

    /**
     * Получить выбранные права редактирования
     */
    getEditPermissions: () => {
      return Array.from(
        document.querySelectorAll('#permListEdit input[type=checkbox]:checked')
      ).map(cb => cb.value);
    },

    /**
     * Получить выбранные права создания
     */
    getCreatePermissions: () => {
      return Array.from(
        document.querySelectorAll('#permListCreate input[type=checkbox]:checked')
      ).map(cb => cb.value);
    }
  };
}

// Публикуем в window для совместимости
if (typeof window !== 'undefined') {
  window.initRoleManager = initRoleManager;
}
