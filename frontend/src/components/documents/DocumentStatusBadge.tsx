"use client";

import type { DocumentStatus } from "@/types/api";

interface DocumentStatusBadgeProps {
  status: string; // human-readable: "Черновик", "На рассмотрении", etc.
  statusCode: DocumentStatus; // machine-readable: "draft", "in_review", etc.
  className?: string;
}

const statusConfig: Record<DocumentStatus, { label: string; color: string; bgColor: string; ringColor: string }> = {
  draft: {
    label: "Черновик",
    color: "text-gray-700",
    bgColor: "bg-gray-50",
    ringColor: "ring-gray-200",
  },
  in_review: {
    label: "На рассмотрении",
    color: "text-cyan-700",
    bgColor: "bg-cyan-50",
    ringColor: "ring-cyan-200",
  },
  approved: {
    label: "Утверждено",
    color: "text-green-700",
    bgColor: "bg-green-50",
    ringColor: "ring-green-200",
  },
  published: {
    label: "Опубликовано",
    color: "text-blue-700",
    bgColor: "bg-blue-50",
    ringColor: "ring-blue-200",
  },
  archived: {
    label: "В архиве",
    color: "text-gray-600",
    bgColor: "bg-gray-100",
    ringColor: "ring-gray-300",
  },
  rejected: {
    label: "Отклонено",
    color: "text-red-700",
    bgColor: "bg-red-50",
    ringColor: "ring-red-200",
  },
};

export function DocumentStatusBadge({ status, statusCode, className = "" }: DocumentStatusBadgeProps) {
  const config = statusConfig[statusCode] || statusConfig.draft;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${config.color} ${config.bgColor} ${config.ringColor} ${className}`}
    >
      {status || config.label}
    </span>
  );
}
