/** Turns a snake_case field key into a human-readable label, e.g.
 * "blood_pressure" -> "Blood pressure". Used anywhere a generic
 * key/value pair (vitals, corrected fields) is rendered directly from
 * data rather than from a hand-labeled form. */
export function labelizeFieldKey(key: string): string {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Splits a textarea's newline-separated lines into a trimmed, non-empty
 * string array -- used for the editable list fields (allergies, follow-up
 * instructions, referrals) in ReviewForm, which store each list as one
 * line per entry for a simple, dependency-free editing UI. */
export function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

export function listToLines(items: string[]): string {
  return items.join("\n");
}
