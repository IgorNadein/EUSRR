"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { MessageCircle, Send, ArrowLeft, Paperclip, X, FileText } from "lucide-react";
import { AppShell } from "../../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { Chat, Message, MessageAttachment } from "@/types/api";
import { useUser } from "@/contexts/UserContext";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

function getChatTitle(chat: Chat): string {
  return chat.name?.trim() || "Диалог";
}

function getChatInitials(chat: Chat): string {
  const title = getChatTitle(chat);
  return (
    title
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() || "")
      .join("") || "Ч"
  );
}

function getMessageInitials(message: Message): string {
  const name = (message.author_name || "").trim();
  if (!name) return "С";
  const parts = name.split(" ").filter(Boolean);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

function formatTime(date?: string): string {
  if (!date) return "";
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function getMessageDate(message: Message): Date | null {
  if (message.created_at) {
    const d = new Date(message.created_at);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  if (message.created_ts) {
    const d = new Date(message.created_ts);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  return null;
}

function formatDayDivider(date: Date): string {
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function messageTime(message: Message): string {
  const d = getMessageDate(message);
  if (!d) return "";

  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) {
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }

  return d.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isSameDay(a: Date | null, b: Date | null): boolean {
  if (!a || !b) return false;
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatFileSize(size?: number): string {
  if (!size || size <= 0) return "";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)} КБ`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} МБ`;
}

function isImageAttachment(att: MessageAttachment): boolean {
  const mime = (att.mime_type || "").toLowerCase();
  const type = (att.file_type || "").toLowerCase();
  const name = (att.file_name || "").toLowerCase();
  const byExt = /\.(png|jpe?g|gif|webp|bmp|svg|avif)$/i.test(name);
  return mime.startsWith("image/") || type === "image" || byExt;
}

function isVideoAttachment(att: MessageAttachment): boolean {
  const mime = (att.mime_type || "").toLowerCase();
  const type = (att.file_type || "").toLowerCase();
  const name = (att.file_name || "").toLowerCase();
  const byExt = /\.(mp4|webm|mov|m4v|avi|mkv|3gp|mpeg|mpg)$/i.test(name);
  return mime.startsWith("video/") || type === "video" || byExt;
}

function isAudioAttachment(att: MessageAttachment): boolean {
  const mime = (att.mime_type || "").toLowerCase();
  const type = (att.file_type || "").toLowerCase();
  return mime.startsWith("audio/") || type === "audio";
}

function resolveAttachmentUrl(url?: string | null): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return encodeURI(url);
  if (url.startsWith("//")) return encodeURI(`https:${url}`);
  if (url.startsWith("/") && BACKEND_URL) {
    return encodeURI(`${BACKEND_URL.replace(/\/$/, "")}${url}`);
  }
  return encodeURI(url);
}

function resolveAvatarUrl(url?: string | null): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return encodeURI(url);
  if (url.startsWith("//")) return encodeURI(`https:${url}`);
  if (url.startsWith("/") && BACKEND_URL) {
    return encodeURI(`${BACKEND_URL.replace(/\/$/, "")}${url}`);
  }
  return encodeURI(url);
}

export default function MessageDialogPage() {
  const params = useParams<{ chatId: string }>();
  const chatId = Number(params.chatId);
  const { user } = useUser();

  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messageText, setMessageText] = useState("");
  const [sending, setSending] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [brokenMedia, setBrokenMedia] = useState<Record<number, boolean>>({});
  const [mediaPreview, setMediaPreview] = useState<{ type: "image" | "video"; src: string; name: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesViewportRef = useRef<HTMLDivElement | null>(null);
  const [initialAnchorId, setInitialAnchorId] = useState<number | null>(null);

  useEffect(() => {
    async function loadChats() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getChats();
        const items = response.results || [];
        setChat(items.find((c) => c.id === chatId) || null);
      } catch (e: any) {
        setError("Не удалось загрузить чат. Проверьте подключение и попробуйте снова.");
      } finally {
        setLoading(false);
      }
    }

    loadChats();
  }, [chatId]);

  useEffect(() => {
    async function loadMessages() {
      if (!chatId || Number.isNaN(chatId) || !chat) {
        setMessages([]);
        setInitialAnchorId(null);
        return;
      }

      try {
        setMessagesLoading(true);
        const around = await apiClient.getChatMessagesAround(chatId, { limit: 40 });
        const aroundMessages = around.messages || [];

        if (aroundMessages.length > 0) {
          setMessages(aroundMessages);
          setInitialAnchorId(around.anchor_id ?? null);
        } else {
          const response = await apiClient.getChatMessages(chatId, { limit: 50 });
          setMessages(response.messages || []);
          setInitialAnchorId(null);
        }
      } catch (e: any) {
        if (String(e?.message || "").includes("403")) {
          setError("Нет доступа к этому чату");
          setMessages([]);
        } else {
          console.error("Ошибка загрузки сообщений:", e);
        }
        setInitialAnchorId(null);
      } finally {
        setMessagesLoading(false);
      }
    }

    loadMessages();
  }, [chatId, chat]);

  useEffect(() => {
    if (messagesLoading || !messagesViewportRef.current || messages.length === 0) return;

    const viewport = messagesViewportRef.current;

    if (initialAnchorId) {
      const el = viewport.querySelector(`[data-message-id="${initialAnchorId}"]`) as HTMLElement | null;
      if (el) {
        el.scrollIntoView({ block: "center" });
        return;
      }
    }

    viewport.scrollTop = viewport.scrollHeight;
  }, [messagesLoading, messages, initialAnchorId]);

  const handleSend = async () => {
    const text = messageText.trim();
    if (!chatId || sending) return;
    if (!text && attachedFiles.length === 0) return;

    try {
      setSending(true);
      const sent = attachedFiles.length
        ? await apiClient.sendMessageWithFiles(chatId, text, attachedFiles)
        : await apiClient.sendMessage(chatId, text);
      setMessages((prev) => [...prev, sent]);
      setMessageText("");
      setAttachedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (e) {
      console.error("Ошибка отправки сообщения:", e);
    } finally {
      setSending(false);
    }
  };

  const handlePickFiles = () => {
    fileInputRef.current?.click();
  };

  const handleFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setAttachedFiles((prev) => [...prev, ...files]);
  };

  const removeAttachedFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMediaPreview(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка чатов...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <div className="sticky top-22 self-start h-[calc(100vh-7.5rem)] overflow-hidden">
        <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
          {chat ? (
            <>
              <header className="mb-4 flex shrink-0 items-center justify-between gap-3 border-b border-gray-100 pb-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                    {chat.avatar ? (
                      <img src={resolveAvatarUrl(chat.avatar)} alt={getChatTitle(chat)} className="h-full w-full object-cover" />
                    ) : (
                      getChatInitials(chat)
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{getChatTitle(chat)}</p>
                    <p className="text-xs text-gray-500">{(chat.type || chat.chat_type) === "group" ? "Групповой чат" : "Диалог"}</p>
                  </div>
                </div>

                <Link
                  href="/messages"
                  aria-label="К списку чатов"
                  title="К списку чатов"
                  className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 transition hover:bg-gray-50 hover:text-sky-700"
                >
                  <ArrowLeft size={16} />
                </Link>
              </header>

              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div ref={messagesViewportRef} className="min-h-0 flex-1 overflow-y-auto rounded-xl bg-gray-50 p-4">
                  {messagesLoading ? (
                    <p className="text-center text-sm text-gray-500">Загрузка сообщений...</p>
                  ) : messages.length === 0 ? (
                    <p className="text-center text-sm text-gray-500">Пока нет сообщений. Напишите первым.</p>
                  ) : (
                    <div className="flex min-h-full flex-col justify-end">
                      {messages.map((message, index) => {
                        const currentDate = getMessageDate(message);
                        const prevDate = index > 0 ? getMessageDate(messages[index - 1]) : null;
                        const showDayDivider = index === 0 || !isSameDay(currentDate, prevDate);

                        const isMine =
                          user?.id &&
                          (message.author_id === user.id || message.author?.id === user.id || message.sender?.id === user.id);

                        return (
                          <div key={message.id} data-message-id={message.id} className="mb-3 last:mb-0">
                            {showDayDivider && currentDate ? (
                              <div className="sticky top-2 z-10 mb-2 text-center">
                                <span className="inline-block rounded-full bg-white/95 px-3 py-1 text-xs text-gray-500 shadow-sm ring-1 ring-gray-200 backdrop-blur">
                                  {formatDayDivider(currentDate)}
                                </span>
                              </div>
                            ) : null}

                            <div className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                              {!isMine ? (
                                <div className="relative mr-2 mt-1 h-8 w-8 shrink-0">
                                  <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-[10px] font-semibold text-white">
                                    {message.avatar || message.author?.avatar ? (
                                      <img
                                        src={resolveAvatarUrl(message.avatar || message.author?.avatar || "")}
                                        alt={message.author_name || "Автор"}
                                        className="h-full w-full object-cover"
                                      />
                                    ) : (
                                      getMessageInitials(message)
                                    )}
                                  </div>
                                  {message.author?.is_active ? (
                                    <span className="absolute -bottom-0.5 -right-0.5 z-10 h-2.5 w-2.5 rounded-full bg-sky-400 ring-2 ring-white" />
                                  ) : null}
                                </div>
                              ) : null}

                              <div
                                className={`max-w-[78%] rounded-2xl px-3 py-2 ${
                                  isMine ? "bg-sky-500 text-white" : "bg-white text-gray-900 ring-1 ring-gray-100"
                                }`}
                              >
                                {!isMine ? (
                                  <p className="mb-1 text-[11px] font-medium text-gray-500">
                                    {message.author_name || message.author?.last_name || message.sender?.last_name || "Сотрудник"}
                                  </p>
                                ) : null}

                                {message.content ? (
                                  <p className="whitespace-pre-wrap text-sm leading-5">{message.content}</p>
                                ) : null}

                                {message.attachments && message.attachments.length > 0 ? (
                                  <div className="mt-2 space-y-2">
                                    {message.attachments.map((att) => (
                                      <div key={att.id}>
                                        {isImageAttachment(att) ? (
                                          <button
                                            type="button"
                                            onClick={() => setMediaPreview({ type: "image", src: resolveAttachmentUrl(att.file_url), name: att.file_name })}
                                            className="block w-full overflow-hidden rounded-lg"
                                          >
                                            <img
                                              src={resolveAttachmentUrl(att.thumbnail || att.file_url)}
                                              alt={att.file_name}
                                              className="max-h-64 w-full rounded-lg object-cover"
                                            />
                                          </button>
                                        ) : isVideoAttachment(att) ? (
                                          brokenMedia[att.id] ? (
                                            <a
                                              href={resolveAttachmentUrl(att.file_url)}
                                              target="_blank"
                                              rel="noreferrer"
                                              className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                                            >
                                              <FileText size={16} className="shrink-0" />
                                              <span className="min-w-0 flex-1 truncate">
                                                Видео не поддерживается в браузере — открыть файл
                                              </span>
                                            </a>
                                          ) : (
                                            <button
                                              type="button"
                                              onClick={() => setMediaPreview({ type: "video", src: resolveAttachmentUrl(att.file_url), name: att.file_name })}
                                              className="block w-full overflow-hidden rounded-lg"
                                            >
                                              <video
                                                preload="metadata"
                                                playsInline
                                                muted
                                                src={resolveAttachmentUrl(att.file_url)}
                                                className="max-h-64 w-full rounded-lg bg-black"
                                                onError={() => setBrokenMedia((prev) => ({ ...prev, [att.id]: true }))}
                                                onLoadedData={() => setBrokenMedia((prev) => ({ ...prev, [att.id]: false }))}
                                              />
                                            </button>
                                          )
                                        ) : isAudioAttachment(att) ? (
                                          <audio
                                            controls
                                            preload="metadata"
                                            className="w-full"
                                            onError={() => setBrokenMedia((prev) => ({ ...prev, [att.id]: true }))}
                                          >
                                            <source src={resolveAttachmentUrl(att.file_url)} type={att.mime_type || "audio/mpeg"} />
                                          </audio>
                                        ) : (
                                          <a
                                            href={resolveAttachmentUrl(att.file_url)}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white/80 px-3 py-2 text-sm text-sky-700 hover:bg-white"
                                          >
                                            <FileText size={16} className="shrink-0" />
                                            <span className="min-w-0 flex-1 truncate">{att.file_name}</span>
                                            <span className="shrink-0 text-xs text-gray-500">{formatFileSize(att.file_size)}</span>
                                          </a>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                ) : null}

                                <p className={`mt-1 text-right text-[11px] ${isMine ? "text-sky-100" : "text-gray-400"}`}>
                                  {messageTime(message)}
                                </p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="mt-3 shrink-0 border-t border-gray-100 bg-white pt-3">
                  {attachedFiles.length > 0 ? (
                    <div className="mb-2 flex flex-wrap gap-2">
                      {attachedFiles.map((file, index) => (
                        <span
                          key={`${file.name}-${file.size}-${index}`}
                          className="inline-flex max-w-full items-center gap-1 rounded-full bg-sky-50 px-3 py-1 text-xs text-sky-700 ring-1 ring-sky-100"
                        >
                          <span className="truncate max-w-[180px]">{file.name}</span>
                          <button
                            type="button"
                            onClick={() => removeAttachedFile(index)}
                            className="rounded-full p-0.5 hover:bg-sky-100"
                            aria-label="Удалить файл"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <div className="flex items-center gap-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      onChange={handleFilesChange}
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={handlePickFiles}
                      className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-white text-gray-600 leading-none transition hover:bg-gray-50 hover:text-sky-700"
                      title="Добавить файлы"
                    >
                      <Paperclip size={16} />
                    </button>
                  <textarea
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    rows={2}
                    placeholder="Введите сообщение..."
                    className="w-full resize-none rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-0 transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  />
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={sending || (!messageText.trim() && attachedFiles.length === 0)}
                    className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-sky-500 text-white leading-none transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                    title="Отправить"
                  >
                    <Send size={16} />
                  </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-[280px] items-center justify-center rounded-xl bg-gray-50 text-center">
              <div>
                <MessageCircle size={20} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Диалог не найден</p>
              </div>
            </div>
          )}
        </section>
        </div>
      )}

      {mediaPreview ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setMediaPreview(null)}
        >
          <button
            type="button"
            onClick={() => setMediaPreview(null)}
            className="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
            aria-label="Закрыть предпросмотр"
          >
            <X size={18} />
          </button>

          <div className="max-h-full max-w-[92vw]" onClick={(e) => e.stopPropagation()}>
            {mediaPreview.type === "image" ? (
              <img src={mediaPreview.src} alt={mediaPreview.name} className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain" />
            ) : (
              <video controls autoPlay className="max-h-[88vh] max-w-[92vw] rounded-lg bg-black" src={mediaPreview.src} />
            )}
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
