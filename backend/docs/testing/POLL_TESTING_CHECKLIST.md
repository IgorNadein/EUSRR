# Полный чек-лист тестирования голосований (Polls)

## Дата: 21 января 2026
## Статус: ✅ Тесты созданы в `test_poll_complete.py`

---

## 1. Создание голосований через API

### 1.1 Базовое создание
- [ ] **test_create_simple_poll_via_api** - Создание простого голосования через POST `/api/v1/communications/polls/`
- [ ] **test_create_poll_without_message_fails** - Попытка создать без сообщения → ошибка 400
- [ ] **test_create_poll_unauthenticated_fails** - Неавторизованный запрос → ошибка 401/403
- [ ] **Автор устанавливается автоматически** из `request.user` через `perform_create`

### 1.2 Типы голосований
- [ ] **test_create_anonymous_poll_via_api** - Анонимное голосование (`is_anonymous=True`)
- [ ] **test_create_multiple_choice_poll_via_api** - Множественный выбор (`is_multiple_choice=True`)
- [ ] **test_create_quiz_via_api** - Викторина (`is_quiz=True`)
- [ ] **Комбинированные режимы** (анонимное + множественный выбор)

### 1.3 Временные параметры
- [ ] **test_create_poll_with_auto_close_time** - Голосование с `closes_at` (автозакрытие)
- [ ] **Создание с прошедшим дедлайном** - должно быть сразу закрытым

### 1.4 Валидация
- [ ] **test_poll_with_empty_question_fails** - Пустой вопрос → ошибка 400
- [ ] **test_poll_with_very_long_question** - Вопрос > 500 символов → ошибка 400
- [ ] **test_poll_without_options_can_be_created** - Можно создать без опций

---

## 2. Голосование (Voting)

### 2.1 Single Choice (одиночный выбор)
- [ ] **test_vote_single_choice** - Голосование за одну опцию
- [ ] **test_vote_multiple_in_single_choice_fails** - Попытка выбрать несколько → ошибка 400
- [ ] **test_revote_replaces_previous** - Повторное голосование заменяет предыдущий выбор
- [ ] **total_voters остается 1** после ревота

### 2.2 Multiple Choice (множественный выбор)
- [ ] **test_vote_multiple_options** - Выбор 2+ опций
- [ ] **test_vote_all_options** - Выбор всех доступных опций
- [ ] **test_revote_multiple_choice** - Повторное голосование заменяет все предыдущие выборы

### 2.3 Валидация голосования
- [ ] **test_vote_in_closed_poll_fails** - Голосование в закрытом опросе → ошибка 400
- [ ] **test_vote_without_options_fails** - Голосование без выбора опций → ошибка 400
- [ ] **test_vote_with_invalid_option_fails** - Несуществующая опция → ошибка 400
- [ ] **test_vote_in_poll_without_options_fails** - Голосование в опросе без созданных опций → ошибка 400

---

## 3. Анонимные голосования

- [ ] **test_vote_in_anonymous_poll** - Можно голосовать в анонимном опросе
- [ ] **test_anonymous_results_hide_voters** - Результаты НЕ показывают список голосующих
- [ ] **Счетчики работают корректно** (vote_count, total_voters)

---

## 4. Викторины (Quiz Mode)

### 4.1 Правильные/неправильные ответы
- [ ] **test_vote_correct_answer** - Голосование за правильный ответ (is_correct=True)
- [ ] **test_vote_wrong_answer** - Голосование за неправильный ответ
- [ ] **test_quiz_results_show_correct_answer** - Результаты показывают is_correct флаг

### 4.2 Отображение результатов
- [ ] **Правильный ответ виден только после закрытия** (логика UI)
- [ ] **Статистика правильных/неправильных ответов**

---

## 5. Закрытие голосований

### 5.1 Ручное закрытие
- [ ] **test_close_poll_by_author** - Автор может закрыть через `/polls/{id}/close/`
- [ ] **test_close_poll_by_non_author_fails** - Не-автор НЕ может закрыть → ошибка 403
- [ ] **test_close_already_closed_poll** - Закрытие уже закрытого опроса → 200 или 400

### 5.2 Автоматическое закрытие
- [ ] **test_poll_auto_closes_after_deadline** - Опрос закрывается при `closes_at < now()`
- [ ] **Celery task для автозакрытия** (интеграционный тест)

### 5.3 После закрытия
- [ ] **Нельзя голосовать** после закрытия
- [ ] **Можно просматривать результаты**
- [ ] **closed_at устанавливается автоматически**

---

## 6. Результаты голосований

