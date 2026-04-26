"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Fuse from "fuse.js";
import type { CurrentMappingRow } from "@/lib/types";
import { LEAGUE_NAMES, POSITION_LABELS } from "@/lib/labels";
import PlayerPhoto from "./PlayerPhoto";

type Props = {
  mapping: CurrentMappingRow[];
  onSelect: (row: CurrentMappingRow) => void;
};

export default function PlayerSearch({ mapping, onSelect }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const fuse = useMemo(
    () =>
      new Fuse(mapping, {
        keys: ["player_name", "team_name"],
        threshold: 0.35,
        ignoreLocation: true,
        minMatchCharLength: 2,
      }),
    [mapping],
  );

  const results = useMemo(() => {
    const trimmed = q.trim();
    if (trimmed.length < 2) return [];
    return fuse.search(trimmed, { limit: 10 }).map((r) => r.item);
  }, [q, fuse]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <input
        type="search"
        autoComplete="off"
        spellCheck={false}
        placeholder="Search any current player by name or club…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        className="w-full rounded-md border border-ink-700 bg-ink-900 px-4 py-3 text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
      />
      {open && q.trim().length >= 2 ? (
        <div className="absolute z-20 mt-1 w-full rounded-md border border-ink-700 bg-ink-900 shadow-xl max-h-96 overflow-auto">
          {results.length === 0 ? (
            <div className="px-4 py-3 text-sm text-ink-400">
              No players match “{q.trim()}”.
            </div>
          ) : (
            <ul>
              {results.map((row) => (
                <li key={row.player_uid}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(row);
                      setQ("");
                      setOpen(false);
                    }}
                    className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-ink-800"
                  >
                    <PlayerPhoto
                      src={row.player_photo_url}
                      name={row.player_name}
                      size={36}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-ink-100">
                        {row.player_name}
                      </div>
                      <div className="truncate text-xs text-ink-400">
                        {row.team_name ?? "—"} ·{" "}
                        {row.league_id != null
                          ? LEAGUE_NAMES[row.league_id] ?? `League ${row.league_id}`
                          : "—"}
                        {row.model_position
                          ? ` · ${POSITION_LABELS[row.model_position] ?? row.model_position}`
                          : ""}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
