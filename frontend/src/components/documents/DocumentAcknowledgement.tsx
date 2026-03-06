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
        <div className="rounded-xl border-2 border-amber-200 bg-amber-50 p-4">
          <div className="mb-3 flex items-start gap-3">
            <CheckCircle size={20} className="mt-0.5 shrink-0 text-amber-600" />
            <div>
              <p className="text-sm font-medium text-amber-900">
                Требуется подтверждение прочтения
              </p>
              <p className="mt-1 text-xs text-amber-700">
                Пожалуйста, подтвердите, что вы прочитали этот документ
              </p>
            </div>
          </div>

          <button
            onClick={handleAcknowledge}
            disabled={isSubmitting}
            className="w-full rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "Подтверждение..." : "Подтвердить прочтение"}
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800 ring-1 ring-green-200">
          <CheckCircle size={16} className="shrink-0" />
          <span>Вы подтвердили прочтение этого документа</span>
        </div>
      )}

      {/* Acknowledgements List */}
      {acknowledgements.length > 0 && (
        <div>
          <button
            onClick={() => setShowAcknowledgements(!showAcknowledgements)}
            className="flex w-full items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-100"
          >
            <span className="flex items-center gap-2">
              <Users size={16} />
              Подтверждений: {acknowledgements.length}
            </span>
            <span className="text-xs text-gray-500">
              {showAcknowledgements ? "Скрыть" : "Показать"}
            </span>
          </button>

          {showAcknowledgements && (
            <div className="mt-2 space-y-2 rounded-lg border border-gray-200 bg-white p-3">
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
                  <div key={ack.id} className="rounded-lg bg-gray-50 p-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">{userName}</span>
                      <span className="text-gray-500">{date}</span>
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
