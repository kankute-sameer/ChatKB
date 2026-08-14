import type { CSSProperties } from "react";
import { tokens } from "@/design/tokens";
import { cn } from "@/lib/utils";

interface TwinOrbitProps {
  size?: number;
  speed?: number;
  className?: string;
}

export function TwinOrbit({ size = 44, speed = 1.4, className }: TwinOrbitProps) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={cn("twin-orbit", className)}
      style={
        {
          "--size": `${size}px`,
          "--speed": `${speed}s`,
          "--dot-a": tokens.colors.ink.DEFAULT,
          "--dot-b": tokens.colors.orbit,
          "--ease": tokens.motion.orbit,
        } as CSSProperties
      }
    >
      <span />
      <span />
    </div>
  );
}