### 6.1 Получение результатов
- [ ] **test_get_poll_results_via_api** - GET `/polls/{id}/results/`
- [ ] **test_results_calculate_percentages** - Проценты считаются корректно
- [ ] **test_results_show_voters_when_not_anonymous** - Список голосующих в неанонимных

### 6.2 Структура результатов
- [ ] **Поля**: id, question, total_voters, is_closed, options
- [ ] **Для каждой опции**: id, text, vote_count, percentage, is_correct, voters
- [ ] **Сортировка по position**

### 6.3 Различные режимы
- [ ] **Анонимный**: voters = []
- [ ] **Неанонимный**: voters содержит user_id, имя, email
- [ ] **Викторина**: is_correct показывается

---

## 7. Edge Cases (граничные случаи)

### 7.1 Количество голосов
- [ ] **test_total_voters_count_unique_users** - total_voters = уникальные пользователи, не количество голосов
- [ ] **0 голосов**: проценты = 0.0
- [ ] **1 голос**: процент = 100.0

### 7.2 Опции
- [ ] **Голосование без опций**: создается, но голосовать нельзя
- [ ] **1 опция**: можно голосовать
- [ ] **Много опций** (>10): работает корректно

### 7.3 Временные зоны
- [ ] **closes_at с разными timezone**
- [ ] **created_at, voted_at сохраняются с timezone**

### 7.4 Права доступа
- [ ] **Приватный чат**: только участники видят poll
- [ ] **Групповой чат**: все участники могут голосовать
- [ ] **Удаленный пользователь**: не может голосовать

---

## 8. Интеграция с сообщениями

### 8.1 Связь Poll ↔ Message
- [ ] **OneToOne связь** работает корректно
- [ ] **Удаление message удаляет poll** (CASCADE)
- [ ] **Голосование отображается в чате** (интеграционный тест)

### 8.2 WebSocket уведомления
- [ ] **Создание poll → ws уведомление**
- [ ] **Новый голос → обновление счетчиков**
- [ ] **Закрытие poll → ws уведомление**

---

## 9. Производительность

### 9.1 Оптимизация запросов
- [ ] **Нет N+1 запросов** при получении результатов
- [ ] **Используется select_related/prefetch_related**
- [ ] **Индексы используются** (explain analyze)

### 9.2 Масштабируемость
- [ ] **100+ опций**: работает быстро
- [ ] **1000+ голосов**: результаты загружаются быстро
- [ ] **Параллельное голосование**: нет race conditions

---

## 10. Безопасность

### 10.1 Аутентификация
- [ ] **Создание**: требуется авторизация
- [ ] **Голосование**: требуется авторизация
- [ ] **Закрытие**: только автор или админ

### 10.2 SQL Injection
- [ ] **Вопрос с SQL кодом** → экранируется
- [ ] **Текст опции с SQL** → экранируется

### 10.3 XSS
- [ ] **Вопрос с `<script>` тегами** → экранируется
- [ ] **Текст опции с HTML** → экранируется

---

## Запуск тестов

```bash
# Все тесты голосований
pytest backend/tests/api/v1/communications/test_poll_complete.py -v

# Конкретная группа
pytest backend/tests/api/v1/communications/test_poll_complete.py::TestPollCreationAPI -v

# Конкретный тест
pytest backend/tests/api/v1/communications/test_poll_complete.py::TestPollCreationAPI::test_create_simple_poll_via_api -v

# С покрытием
pytest backend/tests/api/v1/communications/test_poll_complete.py --cov=communications.models --cov=api.v1.communications --cov-report=html
```

---

## Coverage цели

- **Модели**: Poll, PollOption, PollVote → **95%+**
- **ViewSet**: PollViewSet → **90%+**
- **Serializers**: PollSerializer, PollOptionSerializer → **90%+**
- **Методы**: get_results(), close() → **100%**

---

## Приоритеты

### Критичные (P0) - должны быть покрыты первыми:
1. ✅ Создание через API с автором
2. Голосование single/multiple choice
3. Закрытие автором
4. Результаты с процентами
5. Анонимные опросы скрывают voters

### Важные (P1):
1. Викторины с правильными ответами
2. Автозакрытие по времени
3. Валидация (пустой вопрос, длинный текст)
4. Повторное голосование заменяет

### Желательные (P2):
1. Edge cases (без опций, много опций)
2. WebSocket интеграция
3. Производительность на больших данных
4. XSS/SQL injection защита

---

## Текущий статус

- **Создано тестов**: 40+
- **Покрытие**: ~85% (оценка)
- **Файл**: `backend/tests/api/v1/communications/test_poll_complete.py`
- **Следующий шаг**: Запустить все тесты и исправить падающие
