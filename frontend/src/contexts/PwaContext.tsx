"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  type BeforeInstallPromptEvent,
  isStandaloneDisplayMode,
  registerAppServiceWorker,
} from "@/lib/pwa";

type InstallResult = "accepted" | "dismissed" | "unavailable";

type PwaContextValue = {
  canInstall: boolean;
  isInstalled: boolean;
  isRegistrationReady: boolean;
  install: () => Promise<InstallResult>;
};

const PwaContext = createContext<PwaContextValue | undefined>(undefined);

export function PwaProvider({ children }: { children: ReactNode }) {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(() => isStandaloneDisplayMode());
  const [isRegistrationReady, setIsRegistrationReady] = useState(false);

  useEffect(() => {
    void registerAppServiceWorker()
      .then((registration) => {
        setIsRegistrationReady(Boolean(registration));
      })
      .catch((error) => {
        console.error("[PWA] Service Worker registration failed:", error);
        setIsRegistrationReady(false);
      });
  }, []);

  useEffect(() => {
    const handleBeforeInstallPrompt = (event: Event) => {
      const installEvent = event as BeforeInstallPromptEvent;
      installEvent.preventDefault();
      setDeferredPrompt(installEvent);
    };

    const handleAppInstalled = () => {
      setDeferredPrompt(null);
      setIsInstalled(true);
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  const install = useCallback(async (): Promise<InstallResult> => {
    if (!deferredPrompt) {
      return "unavailable";
    }

    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;

    if (choice.outcome === "accepted") {
      setIsInstalled(true);
      setDeferredPrompt(null);
      return "accepted";
    }

    return "dismissed";
  }, [deferredPrompt]);

  const value = useMemo<PwaContextValue>(
    () => ({
      canInstall: !isInstalled && deferredPrompt !== null,
      isInstalled,
      isRegistrationReady,
      install,
    }),
    [deferredPrompt, install, isInstalled, isRegistrationReady],
  );

  return <PwaContext.Provider value={value}>{children}</PwaContext.Provider>;
}

export function usePwa() {
  const context = useContext(PwaContext);
  if (!context) {
    throw new Error("usePwa must be used within a PwaProvider");
  }
  return context;
}
