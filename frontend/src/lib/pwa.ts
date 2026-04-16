"use client";

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
  prompt: () => Promise<void>;
}

export function isStandaloneDisplayMode(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  const standaloneMatch = window.matchMedia?.("(display-mode: standalone)").matches;
  const navigatorStandalone =
    typeof navigator !== "undefined" &&
    "standalone" in navigator &&
    Boolean((navigator as Navigator & { standalone?: boolean }).standalone);

  return Boolean(standaloneMatch || navigatorStandalone);
}

export async function registerAppServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }

  const existingRegistration = await navigator.serviceWorker.getRegistration("/");
  if (existingRegistration) {
    await existingRegistration.update().catch(() => undefined);
    return existingRegistration;
  }

  const registration = await navigator.serviceWorker.register("/sw.js", {
    scope: "/",
  });

  if (registration.installing) {
    await new Promise<void>((resolve) => {
      registration.installing?.addEventListener("statechange", (event) => {
        if ((event.target as ServiceWorker).state === "activated") {
          resolve();
        }
      });
    });
  }

  return registration;
}
