import { useMemo, type ReactNode } from "react";
import type { Components } from "react-markdown";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  CitationChip,
  type CitationSource,
} from "@/components/ai-elements/inline-citation";
import { cn } from "@/lib/utils";

const CITE_GROUP = /(\[cite:[0-9a-fA-F]{8}\])+/g;
const CITE_ID = /\[cite:([0-9a-fA-F]{8})\]/g;
/** Survives react-markdown's default urlTransform (cite:// does not). */
const CITE_PREFIX = "https://cite.local/";

function rewriteCiteMarkers(text: string): string {
  return text.replace(CITE_GROUP, (group) => {
    const ids = [...group.matchAll(CITE_ID)].map((match) =>
      match[1].toLowerCase(),
    );
    return `[cite](${CITE_PREFIX}${ids.join(",")})`;
  });
}

function markdownComponents(sources: CitationSource[]): Components {
  const byId = new Map(
    sources.map((source) => [source.sourceId.toLowerCase(), source]),
  );
  return {
    p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
    strong: ({ children }) => <strong className="font-medium">{children}</strong>,
    em: ({ children }) => <em>{children}</em>,
    h1: ({ children }) => <h1 className="mb-3 font-medium last:mb-0">{children}</h1>,
    h2: ({ children }) => <h2 className="mb-3 font-medium last:mb-0">{children}</h2>,
    h3: ({ children }) => <h3 className="mb-2 font-medium last:mb-0">{children}</h3>,
    ul: ({ children }) => (
      <ul className="mb-3 list-disc pl-5 last:mb-0">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="mb-3 list-decimal pl-5 last:mb-0">{children}</ol>
    ),
    li: ({ children }) => <li className="mb-1">{children}</li>,
    code: ({ children, className }) => {
      const block = Boolean(className);
      if (block) {
        return (
          <code className="block overflow-x-auto whitespace-pre rounded bg-gray-50 p-3 text-sm">
            {children}
          </code>
        );
      }
      return <code className="rounded bg-gray-50 px-1">{children}</code>;
    },
    pre: ({ children }) => <pre className="mb-3 last:mb-0">{children}</pre>,
    a: ({ href, children }) => {
      const chip = citeChip(href, byId);
      if (chip !== undefined) return chip;
      return (
        <a href={href} className="text-accent underline" target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
  };
}

function citeChip(
  href: string | undefined,
  byId: Map<string, CitationSource>,
): ReactNode {
  if (!href?.startsWith(CITE_PREFIX)) return undefined;
  const ids = href.slice(CITE_PREFIX.length).split(",").filter(Boolean);
  const resolved = ids
    .map((id) => byId.get(id.toLowerCase()))
    .filter((source): source is CitationSource => Boolean(source));
  if (resolved.length === 0) return null;
  return <CitationChip sources={resolved} />;
}

export function MarkdownBody({
  text,
  className,
  sources = [],
}: {
  text: string;
  className?: string;
  sources?: CitationSource[];
}) {
  const rewritten = useMemo(() => rewriteCiteMarkers(text), [text]);
  const components = useMemo(() => markdownComponents(sources), [sources]);
  return (
    <div className={cn("min-w-0", className)}>
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {rewritten}
      </Markdown>
    </div>
  );
}
