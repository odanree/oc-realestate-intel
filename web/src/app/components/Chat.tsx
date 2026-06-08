"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Citation,
  GraphFact,
  Parcel,
  StreamEvent,
  streamQuery,
} from "@/lib/api";
import AgentTrace, { TraceEvent } from "./AgentTrace";
import ParcelList from "./ParcelList";
import TitleChain from "./TitleChain";

type Turn = {
  id: string;
  query: string;
  status: "streaming" | "done" | "error";
  intent?: string;
  answer?: string;
  citations: Citation[];
  parcels: Parcel[];
  graph_facts: GraphFact[];
  trace: TraceEvent[];
  errorMessage?: string;
};

const EXAMPLES = [
  "Who owns parcel 461-211-62?",
  "What does FLORES FAMILY TR own?",
  "Find parcels on Bridgeport Road in Irvine",
  "Show the title chain for 461-211-62",
];

export default function Chat() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new turns/events.
  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  const submit = useCallback(
    async (q: string) => {
      const query = q.trim();
      if (!query || busy) return;
      setBusy(true);
      setInput("");

      const turnId = crypto.randomUUID();
      const newTurn: Turn = {
        id: turnId,
        query,
        status: "streaming",
        citations: [],
        parcels: [],
        graph_facts: [],
        trace: [{ stage: "router", label: "Routing…", t: Date.now() }],
      };
      setTurns((t) => [...t, newTurn]);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        for await (const evt of streamQuery(query, ctrl.signal)) {
          setTurns((prev) =>
            prev.map((t) => (t.id === turnId ? applyEvent(t, evt) : t)),
          );
        }
      } catch (e) {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === turnId
              ? { ...t, status: "error", errorMessage: (e as Error).message }
              : t,
          ),
        );
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit(input);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 h-[calc(100vh-160px)]">
      <div className="flex flex-col bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <div ref={transcriptRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {turns.length === 0 && <EmptyState onPick={submit} />}
          {turns.map((turn) => (
            <TurnView key={turn.id} turn={turn} />
          ))}
        </div>
        <form
          onSubmit={onSubmit}
          className="border-t border-zinc-200 dark:border-zinc-800 px-4 py-3 flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a parcel, owner, address, or title chain…"
            disabled={busy}
            className="flex-1 px-3 py-2 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={busy || input.trim().length === 0}
            className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-300 dark:disabled:bg-zinc-700 disabled:cursor-not-allowed text-white text-sm font-medium"
          >
            {busy ? "Thinking…" : "Send"}
          </button>
        </form>
      </div>
      <aside className="hidden lg:block">
        <SidePanel turn={turns[turns.length - 1]} />
      </aside>
    </div>
  );
}

function applyEvent(turn: Turn, evt: StreamEvent): Turn {
  switch (evt.kind) {
    case "router":
      return {
        ...turn,
        intent: evt.intent,
        trace: [
          ...turn.trace,
          { stage: "router", label: `Intent: ${evt.intent}`, t: Date.now() },
        ],
      };
    case "retrieval":
      return {
        ...turn,
        parcels: evt.parcels,
        graph_facts: evt.graph_facts,
        trace: [
          ...turn.trace,
          {
            stage: "retrieval",
            label: `Retrieved ${evt.parcels.length} parcel${evt.parcels.length === 1 ? "" : "s"}${evt.graph_facts.length ? ` · ${evt.graph_facts.length} transfers` : ""}`,
            t: Date.now(),
          },
        ],
      };
    case "comparison":
      return {
        ...turn,
        parcels: evt.parcels,
        trace: [
          ...turn.trace,
          {
            stage: "comparison",
            label: `Comparison set: ${evt.parcels.length} parcels`,
            t: Date.now(),
          },
        ],
      };
    case "summarize":
      return {
        ...turn,
        answer: evt.answer,
        citations: evt.citations,
        trace: [
          ...turn.trace,
          { stage: "summarize", label: "Synthesized answer", t: Date.now() },
        ],
      };
    case "done":
      return { ...turn, status: "done" };
    case "error":
      return { ...turn, status: "error", errorMessage: evt.message };
    default:
      return turn;
  }
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-2xl bg-blue-600 text-white px-4 py-2 rounded-2xl rounded-br-md">
          {turn.query}
        </div>
      </div>
      {turn.intent && <IntentBadge intent={turn.intent} />}
      {turn.answer ? (
        <div className="max-w-2xl bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 px-4 py-3 rounded-2xl rounded-bl-md prose prose-sm dark:prose-invert max-w-none">
          <Markdownish text={turn.answer} />
          {turn.citations.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2 not-prose">
              {turn.citations.map((c) => (
                <a
                  key={c.apn}
                  href="#"
                  className="text-xs font-mono px-2 py-1 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-200"
                >
                  {c.apn}
                </a>
              ))}
            </div>
          )}
        </div>
      ) : (
        <AgentTrace events={turn.trace} streaming={turn.status === "streaming"} />
      )}
      {turn.status === "error" && (
        <div className="text-sm text-red-600 dark:text-red-400">
          error: {turn.errorMessage}
        </div>
      )}
    </div>
  );
}

