"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl" | "full";
  showCloseButton?: boolean;
  closeOnClickOutside?: boolean;
  closeOnEsc?: boolean;
  footer?: ReactNode;
  className?: string;
  /** Remove default content padding while keeping the standard modal frame */
  noPadding?: boolean;
  /** Hide the built-in header (caller manages its own header inside children) */
  noHeader?: boolean;
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
  footer,
  className = "",
  noPadding = false,
  noHeader = false,
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }

    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

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

  useEffect(() => {
    if (!isOpen || !contentRef.current) return;

    const focusableElements = contentRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements.length === 0) return;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    firstElement?.focus();

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          lastElement?.focus();
          e.preventDefault();
        }
      } else {
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
    sm: "max-w-[95vw] sm:max-w-md",
    md: "max-w-[95vw] sm:max-w-2xl",
    lg: "max-w-[95vw] sm:max-w-4xl",
    xl: "max-w-[95vw] sm:max-w-6xl",
    full: "max-w-[98vw] sm:max-w-[95vw]",
  };

  const modalSizeClass = `w-full ${sizeClasses[size]} max-h-[95vh] sm:max-h-[90vh]`;

  const showHeader = !noHeader && (title || showCloseButton);

  return (
    <div
      ref={modalRef}
      onClick={handleBackdropClick}
      data-overlay-root="true"
      className="app-overlay fixed inset-0 z-[100] flex items-center justify-center p-2 transition-opacity duration-200 opacity-100 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
    >
      <div
        ref={contentRef}
        className={`app-surface-elevated flex scale-100 flex-col overflow-hidden rounded-xl opacity-100 transition-all duration-200 sm:rounded-2xl ${modalSizeClass} ${className}`}
      >
        {/* Header */}
        {showHeader && (
          <div className="mb-3 flex shrink-0 items-center gap-2 px-4 pt-4 sm:mb-4 sm:gap-3 sm:px-6 sm:pt-6">
            {title && (
              <h3
                id="modal-title"
                className="min-w-0 flex-1 truncate text-sm font-semibold text-[var(--foreground)] sm:text-base lg:text-lg"
                title={title}
              >
                {title}
              </h3>
            )}
            <div className="flex shrink-0 items-center gap-2">
              {showCloseButton && (
                <button
                  onClick={onClose}
                  className="app-icon-button rounded-full p-1"
                  title="Закрыть"
                >
                  <X size={20} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Content */}
        <div
          className={noPadding
            ? "min-h-0 flex flex-1 flex-col"
            : "min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 sm:px-6"}
        >
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="app-divider shrink-0 border-t px-4 py-3 sm:px-6 sm:py-4">{footer}</div>
        )}

        {/* Bottom padding */}
        {!noPadding && <div className="pb-4 sm:pb-6" />}
      </div>
    </div>
  );
}
