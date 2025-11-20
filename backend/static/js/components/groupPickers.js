/**
 * groupPickers.js
 * Управление выбором групп с чипсами и модальными окнами
 * Используется в формах создания/редактирования должностей и сотрудников
 * 
 * @module groupPickers
 * @version 1.0.0
 */

/**
 * Инициализация пикера групп для создания должности
 */
export function initPositionGroupPicker() {
  const chipsBox = document.getElementById('pos_groups_chips');
  const hiddenInp = document.getElementById('pos_groups_hidden');
  const listBox = document.getElementById('groupsList');
  const searchInp = document.getElementById('groupsSearch');
  const clearBtn = document.getElementById('groupsClear');
  const doneBtn = document.getElementById('groupsDone');

  if (!listBox || !hiddenInp) {
    return null; // Тихий выход, если элементы не найдены
  }

  // Текущее множество выбранных id
  const sel = new Set(
    (hiddenInp.value || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  );

  // Рендер чипсов
  function renderChips() {
    if (!chipsBox) return;
    chipsBox.innerHTML = '';
    if (sel.size === 0) {
      return;
    }
    // Соберём карту id->название из списка
    const nameById = {};
    listBox.querySelectorAll('.group-check').forEach((ch) => {
      nameById[ch.value] =
        ch.closest('.list-group-item').querySelector('span.flex-grow-1')?.textContent ||
        '#' + ch.value;
    });
    for (const id of sel) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.dataset.id = id;
      chip.innerHTML = `${nameById[id] || '#' + id} <button type="button" class="btn btn-sm p-0 ms-1" aria-label="Удалить" style="line-height:1;">×</button>`;
      chipsBox.appendChild(chip);
    }
  }

  // Синхронизация чекбоксов ↔ выбранные
  function syncChecksFromSel() {
    listBox.querySelectorAll('.group-check').forEach((ch) => {
      ch.checked = sel.has(ch.value);
    });
  }

  function syncSelFromChecks() {
    sel.clear();
    listBox.querySelectorAll('.group-check:checked').forEach((ch) => sel.add(ch.value));
  }

  function saveHidden() {
    hiddenInp.value = Array.from(sel).join(',');
  }

  // Интерактив: клик по чекбоксу
  listBox.addEventListener('change', (e) => {
    const ch = e.target.closest('.group-check');
    if (!ch) return;
    if (ch.checked) sel.add(ch.value);
    else sel.delete(ch.value);
  });

  // Фильтр
  searchInp?.addEventListener('input', () => {
    const q = (searchInp.value || '').toLowerCase().trim();
    listBox.querySelectorAll('.list-group-item').forEach((row) => {
      const name = row.querySelector('.flex-grow-1')?.textContent.toLowerCase() || '';
      const id = row.querySelector('.group-check')?.value || '';
      row.classList.toggle('d-none', !(name.includes(q) || id.includes(q)));
    });
  });

  // Сброс
  clearBtn?.addEventListener('click', () => {
    sel.clear();
    syncChecksFromSel();
    renderChips();
    saveHidden();
  });

  // Готово
  doneBtn?.addEventListener('click', () => {
    syncSelFromChecks();
    renderChips();
    saveHidden();
  });

  // Удаление из чипса
  chipsBox?.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    const chip = btn?.closest('.chip');
    if (!chip) return;
    sel.delete(chip.dataset.id);
    renderChips();
    syncChecksFromSel();
    saveHidden();
  });

  // Инициализация
  renderChips();
  syncChecksFromSel();

  // Связь с кнопкой "Создать и назначить"
  const posCreateBtn = document.getElementById('posCreateBtn');
  if (posCreateBtn) {
    posCreateBtn.addEventListener(
      'click',
      () => {
        if (hiddenInp) {
          posCreateBtn.dataset.groupsSelected = hiddenInp.value;
        }
      },
      { capture: true }
    );
  }

  // Переместим модал в body (важно для правильного z-index)
  const modal = document.getElementById('groupsPickerModal');
  if (modal) {
    console.log('groupPicker: moving modal to body, current parent:', modal.parentNode.nodeName);
    // Проверяем, что модал еще не перемещен
    if (modal.parentNode !== document.body) {
      document.body.appendChild(modal);
      console.log('groupPicker: modal moved to body');
    } else {
      console.log('groupPicker: modal already in body');
    }
    // Убедимся, что у модала правильные атрибуты
    if (!modal.hasAttribute('data-bs-backdrop')) {
      modal.setAttribute('data-bs-backdrop', 'true');
    }
    if (!modal.hasAttribute('data-bs-keyboard')) {
      modal.setAttribute('data-bs-keyboard', 'true');
    }
  } else {
    console.warn('groupPicker: modal #groupsPickerModal not found');
  }

  return {
    renderChips,
    getSelectedIds: () => Array.from(sel)
  };
}

