/**
 * TeamWheel - интерактивный виджет команды отдела с автоскроллом
 * 
 * Визуализирует членов команды в виде вращающегося колеса с 4 колонками,
 * отсортированными разными способами. Поддерживает:
 * - Автоматический скролл с изменением направления
 * - Ручной контроль (мышь/тач/колесико)
 * - Клик по аватару для фокусировки на сотруднике
 * - Fallback на руководителя при пустой команде
 * 
 * @module components/teamWheel
 */

/**
 * Инициализирует TeamWheel виджет
 * 
 * @param {Object} options - Параметры конфигурации
 * @param {string} options.wheelId - ID элемента колеса
 * @param {string} options.dataSourceId - ID элемента с данными членов команды
 * @param {Object} options.fallback - Данные руководителя для fallback
 * @param {string} options.fallback.avatar - URL аватара руководителя
 * @param {string} options.fallback.name - Имя руководителя
 * @param {string} options.fallback.role - Роль руководителя
 * @param {string} options.fallback.email - Email руководителя
 * @returns {void}
 * 
 * @example
 * initTeamWheel({
 *   wheelId: 'teamWheel-123',
 *   dataSourceId: 'teamData-123',
 *   fallback: {
 *     avatar: '/media/avatar.jpg',
 *     name: 'Иванов Иван',
 *     role: 'Руководитель отдела',
 *     email: 'ivanov@example.com'
 *   }
 * });
 */
export function initTeamWheel(options) {
  const {
    wheelId,
    dataSourceId,
    fallback = {}
  } = options;

  const wheel = document.getElementById(wheelId);
  if (!wheel) return;

  const columns = wheel.querySelector('[data-columns]');
  const col1 = columns.querySelector('[data-col="1"]');
  const col2 = columns.querySelector('[data-col="2"]');
  const col3 = columns.querySelector('[data-col="3"]');
  const col4 = columns.querySelector('[data-col="4"]');

  const focus = wheel.querySelector('[data-focus]');
  const fImg = wheel.querySelector('[data-focus-img]');
  const fFallback = wheel.querySelector('[data-focus-fallback]');

  const wrapper = wheel.closest('.team-wrap');
  const hintBox = wrapper ? wrapper.querySelector('[data-hint]') : null;
  const details = wrapper ? wrapper.querySelector('[data-details]') : null;
  const dName = wrapper ? wrapper.querySelector('[data-details-name]') : null;
  const dRole = wrapper ? wrapper.querySelector('[data-details-role]') : null;
  const dMail = wrapper ? wrapper.querySelector('[data-details-email]') : null;

  const arcProg = wheel.querySelector('.arc-prog');

  // Источник данных
  const src = document.getElementById(dataSourceId);
  const members = Array.from(src ? src.children : [])
    .map(n => ({
      id: Number(n.getAttribute('data-id') || '0'),
      name: n.getAttribute('data-name') || '',
      role: n.getAttribute('data-role') || '',
      email: n.getAttribute('data-email') || '',
      avatar: n.getAttribute('data-avatar') || '',
      active: n.getAttribute('data-active') === '1'
    }))
    .filter(m => m.active); // Показываем только активных сотрудников

  // Если никого нет — показываем руководителя
  if (!members.length) {
    showFallback(columns, focus, fImg, fFallback, hintBox, details, dName, dRole, dMail, fallback);
    return;
  }

  // Сортировки для 4 колонок
  const byNameAsc = [...members].sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  const byNameDesc = [...members].sort((a, b) => b.name.localeCompare(a.name, 'ru'));
  const byIdAsc = [...members].sort((a, b) => a.id - b.id);
  const byRoleAsc = [...members].sort((a, b) => {
    const ra = (a.role || '').toLowerCase();
    const rb = (b.role || '').toLowerCase();
    if (ra === rb) return a.name.localeCompare(b.name, 'ru');
    return ra < rb ? -1 : 1;
  });

  fillCol(col1, byNameAsc);
  fillCol(col2, byNameDesc);
  fillCol(col3, byIdAsc);
  fillCol(col4, byRoleAsc);

  // Инициализация автоскролла
  setupAutoScroll(wheel, columns, arcProg, focus, fImg, fFallback, hintBox, details, dName, dRole, dMail);
}

/**
 * Показывает fallback (руководителя) когда команда пуста
 * @private
 */
function showFallback(columns, focus, fImg, fFallback, hintBox, details, dName, dRole, dMail, fallback) {
  columns.classList.add('d-none');
  focus.classList.remove('d-none');

  const { avatar, name, role, email } = fallback;

  if (avatar) {
    fImg.src = avatar;
    fImg.alt = name || 'Руководитель';
    fImg.style.display = 'block';
    fFallback.style.display = 'none';
  } else {
    fImg.removeAttribute('src');
    fImg.style.display = 'none';
    fFallback.style.display = 'block';
  }

  if (hintBox) hintBox.classList.add('d-none');
  if (details) {
    details.classList.remove('d-none');
    if (dName) dName.textContent = name || 'Руководитель';
    if (dRole) dRole.textContent = role || 'Руководитель отдела';
    if (dMail) dMail.textContent = email || '';
  }
}

