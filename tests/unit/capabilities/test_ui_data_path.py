"""The UI actually reaches its own API — the gap roll 1 fell through.

The regression case is roll 1's real source (`cyc_04d36309d793`): five page calls with
unprefixed paths against routes at `/api/runs`, in an app that passed 36/36 checks, all
five contract probes, `tests_pass`, `frontend_build`, and the boot audit. Nothing in the
pipeline followed the path the UI itself takes.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.ui_data_path import (
    LIVE_SERVER,
    METHOD_NOT_ALLOWED,
    PAGE_NOT_API,
    ROUTE_MISSING,
    SAMPLE_SEGMENT,
    SERVED,
    classify_ui_response,
    describe_failure,
    expects_json,
    extract_ui_calls,
)

pytestmark = [pytest.mark.domain_capabilities]

# Verbatim shapes from roll 1's delivered app/page.tsx and app/runs/[run_id]/page.tsx.
_ROLL_1_UI = {
    "app/page.tsx": """'use client';
import { api } from '@/lib/api';
export default function Page() {
  const data = await api<Run[]>('/runs');
  await api('/runs', { method: 'POST', body: JSON.stringify(formData) });
}
""",
    "app/runs/[run_id]/page.tsx": """'use client';
import { api } from '@/lib/api';
export default function Page() {
  const data = await api<Run>(`/runs/${runId}`);
  await api(`/runs/${runId}/join`, { method: 'POST' });
  await api(`/runs/${runId}/leave`, { method: 'POST' });
}
""",
}

_CORRECT_UI = {
    "app/page.tsx": """'use client';
import { api } from '@/lib/api';
const data = await api<Run[]>('/api/runs');
const one = await api<Run>(`/api/runs/${runId}`);
"""
}


class TestExtraction:
    def test_roll_ones_five_calls_are_all_found(self):
        calls = extract_ui_calls(_ROLL_1_UI, "nextjs_ts")
        assert [c.request_path for c in calls] == [
            "/runs",
            "/runs",
            f"/runs/{SAMPLE_SEGMENT}",
            f"/runs/{SAMPLE_SEGMENT}/join",
            f"/runs/{SAMPLE_SEGMENT}/leave",
        ]
        # the message must point at real source, or a failure is unactionable
        assert calls[0].location() == "app/page.tsx:4"

    def test_the_seam_prefix_is_applied_per_stack(self):
        """Stack #1's helper prepends `/api`; stack #2's fetches verbatim. Assuming
        either convention for the other stack is exactly roll 1's defect."""
        ui = {"src/views/RunsListView.jsx": "const d = await apiFetch('/runs')"}
        assert extract_ui_calls(ui, "fullstack_fastapi_react")[0].request_path == "/api/runs"
        assert extract_ui_calls(ui, "nextjs_ts")[0].request_path == "/runs"

    def test_an_unknown_stack_yields_nothing_rather_than_guessing(self):
        """A guessed prefix would invent failures in an app that works."""
        assert extract_ui_calls(_ROLL_1_UI, "django_htmx") == []

    def test_route_handlers_are_not_ui(self):
        """A route handler talking to the store is not a UI data call."""
        files = {"app/api/runs/route.ts": "const rows = store.all('runs')"}
        assert extract_ui_calls(files, "nextjs_ts") == []

    def test_a_raw_fetch_bypasses_the_seam_so_takes_no_prefix(self):
        files = {"app/page.tsx": "const r = await fetch('/api/runs')"}
        (call,) = extract_ui_calls(files, "fullstack_fastapi_react")
        assert call.request_path == "/api/runs"