/**
 * Инициализация пикера групп для редактирования должности
 */
export function initPositionEditGroupPicker() {
  const chipsBox = document.getElementById('pos_edit_groups_chips');
  const hidden = document.getElementById('pos_edit_groups_hidden');
  const listBox = document.getElementById('posEditGroupsList');
  const search = document.getElementById('posEditGroupsSearch');
  const clearBtn = document.getElementById('posEditGroupsClear');
  const doneBtn = document.getElementById('posEditGroupsDone');
  const clearGroupsBtn = document.getElementById('posEditClearGroups');

  if (!listBox || !hidden) {
    return null; // Тихий выход, если элементы не найдены
  }

  // Переместим модал в body (важно для правильного z-index)
  const modalEl = document.getElementById('posEditGroupsPickerModal');
  if (modalEl) {
    console.log('editGroupPicker: moving modal to body, current parent:', modalEl.parentNode.nodeName);
    if (modalEl.parentNode !== document.body) {
      document.body.appendChild(modalEl);
      console.log('editGroupPicker: modal moved to body');
    } else {
      console.log('editGroupPicker: modal already in body');
    }
    // Убедимся, что у модала правильные атрибуты
    if (!modalEl.hasAttribute('data-bs-backdrop')) {
      modalEl.setAttribute('data-bs-backdrop', 'true');
    }
    if (!modalEl.hasAttribute('data-bs-keyboard')) {
      modalEl.setAttribute('data-bs-keyboard', 'true');
    }
  } else {
    console.warn('editGroupPicker: modal #posEditGroupsPickerModal not found');
  }

  function currentIds() {
    const v = (hidden?.value || '').trim();
    return v
      ? v
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      : [];
  }

  function setIds(ids) {
    if (hidden) hidden.value = (ids || []).join(',');
    renderChips();
    syncChecksFromHidden();
  }

  function renderChips() {
    if (!chipsBox) return;
    chipsBox.innerHTML = '';
    const ids = currentIds();
    if (!ids.length) return;
    const nameById = {};
    listBox?.querySelectorAll('.pos-edit-group-check').forEach((ch) => {
      const nm =
        ch.closest('.list-group-item')?.querySelector('.flex-grow-1')?.textContent || '#' + ch.value;
      nameById[ch.value] = nm;
    });
    ids.forEach((id) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.dataset.id = id;
      chip.innerHTML = `${nameById[id] || '#' + id} <button type="button" class="btn btn-sm p-0 ms-1" aria-label="Удалить" style="line-height:1;">×</button>`;
      chipsBox.appendChild(chip);
    });
  }

  chipsBox?.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    const chip = btn?.closest('.chip');
    if (!chip) return;
    const ids = new Set(currentIds());
    ids.delete(chip.dataset.id);
    setIds(Array.from(ids));
  });

  function syncChecksFromHidden() {
    const ids = new Set(currentIds());
    listBox?.querySelectorAll('.pos-edit-group-check').forEach((ch) => (ch.checked = ids.has(ch.value)));
  }

  function syncHiddenFromChecks() {
    const ids = [];
    listBox?.querySelectorAll('.pos-edit-group-check:checked').forEach((ch) => ids.push(ch.value));
    setIds(ids);
  }

  search?.addEventListener('input', () => {
    const q = (search.value || '').toLowerCase().trim();
    listBox?.querySelectorAll('.list-group-item').forEach((row) => {
      const name = row.querySelector('.flex-grow-1')?.textContent.toLowerCase() || '';
      const id = row.querySelector('.pos-edit-group-check')?.value || '';
      row.classList.toggle('d-none', !(name.includes(q) || id.includes(q)));
    });
  });

  clearBtn?.addEventListener('click', () => {
    listBox?.querySelectorAll('.pos-edit-group-check').forEach((ch) => (ch.checked = false));
    setIds([]);
  });

  doneBtn?.addEventListener('click', syncHiddenFromChecks);
  clearGroupsBtn?.addEventListener('click', () => setIds([]));

  // Expose render function globally for position manager
  window.renderPositionChips = renderChips;

  return {
    renderChips,
    setIds,
    getIds: currentIds
  };
}
