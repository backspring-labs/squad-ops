# Test Execution Report

**Result:** tests failed (exit code 1, 1 test file(s), 18 source file(s))

**Exit code:** 1

**Test files:** 1

**Source files:** 18


## stdout

```
=== Frontend (vitest) ===

 RUN  v2.1.9 /tmp/qa_node_mxxhrrl8/frontend

 ✓ src/__tests__/runs.test.jsx > CreateRunView > renders all six form fields and the submit button
 ✓ src/__tests__/runs.test.jsx > CreateRunView > does not call the API when required fields are empty
 × src/__tests__/runs.test.jsx > CreateRunView > navigates to the runs list after a successful create 1015ms
   → Unable to find an element by: [data-testid="runs-list-view"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > CreateRunView > displays a server error when the API rejects the create request 1014ms
   → Unable to find an element by: [data-testid="create-run-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > RunsListView > renders a list of runs with title, datetime, location, and participant count
   → Unable to find an element by: [data-testid="run-row"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-list-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mUpcoming Runs[0m
        [36m</h1>[39m
        [36m<p>[39m
          [36m<a[39m
            [33mdata-testid[39m=[32m"create-run-link"[39m
            [33mhref[39m=[32m"/create"[39m
          [36m>[39m
            [0mCreate a new run[0m
          [36m</a>[39m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > RunsListView > shows empty state when no runs exist
   → Unable to find an element by: [data-testid="empty-state"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-list-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mUpcoming Runs[0m
        [36m</h1>[39m
        [36m<p>[39m
          [36m<a[39m
            [33mdata-testid[39m=[32m"create-run-link"[39m
            [33mhref[39m=[32m"/create"[39m
          [36m>[39m
            [0mCreate a new run[0m
          [36m</a>[39m
        [36m</p>[39m
        [36m<ul>[39m
          [36m<li>[39m
            [36m<a[39m
              [33mdata-testid[39m=[32m"run-row"[39m
              [33mhref[39m=[32m"/runs/r1"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-title"[39m
              [36m>[39m
                [0mMorning 5K[0m
              [36m</span>[39m
              [0m — [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-datetime"[39m
              [36m>[39m
                [0m2025-06-15T07:00:00[0m
              [36m</span>[39m
              [0m — [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-location"[39m
              [36m>[39m
                [0mRiverside Park[0m
              [36m</span>[39m
              [0m — [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"participant-count"[39m
              [36m>[39m
                [0m2[0m
                [0m participant[0m
                [0ms[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
        [36m</ul>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > RunDetailView > renders run fields and the participant list
   → Unable to find an element by: [data-testid="run-title"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mRun Detail[0m
        [36m</h1>[39m
        [36m<p[39m
          [33mdata-testid[39m=[32m"run-detail-error"[39m
          [33mrole[39m=[32m"alert"[39m
        [36m>[39m
          [0mTitle is required[0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > RunDetailView > join form submits, triggers a refresh, and shows the new participant
   → Unable to find an element by: [data-testid="participant-name"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m/>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m/>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m/>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m0[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<p>[39m
            [0mNo participants yet.[0m
          [36m</p>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > RunDetailView > displays the duplicate-name error when join is rejected 1013ms
   → Unable to find an element by: [data-testid="run-detail-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m/>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m/>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m/>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m0[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<p>[39m
            [0mNo participants yet.[0m
          [36m</p>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m/>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m/>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m/>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m0[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<p>[39m
            [0mNo participants yet.[0m
          [36m</p>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 × src/__tests__/runs.test.jsx > RunDetailView > leave form removes a participant and refreshes the view
   → expected [ <li …(1)></li>, <li …(1)></li> ] to have a length of 1 but got 2
 × src/__tests__/runs.test.jsx > RunDetailView > shows a not-found error for an unknown run id 1010ms
   → Unable to find an element by: [data-testid="run-detail-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m>[39m
          [0mMorning 5K[0m
        [36m</h1>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m>[39m
            [0m2025-06-15T07:00:00[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m>[39m
            [0mRiverside Park[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mDistance[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-distance"[39m
          [36m>[39m
            [0m5K[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mPace Target[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-pace-target"[39m
          [36m>[39m
            [0m9:30/mi[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mRoute Notes[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-route-notes"[39m
          [36m>[39m
            [0mLoop around the lake[0m
          [36m</dd>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m1[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<ul[39m
            [33mdata-testid[39m=[32m"participant-list"[39m
          [36m>[39m
            [36m<li[39m
              [33mdata-testid[39m=[32m"participant-name"[39m
            [36m>[39m
              [0mAlice[0m
            [36m</li>[39m
          [36m</ul>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m>[39m
          [0mMorning 5K[0m
        [36m</h1>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m>[39m
            [0m2025-06-15T07:00:00[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m>[39m
            [0mRiverside Park[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mDistance[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-distance"[39m
          [36m>[39m
            [0m5K[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mPace Target[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-pace-target"[39m
          [36m>[39m
            [0m9:30/mi[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mRoute Notes[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-route-notes"[39m
          [36m>[39m
            [0mLoop around the lake[0m
          [36m</dd>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m1[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<ul[39m
            [33mdata-testid[39m=[32m"participant-list"[39m
          [36m>[39m
            [36m<li[39m
              [33mdata-testid[39m=[32m"participant-name"[39m
            [36m>[39m
              [0mAlice[0m
            [36m</li>[39m
          [36m</ul>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

⎯⎯⎯⎯⎯⎯ Unhandled Errors ⎯⎯⎯⎯⎯⎯

Vitest caught 5 unhandled errors during the test run.
This might cause false positive tests. Resolve unhandled errors to make sure your tests are not affected.
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
 Test Files  1 failed (1)
      Tests  9 failed | 2 passed (11)
     Errors  5 errors
   Start at  13:10:53
   Duration  4.72s (transform 82ms, setup 71ms, collect 79ms, tests 4.14s, environment 198ms, prepare 43ms)

JSON report written to /tmp/qa_node_mxxhrrl8/frontend/.vitest_report.json

```


