/**
 * Утилиты для построения URL с учетом переменных окружения
 */

export function getBackendUrl(): string {
  if (typeof window === 'undefined') {
    // На сервере используем публичный адрес
    return process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:9000';
  }
  // На клиенте используем публичный URL
  return process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:9000';
}

export function getWebSocketUrl(): string {
  // Если есть прямая переменная для WebSocket - используем её
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  
  const backendUrl = getBackendUrl();
  
  // Преобразуем http(s) в ws(s)
  if (backendUrl.startsWith('https://')) {
    return backendUrl.replace(/^https:\/\//, 'wss://') + '/ws/';
  }
  if (backendUrl.startsWith('http://')) {
    return backendUrl.replace(/^http:\/\//, 'ws://') + '/ws/';
  }
  
  // На случай если URL без протокола
  return `${backendUrl.startsWith('localhost') ? 'ws://' : 'wss://'}${backendUrl}/ws/`;
}

export function resolveMediaUrl(url?: string | null): string {
  const raw = (url || '').trim();
  if (!raw) return '';

  // Если data-URI или полный URL, возвращаем как есть
  if (/^data:/i.test(raw) || /^https?:\/\/|^wss?:\/\//i.test(raw)) {
    return raw;
  }

  const backendBase = getBackendUrl().replace(/\/$/, '');
  
  // Если путь начинается с /, добавляем к base URL
  if (raw.startsWith('/')) {
    return `${backendBase}${raw}`;
  }
  
  // Иначе добавляем слеш
  return `${backendBase}/${raw}`;
}

export function buildApiUrl(endpoint: string): string {
  const base = getBackendUrl().replace(/\/$/, '');
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${base}${path}`;
}
