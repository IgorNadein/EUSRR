"use client";

import { UserProvider } from "@/contexts/UserContext";
import { CalendarProvider } from "@/contexts/CalendarContext";
import { ReactNode } from "react";
import { Toaster } from "sonner";

export function Providers({ children }: { children: ReactNode }) {
    return (
        <UserProvider>
            <CalendarProvider>
                <Toaster position="top-right" richColors />
                {children}
            </CalendarProvider>
        </UserProvider>
    );
}