class TestClassification:
    def test_a_framework_404_is_a_missing_route(self):
        """Next serves its own 404 page as HTML when nothing is mounted at the path."""
        assert classify_ui_response("/runs", 404, "text/html; charset=utf-8") == ROUTE_MISSING

    def test_an_apps_own_404_envelope_means_the_route_answered(self):
        """The discriminator that keeps correct apps passing: an unknown id returns 404
        through the scaffold's frozen errorResponse — JSON, not the framework's page."""
        assert classify_ui_response("/api/runs/x", 404, "application/json") == SERVED

    @pytest.mark.parametrize("status", [200, 201, 400, 409, 422, 500])
    def test_any_other_answer_means_the_route_exists(self, status):
        """This check asks only whether a route is mounted; whether the response is
        semantically right is the contract probes' question, not this one."""
        assert classify_ui_response("/api/runs", status, "application/json") == SERVED

    def test_an_absolute_url_is_the_live_server_class(self):
        assert classify_ui_response("http://localhost:3000/api/runs", 200, "") == LIVE_SERVER


class TestPageCollision:
    """The miss the first version of this check shipped with, caught by running it
    against roll 1's real app: App Router serves pages and API handlers from ONE tree
    (#859), so a wrong API path can land on a PAGE instead of 404ing. Roll 1's
    `api(`/runs/${runId}`)` hit `app/runs/[run_id]/page.tsx` — 200, HTML — and a
    404-only rule called it served."""

    def test_html_through_the_json_seam_is_a_page_not_the_api(self):
        assert (
            classify_ui_response("/runs/x", 200, "text/html; charset=utf-8", via_seam=True)
            == PAGE_NOT_API
        )

    def test_a_raw_fetch_may_legitimately_receive_html(self):
        """`fetch` promises nothing about the body; only the seam parses JSON by
        construction, so only the seam's calls are held to it."""
        assert classify_ui_response("/runs/x", 200, "text/html", via_seam=False) == SERVED

    def test_the_seam_functions_are_the_json_ones(self):
        assert expects_json("api") and expects_json("apiFetch")
        assert not expects_json("fetch")

    def test_the_message_explains_the_silent_shape(self):
        files = {"app/runs/[run_id]/page.tsx": "const d = await api<Run>(`/runs/${runId}`)"}
        (call,) = extract_ui_calls(files, "nextjs_ts")
        message = describe_failure(call, PAGE_NOT_API)
        assert "serves a PAGE, not the API" in message
        assert "renders blank" in message


class TestFailureMessages:
    def test_a_missing_route_message_names_file_line_and_both_paths(self):
        (call, *_) = extract_ui_calls(_ROLL_1_UI, "nextjs_ts")
        message = describe_failure(call, ROUTE_MISSING)
        assert "app/page.tsx:4" in message
        assert "'/runs'" in message
        assert "404s for every user" in message

    def test_the_live_server_message_names_its_own_class(self):
        files = {"app/page.tsx": "const r = await fetch('http://localhost:3000/api/runs')"}
        (call,) = extract_ui_calls(files, "nextjs_ts")
        assert "live server" in describe_failure(call, LIVE_SERVER)


#: The shape a formatter produces once a call carries a second argument: the opening
#: `api<Run>(` sits alone and the path lands on the next line. Verbatim from P6 roll 1's
#: `app/runs/[run_id]/page.tsx` (lines 58 and 88) and reproduced by rolls 3 and 4.
_WRAPPED_UI = {
    "app/runs/[run_id]/page.tsx": """'use client';
import { api } from '@/lib/api';
export default function Page() {
  const updatedRun = await api<Run>(
    `/api/runs/${runId}/join`,
    { method: 'POST' }
  );
  const afterLeave = await api<Run>(
    `/api/runs/${runId}/leave`,
    { method: 'POST' }
  );
}
"""
}


