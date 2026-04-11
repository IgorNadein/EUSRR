"use client";

import { useState } from "react";
import { CheckCircle, Users } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";
import type { Document } from "@/types/api";

interface DocumentAcknowledgementProps {
  document: Document;
  onAcknowledge?: () => void;
}

export function DocumentAcknowledgement({
  document,
  onAcknowledge,
}: DocumentAcknowledgementProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAcknowledgements, setShowAcknowledgements] = useState(false);

  const handleAcknowledge = async () => {
    setIsSubmitting(true);
    try {
      await apiClient.acknowledgeDocument(document.id);
      toast.success("Прочтение подтверждено");
      if (onAcknowledge) {
        onAcknowledge();
      }
    } catch (err) {
      console.error("Ошибка подтверждения:", err);
      toast.error("Не удалось подтвердить прочтение");
    } finally {
      setIsSubmitting(false);
    }
  };

  const acknowledgements = document.acknowledgements || [];
  const isAcknowledged = document.is_acknowledged || false;

  return (
    <div className="space-y-3">
      {/* Acknowledge Button/Status */}
      {!isAcknowledged ? (
        <div className="app-feedback-warning rounded-xl p-4">
          <div className="mb-3 flex items-start gap-3">
            <CheckCircle size={20} className="mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium">
                Требуется подтверждение прочтения
              </p>
              <p className="mt-1 text-xs opacity-80">
                Пожалуйста, подтвердите, что вы прочитали этот документ
              </p>
            </div>
          </div>

          <button
            onClick={handleAcknowledge}
            disabled={isSubmitting}
            className="app-action-primary w-full rounded-lg px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "Подтверждение..." : "Подтвердить прочтение"}
          </button>
        </div>
      ) : (
        <div className="app-feedback-success flex items-center gap-2 rounded-lg px-3 py-2 text-sm">
          <CheckCircle size={16} className="shrink-0" />
          <span>Вы подтвердили прочтение этого документа</span>
        </div>
      )}

      {/* Acknowledgements List */}
      {acknowledgements.length > 0 && (
        <div>
          <button
            onClick={() => setShowAcknowledgements(!showAcknowledgements)}
            className="app-action-secondary flex w-full items-center justify-between rounded-lg px-4 py-2 text-sm"
          >
            <span className="flex items-center gap-2">
              <Users size={16} />
              Подтверждений: {acknowledgements.length}
            </span>
            <span className="app-text-muted text-xs">
              {showAcknowledgements ? "Скрыть" : "Показать"}
            </span>
          </button>

          {showAcknowledgements && (
            <div className="app-surface mt-2 space-y-2 rounded-lg p-3">
              {acknowledgements.map((ack) => {
                const userName = ack.user
                  ? `${ack.user.last_name} ${ack.user.first_name}`.trim()
                  : "Пользователь";
                const date = new Date(ack.acknowledged_at).toLocaleDateString("ru-RU", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                });

                return (
                  <div key={ack.id} className="app-surface-muted rounded-lg p-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[var(--foreground)]">{userName}</span>
                      <span className="app-text-muted">{date}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
