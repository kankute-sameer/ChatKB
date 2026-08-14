import type { AvatarColor } from "@/design/tokens";

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatar: AvatarColor;
  scope: "my" | "workspace";
  skills: string[];
  knowledgeBaseIds: string[];
  instructions: string;
  howYouOperate: string[];
  workingEffectively: string[];
  builderThreadId: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  subtitle: string;
  createdBy: string;
  visibility: "personal" | "workspace";
  createdAt: string;
  agentIds: string[];
}

export interface KBFile {
  id: string;
  kbId: string;
  name: string;
  size: string;
  status: "ready" | "processing";
  addedAt: string;
}

export interface ChatThread {
  id: string;
  title: string;
  agentId?: string;
}

export interface Citation {
  id: string;
  label: string;
}

export interface ChatMessage {
  id: string;
  threadId: string;
  role: "user" | "assistant";
  content: string;
  thought?: string;
  thoughtStreaming?: boolean;
  citations?: Citation[];
}

export const agents: Agent[] = [
  {
    id: "agent-creator",
    name: "Agent Creator",
    description: "Helps you design, refine, and publish work agents.",
    avatar: "blue",
    scope: "my",
    skills: ["sarvam-docx", "sarvam-pdf"],
    knowledgeBaseIds: ["flat-prose"],
    instructions:
      "You are Agent Creator. Help the user specify goals, tools, knowledge sources, and operating rules for a new work agent. Ask clarifying questions before writing instructions. Prefer short, testable procedures over vague advice.",
    howYouOperate: [
      "Start by restating the job to be done in one sentence.",
      "Propose the smallest set of tools and knowledge bases required.",
      "Draft instructions as numbered operating rules, not essays.",
      "Offer a playground prompt the user can run immediately.",
    ],
    workingEffectively: [
      "Cite files from attached knowledge bases when answering factual questions.",
      "If a connector is missing, say so and suggest the Connect button.",
      "Keep replies concise unless the user asks for a full spec.",
      "Never invent tools or files that are not attached.",
    ],
    builderThreadId: "builder-agent-creator",
  },
  {
    id: "integration-test",
    name: "Integration Test Agent",
    description: "Runs scripted checks against knowledge bases and tools.",
    avatar: "red",
    scope: "workspace",
    skills: ["sarvam-pdf"],
    knowledgeBaseIds: ["flat-prose"],
    instructions:
      "You are Integration Test Agent. Execute the user's test plan against attached knowledge bases and report pass/fail with citations. Do not improvise extra cases unless asked.",
    howYouOperate: [
      "Read the test plan before touching any file.",
      "Run each case in order and record expected vs actual.",
      "Stop on the first blocking failure unless told to continue.",
    ],
    workingEffectively: [
      "Always attach the source file name in the result.",
      "Use web search only when the plan explicitly requires it.",
      "Summarize at the end: passed, failed, skipped.",
    ],
    builderThreadId: "builder-integration-test",
  },
];

export const knowledgeBases: KnowledgeBase[] = [
  {
    id: "flat-prose",
    name: "Flat prose",
    subtitle: "Product docs and grouping notes",
    createdBy: "You",
    visibility: "personal",
    createdAt: "12 Aug 2026",
    agentIds: ["agent-creator", "integration-test"],
  },
];

export const kbFiles: KBFile[] = [
  {
    id: "structure-grouping",
    kbId: "flat-prose",
    name: "structure_grouping_test.pdf",
    size: "248 KB",
    status: "ready",
    addedAt: "12 Aug 2026",
  },
];

export const chatThreads: ChatThread[] = [
  { id: "kb-search", title: "Knowledge Base Search", agentId: "agent-creator" },
  { id: "untitled", title: "Untitled", agentId: "agent-creator" },
  { id: "meridian", title: "Meridian Migration", agentId: "integration-test" },
  { id: "kb-file", title: "Knowledge Base File", agentId: "agent-creator" },
  { id: "system-prompt", title: "System Prompt", agentId: "agent-creator" },
  { id: "prompt-request", title: "Prompt Request", agentId: "integration-test" },
];

