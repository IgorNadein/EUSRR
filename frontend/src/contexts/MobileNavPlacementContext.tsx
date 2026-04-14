"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  initializeMobileNavPlacement,
  readMobileNavPlacementPreference,
  setMobileNavPlacementPreference,
  subscribeToMobileNavPlacementChanges,
  type MobileNavPlacement,
} from "@/lib/mobileNavPlacement";

type MobileNavPlacementContextValue = {
  mobileNavPlacement: MobileNavPlacement;
  setMobileNavPlacement: (placement: MobileNavPlacement) => void;
};

const MobileNavPlacementContext = createContext<MobileNavPlacementContextValue | null>(null);

export function MobileNavPlacementProvider({ children }: { children: ReactNode }) {
  const [mobileNavPlacement, setMobileNavPlacementState] = useState<MobileNavPlacement>(() => {
    if (typeof window === "undefined") {
      return "top";
    }

    return initializeMobileNavPlacement();
  });

  useEffect(() => {
    const sync = () => {
      const preference = readMobileNavPlacementPreference();
      setMobileNavPlacementState(preference);
    };

    initializeMobileNavPlacement();
    return subscribeToMobileNavPlacementChanges(sync);
  }, []);

  const setMobileNavPlacement = useCallback((nextPlacement: MobileNavPlacement) => {
    setMobileNavPlacementPreference(nextPlacement);
    setMobileNavPlacementState(nextPlacement);
  }, []);

  const value = useMemo(
    () => ({
      mobileNavPlacement,
      setMobileNavPlacement,
    }),
    [mobileNavPlacement, setMobileNavPlacement],
  );

  return (
    <MobileNavPlacementContext.Provider value={value}>
      {children}
    </MobileNavPlacementContext.Provider>
  );
}

export function useMobileNavPlacement() {
  const context = useContext(MobileNavPlacementContext);

  if (!context) {
    throw new Error("useMobileNavPlacement must be used within MobileNavPlacementProvider");
  }

  return context;
}
