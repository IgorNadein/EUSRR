"use client";

import { useEffect, useRef, RefObject } from "react";

export interface UseModalOptions {
  isOpen: boolean;
  onClose?: () => void;
  closeOnEsc?: boolean;
  trapFocus?: boolean;
  lockBodyScroll?: boolean;
}

/**
 * Хук для универсального управления модальными окнами
 * - Закрытие по ESC
 * - Trap focus внутри модала
 * - Блокировка прокрутки body
 */
export function useModal<T extends HTMLElement = HTMLDivElement>({
  isOpen,
  onClose,
  closeOnEsc = true,
  trapFocus = true,
  lockBodyScroll = true,
}: UseModalOptions) {
  const modalRef = useRef<T>(null);

  // Блокировка прокрутки body
  useEffect(() => {
    if (!lockBodyScroll) return;

    if (isOpen) {
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      document.body.style.overflow = "hidden";
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    } else {
      document.body.style.overflow = "";
      document.body.style.paddingRight = "";
    }

    return () => {
      document.body.style.overflow = "";
      document.body.style.paddingRight = "";
    };
  }, [isOpen, lockBodyScroll]);

  // Закрытие по ESC
  useEffect(() => {
    if (!isOpen || !closeOnEsc || !onClose) return;

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [isOpen, closeOnEsc, onClose]);

  // Focus trap
  useEffect(() => {
    if (!isOpen || !trapFocus || !modalRef.current) return;

    const modalElement = modalRef.current;
    const focusableElements = modalElement.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements.length === 0) return;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    // Сохраняем ранее сфокусированный элемент
    const previouslyFocused = document.activeElement as HTMLElement;

    // Фокус на первый элемент при открытии
    setTimeout(() => firstElement?.focus(), 0);

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

      // Проверяем, что фокус внутри модала
      if (!modalElement.contains(document.activeElement)) {
        e.preventDefault();
        firstElement?.focus();
        return;
      }

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          lastElement?.focus();
          e.preventDefault();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          firstElement?.focus();
          e.preventDefault();
        }
      }
    };

    document.addEventListener("keydown", handleTab);

    return () => {
      document.removeEventListener("keydown", handleTab);
      // Возвращаем фокус на предыдущий элемент
      if (previouslyFocused && document.body.contains(previouslyFocused)) {
        previouslyFocused.focus();
      }
    };
  }, [isOpen, trapFocus]);

  return modalRef;
}

/**
 * Хук для закрытия модала по клику вне его области
 */
export function useClickOutside<T extends HTMLElement = HTMLDivElement>(
  callback: () => void,
  enabled = true
) {
  const ref = useRef<T>(null);

  useEffect(() => {
    if (!enabled) return;

    const handleClick = (e: MouseEvent) => {
      if (ref.current && e.target === ref.current) {
        callback();
      }
    };

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [callback, enabled]);

  return ref;
}