/**
 * Создает элемент для члена команды
 * @private
 */
function makeItem(member) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'wheel-item';
  btn.setAttribute('data-id', String(member.id));
  btn.setAttribute('data-name', member.name);
  btn.setAttribute('data-role', member.role || '');
  btn.setAttribute('data-email', member.email || '');
  btn.setAttribute('data-avatar', member.avatar || '');

  const inner = document.createElement('span');
  inner.className = 'ava';
  
  if (member.avatar) {
    const img = document.createElement('img');
    img.alt = '';
    img.src = member.avatar;
    inner.appendChild(img);
  } else {
    const ico = document.createElement('i');
    ico.className = 'bi-person';
    inner.appendChild(ico);
  }
  
  btn.appendChild(inner);
  return btn;
}

/**
 * Заполняет колонку элементами (с дублированием для бесконечного скролла)
 * @private
 */
function fillCol(root, arr) {
  root.innerHTML = '';
  // Дублируем для «бесконечной» прокрутки
  for (let k = 0; k < 2; k++) {
    arr.forEach(m => root.appendChild(makeItem(m)));
  }
}

/**
 * Настраивает автоматический скролл с ручным управлением
 * @private
 */
function setupAutoScroll(wheel, columns, arcProg, focus, fImg, fFallback, hintBox, details, dName, dRole, dMail) {
  let vScroll = 0;
  let dir = 1; // 1 -> вниз, -1 -> вверх
  const speed = 0.45; // px/frame
  let hover = false;
  let focused = false;
  let maxY = Math.max(0, columns.scrollHeight - wheel.clientHeight);

  function applyScroll() {
    columns.style.transform = `translateY(${-vScroll}px)`;
    if (maxY <= 0) {
      arcProg.style.strokeDashoffset = 1;
    } else {
      const p = vScroll / maxY; // 0..1
      arcProg.style.strokeDashoffset = (1 - p).toFixed(4);
    }
  }

  function recalc() {
    maxY = Math.max(0, columns.scrollHeight - wheel.clientHeight);
    vScroll = Math.min(vScroll, maxY);
    applyScroll();
  }

  new ResizeObserver(recalc).observe(wheel);
  window.addEventListener('resize', recalc);

  function loop() {
    if (!hover && !focused && maxY > 0) {
      vScroll += dir * speed;
      if (vScroll >= maxY) {
        vScroll = maxY;
        dir = -1; // на нижней границе едем вверх
      } else if (vScroll <= 0) {
        vScroll = 0;
        dir = 1; // цикл завершается только на верхней точке
      }
      applyScroll();
    }
    requestAnimationFrame(loop);
  }

  applyScroll();
  requestAnimationFrame(loop);

  // Hover — пауза автоскролла
  wheel.addEventListener('mouseenter', () => { hover = true; });
  wheel.addEventListener('mouseleave', () => { hover = false; });

  // Ручной скролл колесом
  wheel.addEventListener('wheel', (e) => {
    if (!focused) {
      e.preventDefault();
      vScroll = Math.min(maxY, Math.max(0, vScroll + e.deltaY));
      applyScroll();
    }
  }, { passive: false });

  // Ручной скролл тачем
  let tStartY = null;
  wheel.addEventListener('touchstart', (e) => {
    if (e.touches && e.touches.length) {
      tStartY = e.touches[0].clientY;
    }
  }, { passive: true });

  wheel.addEventListener('touchmove', (e) => {
    if (tStartY != null && !focused) {
      const y = e.touches[0].clientY;
      const dy = tStartY - y;
      vScroll = Math.min(maxY, Math.max(0, vScroll + dy));
      tStartY = y;
      applyScroll();
      e.preventDefault();
    }
  }, { passive: false });

  wheel.addEventListener('touchend', () => { tStartY = null; });

  // Фокус: клик по мини-аве
  columns.addEventListener('click', (e) => {
    const btn = e.target.closest('.wheel-item');
    if (!btn) return;

    const ava = btn.getAttribute('data-avatar') || '';
    const name = btn.getAttribute('data-name') || 'Сотрудник';
    const role = btn.getAttribute('data-role') || '';
    const mail = btn.getAttribute('data-email') || '';

    focused = true;
    columns.classList.add('d-none');
    focus.classList.remove('d-none');

    if (ava) {
      fImg.src = ava;
      fImg.alt = name;
      fImg.style.display = 'block';
      fFallback.style.display = 'none';
    } else {
      fImg.removeAttribute('src');
      fImg.style.display = 'none';
      fFallback.style.display = 'block';
    }

    if (hintBox) hintBox.classList.add('d-none');
    if (details) {
      details.classList.remove('d-none');
      if (dName) dName.textContent = name;
      if (dRole) dRole.textContent = role;
      if (dMail) dMail.textContent = mail;
    }
  });

  // Выход из фокуса — клик по большому кругу
  focus.addEventListener('click', () => {
    focused = false;
    focus.classList.add('d-none');
    columns.classList.remove('d-none');
  });
}

// Backward compatibility - expose to window
if (typeof window !== 'undefined') {
  window.initTeamWheel = initTeamWheel;
}
