"use client";

import { apiClient } from "@/lib/api";
import type { Request } from "@/types/api";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

type UseRequestsPageScreenParams = {
  detailsRequestId?: number | null;
  requests: Request[];
  setDetailsRequest: (request: Request | null) => void;
};

export function useRequestsPageScreen({
  detailsRequestId,
  requests,
  setDetailsRequest,
}: UseRequestsPageScreenParams) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requestMenuRef = useRef<HTMLDivElement | null>(null);
  const openedLinkedRequestIdRef = useRef<number | null>(null);
  const loadingLinkedRequestIdRef = useRef<number | null>(null);
  const [requestMenuOpenId, setRequestMenuOpenId] = useState<number | null>(null);
  const linkedRequestId = Number(searchParams.get("request") || "");

  const clearRequestParam = () => {
    if (!searchParams.get("request")) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.delete("request");
    router.replace(nextParams.toString() ? `${pathname}?${nextParams.toString()}` : pathname, { scroll: false });
  };

  const closeDetailsRequest = () => {
    setDetailsRequest(null);
    clearRequestParam();
  };

  useEffect(() => {
    if (!linkedRequestId) {
      openedLinkedRequestIdRef.current = null;
      loadingLinkedRequestIdRef.current = null;
      return;
    }

    if (detailsRequestId === linkedRequestId) {
      openedLinkedRequestIdRef.current = linkedRequestId;
      loadingLinkedRequestIdRef.current = null;
      return;
    }

    if (openedLinkedRequestIdRef.current === linkedRequestId) {
      return;
    }

    const existing = requests.find((item) => item.id === linkedRequestId);
    if (existing) {
      openedLinkedRequestIdRef.current = linkedRequestId;
      loadingLinkedRequestIdRef.current = null;
      setDetailsRequest(existing);
      return;
    }

    if (loadingLinkedRequestIdRef.current === linkedRequestId) {
      return;
    }

    loadingLinkedRequestIdRef.current = linkedRequestId;

    let cancelled = false;

    apiClient.getRequest(linkedRequestId)
      .then((request) => {
        if (!cancelled && openedLinkedRequestIdRef.current !== linkedRequestId) {
          openedLinkedRequestIdRef.current = linkedRequestId;
          loadingLinkedRequestIdRef.current = null;
          setDetailsRequest(request);
        }
      })
      .catch((error) => {
        loadingLinkedRequestIdRef.current = null;
        console.error("Ошибка deep-link заявления:", error);
      });

    return () => {
      cancelled = true;
    };
  }, [detailsRequestId, linkedRequestId, requests, setDetailsRequest]);

  useEffect(() => {
    if (requestMenuOpenId === null) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (requestMenuRef.current && !requestMenuRef.current.contains(event.target as Node)) {
        setRequestMenuOpenId(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setRequestMenuOpenId(null);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [requestMenuOpenId]);

  return {
    closeDetailsRequest,
    requestMenuOpenId,
    requestMenuRef,
    setRequestMenuOpenId,
  };
}

export type RequestsPageScreenController = ReturnType<typeof useRequestsPageScreen>;
