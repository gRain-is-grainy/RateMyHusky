/**
 * Returns a numeric sort key for a term title where higher = more recent.
 * Primary sort is by year; secondary is by season/modifier within the year.
 *
 * Order within a year (highest → most recent):
 *   Fall (7) > Fall A (6) > Full Summer (5) > Summer 2 (4) > Summer 1 (3) > Spring (2) > Spring A (1)
 */
export function termSortKey(title: string): number {
  if (!title) return 0;
  const lower = title.toLowerCase();
  // Try word-bounded year first (e.g. "Fall 2025"), then 4-digit prefix of 6-digit code (e.g. "202510")
  const yearMatch = lower.match(/\b(20\d{2})\b/) ?? lower.match(/(20\d{2})\d{2}/);
  if (!yearMatch) return 0;
  const year = parseInt(yearMatch[1]);

  let subKey = 0;
  if (/\bfall\b/.test(lower)) {
    // "Fall A 2025" has "fall a" directly; "Fall 2024 Law A Term" does NOT
    subKey = /\bfall\s+a\b/.test(lower) ? 6 : 7;
  } else if (/\bfull\s+summer\b/.test(lower)) {
    subKey = 5;
  } else if (/\bsummer\b/.test(lower)) {
    if (/\bsummer\s+2\b/.test(lower)) subKey = 4;
    else if (/\bsummer\s+1\b/.test(lower)) subKey = 3;
    else subKey = 4; // generic summer (no number)
  } else if (/\bspring\b/.test(lower)) {
    subKey = /\bspring\s+a\b/.test(lower) ? 1 : 2;
  }
  // Winter and unknown terms get subKey = 0

  return year * 10 + subKey;
}
