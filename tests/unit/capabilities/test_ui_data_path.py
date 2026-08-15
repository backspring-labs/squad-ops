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


def test_a_correctly_wired_ui_produces_no_failing_paths():
    """The check must pass the app roll 1 should have shipped."""
    calls = extract_ui_calls(_CORRECT_UI, "nextjs_ts")
    assert [c.request_path for c in calls] == ["/api/runs", f"/api/runs/{SAMPLE_SEGMENT}"]
    for call in calls:
        assert classify_ui_response(call.request_path, 200, "application/json") == SERVED
