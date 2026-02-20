"use client";

import { Heart, MessageSquare } from "lucide-react";
import { AppShell } from "../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useState } from "react";
import type { Post } from "@/types/api";
import { useUser } from "@/contexts/UserContext";

export default function Home() {
  const { user } = useUser();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';

  useEffect(() => {
    async function loadPosts() {
      try {
        const response = await apiClient.getPosts();
        setPosts(response.results);
      } catch (err: any) {
        console.error('Ошибка загрузки ленты:', err);
        setError('Не удалось загрузить ленту');
      } finally {
        setLoading(false);
      }
    }
    loadPosts();
  }, []);

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent"></div>
            <p className="text-sm text-gray-500">Загрузка ленты...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      </AppShell>
    );
  }
  return (
    <AppShell>
      <div className="space-y-4">
        {posts.length === 0 ? (
          <div className="rounded-2xl bg-gray-50 p-8 text-center">
            <p className="text-sm text-gray-500">Пока нет постов в ленте</p>
          </div>
        ) : (
          posts.map((post) => {
            const authorName = post.author
              ? `${post.author.last_name} ${post.author.first_name}`.trim()
              : 'Аноним';
            const authorInitials = post.author
              ? `${post.author.last_name?.[0] || ''}${post.author.first_name?.[0] || ''}`
              : 'А';
            const isAuthorOnline =
              typeof post.author?.is_active === 'boolean'
                ? post.author.is_active
                : Boolean(post.author?.id && user?.id && post.author.id === user.id && user.is_active);

            // Форматируем дату
            const postDate = new Date(post.created_at);
            const now = new Date();
            const diffMs = now.getTime() - postDate.getTime();
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const timeAgo = diffHours < 1
              ? 'только что'
              : diffHours < 24
                ? `${diffHours} ч. назад`
                : `${Math.floor(diffHours / 24)} дн. назад`;

            return (
              <article key={post.id} className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
                <header className="mb-3 flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="relative h-10 w-10">
                      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                        {post.author?.avatar ? (
                          <img src={post.author.avatar} alt={authorName} className="h-full w-full object-cover" />
                        ) : (
                          authorInitials
                        )}
                      </div>
                      {isAuthorOnline ? (
                        <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
                      ) : null}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{authorName}</p>
                      <p className="text-xs text-gray-500">{timeAgo}</p>
                    </div>
                  </div>
                </header>
                <p className="text-sm leading-6 text-gray-800">{post.content}</p>
                {post.image && (
                  <div className="mt-3 overflow-hidden rounded-lg">
                    <img src={post.image} alt="" className="w-full" />
                  </div>
                )}
                <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
                  <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                    <Heart size={16} className="text-gray-400" /> {post.likes_count || 0}
                  </button>
                  <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                    <MessageSquare size={16} className="text-gray-400" /> {post.comments_count || 0}
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>
    </AppShell>
  );
}
