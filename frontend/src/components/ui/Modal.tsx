"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X, Maximize2, Minimize2 } from "lucide-react";
import { useState } from "react";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode | ((isFullscreen: boolean) => ReactNode);
  size?: "sm" | "md" | "lg" | "xl" | "full";
  showCloseButton?: boolean;
  closeOnClickOutside?: boolean;
  closeOnEsc?: boolean;
  showFullscreenToggle?: boolean;
  footer?: ReactNode;
  className?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  showCloseButton = true,
  closeOnClickOutside = true,
  closeOnEsc = true,
  showFullscreenToggle = false,
  footer,
  className = "",
}: ModalProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Анимация появления
  useEffect(() => {
    if (isOpen) {
      setIsAnimating(true);
      // Блокируем прокрутку body
      document.body.style.overflow = "hidden";
    } else {
      // Разблокируем прокрутку при закрытии
      document.body.style.overflow = "";
    }

    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // ESC для закрытия
  useEffect(() => {
    if (!isOpen || !closeOnEsc) return;

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
    if (!isOpen || !contentRef.current) return;

    const focusableElements = contentRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements.length === 0) return;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    // Фокус на первый элемент при открытии
    firstElement?.focus();

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

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
    return () => document.removeEventListener("keydown", handleTab);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (closeOnClickOutside && e.target === modalRef.current) {
      onClose();
    }
  };

  const sizeClasses = {
    sm: "max-w-md",
    md: "max-w-2xl",
    lg: "max-w-4xl",
    xl: "max-w-6xl",
    full: "max-w-[95vw]",
  };

  const modalSizeClass = isFullscreen
    ? "w-screen h-screen max-w-none rounded-none"
    : `w-full ${sizeClasses[size]} max-h-[90vh]`;

  return (
    <div
      ref={modalRef}
      onClick={handleBackdropClick}
      className={`fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 transition-opacity duration-200 ${
        isAnimating ? "opacity-100" : "opacity-0"
      }`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
    >
      <div
        ref={contentRef}
        className={`flex flex-col rounded-2xl bg-white shadow-xl overflow-y-auto transition-all duration-200 ${modalSizeClass} ${
          isAnimating ? "scale-100 opacity-100" : "scale-95 opacity-0"
        } ${className}`}
      >
        {/* Header */}
        {(title || showCloseButton || showFullscreenToggle) && (
          <div className="flex shrink-0 items-center justify-between mb-4 px-6 pt-6">
            {title && (
              <h3 id="modal-title" className="text-lg font-semibold text-gray-900">
                {title}
              </h3>
            )}
            <div className="ml-auto flex items-center gap-2">
              {showFullscreenToggle && (
                <button
                  onClick={() => setIsFullscreen(!isFullscreen)}
                  className="rounded-full p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
                  title={isFullscreen ? "Выйти из полноэкранного режима" : "Полноэкранный режим"}
                >
                  {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                </button>
              )}
              {showCloseButton && (
                <button
                  onClick={onClose}
                  className="rounded-full p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
                  title="Закрыть"
                >
                  <X size={20} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="px-6">
          {typeof children === "function" ? children(isFullscreen) : children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="shrink-0 border-t border-gray-200 px-6 py-4 mt-4">{footer}</div>
        )}

        {/* Bottom padding */}
        <div className="pb-6" />
      </div>
    </div>
  );
}
