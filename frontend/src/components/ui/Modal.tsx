"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useState } from "react";

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
  closeOnClickOutside = false,
  closeOnEsc = true,
  footer,
  className = "",
  noPadding = false,
  noHeader = false,
}: ModalProps) {
  const [isAnimating, setIsAnimating] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      setIsAnimating(true);
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
      className={`fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-2 sm:p-4 transition-opacity duration-200 ${
        isAnimating ? "opacity-100" : "opacity-0"
      }`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
    >
      <div
        ref={contentRef}
        className={`flex flex-col rounded-xl sm:rounded-2xl bg-white shadow-xl overflow-hidden transition-all duration-200 ${modalSizeClass} ${
          isAnimating ? "scale-100 opacity-100" : "scale-95 opacity-0"
        } ${className}`}
      >
        {/* Header */}
        {showHeader && (
          <div className="mb-3 flex shrink-0 items-center gap-2 px-4 pt-4 sm:mb-4 sm:gap-3 sm:px-6 sm:pt-6">
            {title && (
              <h3
                id="modal-title"
                className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-900 sm:text-base lg:text-lg"
                title={title}
              >
                {title}
              </h3>
            )}
            <div className="flex shrink-0 items-center gap-2">
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
        <div
          className={noPadding
            ? "min-h-0 flex flex-1 flex-col"
            : "min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 sm:px-6"}
        >
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="shrink-0 border-t border-gray-200 px-4 py-3 sm:px-6 sm:py-4">{footer}</div>
        )}

        {/* Bottom padding */}
        {!noPadding && <div className="pb-4 sm:pb-6" />}
      </div>
    </div>
  );
}
