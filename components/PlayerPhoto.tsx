"use client";

import { useState } from "react";
import clsx from "clsx";
import { initials } from "@/lib/format";

type Props = {
  src?: string | null;
  name: string;
  size?: number;
  className?: string;
};

export default function PlayerPhoto({ src, name, size = 56, className }: Props) {
  const [errored, setErrored] = useState(false);
  const showImg = !!src && !errored;
  return (
    <div
      className={clsx(
        "relative shrink-0 overflow-hidden rounded-full bg-ink-800 ring-1 ring-ink-700 flex items-center justify-center text-ink-200",
        className,
      )}
      style={{ width: size, height: size }}
    >
      {showImg ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src!}
          alt={name}
          width={size}
          height={size}
          className="h-full w-full object-cover"
          onError={() => setErrored(true)}
        />
      ) : (
        <span
          className="font-semibold tracking-tight"
          style={{ fontSize: Math.max(11, size * 0.36) }}
        >
          {initials(name)}
        </span>
      )}
    </div>
  );
}
