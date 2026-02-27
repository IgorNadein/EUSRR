# План улучшения чатов /messages

**Дата:** 25 февраля 2026  
**Цель:** Улучшить приложение /messages, используя лучшие практики из /messages-chatscope

---

## Текущие проблемы /messages

### ❌ Нет WebSocket real-time обновлений
- Сообщения обновляются только при ручном обновлении страницы
- Нет синхронизации между вкладками
- Редактирование/удаление не отображается в реальном времени

### ❌ Нет индикатора "печатает..."
- Непонятно, печатает ли собеседник ответ

### ❌ Оптимистичные обновления без подтверждения
- Добавляет сообщение в UI сразу после отправки
- Если запрос упадет, сообщение останется в UI (нет rollback)

### ✅ Что работает хорошо
- Реакции на сообщения
- Редактирование сообщений
- Цитирование (reply_to)
- Прикрепление файлов
- Предпросмотр медиа
- Эмодзи пикер
- Бесконечная прокрутка (pagination)

---

## Что есть в /messages-chatscope

### ✅ WebSocket real-time обновления
```typescript
const ws = new WebSocket('ws://localhost:9000/ws/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'chat_message') {
    setMessages(prev => [...prev, data.payload]);
  }
  else if (data.type === 'chat_message_edited') {
    setMessages(prev => prev.map(m => 
      m.id === data.payload.id ? { ...m, ...data.payload } : m
    ));
  }
  else if (data.type === 'chat_message_deleted') {
    setMessages(prev => prev.filter(m => m.id !== data.message_id));
  }
  else if (data.type === 'chat_user_typing') {
    setTyping(true);
    setTimeout(() => setTyping(false), 3000);
  }
};
```

### ✅ Индикатор "печатает..."
```typescript
const handleTyping = () => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ action: 'typing' }));
  }
};

// В UI:
{typing && <TypingIndicator content="Собеседник печатает..." />}
```

### ✅ WebSocket-first подход
- Отправляет через REST API
- Получает подтверждение через WebSocket
- Нет оптимистичных обновлений (надежнее)

---

## План улучшений

### Этап 1: Добавить WebSocket (HIGH PRIORITY) 🔥

**Цель:** Добавить real-time обновления без удаления существующего функционала

**Задачи:**
1. ✅ Создать хук `useWebSocket` для переиспользования
2. ✅ Подключить WebSocket к чату при открытии
3. ✅ Обрабатывать события:
   - `chat_message` - новое сообщение
   - `chat_message_edited` - редактирование
   - `chat_message_deleted` - удаление
   - `chat_user_typing` - печатает
4. ✅ Отключать WebSocket при закрытии чата
5. ✅ Переподключение при разрыве соединения

**Файлы для изменения:**
- `frontend/src/hooks/useWebSocket.ts` (новый)
- `frontend/src/app/messages/[chatId]/page.tsx` (добавить хук)

**Время:** ~2-3 часа

---

### Этап 2: Индикатор "печатает..." (MEDIUM PRIORITY)

**Цель:** Показывать когда собеседник печатает

**Задачи:**
1. ✅ Отправлять событие `typing` при вводе текста
2. ✅ Обрабатывать `chat_user_typing` от других пользователей
3. ✅ Добавить UI компонент "печатает..."
4. ✅ Таймаут 3 секунды без активности

**Файлы для изменения:**
- `frontend/src/app/messages/[chatId]/page.tsx` (UI + логика)
- `frontend/src/components/TypingIndicator.tsx` (новый)

**Время:** ~1 час

---

### Этап 3: Улучшить отправку сообщений (LOW PRIORITY)

**Цель:** Более надежная доставка

**Задачи:**
1. ✅ Убрать оптимистичное добавление сообщения
2. ✅ Добавить loading состояние для отправляемого сообщения
3. ✅ Показывать "Отправка..." пока сообщение не подтверждено
4. ✅ Добавлять сообщение только после WebSocket события

**Альтернатива:** Оставить оптимистичное + добавить rollback при ошибке

**Файлы для изменения:**
- `frontend/src/app/messages/[chatId]/page.tsx`

**Время:** ~1-2 часа

---

