/**
 * positionManager.js
 * Управление должностями в форме редактирования сотрудника
 * Функции: создание, редактирование, назначение должностей
 * 
 * @module positionManager
 * @version 1.0.0
 */

/**
 * Инициализация менеджера должностей
 */
export function initPositionManager(options = {}) {
  const form = document.getElementById('apiEditForm');
  const block = document.getElementById('positionBlock');
  if (!form || !block) {
    return null; // Тихий выход, если элементы не найдены
  }

  const select = document.getElementById('f_position');
  const csrftoken = form.querySelector('input[name=csrfmiddlewaretoken]')?.value || '';
  const createUrl = block.dataset.createUrl || '';
  const assignUrl = block.dataset.assignUrl || '';
  const canAssign = block.dataset.canAssign === '1';

  function busy(btn, on) {
    const lbl = btn.querySelector('.lbl');
    const sp = btn.querySelector('.spinner-border');
    if (on) {
      btn.setAttribute('disabled', '');
      sp?.classList.remove('d-none');
      lbl?.classList.add('visually-hidden');
    } else {
      btn.removeAttribute('disabled');
      sp?.classList.add('d-none');
      lbl?.classList.remove('visually-hidden');
    }
  }

  function msg(el, text, ok) {
    if (!el) return;
    el.textContent = text || '';
    el.classList.toggle('d-none', !text);
    el.classList.toggle('text-success', !!ok);
    el.classList.toggle('text-danger', !ok);
  }

  // Создание новой должности
  document.getElementById('posCreateBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('posCreateBtn');
    const m = document.getElementById('posCreateMsg');
    msg(m, '');

    if (!createUrl || !assignUrl) {
      msg(m, 'Не настроены URL создания/назначения.', false);
      return;
    }

    const name = (document.getElementById('pos_name')?.value || '').trim();
    const description = (document.getElementById('pos_desc')?.value || '').trim();
    if (!name) {
      msg(m, 'Укажите название должности.', false);
      return;
    }

    let groupIds = [];
    if (canAssign) {
      const msel = document.getElementById('pos_groups');
      const hid = document.getElementById('pos_groups_hidden');
      const csv = document.getElementById('pos_groups_csv');

      if (msel) groupIds = Array.from(msel.selectedOptions).map((o) => o.value).filter(Boolean);
      else if (hid) groupIds = (hid.value || '').split(',').map((s) => s.trim()).filter(Boolean);
      else if (csv) groupIds = (csv.value || '').split(',').map((s) => s.trim()).filter(Boolean);

      groupIds = groupIds.map((id) => Number(id)).filter((n) => !Number.isNaN(n));
    }

    busy(btn, true);
    try {
      // 1) Создаём должность
      const createPayload = { name, description };
      if (canAssign && groupIds.length) createPayload.groups = groupIds;

      const cResp = await fetch(createUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify(createPayload)
      });
      const cData = await (async () => {
        try {
          return await cResp.json();
        } catch {
          return null;
        }
      })();
      if (!cResp.ok) {
        msg(m, cData?.detail || JSON.stringify(cData) || `HTTP ${cResp.status}`, false);
        return;
      }
      const newId = cData?.id;
      if (!newId) {
        msg(m, 'API не вернул id новой должности.', false);
        return;
      }

      // 2) Назначаем сотруднику
      const eResp = await fetch(assignUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({ position_id: newId })
      });
      const eData = await (async () => {
        try {
          return await eResp.json();
        } catch {
          return null;
        }
      })();
      if (!eResp.ok) {
        msg(
          m,
          'Создано, но не назначено: ' + (eData?.detail || JSON.stringify(eData) || `HTTP ${eResp.status}`),
          false
        );
        return;
      }

      // 3) Обновляем селект и закрываем панель
      if (select) {
        let opt = Array.from(select.options).find((o) => o.value == String(newId));
        if (!opt) {
          opt = document.createElement('option');
          opt.value = String(newId);
          opt.textContent = cData?.name || 'Должность #' + newId;
          select.appendChild(opt);
        }
        select.value = String(newId);
        select.dataset.init = String(newId);
      }
      msg(m, 'Должность создана и назначена.', true);
      try {
        if (window.bootstrap)
          new bootstrap.Collapse(document.getElementById('newPositionPane'), { toggle: false }).hide();
      } catch (_) {}
    } catch (ex) {
      console.error(ex);
      msg(m, 'Неожиданная ошибка при создании/назначении.', false);
    } finally {
      busy(btn, false);
    }
  });

  // Редактирование существующей должности
  const updateTpl = block.dataset.updateUrlTpl || '';
  const detailTpl = block.dataset.detailUrlTpl || '';

  function buildUrlFromTpl(tpl, id) {
    if (!tpl) return '';
    if (tpl.includes('/0/')) return tpl.replace('/0/', `/${id}/`);
    if (tpl.endsWith('0')) return tpl.slice(0, -1) + id;
    return tpl.replace('0', String(id));
  }

  function buildUpdateUrl(posId) {
    return buildUrlFromTpl(updateTpl, posId);
  }
  function buildDetailUrl(posId) {
    return buildUrlFromTpl(detailTpl, posId);
  }

  async function loadPositionDetail(posId) {
    const msgBox = document.getElementById('posEditMsg');
    const loadBtn = document.getElementById('posEditLoadBtn');
    const nameInp = document.getElementById('pos_edit_name');
    const descInp = document.getElementById('pos_edit_desc');

    function showMsg(text, ok) {
      msgBox.textContent = text || '';
      msgBox.classList.toggle('d-none', !text);
      msgBox.classList.toggle('text-success', !!ok);
      msgBox.classList.toggle('text-danger', !ok);
    }

    if (!posId) {
      showMsg('Выберите должность в выпадающем списке.', false);
      return;
    }
    const url = buildDetailUrl(posId);
    if (!url) {
      showMsg('Не настроен URL detail-вьюхи должности.', false);
      return;
    }

    showMsg('', true);
    busy(loadBtn, true);
    try {
      const resp = await fetch(url, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
      });
      const data = await (async () => {
        try {
          return await resp.json();
        } catch {
          return null;
        }
      })();
      if (!resp.ok) {
        showMsg(data?.detail || `Не удалось загрузить должность (HTTP ${resp.status})`, false);
        return;
      }

      nameInp && (nameInp.value = data?.name || '');
      descInp && (descInp.value = data?.description || '');

      if (canAssign) {
        const groupsRaw = Array.isArray(data?.groups)
          ? data.groups
          : Array.isArray(data?.groups_ids)
          ? data.groups_ids
          : [];
        const ids = groupsRaw
          .map((x) => (typeof x === 'number' ? String(x) : String(x?.id || x)))
          .filter(Boolean);
        const hidden = document.getElementById('pos_edit_groups_hidden');
        if (hidden) {
          hidden.value = ids.join(',');
          // Trigger render chips if function exists
          if (typeof window.renderPositionChips === 'function') {
            window.renderPositionChips();
          }
        }
      }
      showMsg('Данные должности загружены.', true);
    } catch (_) {
      showMsg('Ошибка загрузки должности.', false);
    } finally {
      busy(loadBtn, false);
    }
  }

  async function savePositionChanges() {
    const msgBox = document.getElementById('posEditMsg');
    const saveBtn = document.getElementById('posEditSaveBtn');
    const nameInp = document.getElementById('pos_edit_name');
    const descInp = document.getElementById('pos_edit_desc');
    const hidden = document.getElementById('pos_edit_groups_hidden');

    function showMsg(text, ok) {
      msgBox.textContent = text || '';
      msgBox.classList.toggle('d-none', !text);
      msgBox.classList.toggle('text-success', !!ok);
      msgBox.classList.toggle('text-danger', !ok);
    }

    const posId = Number(select.value || 0);
    if (!posId) {
      showMsg('Сначала выберите должность, которую хотите редактировать.', false);
      return;
    }
    const updateUrl = buildUpdateUrl(posId);
    if (!updateUrl) {
      showMsg('Не настроен URL обновления должности.', false);
      return;
    }

    const payload = {};
    const nm = (nameInp?.value || '').trim();
    const ds = (descInp?.value || '').trim();
    if (nm) payload.name = nm;
    payload.description = ds;
    if (canAssign) {
      const csv = (hidden?.value || '').trim();
      const ids = csv ? csv.split(',').map((s) => s.trim()).filter(Boolean) : [];
      const groups = ids.map((x) => Number(x)).filter((n) => !Number.isNaN(n));
      payload.groups = groups;
    }

    showMsg('', true);
    busy(saveBtn, true);
    try {
      const resp = await fetch(updateUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrftoken
        },
        body: JSON.stringify(payload)
      });
      const data = await (async () => {
        try {
          return await resp.json();
        } catch {
          return null;
        }
      })();
      if (!resp.ok) {
        showMsg(data?.detail || `Не удалось сохранить (HTTP ${resp.status})`, false);
        return;
      }

      if (payload.name) {
        const opt = Array.from(select.options).find((o) => o.value == String(posId));
        if (opt) opt.textContent = payload.name;
      }

      try {
        if (window.bootstrap)
          new bootstrap.Collapse(document.getElementById('editPositionPane'), { toggle: false }).hide();
      } catch (_) {}
      showMsg('Изменения сохранены.', true);
    } catch (_) {
      showMsg('Ошибка сохранения изменений.', false);
    } finally {
      busy(saveBtn, false);
    }
  }

  document.getElementById('toggleEditPositionBtn')?.addEventListener('click', () => {
    const posId = Number(select.value || 0);
    if (posId) setTimeout(() => loadPositionDetail(posId), 150);
    else {
      const msgBox = document.getElementById('posEditMsg');
      msgBox.textContent = 'Выберите должность в выпадающем списке.';
      msgBox.classList.remove('d-none');
      msgBox.classList.add('text-danger');
    }
  });

  document.getElementById('posEditLoadBtn')?.addEventListener('click', () =>
    loadPositionDetail(Number(select.value || 0))
  );
  document.getElementById('posEditSaveBtn')?.addEventListener('click', savePositionChanges);

  return {
    loadPosition: loadPositionDetail,
    savePosition: savePositionChanges
  };
}
