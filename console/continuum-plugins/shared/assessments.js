// The crew's assessments of a goal set's expected results, as a view reads them (SIP-0115 §5.7,
// §8.3; slice 5, #2888). `GET /api/v1/campaigns/{id}/assessments` answers
// `CampaignAssessmentsResponse`: campaign_id, project_id, revision, log_seq, and `results`, one per
// expected result of the revision the Campaign reads now: `expected_result`, its `statement` and
// `surface` at that revision, `standing` (`current`, `stale`, `conflicting` or `unassessed`) and
// `assessments`, the latest alone or, while they conflict, each that disagrees, newest first. The
// Campaigns plugin and the goals panel both show it, so what a standing says is said once, here.

/** Where a framework cause's issue is filed: an assessment names it by number (§5.7). */
export const ISSUES_URL = 'https://github.com/backspring-labs/squad-ops/issues';

const STANDING_LABELS = {
  current: 'current',
  stale: 'stale: an acceptance or a revision came after it',
  conflicting: 'conflicting: only a new assessment naming both ends it',
  unassessed: 'not assessed',
};

const READINGS = { met: 'met', not_met: 'not met', unclear: 'unclear' };

const CAUSES = {
  app_work: "the squad's next increment",
  framework_defect: 'a framework defect',
  framework_gap: 'a framework gap',
  needs_owner: 'needs the owner',
};

/** One assessment as a row shows it. */
export function assessmentEntry(assessment) {
  return {
    sequence: assessment.sequence,
    reading: assessment.reading,
    readingText: READINGS[assessment.reading] ?? assessment.reading,
    causeText: assessment.cause ? (CAUSES[assessment.cause] ?? assessment.cause) : null,
    issue: assessment.issue ?? null,
    issueUrl: assessment.issue != null ? `${ISSUES_URL}/${assessment.issue}` : null,
    author: assessment.author,
    revision: assessment.goals_revision,
    sourceRef: assessment.source_ref ?? null,
    createdAt: assessment.created_at,
  };
}

/** One expected result's standing as a view shows it; one it doesn't know is shown as it reads. */
export function standingRow(result) {
  return {
    expected_result: result.expected_result,
    statement: result.statement ?? null,
    surface: result.surface ?? null,
    standing: result.standing,
    label: STANDING_LABELS[result.standing] ?? result.standing,
    entries: (result.assessments ?? []).map(assessmentEntry),
  };
}

/** Each expected result of the view, in the goal set's order. */
export const standingRows = (view) => (view?.results ?? []).map(standingRow);

const sameDefinition = (a, b) =>
  a.statement === b.statement && JSON.stringify(a.surface) === JSON.stringify(b.surface);

/**
 * The row for `result`, an expected result the viewer shows from its own revision, or null: no
 * Campaign is chosen, or it reads a revision that doesn't hold the result. Never a row saying it
 * wasn't assessed, which would be a claim about a Campaign that can't have assessed it.
 *
 * A pinned Campaign reads an earlier revision, where the same id may say something else. Then
 * `readAs` is the definition this row is about, so a reading is never shown as if it judged the
 * statement beside it; otherwise it is null.
 */
export function standingOf(view, result) {
  const found = (view?.results ?? []).find((r) => r.expected_result === result.id);
  if (!found) return null;
  const row = standingRow(found);
  const readAs = sameDefinition(row, result)
    ? null
    : { revision: view.revision, statement: row.statement, surface: row.surface };
  return { ...row, readAs };
}