export const messages: ChatMessage[] = [
  {
    id: "m1",
    threadId: "kb-search",
    role: "user",
    content: "Search the knowledge base for the grouping structure.",
  },
  {
    id: "m2",
    threadId: "kb-search",
    role: "assistant",
    thought: "Thought for 1s · Used 2 tools",
    content:
      "The grouping structure in Flat prose splits records into header, body, and trailer blocks. Headers carry the batch id; body rows are keyed by `group_id`; trailers hold counts. Empty groups are dropped before export.",
    citations: [{ id: "c1", label: "structure_grouping_test.pdf" }],
  },
  {
    id: "m3",
    threadId: "kb-search",
    role: "user",
    content: "What should fail the integration test?",
  },
  {
    id: "m4",
    threadId: "kb-search",
    role: "assistant",
    thought: "Thought for 1s · Used 1 tool",
    content:
      "Fail the case if a body row has no `group_id`, if the trailer count does not match the body, or if an empty group is still present after the drop step.",
    citations: [{ id: "c2", label: "structure_grouping_test.pdf" }],
  },
  {
    id: "b1",
    threadId: "builder-agent-creator",
    role: "user",
    content: "Help me tighten this agent's instructions for KB search.",
  },
  {
    id: "b2",
    threadId: "builder-agent-creator",
    role: "assistant",
    thought: "Thought for 1s · Used 3 tools",
    content:
      "Lead with the job: answer from attached knowledge bases, cite the file, and ask when the corpus is silent. I would drop the generic “be helpful” line — it competes with the citation rule.",
  },
  {
    id: "b3",
    threadId: "builder-agent-creator",
    role: "user",
    content: "Add a rule for when web search is allowed.",
  },
  {
    id: "b4",
    threadId: "builder-agent-creator",
    role: "assistant",
    thought: "Thought for 1s · Used 1 tool",
    content:
      "Use web search only after the attached KBs miss, and say that you went outside the corpus. Put that as the last operating rule so retrieval stays the default.",
  },
  {
    id: "b5",
    threadId: "builder-integration-test",
    role: "user",
    content: "Walk me through a playground case for the grouping PDF.",
  },
  {
    id: "b6",
    threadId: "builder-integration-test",
    role: "assistant",
    thought: "Thought for 1s · Used 2 tools",
    content:
      "Try: “Given structure_grouping_test.pdf, list the fail conditions for empty groups.” The agent should cite the PDF and mention trailer counts. If it improvises extra cases, the instructions are still too loose.",
    citations: [{ id: "c3", label: "structure_grouping_test.pdf" }],
  },
  {
    id: "u1",
    threadId: "untitled",
    role: "user",
    content: "Draft a first message for this agent.",
  },
  {
    id: "u2",
    threadId: "untitled",
    role: "assistant",
    thought: "Thought for 1s",
    content: "Ask it to restate the job in one sentence, then list the attached KBs it will use.",
  },
  {
    id: "md1",
    threadId: "meridian",
    role: "user",
    content: "What still blocks the Meridian migration?",
  },
  {
    id: "md2",
    threadId: "meridian",
    role: "assistant",
    thought: "Thought for 1s · Used 2 tools",
    content:
      "The grouping export still emits empty groups. Until trailer counts match body rows, the Meridian load job will reject the file.",
    citations: [{ id: "c4", label: "structure_grouping_test.pdf" }],
  },
];

export function getAgent(id: string) {
  return agents.find((agent) => agent.id === id);
}

export function getKnowledgeBase(id: string) {
  return knowledgeBases.find((kb) => kb.id === id);
}

export function getThread(id: string) {
  return chatThreads.find((thread) => thread.id === id);
}

export function messagesFor(threadId: string) {
  return messages.filter((message) => message.threadId === threadId);
}

export function filesFor(kbId: string) {
  return kbFiles.filter((file) => file.kbId === kbId);
}

export function agentsForKb(kb: KnowledgeBase) {
  return agents.filter((agent) => kb.agentIds.includes(agent.id));
}
