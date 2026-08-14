import type { Components } from "react-markdown";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

const components: Components = {
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
  a: ({ href, children }) => (
    <a href={href} className="text-accent underline" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
};

export function MarkdownBody({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </Markdown>
    </div>
  );
}
