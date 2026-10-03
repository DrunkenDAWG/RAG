import { clsx, type ClassValue } from "clsx";
import type { Source } from "../types";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

// "Page 42" / "Pages 42–43", or null when the source has no page metadata
export function formatPages(source: Source): string | null {
  if (!source.page) return null;
  return source.page_end && source.page_end !== source.page
    ? `Pages ${source.page}–${source.page_end}`
    : `Page ${source.page}`;
}
