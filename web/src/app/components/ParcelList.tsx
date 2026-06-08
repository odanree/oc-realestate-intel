"use client";

import { Parcel } from "@/lib/api";

export default function ParcelList({ parcels }: { parcels: Parcel[] }) {
  if (!parcels.length) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400 mb-2">
        Retrieved parcels
      </h3>
      <ul className="space-y-2">
        {parcels.map((p, i) => (
          <li
            key={`${p.apn ?? i}`}
            className="text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md p-2"
          >
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-zinc-900 dark:text-zinc-100">
                {p.apn ?? "—"}
              </span>
              {p.year_built ? (
                <span className="text-zinc-400 text-[10px]">{p.year_built}</span>
              ) : null}
            </div>
            <div className="text-zinc-700 dark:text-zinc-300 mt-0.5 truncate">
              {p.address ?? "—"}
            </div>
            {p.owner ? (
              <div className="text-zinc-500 dark:text-zinc-400 mt-0.5 truncate">
                {p.owner}{" "}
                <span className="text-[10px] uppercase">
                  ({p.owner_kind ?? "—"})
                </span>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
