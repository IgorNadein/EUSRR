"use client";

import { useState } from "react";
import { 
  Send, 
  CheckCircle, 
  XCircle, 
  Globe, 
  RotateCcw, 
  Archive, 
  ArchiveRestore 
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import type { DocumentStatus } from "@/types/api";

interface DocumentWorkflowButtonsProps {
  documentId: number;
  currentStatus: DocumentStatus;
  onStatusChange?: () => void;
}

interface WorkflowAction {
  label: string;
  icon: React.ReactNode;
  action: () => Promise<any>;
  confirmMessage?: string;
  successMessage: string;
  variant: "primary" | "success" | "danger" | "secondary";
}

export function DocumentWorkflowButtons({
  documentId,
  currentStatus,
  onStatusChange,
}: DocumentWorkflowButtonsProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleAction = async (action: WorkflowAction) => {
    if (action.confirmMessage && !window.confirm(action.confirmMessage)) {
      return;
    }

    setIsLoading(true);
    try {
      await action.action();
      toast.success(action.successMessage);
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (err) {
      console.error("Ошибка изменения статуса:", err);
      toast.error("Не удалось изменить статус документа");
    } finally {
      setIsLoading(false);
    }
  };

  const getAvailableActions = (): WorkflowAction[] => {
    const actions: WorkflowAction[] = [];

    switch (currentStatus) {
      case "draft":
        actions.push({
          label: "Отправить на рассмотрение",
          icon: <Send size={14} />,
          action: () => apiClient.submitDocumentForReview(documentId),
          successMessage: "Документ отправлен на рассмотрение",
          variant: "primary",
        });
        break;

      case "in_review":
        actions.push(
          {
            label: "Утвердить",
            icon: <CheckCircle size={14} />,
            action: () => apiClient.approveDocument(documentId),
            confirmMessage: "Вы уверены, что хотите утвердить этот документ?",
            successMessage: "Документ утвержден",
            variant: "success",
          },
          {
            label: "Отклонить",
            icon: <XCircle size={14} />,
            action: () => apiClient.rejectDocument(documentId),
            confirmMessage: "Вы уверены, что хотите отклонить этот документ?",
            successMessage: "Документ отклонен",
            variant: "danger",
          },
          {
            label: "Вернуть в черновик",
            icon: <RotateCcw size={14} />,
            action: () => apiClient.returnDocumentToDraft(documentId),
            successMessage: "Документ возвращен в черновик",
            variant: "secondary",
          }
        );
        break;

      case "approved":
        actions.push({
          label: "Опубликовать",
          icon: <Globe size={14} />,
          action: () => apiClient.publishDocument(documentId),
          confirmMessage: "Опубликовать этот документ для всех пользователей?",
          successMessage: "Документ опубликован",
          variant: "primary",
        });
        break;

      case "published":
        actions.push({
          label: "Архивировать",
          icon: <Archive size={14} />,
          action: () => apiClient.archiveDocument(documentId),
          confirmMessage: "Архивировать этот документ?",
          successMessage: "Документ архивирован",
          variant: "secondary",
        });
        break;

      case "archived":
        actions.push({
          label: "Разархивировать",
          icon: <ArchiveRestore size={14} />,
          action: () => apiClient.unarchiveDocument(documentId),
          successMessage: "Документ разархивирован",
          variant: "primary",
        });
        break;
    }

    return actions;
  };

  const actions = getAvailableActions();

  if (actions.length === 0) {
    return null;
  }

  const variantClasses = {
    primary: "bg-sky-600 hover:bg-sky-700 text-white",
    success: "bg-green-600 hover:bg-green-700 text-white",
    danger: "bg-red-600 hover:bg-red-700 text-white",
    secondary: "bg-gray-200 hover:bg-gray-300 text-gray-800",
  };

  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((action, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleAction(action)}
          disabled={isLoading}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
            variantClasses[action.variant]
          }`}
        >
          {action.icon}
          {action.label}
        </button>
      ))}
    </div>
  );
}
