"use client";

import React, { useState, useEffect, useRef } from 'react';
import {
  MainContainer,
  Sidebar,
  Search,
  ConversationList,
  Conversation,
  Avatar,
  ChatContainer,
  ConversationHeader,
  MessageList,
  Message,
  MessageInput,
  MessageSeparator,
  TypingIndicator,
} from '@chatscope/chat-ui-kit-react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import { AppShell } from '@/components/AppShell';
import { apiClient } from '@/lib/api';
import { useUser } from '@/contexts/UserContext';
import type { Chat as ChatType, Message as MessageType } from '@/types/api';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "https://corp.robotail.pro";

function resolveAvatarUrl(url?: string | null): string {
  if (!url) return "";
  if (url.startsWith("data:")) return url;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("//")) return `https:${url}`;
  if (url.startsWith("/") && BACKEND_URL) {
    return `${BACKEND_URL.replace(/\/$/, "")}${url}`;
  }
  if (BACKEND_URL) {
    return `${BACKEND_URL.replace(/\/$/, "")}/${url.replace(/^\/+/, "")}`;
  }
  return url;
}

function getChatTitle(chat: ChatType, currentUserId?: number): string {
  const chatKind = chat.chat_type || chat.type;
  const rawName = (chat.name || "").trim();

  if (chatKind === "direct" || chatKind === "private" || !rawName || rawName.toLowerCase() === "диалог") {
    if (chat.interlocutor?.name?.trim()) {
      return chat.interlocutor.name.trim();
    }

    const detailsOther = (chat.participant_details || []).find((p) => p.id !== currentUserId);
    if (detailsOther?.name?.trim()) {
      return detailsOther.name.trim();
    }

    const participants = (chat.participants || []).filter(
      (p): p is Exclude<typeof p, number> => typeof p === "object" && p !== null
    );
    const other = participants.find((p) => p.id !== currentUserId);
    if (other && typeof other === "object") {
      const name = `${other.last_name || ""} ${other.first_name || ""}`.trim();
      if (name) return name;
      if (other.email) return other.email;
    }
  }

  return rawName || "Диалог";
}

function getChatAvatar(chat: ChatType, currentUserId?: number): string {
  const chatKind = chat.chat_type || chat.type;
  if (chatKind === "direct" || chatKind === "private") {
    if (chat.interlocutor?.avatar) return resolveAvatarUrl(chat.interlocutor.avatar);

    const detailsOther = (chat.participant_details || []).find((p) => p.id !== currentUserId);
    if (detailsOther?.avatar) return resolveAvatarUrl(detailsOther.avatar);

    const participants = (chat.participants || []).filter(
      (p): p is Exclude<typeof p, number> => typeof p === "object" && p !== null
    );
    const other = participants.find((p) => p.id !== currentUserId);
    if (other?.avatar) return resolveAvatarUrl(other.avatar);
  }
  return resolveAvatarUrl(chat.avatar);
}

