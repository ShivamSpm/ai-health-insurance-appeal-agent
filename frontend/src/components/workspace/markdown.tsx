"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";
import { CITATION_RE } from "@/lib/format";

/** Clickable plan citation: jumps to the section in the plan document. */
export function CitationChip({
  chunkId,
  onCite,
  className,
}: {
  chunkId: string;
  onCite?: (chunkId: string) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onCite?.(chunkId)}
      className={cn(
        "inline-flex items-center rounded-md border border-blue-300 bg-blue-50 px-1.5 font-mono text-[0.8em] leading-5 text-blue-800 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200",
        className,
      )}
      title={`Open ${chunkId} in the plan`}
    >
      {chunkId}
    </button>
  );
}

/** Markdown with [plan-N.N] citations rendered as chips. */
export function Markdown({
  text,
  onCite,
  className,
}: {
  text: string;
  onCite?: (chunkId: string) => void;
  className?: string;
}) {
  const linked = text.replace(CITATION_RE, (_, id: string) => `[${id}](#cite-${id})`);
  return (
    <div className={cn("md text-sm", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("#cite-") ? (
              <CitationChip chunkId={href.slice(6)} onCite={onCite} />
            ) : (
              <a href={href} target="_blank" rel="noreferrer" className="underline">
                {children}
              </a>
            ),
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}
