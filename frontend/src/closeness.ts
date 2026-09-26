// Turns a search score (0 to 1, where 1 is the best result of the query) into the colour of the bar on
// a result card's edge and a word for its tooltip. Every result stays fully visible; only the bar changes.

type Closeness = {
  label: string
  barClass: string
}

// Checked from the top: the first step whose threshold the score reaches wins.
const STEPS: { minimumScore: number; closeness: Closeness }[] = [
  { minimumScore: 0.75, closeness: { label: 'Close match', barClass: 'bg-indigo-600' } },
  { minimumScore: 0.5, closeness: { label: 'Good match', barClass: 'bg-indigo-400' } },
  { minimumScore: 0.25, closeness: { label: 'Partial match', barClass: 'bg-indigo-200' } },
  { minimumScore: 0, closeness: { label: 'Distant match', barClass: 'bg-gray-200' } },
]

export function closeness(score: number): Closeness {
  for (const step of STEPS) {
    if (score >= step.minimumScore) {
      return step.closeness
    }
  }
  return STEPS[STEPS.length - 1].closeness
}
