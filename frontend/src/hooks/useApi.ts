"use client";

import { useEffect, useState } from 'react';
import apiClient from '@/lib/api';
import type { User, Post, PaginatedResponse } from '@/types/api';

export function useCurrentUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchUser() {
      try {
        const data = await apiClient.getCurrentUser();
        setUser(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchUser();
  }, []);

  return { user, loading, error };
}

export function useEmployees(params?: { search?: string; department?: string }) {
  const [employees, setEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchEmployees() {
      try {
        setLoading(true);
        const data = await apiClient.getEmployees(params);
        setEmployees(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchEmployees();
  }, [params?.search, params?.department]);

  return { employees, loading, error, refetch: () => {} };
}

export function useDepartments() {
  const [departments, setDepartments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchDepartments() {
      try {
        const data = await apiClient.getDepartments();
        setDepartments(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchDepartments();
  }, []);

  return { departments, loading, error };
}

export function usePosts(params?: { page?: number; search?: string }) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    async function fetchPosts() {
      try {
        setLoading(true);
        const data: PaginatedResponse<Post> = await apiClient.getPosts(params);
        setPosts(data.results);
        setHasMore(!!data.next);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchPosts();
  }, [params?.page, params?.search]);

  return { posts, loading, error, hasMore, refetch: () => {} };
}

export function useDocuments(params?: { search?: string; type?: string }) {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchDocuments() {
      try {
        const data = await apiClient.getDocuments(params);
        setDocuments(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchDocuments();
  }, [params?.search, params?.type]);

  return { documents, loading, error };
}

export function useRequests(params?: { status?: string; type?: string }) {
  const [requests, setRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchRequests() {
      try {
        const data = await apiClient.getRequests(params);
        setRequests(data.results || data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchRequests();
  }, [params?.status, params?.type]);

  return { requests, loading, error };
}

export function useChats() {
  const [chats, setChats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchChats() {
      try {
        const data = await apiClient.getAllChats();
        setChats(data);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchChats();
  }, []);

  return { chats, loading, error };
}

// Re-export useNotifications from context for backwards compatibility
export { useNotifications } from '@/contexts/NotificationsContext';
