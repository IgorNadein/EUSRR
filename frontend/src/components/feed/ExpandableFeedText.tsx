"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

type ExpandableFeedTextProps = {
  text: string;
  className?: string;
};

export function ExpandableFeedText({ text, className = "" }: ExpandableFeedTextProps) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > 320 || text.split("\n").length > 6;

  return (
    <div>
      <p
        className={`app-text-wrap whitespace-pre-line text-sm leading-6 text-[var(--foreground)] ${
          isLong && !expanded ? "line-clamp-6" : ""
        } ${className}`}
      >
        {text}
      </p>
      {isLong ? (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="app-accent-text mt-1 inline-flex items-center gap-1 py-1 text-xs font-medium hover:text-[var(--accent-primary-strong)]"
          aria-expanded={expanded}
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {expanded ? "Скрыть" : "Подробнее"}
        </button>
      ) : null}
    </div>
  );
}
