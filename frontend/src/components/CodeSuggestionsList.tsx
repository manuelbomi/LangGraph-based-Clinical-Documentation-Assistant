import type { ProblemCodeSuggestions } from "../api/types";

interface CodeSuggestionsListProps {
  suggestions: ProblemCodeSuggestions[];
}

/** Renders semantic-search ICD-10 suggestions for each problem-list item.
 * Always labeled "for clinician confirmation" -- these are never applied to
 * a patient's record automatically. See the root README's Scope & Safety
 * section and `code_lookup_node`. */
export function CodeSuggestionsList({ suggestions }: CodeSuggestionsListProps) {
  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <h4 className="text-xs font-semibold uppercase text-slate-500">
        Suggested ICD-10 codes <span className="normal-case text-slate-400">(for clinician confirmation)</span>
      </h4>
      {suggestions.map((entry, i) => (
        <div key={i} className="border-t border-slate-100 pt-2 first:border-t-0 first:pt-0">
          <div className="mb-1 font-medium text-slate-700">{entry.problem}</div>
          <ul className="space-y-0.5">
            {entry.suggestions.map((code) => (
              <li key={code.code} className="flex items-center justify-between text-xs text-slate-600">
                <span>
                  <span className="font-mono font-medium text-brand-700">{code.code}</span> -- {code.description}
                </span>
                <span className="text-slate-400">{(code.score * 100).toFixed(0)}% match</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
