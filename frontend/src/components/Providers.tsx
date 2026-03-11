"use client";

import { UserProvider } from "@/contexts/UserContext";
import { CalendarProvider } from "@/contexts/CalendarContext";
import { NotificationsProvider } from "@/contexts/NotificationsContext";
import { ReactNode } from "react";
import { Toaster } from "sonner";

export function Providers({ children }: { children: ReactNode }) {
    return (
        <UserProvider>
            <NotificationsProvider>
                <CalendarProvider>
                    <Toaster position="top-right" richColors />
                    {children}
                </CalendarProvider>
            </NotificationsProvider>
        </UserProvider>
    );
}
