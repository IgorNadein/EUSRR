"use client";

import type { ReactNode } from "react";

type DesktopStickyRailProps = {
  widthClass: string;
  pinned?: boolean;
  children: ReactNode;
};

export function DesktopStickyRail({ widthClass, pinned = true, children }: DesktopStickyRailProps) {
  return (
    <aside className={`hidden flex-shrink-0 lg:block ${widthClass}`}>
      <div
        className={`space-y-4 ${
          pinned
            ? "lg:sticky lg:top-[5.5rem] lg:max-h-[calc(100dvh-5.5rem)] lg:overflow-y-auto lg:pb-2"
            : "lg:h-full lg:min-h-0 lg:overflow-y-auto"
        }`}
      >
        {children}
      </div>
    </aside>
  );
}
