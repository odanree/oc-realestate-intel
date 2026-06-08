"use client";

import { GraphFact } from "@/lib/api";

export default function TitleChain({ facts }: { facts: GraphFact[] }) {
  if (!facts.length) return null;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
          Title chain
        </h3>
        <span
          title="Real assessor / recorder data is paywalled. See app/ingestion/synthetic_owners.py"
          className="text-[9px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
        >
          synthetic
        </span>
      </div>
      <ol className="space-y-2">
        {facts.map((f, i) => (
          <li
            key={`${f.doc_number ?? i}`}
            className="text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md p-2"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {f.date ?? "—"}
              </span>
              {f.price ? (
                <span className="text-emerald-600 dark:text-emerald-400 font-mono">
                  ${f.price.toLocaleString()}
                </span>
              ) : null}
            </div>
            <div className="text-zinc-500 dark:text-zinc-400 mt-1 truncate">
              {f.grantor ?? "—"} → {f.grantee ?? "—"}
            </div>
            {f.doc_number ? (
              <div className="text-zinc-400 dark:text-zinc-500 mt-0.5 font-mono text-[10px]">
                doc# {f.doc_number}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