class TestWrappedCallSites:
    """#952. The first version scanned `content.split("\\n")` line by line, so a call
    written across two lines matched nothing. That does not weaken the check — it removes
    it, silently, while the roll still reads as audited. P6 roll 1 passed with its join and
    leave call sites extracted as zero, and the defect class this module exists to catch is
    exactly the one those two calls could have carried."""

    def test_a_call_whose_path_wraps_to_the_next_line_is_found(self):
        calls = extract_ui_calls(_WRAPPED_UI, "nextjs_ts")
        assert [c.request_path for c in calls] == [
            f"/api/runs/{SAMPLE_SEGMENT}/join",
            f"/api/runs/{SAMPLE_SEGMENT}/leave",
        ]

    def test_the_line_reported_is_where_the_call_opens_not_where_the_path_sits(self):
        """A message pointing at the path line sends a reader to an argument rather than
        to the call, and the call is what has to change."""
        calls = extract_ui_calls(_WRAPPED_UI, "nextjs_ts")
        assert [c.line for c in calls] == [4, 8]
        assert "app/runs/[run_id]/page.tsx:4" in describe_failure(calls[0], ROUTE_MISSING)

    def test_an_unterminated_quote_does_not_swallow_the_rest_of_the_file(self):
        """Scanning whole content makes a runaway match possible where line-scanning made
        it impossible, so the path class excludes newlines. Without that, one stray
        backtick yields a single call with a multi-line garbage path and every real call
        after it disappears."""
        files = {
            "app/page.tsx": "const a = await api('/api/runs\nconst b = await api('/api/teams')\n"
        }
        calls = extract_ui_calls(files, "nextjs_ts")
        assert [c.request_path for c in calls] == ["/api/teams"]

    def test_a_wrapped_call_and_an_inline_call_are_both_found_in_source_order(self):
        files = {
            "app/page.tsx": """const list = await api<Run[]>('/api/runs');
const joined = await api<Run>(
  `/api/runs/${runId}/join`,
  { method: 'POST' }
);
"""
        }
        calls = extract_ui_calls(files, "nextjs_ts")
        assert [(c.line, c.request_path) for c in calls] == [
            (1, "/api/runs"),
            (2, f"/api/runs/{SAMPLE_SEGMENT}/join"),
        ]


class TestMethodNotAllowed:
    """#953. The probe is a GET whatever verb the UI uses — sending the real verb would
    mutate the app under audit and make a second run of the audit meaningless. A POST-only
    route therefore answers 405 from the router with no content type, which the
    not-JSON rule read as `PAGE_NOT_API`. P6 rolls 3 and 4 were both failed on correct
    join and leave routes, each needing a human to boot the app and POST by hand."""

    @pytest.mark.parametrize("content_type", ["", "text/plain", "text/html; charset=utf-8"])
    def test_a_405_means_the_route_exists_whatever_it_carries(self, content_type):
        """405 is the strongest available evidence: the router matched the path and
        rejected only the method."""
        verdict = classify_ui_response(
            "/api/runs/x/join", METHOD_NOT_ALLOWED, content_type, via_seam=True
        )
        assert verdict == SERVED

    def test_a_page_is_still_caught_after_the_405_rule(self):
        """The over-correction to guard against: 405 becoming SERVED must not make every
        non-JSON answer SERVED. A page answers 200 with HTML and never 405."""
        assert (
            classify_ui_response("/runs/x", 200, "text/html; charset=utf-8", via_seam=True)
            == PAGE_NOT_API
        )

    def test_a_framework_404_is_still_a_missing_route(self):
        assert classify_ui_response("/api/nope", 404, "text/html") == ROUTE_MISSING


def test_the_two_defects_masked_each_other_on_a_correct_app():
    """The reason these ship together. Roll 1's wrapped join/leave calls were never
    extracted (#952), so its audit passed vacuously. Fixing extraction alone would have
    surfaced those same calls into the 405 misread (#953) and failed a correct app —
    turning a false pass into a false failure. Only both together verify it."""
    calls = extract_ui_calls(_WRAPPED_UI, "nextjs_ts")
    assert len(calls) == 2, "extraction must find them at all"
    for call in calls:
        # what a correct POST-only route actually answers a GET probe with
        assert classify_ui_response(call.request_path, METHOD_NOT_ALLOWED, "") == SERVED


def test_a_correctly_wired_ui_produces_no_failing_paths():
    """The check must pass the app roll 1 should have shipped."""
    calls = extract_ui_calls(_CORRECT_UI, "nextjs_ts")
    assert [c.request_path for c in calls] == ["/api/runs", f"/api/runs/{SAMPLE_SEGMENT}"]
    for call in calls:
        assert classify_ui_response(call.request_path, 200, "application/json") == SERVED
