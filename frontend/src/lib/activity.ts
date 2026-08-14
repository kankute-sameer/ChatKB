import type { LucideIcon } from "lucide-react";
import { Globe, Wrench } from "lucide-react";

export type ThoughtActivity = {
  kind: "thought";
  id: string;
  text: string;
  state?: string;
};

export type ToolActivity = {
  kind: "tool";
  id: string;
  toolName: string;
  input: unknown;
  output: unknown;
  state?: string;
};

export type ActivityItem = ThoughtActivity | ToolActivity;

export type ActivitySegment = {
  activity: ActivityItem[];
  text: string;
};

export type LoosePart = {
  type: string;
  [key: string]: unknown;
};

export type ToolDisplay = {
  summary: string;
  icon: LucideIcon;
  headline: (input: unknown) => string;
};

const TOOL_DISPLAY: Record<string, ToolDisplay> = {
  web_search: {
    summary: "Searched the web",
    icon: Globe,
    headline: (input) => {
      const query = stringField(input, "query");
      return query ? `Searched the web for ${query}` : "Searched the web";
    },
  },
};

export function toolDisplay(toolName: string): ToolDisplay {
  return TOOL_DISPLAY[toolName] ?? defaultToolDisplay(toolName);
}

function defaultToolDisplay(toolName: string): ToolDisplay {
  const summary = `Used ${toolName}`;
  return {
    summary,
    icon: Wrench,
    headline: (input) => {
      const arg = firstStringArg(input);
      return arg ? `${summary} for ${arg}` : summary;
    },
  };
}

export type WebSearchHit = {
  title: string;
  url: string;
  publishedDate?: string | null;
};

export function webSearchHits(output: unknown): WebSearchHit[] {
  const parsed = parseJsonValue(output);
  if (!Array.isArray(parsed)) return [];
  const hits: WebSearchHit[] = [];
  for (const item of parsed) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const record = item as Record<string, unknown>;
    const url = typeof record.url === "string" ? record.url.trim() : "";
    if (!url) continue;
    const title =
      typeof record.title === "string" && record.title.trim()
        ? record.title.trim()
        : url;
    const published =
      typeof record.published_date === "string"
        ? record.published_date
        : typeof record.publishedDate === "string"
          ? record.publishedDate
          : null;
    hits.push({ title, url, publishedDate: published });
  }
  return hits;
}

export function toolErrorMessage(output: unknown): string {
  const record = asRecord(output);
  return typeof record?.error === "string" ? record.error : "";
}

function parseJsonValue(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}

export function outputPreview(output: unknown, limit = 100): string {
  if (output == null) return "";
  const text = typeof output === "string" ? output : JSON.stringify(output);
  if (!text) return "";
  return text.length <= limit ? text : text.slice(0, limit);
}

export function splitThought(text: string): { title: string; body: string } {
  const trimmed = text.trim();
  const heading = trimmed.match(/^\*\*(.+?)\*\*\s*(?:\n+([\s\S]*))?$/);
  if (heading) {
    return { title: heading[1], body: heading[2]?.trim() ?? "" };
  }
  const [first, ...rest] = trimmed.split(/\n+/);
  const title = first.replace(/^\*\*|\*\*$/g, "").trim() || "Thought";
  if (rest.length) {
    return { title, body: rest.join("\n\n").trim() };
  }
  if (title.length <= 80) {
    return { title, body: "" };
  }
  return { title: "Thought", body: trimmed };
}

export function segmentSummary(
  activity: ActivityItem[],
  options?: { includeDuration?: boolean; seconds?: number | null },
): string {
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const item of activity) {
    const label =
      item.kind === "thought"
        ? options?.includeDuration && options.seconds != null
          ? `Thought for ${options.seconds}s`
          : "Thought"
        : toolDisplay(item.toolName).summary;
    if (seen.has(label)) continue;
    seen.add(label);
    labels.push(label);
  }
  return labels.join(" · ");
}

export function hasActivity(segments: ActivitySegment[]): boolean {
  return segments.some((segment) => segment.activity.length > 0);
}

export function segmentsFromParts(
  parts: readonly LoosePart[],
): ActivitySegment[] {
  const segments: ActivitySegment[] = [];
  let current: ActivitySegment = { activity: [], text: "" };

  const flush = () => {
    if (current.activity.length || current.text) {
      segments.push(current);
    }
    current = { activity: [], text: "" };
  };

  parts.forEach((part, index) => {
    if (part.type === "source-url" || part.type === "step-start") return;
    if (part.type === "reasoning") {
      if (current.text) flush();
      current.activity.push({
        kind: "thought",
        id: `thought-${index}`,
        text: asString(part.text) ?? "",
        state: asString(part.state),
      });
      return;
    }
    if (isToolPart(part)) {
      if (current.text) flush();
      current.activity.push({
        kind: "tool",
        id: asString(part.toolCallId) ?? `tool-${index}`,
        toolName: toolNameFromPart(part),
        input: part.input,
        output: part.output,
        state: asString(part.state),
      });
      return;
    }
    if (part.type === "text") {
      current.text += asString(part.text) ?? "";
    }
  });

  flush();
  return segments;
}

function isToolPart(part: LoosePart): boolean {
  if (part.type === "dynamic-tool") return true;
  if (part.type.startsWith("tool-")) return true;
  return Boolean(asString(part.toolCallId) && asString(part.toolName));
}

function toolNameFromPart(part: LoosePart): string {
  const named = asString(part.toolName);
  if (named) return named;
  if (part.type.startsWith("tool-")) {
    return part.type.slice("tool-".length) || "tool";
  }
  return "tool";
}

export function messageSegments(message: {
  id: string;
  content: string;
  thought?: string;
  parts?: readonly LoosePart[];
  segments?: ActivitySegment[];
}): ActivitySegment[] {
  if (message.parts !== undefined) return segmentsFromParts(message.parts);
  if (message.segments !== undefined) return message.segments;
  const activity: ActivityItem[] = message.thought?.trim()
    ? [
        {
          kind: "thought",
          id: `${message.id}-thought`,
          text: message.thought,
        },
      ]
    : [];
  if (!activity.length && !message.content) return [];
  return [{ activity, text: message.content }];
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  if (typeof value === "string") {
    try {
      const parsed: unknown = JSON.parse(value);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return undefined;
    }
  }
  return undefined;
}

function stringField(value: unknown, key: string): string {
  const record = asRecord(value);
  const field = record?.[key];
  return typeof field === "string" ? field.trim() : "";
}

function firstStringArg(value: unknown): string {
  const record = asRecord(value);
  if (!record) return typeof value === "string" ? value.trim() : "";
  for (const field of Object.values(record)) {
    if (typeof field === "string" && field.trim()) return field.trim();
  }
  return "";
}
