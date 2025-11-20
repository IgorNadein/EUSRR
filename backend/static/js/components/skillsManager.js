/**
 * skillsManager.js
 * Управление навыками сотрудника (добавление/удаление через AJAX)
 * 
 * @module skillsManager
 * @version 1.0.0
 */

import { esc } from '../utils/stringUtils.js';

/**
 * Инициализация менеджера навыков
 * @param {Object} options - Опции конфигурации
 * @param {string} options.blockId - ID блока с навыками
 * @param {string} options.formId - ID формы добавления
 * @param {string} options.collapseId - ID collapse элемента формы
 * @param {string} options.removeUrl - URL для удаления навыка
 * @returns {Object|null} Публичный API или null если элементы не найдены
 */
export function initSkillsManager(options = {}) {
  const block = document.getElementById(options.blockId || 'skillsBlock');
  
  // Проверяем, что блок существует и редактируемый
  if (!block || block.dataset.editable !== '1') {
    console.log('skillsManager: skip (block not found or not editable)');
    return null;
  }

  const elems = {
    form: document.getElementById(options.formId || 'skillAddForm'),
    chipsWrap: block.querySelector('.chips'),
    addBtn: block.querySelector('.chip-add'),
    collapseEl: document.getElementById(options.collapseId || 'skillsForm')
  };

  if (!elems.form || !elems.chipsWrap) {
    console.warn('skillsManager: required elements not found');
    return null;
  }

  const config = {
    removeUrl: options.removeUrl || elems.form.dataset.removeUrl || '',
    addUrl: elems.form.action
  };

  const csrf = elems.form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

  // Bootstrap Collapse instance
  let bsCollapse = null;
  if (window.bootstrap && elems.collapseEl) {
    bsCollapse = new bootstrap.Collapse(elems.collapseEl, { toggle: false });
  }

  /**
   * Добавить навык
   * @param {string} skillName - Название навыка
   */
  async function addSkill(skillName) {
    const input = elems.form.querySelector('input[name="skill_name"]');
    const submitBtn = elems.form.querySelector('[type="submit"]');
    
    if (!skillName.trim()) {
      input?.focus();
      return;
    }

    submitBtn?.setAttribute('disabled', '');

    try {
      const resp = await fetch(config.addUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body: new URLSearchParams({ skill_name: skillName })
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      let data = null;
      try {
        data = await resp.json();
      } catch (_) {}

      const displayName = (data && (data.name || data?.skill?.name || data?.title)) || skillName;
      const skillId = (data && (data.id || data?.skill?.id)) || '';

      // Проверяем, не добавлен ли уже этот навык
      const exists = [...elems.chipsWrap.querySelectorAll('.chip-skill')].some(
        el => (el.dataset.skillName || el.textContent).trim().toLowerCase() === displayName.toLowerCase()
      );

      if (!exists) {
        removeEmptyNote();
        const chip = createSkillChip(skillId, displayName);
        elems.chipsWrap.insertBefore(chip, elems.addBtn);
        
        // Анимация пульсации кнопки "добавить"
        elems.addBtn?.classList.add('pulse');
        setTimeout(() => elems.addBtn?.classList.remove('pulse'), 180);
      }

      // Очистить input и закрыть форму
      if (input) input.value = '';
      if (bsCollapse) {
        bsCollapse.hide();
      } else {
        elems.collapseEl?.classList.remove('show');
      }

    } catch (e) {
      console.error('skillsManager: add error', e);
      location.reload();
    } finally {
      submitBtn?.removeAttribute('disabled');
    }
  }

  /**
   * Удалить навык
   * @param {HTMLElement} chip - Элемент chip с навыком
   */
  async function removeSkill(chip) {
    const skillId = chip.dataset.skillId || '';
    const skillName = chip.dataset.skillName || chip.textContent.trim();
    const delBtn = chip.querySelector('.chip-del-btn');

    if (delBtn) delBtn.disabled = true;

    try {
      const resp = await fetch(config.removeUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        body: new URLSearchParams({ skill_id: skillId, skill_name: skillName })
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      chip.remove();

      // Если больше нет навыков, показать заглушку
      if (!elems.chipsWrap.querySelector('.chip-skill')) {
        showEmptyNote();
      }

    } catch (e) {
      console.error('skillsManager: remove error', e);
      location.reload();
    } finally {
      if (delBtn) delBtn.disabled = false;
    }
  }

  /**
   * Создать chip элемент для навыка
   * @param {string} skillId - ID навыка
   * @param {string} displayName - Отображаемое имя
   * @returns {HTMLElement} Chip элемент
   */
  function createSkillChip(skillId, displayName) {
    const chip = document.createElement('span');
    chip.className = 'chip chip-skill';
    chip.dataset.skillId = String(skillId || '');
    chip.dataset.skillName = displayName;
    chip.innerHTML = `
      <span class="lbl">${esc(displayName)}</span>
      <button type="button" class="chip-del-btn" title="Убрать навык" aria-label="Убрать навык">
        <i class="bi bi-dash-lg"></i>
      </button>`;
    return chip;
  }

  /**
   * Показать заглушку "нет навыков"
   */
  function showEmptyNote() {
    const note = document.createElement('span');
    note.className = 'skills-empty';
    note.textContent = '';
    elems.chipsWrap.insertBefore(note, elems.addBtn);
  }

  /**
   * Удалить заглушку "нет навыков"
   */
  function removeEmptyNote() {
    elems.chipsWrap.querySelector('.skills-empty')?.remove();
  }

  // ===== Event listeners =====

  // Обработка отправки формы
  elems.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = elems.form.querySelector('input[name="skill_name"]');
    const skillName = (input?.value || '').trim();
    await addSkill(skillName);
  });

  // Обработка удаления навыка
  elems.chipsWrap.addEventListener('click', async (e) => {
    const delBtn = e.target.closest('.chip-del-btn');
    if (!delBtn) return;

    const chip = delBtn.closest('.chip-skill');
    if (!chip) return;

    await removeSkill(chip);
  });

  console.log('skillsManager: initialized');

  // Публичный API
  return {
    addSkill,
    refresh: () => location.reload()
  };
}