function IntentBadge({ intent }: { intent: string }) {
  const colors: Record<string, string> = {
    lookup: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    compare: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    summarize: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
    title_chain: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
    portfolio: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-950 dark:text-fuchsia-300",
    unknown: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  };
  return (
    <span
      className={`inline-block text-xs font-mono px-2 py-0.5 rounded ${colors[intent] ?? colors.unknown}`}
    >
      intent: {intent}
    </span>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="text-center py-12">
      <h2 className="text-zinc-900 dark:text-zinc-100 text-lg font-semibold mb-1">
        Ask about Orange County parcels
      </h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        Lookup by APN or address, list ownership, trace title chains.
      </p>
      <div className="flex flex-wrap gap-2 justify-center max-w-xl mx-auto">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="text-xs px-3 py-1.5 rounded-full border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function SidePanel({ turn }: { turn?: Turn }) {
  if (!turn) {
    return (
      <div className="h-full bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 text-xs text-zinc-500 dark:text-zinc-400">
        Retrieved facts will appear here as you ask questions.
      </div>
    );
  }
  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 space-y-4">
      <div>
        <h3 className="text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400 mb-2">
          Agent trace
        </h3>
        <AgentTrace events={turn.trace} streaming={turn.status === "streaming"} compact />
      </div>
      <ParcelList parcels={turn.parcels} />
      <TitleChain facts={effectiveTitleChain(turn)} />
    </div>
  );
}

function effectiveTitleChain(turn: Turn): GraphFact[] {
  if (turn.graph_facts.length) return turn.graph_facts;
  // Fall back to the first parcel's embedded title chain (lookup-intent case).
  const first = turn.parcels[0];
  return first?.title_chain ?? [];
}

// Tiny markdown rendering: paragraphs, bold, headings, lists, tables.
// Avoids a markdown dependency for the scaffold.
function Markdownish({ text }: { text: string }) {
  // Block split on double newline; lines with leading "|" are tables.
  const blocks = text.split(/\n{2,}/);
  return (
    <>
      {blocks.map((block, i) => {
        if (block.startsWith("|") && block.includes("\n|")) {
          return <MdTable key={i} src={block} />;
        }
        if (block.startsWith("##")) {
          return (
            <h3 key={i} className="font-semibold mt-2">
              {block.replace(/^#+\s*/, "")}
            </h3>
          );
        }
        if (block.match(/^\s*[-*]\s+/m)) {
          const items = block
            .split("\n")
            .filter((l) => l.trim())
            .map((l) => l.replace(/^\s*[-*]\s+/, ""));
          return (
            <ul key={i} className="list-disc pl-5">
              {items.map((it, j) => (
                <li key={j}>{renderInline(it)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="whitespace-pre-wrap leading-relaxed">
            {renderInline(block)}
          </p>
        );
      })}
    </>
  );
}

function renderInline(s: string): React.ReactNode {
  // **bold**
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function MdTable({ src }: { src: string }) {
  const lines = src.split("\n").filter((l) => l.startsWith("|"));
  if (lines.length < 2) return <pre className="text-xs">{src}</pre>;
  const rows = lines
    .filter((l) => !/^\|\s*[-:|\s]+\s*\|/.test(l))
    .map((l) =>
      l
        .split("|")
        .slice(1, -1)
        .map((c) => c.trim()),
    );
  const [head, ...body] = rows;
  return (
    <div className="overflow-x-auto not-prose -mx-1">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th
                key={i}
                className="text-left font-medium px-2 py-1 border-b border-zinc-200 dark:border-zinc-700"
              >
                {renderInline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className="px-2 py-1 border-b border-zinc-100 dark:border-zinc-800 font-mono text-[11px]"
                >
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
