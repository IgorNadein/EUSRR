"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { apiClient } from "@/lib/api";
import type { User } from "@/types/api";

interface UserContextType {
    user: User | null;
    loading: boolean;
    error: string | null;
    refreshUser: () => Promise<void>;
    logout: () => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadUser = async () => {
        try {
            setLoading(true);
            setError(null);

            // Проверяем наличие токена
            const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
            if (!token) {
                setUser(null);
                setLoading(false);
                return;
            }

            // Загружаем данные пользователя
            // ApiClient автоматически обновит токен если он истёк
            const userData = await apiClient.getCurrentUser();
            setUser(userData);
        } catch (err: any) {
            console.error('Ошибка загрузки пользователя:', err);
            setError(err.message);
            setUser(null);

            // Токены уже очищены в ApiClient если refresh token тоже истёк
            // Проверяем, остались ли токены - если нет, значит сессия истекла
            const hasToken = typeof window !== 'undefined' && localStorage.getItem('access_token');
            if (!hasToken) {
                // Токены очищены - сессия истекла, redirect на login
                if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
                    window.location.href = '/login';
                }
            }
        } finally {
            setLoading(false);
        }
    };

    const refreshUser = async () => {
        await loadUser();
    };

    const logout = () => {
        apiClient.clearToken();
        setUser(null);
        if (typeof window !== 'undefined') {
            window.location.href = '/login';
        }
    };

    // Загружаем пользователя при монтировании
    useEffect(() => {
        loadUser();
    }, []);

    const value: UserContextType = {
        user,
        loading,
        error,
        refreshUser,
        logout,
    };

    return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
    const context = useContext(UserContext);
    if (context === undefined) {
        throw new Error('useUser must be used within a UserProvider');
    }
    return context;
}
