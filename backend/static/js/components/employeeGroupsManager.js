/**
 * employeeGroupsManager.js
 * Управление членством сотрудника в группах (добавление, удаление, создание, удаление групп)
 * 
 * @module employeeGroupsManager
 * @version 1.0.0
 */

/**
 * Инициализация менеджера групп сотрудника
 * @param {Object} options - Опции конфигурации
 * @param {string} options.employeeId - ID сотрудника
 * @param {string} options.bulkAddUrl - URL для массового добавления
 * @param {string} options.bulkRemoveUrl - URL для массового удаления
 * @param {string} options.createGroupUrl - URL для создания группы
 * @param {string} options.deleteGroupUrl - URL для удаления группы
 */
export function initEmployeeGroupsManager(options = {}) {
  // Элементы
  const elems = {
    assignBtn: document.getElementById('empGroupsAssignBtn'),
    removeBtn: document.getElementById('empGroupsRemoveBtn'),
    createBtn: document.getElementById('empGroupsCreateBtn'),
    deleteBtn: document.getElementById('empGroupsDeleteBtn'),
    msg: document.getElementById('empGroupsMsg'),
    createMsg: document.getElementById('empGroupsCreateMsg'),
    deleteMsg: document.getElementById('empGroupsDeleteMsg'),
    groupsList: document.getElementById('empGroupsList'),
    assignedList: document.getElementById('empGroupsAssigned'),
    searchInput: document.getElementById('empGroupsSearch'),
    clearBtn: document.getElementById('empGroupsClear'),
    doneBtn: document.getElementById('empGroupsDone'),
    createNameInput: document.getElementById('empGroupsCreateName'),
    deleteSelect: document.getElementById('empGroupsDeleteSelect')
  };

  // Если основных элементов нет - функционал не используется на этой странице
  if (!elems.assignBtn && !elems.groupsList) {
    console.log('employeeGroupsManager: skip (no elements)');
    return null;
  }

  console.log('employeeGroupsManager: initializing with elements:', {
    assignBtn: !!elems.assignBtn,
    groupsList: !!elems.groupsList,
    assignedList: !!elems.assignedList
  });

  // Конфигурация из data-атрибутов блока
  const block = document.getElementById('empGroupsBlock');
  const config = {
    bulkUrl: options.bulkUrl || block?.dataset.bulkUrl || '',
    createGroupUrl: options.createGroupUrl || block?.dataset.createUrl || '',
    deleteGroupUrl: options.deleteGroupUrl || block?.dataset.deleteUrl || ''
  };

  if (!config.bulkUrl) {
    console.warn('employeeGroupsManager: bulkUrl not configured');
  }

  // ===== Helpers =====

  function busy(btn, on) {
    if (!btn) return;
    btn.disabled = on;
    const spinner = btn.querySelector('.spinner-border');
    if (spinner) {
      spinner.classList.toggle('d-none', !on);
    }
  }

  function showMsg(text, success = true, targetElem = elems.msg) {
    if (!targetElem) return;
    targetElem.textContent = text;
    targetElem.className = success ? 'alert alert-success mt-2' : 'alert alert-danger mt-2';
    targetElem.classList.remove('d-none');
    setTimeout(() => targetElem.classList.add('d-none'), 4000);
  }

  // Получить выбранные ID из модального окна
  function selectedIds() {
    const checks = elems.groupsList?.querySelectorAll('.emp-group-check:checked') || [];
    return Array.from(checks).map((ch) => ch.value);
  }

  // Получить карту имен групп
  function getGroupNames() {
    const nameById = {};
    const checks = elems.groupsList?.querySelectorAll('.emp-group-check') || [];
    checks.forEach((ch) => {
      nameById[ch.value] = ch.dataset.cn || `#${ch.value}`;
    });
    return nameById;
  }

  // Сбросить выбор в модале
  function clearSelection() {
    const checks = elems.groupsList?.querySelectorAll('.emp-group-check') || [];
    checks.forEach((ch) => (ch.checked = false));
  }

  async function postJSON(url, body) {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfInput?.value || ''
      },
      body: JSON.stringify(body)
    });
    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(txt || resp.statusText);
    }
    return await resp.json();
  }

  // ===== Pills rendering =====

  function addAssignedBadges(groupIds, groupNames = {}) {
    if (!elems.assignedList || !groupIds.length) return;
    
    // Удалим "Нет персональных групп" если есть
    const emptyMsg = elems.assignedList.querySelector('.text-secondary.small');
    if (emptyMsg) emptyMsg.remove();
    
    groupIds.forEach((gid) => {
      const existing = elems.assignedList.querySelector(`[data-gid="${gid}"]`);
      if (existing) return; // уже есть

      const badge = document.createElement('span');
      badge.className = 'badge rounded-pill bg-primary-subtle text-primary-emphasis border';
      badge.dataset.gid = gid;
      badge.textContent = groupNames[gid] || `#${gid}`;
      elems.assignedList.appendChild(badge);
    });
  }

  function removeAssignedBadges(groupIds) {
    if (!elems.assignedList) return;
    groupIds.forEach((gid) => {
      const badge = elems.assignedList.querySelector(`[data-gid="${gid}"]`);
      if (badge) badge.remove();
    });
    
    // Если больше нет badges, покажем "Нет персональных групп"
    if (!elems.assignedList.querySelector('[data-gid]')) {
      const emptyMsg = document.createElement('span');
      emptyMsg.className = 'text-secondary small';
      emptyMsg.textContent = 'Нет персональных групп';
      elems.assignedList.appendChild(emptyMsg);
    }
  }

  // ===== Assign/Remove groups =====

  async function assignGroups() {
    const ids = selectedIds();
    if (!ids.length) {
      showMsg('Не выбрано ни одной группы', false);
      return;
    }

    if (!config.bulkUrl) {
      showMsg('URL не настроен', false);
      return;
    }

    busy(elems.assignBtn, true);
    try {
      const data = await postJSON(config.bulkUrl, { 
        action: 'add',
        group_ids: ids 
      });
      showMsg(data.message || 'Группы назначены', true);

      // Добавляем badges
      const groupNames = getGroupNames();
      addAssignedBadges(ids, groupNames);
      
      clearSelection();
    } catch (err) {
      showMsg('Ошибка: ' + err.message, false);
    } finally {
      busy(elems.assignBtn, false);
    }
  }

  async function removeGroups() {
    const ids = selectedIds();
    if (!ids.length) {
      showMsg('Не выбрано ни одной группы', false);
      return;
    }

    if (!config.bulkUrl) {
      showMsg('URL не настроен', false);
      return;
    }

    busy(elems.removeBtn, true);
    try {
      const data = await postJSON(config.bulkUrl, { 
        action: 'remove',
        group_ids: ids 
      });
      showMsg(data.message || 'Группы сняты', true);

      removeAssignedBadges(ids);
      clearSelection();
    } catch (err) {
      showMsg('Ошибка: ' + err.message, false);
    } finally {
      busy(elems.removeBtn, false);
    }
  }

  // ===== Create group =====

  async function createGroup() {
    const name = elems.createNameInput?.value.trim();
    if (!name) {
      showMsg('Введите имя группы', false, elems.createMsg);
      return;
    }
    if (!config.createGroupUrl) {
      showMsg('URL создания не настроен', false, elems.createMsg);
      return;
    }

    busy(elems.createBtn, true);
    try {
      const data = await postJSON(config.createGroupUrl, { name });
      showMsg(data.message || 'Группа создана', true, elems.createMsg);
      if (elems.createNameInput) elems.createNameInput.value = '';

      // Перезагрузим страницу через секунду
      setTimeout(() => location.reload(), 1500);
    } catch (err) {
      showMsg('Ошибка: ' + err.message, false, elems.createMsg);
    } finally {
      busy(elems.createBtn, false);
    }
  }

  // ===== Delete group =====

  async function deleteGroup() {
    const gid = elems.deleteSelect?.value;
    if (!gid) {
      showMsg('Выберите группу для удаления', false, elems.deleteMsg);
      return;
    }
    
    const groupName = elems.deleteSelect?.selectedOptions[0]?.textContent || '';
    if (!confirm(`Удалить группу "${groupName}"?`)) return;

    if (!config.deleteGroupUrl) {
      showMsg('URL удаления не настроен', false, elems.deleteMsg);
      return;
    }

    busy(elems.deleteBtn, true);
    try {
      const data = await postJSON(config.deleteGroupUrl, { group_id: gid });
      showMsg(data.message || 'Группа удалена', true, elems.deleteMsg);
      
      // Удалим из селекта
      const option = elems.deleteSelect?.querySelector(`option[value="${gid}"]`);
      if (option) option.remove();
      
      // Перезагрузим страницу через секунду
      setTimeout(() => location.reload(), 1500);
    } catch (err) {
      showMsg('Ошибка: ' + err.message, false, elems.deleteMsg);
    } finally {
      busy(elems.deleteBtn, false);
    }
  }

  // ===== Search in modal =====

  function filterGroups() {
    const query = elems.searchInput?.value.toLowerCase().trim() || '';
    const items = elems.groupsList?.querySelectorAll('.list-group-item') || [];
    
    items.forEach((item) => {
      const text = item.textContent.toLowerCase();
      const match = !query || text.includes(query);
      item.style.display = match ? '' : 'none';
    });
  }

  // ===== Event listeners =====

  elems.assignBtn?.addEventListener('click', assignGroups);
  elems.removeBtn?.addEventListener('click', removeGroups);
  elems.createBtn?.addEventListener('click', createGroup);
  elems.deleteBtn?.addEventListener('click', deleteGroup);
  
  // Поиск в модале
  elems.searchInput?.addEventListener('input', filterGroups);
  
  // Кнопки модала
  elems.clearBtn?.addEventListener('click', clearSelection);
  elems.doneBtn?.addEventListener('click', () => {
    // Просто закрываем модал (Bootstrap сделает это сам через data-bs-dismiss)
  });

  // Переместим модал в body (важно для правильного z-index)
  const modal = document.getElementById('empGroupsPickerModal');
  if (modal) {
    console.log('employeeGroupsManager: moving modal to body, current parent:', modal.parentNode.nodeName);
    if (modal.parentNode !== document.body) {
      document.body.appendChild(modal);
      console.log('employeeGroupsManager: modal moved to body');
    } else {
      console.log('employeeGroupsManager: modal already in body');
    }
    // Убедимся, что у модала правильные атрибуты
    if (!modal.hasAttribute('data-bs-backdrop')) {
      modal.setAttribute('data-bs-backdrop', 'true');
    }
    if (!modal.hasAttribute('data-bs-keyboard')) {
      modal.setAttribute('data-bs-keyboard', 'true');
    }
  } else {
    console.warn('employeeGroupsManager: modal #empGroupsPickerModal not found');
  }

  // Публичный API
  return {
    assign: assignGroups,
    remove: removeGroups,
    createGroup,
    deleteGroup,
    refresh: () => location.reload()
  };
}
