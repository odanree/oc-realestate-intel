"use client";

export type TraceEvent = {
  stage: "router" | "retrieval" | "comparison" | "summarize";
  label: string;
  t: number;
};

const STAGE_COLORS: Record<string, string> = {
  router: "bg-indigo-500",
  retrieval: "bg-emerald-500",
  comparison: "bg-amber-500",
  summarize: "bg-sky-500",
};

export default function AgentTrace({
  events,
  streaming,
  compact = false,
}: {
  events: TraceEvent[];
  streaming: boolean;
  compact?: boolean;
}) {
  return (
    <ol className={compact ? "space-y-1" : "space-y-1.5"}>
      {events.map((evt, i) => {
        const isLast = i === events.length - 1;
        return (
          <li
            key={i}
            className={`flex items-center gap-2 ${compact ? "text-[11px]" : "text-xs"} text-zinc-700 dark:text-zinc-300`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${STAGE_COLORS[evt.stage] ?? "bg-zinc-400"} ${
                streaming && isLast ? "animate-pulse" : ""
              }`}
              aria-hidden
            />
            <span className="font-mono text-zinc-500 dark:text-zinc-400 w-20">
              {evt.stage}
            </span>
            <span>{evt.label}</span>
          </li>
        );
      })}
      {streaming && (
        <li className="flex items-center gap-2 text-xs text-zinc-400 dark:text-zinc-500 italic">
          <span className="w-1.5 h-1.5 rounded-full bg-zinc-300 dark:bg-zinc-600 animate-pulse" />
          working…
        </li>
      )}
    </ol>
  );
}