## stderr

```
=== Frontend (vitest) ===
stderr | src/__tests__/runs.test.jsx > CreateRunView > renders all six form fields and the submit button
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 9 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/runs.test.jsx > CreateRunView > navigates to the runs list after a successful create
TestingLibraryElementError: Unable to find an element by: [data-testid="runs-list-view"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:86:33
 ❯ src/__tests__/runs.test.jsx:83:25
     81|     fireEvent.click(screen.getByTestId('create-run-submit'))
     82| 
     83|     expect(await screen.findByTestId('runs-list-view')).toBeInTheDocum…
       |                         ^
     84|     expect(screen.getByTestId('run-title')).toHaveTextContent('Morning…
     85|   })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/9]⎯

 FAIL  src/__tests__/runs.test.jsx > CreateRunView > displays a server error when the API rejects the create request
TestingLibraryElementError: Unable to find an element by: [data-testid="create-run-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
          [33mnovalidate[39m=[32m""[39m
        [36m>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-title"[39m
            [36m>[39m
              [0mTitle [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-title"[39m
              [33mid[39m=[32m"field-title"[39m
              [33mname[39m=[32m"title"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-datetime"[39m
            [36m>[39m
              [0mDate / Time [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-datetime"[39m
              [33mid[39m=[32m"field-datetime"[39m
              [33mname[39m=[32m"datetime"[39m
              [33mtype[39m=[32m"datetime-local"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-meeting-location"[39m
            [36m>[39m
              [0mMeeting Location [0m
              [36m<span[39m
                [33maria-hidden[39m=[32m"true"[39m
              [36m>[39m
                [0m*[0m
              [36m</span>[39m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-meeting-location"[39m
              [33mid[39m=[32m"field-meeting-location"[39m
              [33mname[39m=[32m"meeting_location"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-distance"[39m
            [36m>[39m
              [0mDistance (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-distance"[39m
              [33mid[39m=[32m"field-distance"[39m
              [33mname[39m=[32m"distance"[39m
              [33mplaceholder[39m=[32m"e.g. 5K, 6 mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-pace-target"[39m
            [36m>[39m
              [0mPace Target (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-pace-target"[39m
              [33mid[39m=[32m"field-pace-target"[39m
              [33mname[39m=[32m"pace_target"[39m
              [33mplaceholder[39m=[32m"e.g. 9:00-10:00/mi"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<p>[39m
            [36m<label[39m
              [33mfor[39m=[32m"field-route-notes"[39m
            [36m>[39m
              [0mRoute Notes (optional)[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"field-route-notes"[39m
              [33mid[39m=[32m"field-route-notes"[39m
              [33mname[39m=[32m"route_notes"[39m
              [33mtype[39m=[32m"text"[39m
            [36m/>[39m
          [36m</p>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:86:33
 ❯ src/__tests__/runs.test.jsx:101:34
     99|     fireEvent.click(screen.getByTestId('create-run-submit'))
    100| 
    101|     const errorEl = await screen.findByTestId('create-run-error')
       |                                  ^
    102|     expect(errorEl).toHaveTextContent('Title is required')
    103|   })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunsListView > renders a list of runs with title, datetime, location, and participant count
TestingLibraryElementError: Unable to find an element by: [data-testid="run-row"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-list-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mUpcoming Runs[0m
        [36m</h1>[39m
        [36m<p>[39m
          [36m<a[39m
            [33mdata-testid[39m=[32m"create-run-link"[39m
            [33mhref[39m=[32m"/create"[39m
          [36m>[39m
            [0mCreate a new run[0m
          [36m</a>[39m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:76:38
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:52:17
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:95:19
 ❯ src/__tests__/runs.test.jsx:114:19
    112|     await screen.findByTestId('runs-list-view')
    113|     expect(screen.getByTestId('create-run-link')).toBeInTheDocument()
    114|     expect(screen.getByTestId('run-row')).toBeInTheDocument()
       |                   ^
    115|     expect(screen.getByTestId('run-title')).toHaveTextContent('Morning…
    116|     expect(screen.getByTestId('run-datetime')).toHaveTextContent('2025…

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[3/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunsListView > shows empty state when no runs exist
TestingLibraryElementError: Unable to find an element by: [data-testid="empty-state"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-list-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mUpcoming Runs[0m
        [36m</h1>[39m
        [36m<p>[39m
          [36m<a[39m
            [33mdata-testid[39m=[32m"create-run-link"[39m
            [33mhref[39m=[32m"/create"[39m
          [36m>[39m
            [0mCreate a new run[0m
          [36m</a>[39m
        [36m</p>[39m
        [36m<ul>[39m
          [36m<li>[39m
            [36m<a[39m
              [33mdata-testid[39m=[32m"run-row"[39m
              [33mhref[39m=[32m"/runs/r1"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-title"[39m
              [36m>[39m
                [0mMorning 5K[0m
              [36m</span>[39m
              [0m — [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-datetime"[39m
              [36m>[39m
                [0m2025-06-15T07:00:00[0m
              [36m</span>[39m
              [0m — [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-location"[39m
              [36m>[39m
                [0mRiverside Park[0m
              [36m</span>[39m
              [0m — [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"participant-count"[39m
              [36m>[39m
                [0m2[0m
                [0m participant[0m
                [0ms[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
        [36m</ul>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:76:38
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:52:17
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:95:19
 ❯ src/__tests__/runs.test.jsx:127:19
    125| 
    126|     await screen.findByTestId('runs-list-view')
    127|     expect(screen.getByTestId('empty-state')).toBeInTheDocument()
       |                   ^
    128|   })
    129| })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[4/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > renders run fields and the participant list
TestingLibraryElementError: Unable to find an element by: [data-testid="run-title"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mRun Detail[0m
        [36m</h1>[39m
        [36m<p[39m
          [33mdata-testid[39m=[32m"run-detail-error"[39m
          [33mrole[39m=[32m"alert"[39m
        [36m>[39m
          [0mTitle is required[0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:76:38
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:52:17
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:95:19
 ❯ src/__tests__/runs.test.jsx:138:19
    136| 
    137|     await screen.findByTestId('run-detail-view')
    138|     expect(screen.getByTestId('run-title')).toHaveTextContent('Morning…
       |                   ^
    139|     expect(screen.getByTestId('run-datetime')).toHaveTextContent('2025…
    140|     expect(screen.getByTestId('run-location')).toHaveTextContent('Rive…

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[5/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > join form submits, triggers a refresh, and shows the new participant
TestingLibraryElementError: Unable to find an element by: [data-testid="participant-name"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m/>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m/>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m/>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m0[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<p>[39m
            [0mNo participants yet.[0m
          [36m</p>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:76:38
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:109:15
 ❯ src/__tests__/runs.test.jsx:179:19
    177|     await screen.findByTestId('run-detail-view')
    178| 
    179|     expect(screen.getAllByTestId('participant-name')).toHaveLength(1)
       |                   ^
    180| 
    181|     fireEvent.change(screen.getByTestId('join-name-input'), { target: …

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[6/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > displays the duplicate-name error when join is rejected
TestingLibraryElementError: Unable to find an element by: [data-testid="run-detail-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m/>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m/>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m/>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m0[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<p>[39m
            [0mNo participants yet.[0m
          [36m</p>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m/>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m/>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m/>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m0[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<p>[39m
            [0mNo participants yet.[0m
          [36m</p>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:86:33
 ❯ src/__tests__/runs.test.jsx:208:34
    206|     fireEvent.click(screen.getByTestId('join-submit'))
    207| 
    208|     const errorEl = await screen.findByTestId('run-detail-error')
       |                                  ^
    209|     expect(errorEl).toHaveTextContent('A participant with that name al…
    210|   })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[7/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > leave form removes a participant and refreshes the view
AssertionError: expected [ <li …(1)></li>, <li …(1)></li> ] to have a length of 1 but got 2

- Expected
+ Received

- 1
+ 2

 ❯ src/__tests__/runs.test.jsx:238:19
    236| 
    237|     const names = await screen.findAllByTestId('participant-name')
    238|     expect(names).toHaveLength(1)
       |                   ^
    239|     expect(names[0]).toHaveTextContent('Alice')
    240|   })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[8/9]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > shows a not-found error for an unknown run id
TestingLibraryElementError: Unable to find an element by: [data-testid="run-detail-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m>[39m
          [0mMorning 5K[0m
        [36m</h1>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m>[39m
            [0m2025-06-15T07:00:00[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m>[39m
            [0mRiverside Park[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mDistance[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-distance"[39m
          [36m>[39m
            [0m5K[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mPace Target[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-pace-target"[39m
          [36m>[39m
            [0m9:30/mi[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mRoute Notes[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-route-notes"[39m
          [36m>[39m
            [0mLoop around the lake[0m
          [36m</dd>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m1[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<ul[39m
            [33mdata-testid[39m=[32m"participant-list"[39m
          [36m>[39m
            [36m<li[39m
              [33mdata-testid[39m=[32m"participant-name"[39m
            [36m>[39m
              [0mAlice[0m
            [36m</li>[39m
          [36m</ul>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mclass[39m=[32m"app"[39m
    [36m>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"run-detail-view"[39m
      [36m>[39m
        [36m<h1[39m
          [33mdata-testid[39m=[32m"run-title"[39m
        [36m>[39m
          [0mMorning 5K[0m
        [36m</h1>[39m
        [36m<dl>[39m
          [36m<dt>[39m
            [0mDate / Time[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-datetime"[39m
          [36m>[39m
            [0m2025-06-15T07:00:00[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mMeeting Location[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-location"[39m
          [36m>[39m
            [0mRiverside Park[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mDistance[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-distance"[39m
          [36m>[39m
            [0m5K[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mPace Target[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-pace-target"[39m
          [36m>[39m
            [0m9:30/mi[0m
          [36m</dd>[39m
          [36m<dt>[39m
            [0mRoute Notes[0m
          [36m</dt>[39m
          [36m<dd[39m
            [33mdata-testid[39m=[32m"run-route-notes"[39m
          [36m>[39m
            [0mLoop around the lake[0m
          [36m</dd>[39m
        [36m</dl>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mParticipants ([0m
            [0m1[0m
            [0m)[0m
          [36m</h2>[39m
          [36m<ul[39m
            [33mdata-testid[39m=[32m"participant-list"[39m
          [36m>[39m
            [36m<li[39m
              [33mdata-testid[39m=[32m"participant-name"[39m
            [36m>[39m
              [0mAlice[0m
            [36m</li>[39m
          [36m</ul>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mJoin this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"join-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"join-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"join-name-input"[39m
                [33mid[39m=[32m"join-name-input"[39m
                [33mname[39m=[32m"join_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"join-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mJoin[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
        [36m<section>[39m
          [36m<h2>[39m
            [0mLeave this Run[0m
          [36m</h2>[39m
          [36m<form[39m
            [33mdata-testid[39m=[32m"leave-form"[39m
          [36m>[39m
            [36m<p>[39m
              [36m<label[39m
                [33mfor[39m=[32m"leave-name-input"[39m
              [36m>[39m
                [0mName[0m
              [36m</label>[39m
              [36m<input[39m
                [33mdata-testid[39m=[32m"leave-name-input"[39m
                [33mid[39m=[32m"leave-name-input"[39m
                [33mname[39m=[32m"leave_name"[39m
                [33mtype[39m=[32m"text"[39m
              [36m/>[39m
            [36m</p>[39m
            [36m<button[39m
              [33mdata-testid[39m=[32m"leave-submit"[39m
              [33mtype[39m=[32m"submit"[39m
            [36m>[39m
              [0mLeave[0m
            [36m</button>[39m
          [36m</form>[39m
        [36m</section>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:86:33
 ❯ src/__tests__/runs.test.jsx:250:34
    248| 
    249|     await screen.findByTestId('run-detail-view')
    250|     const errorEl = await screen.findByTestId('run-detail-error')
       |                                  ^
    251|     expect(errorEl).toHaveTextContent('does not exist')
    252|   })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[9/9]⎯


⎯⎯⎯⎯ Unhandled Rejection ⎯⎯⎯⎯⎯
TypeError: Cannot read properties of undefined (reading 'value')
 ❯ handleSubmit src/views/CreateRunView.jsx:26:35
     24|     const values = {
     25|       title: e.target.title.value,
     26|       datetime: e.target.datetime.value,
       |                                   ^
     27|       meeting_location: e.target.meeting_location.value,
     28|       distance: e.target.distance.value,
 ❯ HTMLUnknownElement.callCallback node_modules/react-dom/cjs/react-dom.development.js:4164:14
 ❯ HTMLUnknownElement.callTheUserObjectsOperation node_modules/jsdom/lib/jsdom/living/generated/EventListener.js:26:30
 ❯ innerInvokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:350:25
 ❯ invokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:286:3
 ❯ HTMLUnknownElementImpl._dispatch node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:233:9
 ❯ HTMLUnknownElementImpl.dispatchEvent node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:104:17
 ❯ HTMLUnknownElement.dispatchEvent node_modules/jsdom/lib/jsdom/living/generated/EventTarget.js:241:34
 ❯ Object.invokeGuardedCallbackDev node_modules/react-dom/cjs/react-dom.development.js:4213:16
 ❯ invokeGuardedCallback node_modules/react-dom/cjs/react-dom.development.js:4277:31

This error originated in "src/__tests__/runs.test.jsx" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
The latest test that might've caused the error is "navigates to the runs list after a successful create". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.

⎯⎯⎯⎯ Unhandled Rejection ⎯⎯⎯⎯⎯
TypeError: Cannot read properties of undefined (reading 'value')
 ❯ handleSubmit src/views/CreateRunView.jsx:26:35
     24|     const values = {
     25|       title: e.target.title.value,
     26|       datetime: e.target.datetime.value,
       |                                   ^
     27|       meeting_location: e.target.meeting_location.value,
     28|       distance: e.target.distance.value,
 ❯ HTMLUnknownElement.callCallback node_modules/react-dom/cjs/react-dom.development.js:4164:14
 ❯ HTMLUnknownElement.callTheUserObjectsOperation node_modules/jsdom/lib/jsdom/living/generated/EventListener.js:26:30
 ❯ innerInvokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:350:25
 ❯ invokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:286:3
 ❯ HTMLUnknownElementImpl._dispatch node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:233:9
 ❯ HTMLUnknownElementImpl.dispatchEvent node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:104:17
 ❯ HTMLUnknownElement.dispatchEvent node_modules/jsdom/lib/jsdom/living/generated/EventTarget.js:241:34
 ❯ Object.invokeGuardedCallbackDev node_modules/react-dom/cjs/react-dom.development.js:4213:16
 ❯ invokeGuardedCallback node_modules/react-dom/cjs/react-dom.development.js:4277:31

This error originated in "src/__tests__/runs.test.jsx" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
The latest test that might've caused the error is "navigates to the runs list after a successful create". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.

⎯⎯⎯⎯ Unhandled Rejection ⎯⎯⎯⎯⎯
TypeError: Cannot read properties of undefined (reading 'value')
 ❯ handleSubmit src/views/CreateRunView.jsx:26:35
     24|     const values = {
     25|       title: e.target.title.value,
     26|       datetime: e.target.datetime.value,
       |                                   ^
     27|       meeting_location: e.target.meeting_location.value,
     28|       distance: e.target.distance.value,
 ❯ HTMLUnknownElement.callCallback node_modules/react-dom/cjs/react-dom.development.js:4164:14
 ❯ HTMLUnknownElement.callTheUserObjectsOperation node_modules/jsdom/lib/jsdom/living/generated/EventListener.js:26:30
 ❯ innerInvokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:350:25
 ❯ invokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:286:3
 ❯ HTMLUnknownElementImpl._dispatch node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:233:9
 ❯ HTMLUnknownElementImpl.dispatchEvent node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:104:17
 ❯ HTMLUnknownElement.dispatchEvent node_modules/jsdom/lib/jsdom/living/generated/EventTarget.js:241:34
 ❯ Object.invokeGuardedCallbackDev node_modules/react-dom/cjs/react-dom.development.js:4213:16
 ❯ invokeGuardedCallback node_modules/react-dom/cjs/react-dom.development.js:4277:31

This error originated in "src/__tests__/runs.test.jsx" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
The latest test that might've caused the error is "displays a server error when the API rejects the create request". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.

⎯⎯⎯⎯ Unhandled Rejection ⎯⎯⎯⎯⎯
TypeError: Cannot read properties of undefined (reading 'value')
 ❯ handleJoin src/views/RunDetailView.jsx:41:37
     39|     e.preventDefault();
     40|     setJoinError('');
     41|     const name = e.target.join_name.value.trim();
       |                                     ^
     42|     if (!name) {
     43|       setJoinError('Name is required.');
 ❯ HTMLUnknownElement.callCallback node_modules/react-dom/cjs/react-dom.development.js:4164:14
 ❯ HTMLUnknownElement.callTheUserObjectsOperation node_modules/jsdom/lib/jsdom/living/generated/EventListener.js:26:30
 ❯ innerInvokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:350:25
 ❯ invokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:286:3
 ❯ HTMLUnknownElementImpl._dispatch node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:233:9
 ❯ HTMLUnknownElementImpl.dispatchEvent node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:104:17
 ❯ HTMLUnknownElement.dispatchEvent node_modules/jsdom/lib/jsdom/living/generated/EventTarget.js:241:34
 ❯ Object.invokeGuardedCallbackDev node_modules/react-dom/cjs/react-dom.development.js:4213:16
 ❯ invokeGuardedCallback node_modules/react-dom/cjs/react-dom.development.js:4277:31

This error originated in "src/__tests__/runs.test.jsx" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
The latest test that might've caused the error is "displays the duplicate-name error when join is rejected". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.

⎯⎯⎯⎯ Unhandled Rejection ⎯⎯⎯⎯⎯
TypeError: Cannot read properties of undefined (reading 'value')
 ❯ handleLeave src/views/RunDetailView.jsx:69:38
     67|     e.preventDefault();
     68|     setLeaveError('');
     69|     const name = e.target.leave_name.value.trim();
       |                                      ^
     70|     if (!name) {
     71|       setLeaveError('Name is required.');
 ❯ HTMLUnknownElement.callCallback node_modules/react-dom/cjs/react-dom.development.js:4164:14
 ❯ HTMLUnknownElement.callTheUserObjectsOperation node_modules/jsdom/lib/jsdom/living/generated/EventListener.js:26:30
 ❯ innerInvokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:350:25
 ❯ invokeEventListeners node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:286:3
 ❯ HTMLUnknownElementImpl._dispatch node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:233:9
 ❯ HTMLUnknownElementImpl.dispatchEvent node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:104:17
 ❯ HTMLUnknownElement.dispatchEvent node_modules/jsdom/lib/jsdom/living/generated/EventTarget.js:241:34
 ❯ Object.invokeGuardedCallbackDev node_modules/react-dom/cjs/react-dom.development.js:4213:16
 ❯ invokeGuardedCallback node_modules/react-dom/cjs/react-dom.development.js:4277:31

This error originated in "src/__tests__/runs.test.jsx" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
The latest test that might've caused the error is "leave form removes a participant and refreshes the view". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.


```


## Error

backend: no test files provided
