"use client";

import { UserProvider } from "@/contexts/UserContext";
import { CalendarProvider } from "@/contexts/CalendarContext";
import { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
    return (
        <UserProvider>
            <CalendarProvider>
                {children}
            </CalendarProvider>
        </UserProvider>
    );
}