### Этап 4: Синхронизация между вкладками (NICE TO HAVE)

**Цель:** Все открытые вкладки с одним чатом синхронизированы

**Решение:** WebSocket автоматически решает эту проблему ✅

---

## Архитектура решения

### useWebSocket Hook

```typescript
// frontend/src/hooks/useWebSocket.ts

export function useWebSocket(chatId: number | null) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  
  const handlers = useRef({
    onMessage: (data: any) => {},
    onTyping: (userId: number) => {},
    onError: (error: Event) => {},
  });
  
  useEffect(() => {
    if (!chatId) return;
    
    const ws = new WebSocket(`ws://localhost:9000/ws/`);
    wsRef.current = ws;
    
    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({
        action: 'open_chat',
        chat_id: chatId,
        load_history: false
      }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handlers.current.onMessage(data);
    };
    
    ws.onclose = () => setIsConnected(false);
    ws.onerror = handlers.current.onError;
    
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'close_chat', chat_id: chatId }));
      }
      ws.close();
    };
  }, [chatId]);
  
  const sendTyping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'typing' }));
    }
  }, []);
  
  return { isConnected, sendTyping, handlers };
}
```

### Использование в /messages

```typescript
export default function MessageDialogPage() {
  const { isConnected, sendTyping, handlers } = useWebSocket(chatId);
  const [typing, setTyping] = useState(false);
  
  // Обработка WebSocket событий
  useEffect(() => {
    handlers.current.onMessage = (data) => {
      if (data.type === 'chat_message') {
        setMessages(prev => uniqueMessagesById([...prev, data.payload]));
      }
      else if (data.type === 'chat_message_edited') {
        setMessages(prev => prev.map(m => 
          m.id === data.payload.id ? { ...m, ...data.payload } : m
        ));
      }
      else if (data.type === 'chat_message_deleted') {
        setMessages(prev => prev.filter(m => m.id !== data.message_id));
      }
      else if (data.type === 'chat_user_typing') {
        if (data.user_id !== user?.id) {
          setTyping(true);
          setTimeout(() => setTyping(false), 3000);
        }
      }
    };
  }, [user?.id]);
  
  // Отправка "печатает..."
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessageText(e.target.value);
    sendTyping(); // Отправляем индикатор
  };
  
  // UI индикатора
  {typing && (
    <div className="mb-2 text-sm text-gray-500 italic">
      Собеседник печатает...
    </div>
  )}
}
```

---

## Риски и меры предосторожности

### ⚠️ Риск: Дублирование сообщений
**Решение:** Использовать `uniqueMessagesById()` при добавлении

### ⚠️ Риск: Потеря соединения
**Решение:** Добавить автоматическое переподключение

### ⚠️ Риск: Конфликт с существующей логикой
**Решение:** Постепенное внедрение, тестирование на каждом этапе

### ⚠️ Риск: Backend не поддерживает все события
**Решение:** Проверить backend WebSocket endpoints перед началом

---

## Тестирование

### Тест-кейсы:

1. ✅ Отправка сообщения отображается у обоих пользователей
2. ✅ Редактирование сообщения обновляется в реальном времени
3. ✅ Удаление сообщения исчезает у всех
4. ✅ Индикатор "печатает..." появляется при вводе
5. ✅ WebSocket переподключается при разрыве
6. ✅ Нет дублирования сообщений
7. ✅ Работает в нескольких вкладках одновременно

---

## Приоритезация

**Неделя 1:** Этап 1 (WebSocket) + Этап 2 (Typing indicator)  
**Неделя 2:** Этап 3 (Улучшение отправки) + Тестирование  
**Неделя 3:** Bugfixes + Оптимизация

---

## Дополнительные улучшения (будущее)

- 🔄 Показывать статус доставки сообщения (отправлено/доставлено/прочитано)
- 📎 Drag & drop для файлов
- 🖼️ Галерея медиа из чата
- 🔍 Поиск по сообщениям
- 📌 Закрепленные сообщения
- 🔊 Звуковые уведомления о новых сообщениях
- 💾 Офлайн режим с кешированием
- ⚡ Оптимизация производительности для больших чатов (виртуализация списка)
