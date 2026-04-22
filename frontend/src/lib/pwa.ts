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

async function unregisterDevelopmentServiceWorker(): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration("/");
  await registration?.unregister().catch(() => undefined);

  if ("caches" in window) {
    const cacheNames = await caches.keys().catch(() => []);
    await Promise.all(
      cacheNames
        .filter((cacheName) => cacheName.startsWith("eusrr-"))
        .map((cacheName) => caches.delete(cacheName)),
    );
  }
}

export async function registerAppServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }

  if (process.env.NODE_ENV !== "production") {
    await unregisterDevelopmentServiceWorker();
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