export default function ChatscapeMessenger() {
  const { user } = useUser();
  const currentUserId = user?.id;

  const [chats, setChats] = useState<ChatType[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [typingTimeout, setTypingTimeout] = useState<NodeJS.Timeout | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  // Загрузка списка чатов
  useEffect(() => {
    const loadChats = async () => {
      try {
        setLoading(true);
        const response = await apiClient.getChats();
        const chatsList = response.results || [];
        setChats(chatsList);

        // Автоматически открываем первый чат
        if (chatsList.length > 0 && !selectedChatId) {
          setSelectedChatId(chatsList[0].id);
        }
      } catch (error) {
        console.error('Error loading chats:', error);
      } finally {
        setLoading(false);
      }
    };

    loadChats();
  }, []);

  // Загрузка сообщений выбранного чата
  useEffect(() => {
    if (!selectedChatId) return;

    const loadMessages = async () => {
      try {
        setMessagesLoading(true);
        const data = await apiClient.getChatMessages(selectedChatId, { limit: 50 });
        setMessages(data.messages || []);
      } catch (error) {
        console.error('Error loading messages:', error);
      } finally {
        setMessagesLoading(false);
      }
    };

    loadMessages();
  }, [selectedChatId]);

  // WebSocket для real-time обновлений
  useEffect(() => {
    if (!selectedChatId) return;

    const ws = new WebSocket('ws://localhost:9000/ws/');
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ WebSocket connected');
      // Открываем чат
      ws.send(JSON.stringify({
        action: 'open_chat',
        chat_id: selectedChatId,
        load_history: false
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('📨 WebSocket message:', data);

      if (data.type === 'chat_message') {
        // Новое сообщение
        setMessages(prev => {
          // Проверяем, нет ли уже такого сообщения
          if (prev.some(m => m.id === data.payload.id)) {
            return prev;
          }
          return [...prev, data.payload];
        });
      } else if (data.type === 'chat_message_edited') {
        // Редактирование
        setMessages(prev =>
          prev.map(m => m.id === data.payload.id ? { ...m, ...data.payload } : m)
        );
      } else if (data.type === 'chat_message_deleted') {
        // Удаление
        setMessages(prev =>
          prev.filter(m => m.id !== data.message_id)
        );
      } else if (data.type === 'chat_user_typing') {
        // Показываем "печатает..."
        if (data.user_id !== currentUserId) {
          setTyping(true);
          if (typingTimeout) clearTimeout(typingTimeout);
          const timeout = setTimeout(() => setTyping(false), 3000);
          setTypingTimeout(timeout);
        }
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('🔌 WebSocket disconnected');
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          action: 'close_chat',
          chat_id: selectedChatId
        }));
      }
      ws.close();
      if (typingTimeout) clearTimeout(typingTimeout);
    };
  }, [selectedChatId, currentUserId]);

  // Отправка индикатора печати
  const handleTyping = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'typing' }));
    }
  };

  // Отправка сообщения
  const handleSend = async (text: string) => {
    if (!selectedChatId || !text.trim() || sending) return;

    try {
      setSending(true);

      // Отправляем через REST API
      await apiClient.sendMessage(selectedChatId, text);

      // WebSocket автоматически добавит сообщение через chat_message event

    } catch (error) {
      console.error('Error sending message:', error);
      alert('Ошибка отправки сообщения');
    } finally {
      setSending(false);
    }
  };

  // Группировка сообщений по датам
  const groupedMessages = messages.reduce((acc, msg, index) => {
    const date = new Date(msg.created_at || '').toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: 'long',
      year: 'numeric'
    });
    const prevDate = index > 0
      ? new Date(messages[index - 1].created_at || '').toLocaleDateString('ru-RU', {
          day: '2-digit',
          month: 'long',
          year: 'numeric'
        })
      : null;

    if (date !== prevDate) {
      acc.push({ type: 'separator', date });
    }
    acc.push({ type: 'message', data: msg });

    return acc;
  }, [] as Array<{ type: 'separator' | 'message'; date?: string; data?: MessageType }>);

  const selectedChat = chats.find(c => c.id === selectedChatId);

  const filteredChats = search
    ? chats.filter(c => {
        const title = getChatTitle(c, currentUserId).toLowerCase();
        return title.includes(search.toLowerCase());
      })
    : chats;

  return (
    <AppShell>
      <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-100 overflow-hidden" style={{ height: '80vh' }}>
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-gray-900">Мессенджер (Chatscope Experiment)</h1>
          <p className="text-sm text-gray-600 mt-1">Экспериментальная версия с @chatscope/chat-ui-kit-react</p>
        </div>

        <MainContainer responsive style={{ height: 'calc(100% - 60px)' }}>
          {/* Боковая панель со списком чатов */}
          <Sidebar position="left" scrollable={false}>
            <Search
              placeholder="Поиск чатов..."
              value={search}
              onChange={(v) => setSearch(v)}
            />

            <ConversationList loading={loading}>
              {filteredChats.map(chat => {
                const title = getChatTitle(chat, currentUserId);
                const avatar = getChatAvatar(chat, currentUserId);
                const lastMessage = chat.last_message?.content || 'Нет сообщений';
                const unreadCount = chat.unread_count || 0;

                return (
                  <Conversation
                    key={chat.id}
                    name={title}
                    lastSenderName={chat.last_message?.author_name}
                    info={lastMessage.length > 50 ? lastMessage.slice(0, 50) + '...' : lastMessage}
                    active={chat.id === selectedChatId}
                    unreadCnt={unreadCount}
                    onClick={() => setSelectedChatId(chat.id)}
                  >
                    <Avatar
                      src={avatar}
                      name={title}
                    />
                  </Conversation>
                );
              })}
            </ConversationList>
          </Sidebar>

          {/* Основной чат */}
          {selectedChat ? (
            <ChatContainer>
              <ConversationHeader>
                <Avatar
                  src={getChatAvatar(selectedChat, currentUserId)}
                  name={getChatTitle(selectedChat, currentUserId)}
                />
                <ConversationHeader.Content
                  userName={getChatTitle(selectedChat, currentUserId)}
                  info={selectedChat.participant_details?.length
                    ? `${selectedChat.participant_details.length} участников`
                    : ''
                  }
                />
              </ConversationHeader>

              <MessageList
                loading={messagesLoading}
                typingIndicator={typing ? <TypingIndicator content="Печатает..." /> : undefined}
              >
                {groupedMessages.map((item, index) => {
                  if (item.type === 'separator') {
                    return (
                      <MessageSeparator key={`sep-${index}`}>
                        {item.date}
                      </MessageSeparator>
                    );
                  }

                  const msg = item.data!;
                  const isOwn = msg.author_id === currentUserId;

                  return (
                    <Message
                      key={msg.id}
                      model={{
                        message: msg.content || '',
                        sender: msg.author_name || 'Неизвестно',
                        direction: isOwn ? 'outgoing' : 'incoming',
                        position: 'single'
                      }}
                    >
                      {!isOwn && msg.author && (
                        <Avatar
                          src={resolveAvatarUrl(msg.author.avatar)}
                          name={msg.author_name || ''}
                          size="sm"
                        />
                      )}

                      {/* Вложения */}
                      {msg.attachments && msg.attachments.length > 0 && (
                        <Message.CustomContent>
                          <div className="mt-2 space-y-2">
                            {msg.attachments.map((att) => {
                              const isImage = att.file_type === 'image' || att.mime_type?.startsWith('image/');
                              return (
                                <div key={att.id}>
                                  {isImage ? (
                                    <img
                                      src={resolveAvatarUrl(att.file_url)}
                                      alt={att.file_name}
                                      className="max-w-xs rounded shadow"
                                    />
                                  ) : (
                                    <a
                                      href={resolveAvatarUrl(att.file_url)}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-2 text-sky-600 hover:underline text-sm"
                                    >
                                      📎 {att.file_name}
                                    </a>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </Message.CustomContent>
                      )}
                    </Message>
                  );
                })}
              </MessageList>

              <MessageInput
                placeholder="Введите сообщение..."
                onSend={handleSend}
                onChange={handleTyping}
                disabled={sending}
                attachButton={false}
              />
            </ChatContainer>
          ) : (
            <ChatContainer>
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-gray-500">
                  <p className="text-lg font-medium">Выберите чат</p>
                  <p className="text-sm mt-1">Выберите диалог из списка слева</p>
                </div>
              </div>
            </ChatContainer>
          )}
        </MainContainer>
      </div>
    </AppShell>
  );
}
