# Test Execution Report

**Result:** tests failed (exit code 1, 4 test file(s), 17 source file(s))

**Exit code:** 1

**Test files:** 4

**Source files:** 17


## stdout

```
=== Frontend (vitest) ===

 RUN  v2.1.9 /tmp/qa_node_6ne9fnza/frontend

 ✓ src/__tests__/runs.test.jsx > RunsListView > renders run cards with title, datetime, location, and count after loading
 × src/__tests__/runs.test.jsx > RunsListView > shows the empty state when no runs exist 1005ms
   → Found multiple elements by: [data-testid="runs-view"]

Here are the matching elements:

Ignored nodes: comments, script, style
[36m<div[39m
  [33mdata-testid[39m=[32m"runs-view"[39m
[36m>[39m
  [36m<a[39m
    [33mdata-testid[39m=[32m"create-run-link"[39m
    [33mhref[39m=[32m"/create"[39m
  [36m>[39m
    [0mCreate a Run[0m
  [36m</a>[39m
  [36m<ul[39m
    [33mdata-testid[39m=[32m"runs-list"[39m
  [36m>[39m
    [36m<li[39m
      [33mdata-testid[39m=[32m"run-card"[39m
    [36m>[39m
      [36m<a[39m
        [33mhref[39m=[32m"/runs/run-1"[39m
      [36m>[39m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-title"[39m
        [36m>[39m
          [0mMorning 5K[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-datetime"[39m
        [36m>[39m
          [0m2025-01-15T07:00:00[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-location"[39m
        [36m>[39m
          [0mCentral Park[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-count"[39m
        [36m>[39m
          [0m3[0m
        [36m</span>[39m
      [36m</a>[39m
    [36m</li>[39m
    [36m<li[39m
      [33mdata-testid[39m=[32m"run-card"[39m
    [36m>[39m
      [36m<a[39m
        [33mhref[39m=[32m"/runs/run-2"[39m
      [36m>[39m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-title"[39m
        [36m>[39m
          [0mEvening Loop[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-datetime"[39m
        [36m>[39m
          [0m2025-01-16T18:00:00[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-location"[39m
        [36m>[39m
          [0mRiverside Trail[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-count"[39m
        [36m>[39m
          [0m1[0m
        [36m</span>[39m
      [36m</a>[39m
    [36m</li>[39m
  [36m</ul>[39m
[36m</div>[39m

Ignored nodes: comments, script, style
[36m<div[39m
  [33mdata-testid[39m=[32m"runs-view"[39m
[36m>[39m
  [36m<a[39m
    [33mdata-testid[39m=[32m"create-run-link"[39m
    [33mhref[39m=[32m"/create"[39m
  [36m>[39m
    [0mCreate a Run[0m
  [36m</a>[39m
  [36m<div[39m
    [33mdata-testid[39m=[32m"runs-empty-state"[39m
  [36m>[39m
    [36m<p>[39m
      [0mNo runs yet. Create one to get started![0m
    [36m</p>[39m
  [36m</div>[39m
[36m</div>[39m

(If this is intentional, then use the `*AllBy*` variant of the query (like `queryAllByText`, `getAllByText`, or `findAllByText`)).

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<html>[39m
  [36m<head />[39m
  [36m<body>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<ul[39m
          [33mdata-testid[39m=[32m"runs-list"[39m
        [36m>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-1"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mMorning 5K[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-15T07:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mCentral Park[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m3[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-2"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mEvening Loop[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-16T18:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mRiverside Trail[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m1[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
        [36m</ul>[39m
      [36m</div>[39m
    [36m</div>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<div[39m
          [33mdata-testid[39m=[32m"runs-empty-state"[39m
        [36m>[39m
          [36m<p>[39m
            [0mNo runs yet. Create one to get started![0m
          [36m</p>[39m
        [36m</div>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</body>[39m
[36m</html>[39m
 × src/__tests__/runs.test.jsx > RunCreateView > displays a validation error when required fields are empty 1010ms
   → Unable to find an element by: [data-testid="create-run-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<html>[39m
  [36m<head />[39m
  [36m<body>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<ul[39m
          [33mdata-testid[39m=[32m"runs-list"[39m
        [36m>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-1"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mMorning 5K[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-15T07:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mCentral Park[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m3[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-2"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mEvening Loop[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-16T18:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mRiverside Trail[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m1[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
        [36m</ul>[39m
      [36m</div>[39m
    [36m</div>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<div[39m
          [33mdata-testid[39m=[32m"runs-empty-state"[39m
        [36m>[39m
          [36m<p>[39m
            [0mNo runs yet. Create one to get started![0m
          [36m</p>[39m
        [36m</div>[39m
      [36m</div>[39m
    [36m</div>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
        [36m>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"title"[39m
            [36m>[39m
              [0mTitle[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-title"[39m
              [33mid[39m=[32m"title"[39m
              [33mrequired[39m=[32m""[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"datetime"[39m
            [36m>[39m
              [0mDate & Time[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-datetime"[39m
              [33mid[39m=[32m"datetime"[39m
              [33mrequired[39m=[32m""[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"location"[39m
            [36m>[39m
              [0mMeeting Location[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-location"[39m
              [33mid[39m=[32m"location"[39m
              [33mrequired[39m=[32m""[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"distance"[39m
            [36m>[39m
              [0mDistance[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-distance"[39m
              [33mid[39m=[32m"distance"[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"pace"[39m
            [36m>[39m
              [0mPace Target[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-pace"[39m
              [33mid[39m=[32m"pace"[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"notes"[39m
            [36m>[39m
              [0mRoute Notes[0m
            [36m</label>[39m
            [36m<textarea[39m
              [33mdata-testid[39m=[32m"create-run-notes"[39m
              [33mid[39m=[32m"notes"[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</body>[39m
[36m</html>[39m
 × src/__tests__/runs.test.jsx > RunCreateView > submits the form and calls apiFetch with the trimmed payload
   → Found multiple elements by: [data-testid="create-run-title"]

Here are the matching elements:

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"create-run-title"[39m
  [33mid[39m=[32m"title"[39m
  [33mrequired[39m=[32m""[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"create-run-title"[39m
  [33mid[39m=[32m"title"[39m
  [33mrequired[39m=[32m""[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

(If this is intentional, then use the `*AllBy*` variant of the query (like `queryAllByText`, `getAllByText`, or `findAllByText`)).

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ✓ src/__tests__/runs.test.jsx > RunDetailView > renders run details, participant list, and join/leave forms
 × src/__tests__/runs.test.jsx > RunDetailView > shows an error banner when a duplicate join is rejected
   → Found multiple elements by: [data-testid="join-name-input"]

Here are the matching elements:

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"join-name-input"[39m
  [33mplaceholder[39m=[32m"Your name"[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"join-name-input"[39m
  [33mplaceholder[39m=[32m"Your name"[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

(If this is intentional, then use the `*AllBy*` variant of the query (like `queryAllByText`, `getAllByText`, or `findAllByText`)).

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"run-detail-view"[39m
    [36m>[39m
      [36m<h1[39m
        [33mdata-testid[39m=[32m"run-detail-title"[39m
      [36m>[39m
        [0mWeekend Trail Run[0m
      [36m</h1>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-datetime"[39m
      [36m>[39m
        [0m2025-03-01T08:00:00[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-location"[39m
      [36m>[39m
        [0mHillcrest Park[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-distance"[39m
      [36m>[39m
        [0m10K[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-pace"[39m
      [36m>[39m
        [0m9:00/mi[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-notes"[39m
      [36m>[39m
        [0mStart at main gate[0m
      [36m</p>[39m
      [36m<h2>[39m
        [0mParticipants ([0m
        [0m2[0m
        [0m)[0m
      [36m</h2>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"participants-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"participant-item"[39m
        [36m>[39m
          [0mAlice[0m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"participant-item"[39m
        [36m>[39m
          [0mBob[0m
        [36m</li>[39m
      [36m</ul>[39m
      [36m<h3>[39m
        [0mJoin[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"join-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"join-name-input"[39m
          [33mplaceholder[39m=[32m"Your name"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"join-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mJoin[0m
        [36m</button>[39m
      [36m</form>[39m
      [36m<h3>[39m
        [0mLeave[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"leave-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"leave-name-input"[39m
          [33mplaceholder[39m=[32m"Name to remove"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"leave-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mLeave[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"run-detail-view"[39m
    [36m>[39m
      [36m<h1[39m
        [33mdata-testid[39m=[32m"run-detail-title"[39m
      [36m>[39m
        [0mWeekend Trail Run[0m
      [36m</h1>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-datetime"[39m
      [36m>[39m
        [0m2025-03-01T08:00:00[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-location"[39m
      [36m>[39m
        [0mHillcrest Park[0m
      [36m</p>[39m
      [36m<h2>[39m
        [0mParticipants ([0m
        [0m1[0m
        [0m)[0m
      [36m</h2>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"participants-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"participant-item"[39m
        [36m>[39m
          [0mAlice[0m
        [36m</li>[39m
      [36m</ul>[39m
      [36m<h3>[39m
        [0mJoin[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"join-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"join-name-input"[39m
          [33mplaceholder[39m=[32m"Your name"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"join-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mJoin[0m
        [36m</button>[39m
      [36m</form>[39m
      [36m<h3>[39m
        [0mLeave[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"leave-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"leave-name-input"[39m
          [33mplaceholder[39m=[32m"Name to remove"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"leave-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mLeave[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

 Test Files  1 failed (1)
      Tests  4 failed | 2 passed (6)
   Start at  17:45:09
   Duration  2.64s (transform 101ms, setup 32ms, collect 155ms, tests 2.05s, environment 198ms, prepare 37ms)

JSON report written to /tmp/qa_node_6ne9fnza/frontend/.vitest_report.json

```


## stderr

```
=== Frontend (vitest) ===
stderr | src/__tests__/runs.test.jsx > RunsListView > renders run cards with title, datetime, location, and count after loading
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 4 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/runs.test.jsx > RunsListView > shows the empty state when no runs exist
TestingLibraryElementError: Found multiple elements by: [data-testid="runs-view"]

Here are the matching elements:

Ignored nodes: comments, script, style
[36m<div[39m
  [33mdata-testid[39m=[32m"runs-view"[39m
[36m>[39m
  [36m<a[39m
    [33mdata-testid[39m=[32m"create-run-link"[39m
    [33mhref[39m=[32m"/create"[39m
  [36m>[39m
    [0mCreate a Run[0m
  [36m</a>[39m
  [36m<ul[39m
    [33mdata-testid[39m=[32m"runs-list"[39m
  [36m>[39m
    [36m<li[39m
      [33mdata-testid[39m=[32m"run-card"[39m
    [36m>[39m
      [36m<a[39m
        [33mhref[39m=[32m"/runs/run-1"[39m
      [36m>[39m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-title"[39m
        [36m>[39m
          [0mMorning 5K[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-datetime"[39m
        [36m>[39m
          [0m2025-01-15T07:00:00[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-location"[39m
        [36m>[39m
          [0mCentral Park[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-count"[39m
        [36m>[39m
          [0m3[0m
        [36m</span>[39m
      [36m</a>[39m
    [36m</li>[39m
    [36m<li[39m
      [33mdata-testid[39m=[32m"run-card"[39m
    [36m>[39m
      [36m<a[39m
        [33mhref[39m=[32m"/runs/run-2"[39m
      [36m>[39m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-title"[39m
        [36m>[39m
          [0mEvening Loop[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-datetime"[39m
        [36m>[39m
          [0m2025-01-16T18:00:00[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-location"[39m
        [36m>[39m
          [0mRiverside Trail[0m
        [36m</span>[39m
        [0m [0m
        [36m<span[39m
          [33mdata-testid[39m=[32m"run-card-count"[39m
        [36m>[39m
          [0m1[0m
        [36m</span>[39m
      [36m</a>[39m
    [36m</li>[39m
  [36m</ul>[39m
[36m</div>[39m

Ignored nodes: comments, script, style
[36m<div[39m
  [33mdata-testid[39m=[32m"runs-view"[39m
[36m>[39m
  [36m<a[39m
    [33mdata-testid[39m=[32m"create-run-link"[39m
    [33mhref[39m=[32m"/create"[39m
  [36m>[39m
    [0mCreate a Run[0m
  [36m</a>[39m
  [36m<div[39m
    [33mdata-testid[39m=[32m"runs-empty-state"[39m
  [36m>[39m
    [36m<p>[39m
      [0mNo runs yet. Create one to get started![0m
    [36m</p>[39m
  [36m</div>[39m
[36m</div>[39m

(If this is intentional, then use the `*AllBy*` variant of the query (like `queryAllByText`, `getAllByText`, or `findAllByText`)).

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<html>[39m
  [36m<head />[39m
  [36m<body>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<ul[39m
          [33mdata-testid[39m=[32m"runs-list"[39m
        [36m>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-1"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mMorning 5K[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-15T07:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mCentral Park[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m3[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-2"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mEvening Loop[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-16T18:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mRiverside Trail[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m1[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
        [36m</ul>[39m
      [36m</div>[39m
    [36m</div>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<div[39m
          [33mdata-testid[39m=[32m"runs-empty-state"[39m
        [36m>[39m
          [36m<p>[39m
            [0mNo runs yet. Create one to get started![0m
          [36m</p>[39m
        [36m</div>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</body>[39m
[36m</html>[39m
 ❯ Proxy.waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
 ❯ src/__tests__/runs.test.jsx:77:11
     75|     )
     76| 
     77|     await waitFor(() => {
       |           ^
     78|       expect(screen.getByTestId('runs-view')).toBeInTheDocument()
     79|     })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/4]⎯

 FAIL  src/__tests__/runs.test.jsx > RunCreateView > displays a validation error when required fields are empty
TestingLibraryElementError: Unable to find an element by: [data-testid="create-run-error"]

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m

Ignored nodes: comments, script, style
[36m<html>[39m
  [36m<head />[39m
  [36m<body>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<ul[39m
          [33mdata-testid[39m=[32m"runs-list"[39m
        [36m>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-1"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mMorning 5K[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-15T07:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mCentral Park[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m3[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
          [36m<li[39m
            [33mdata-testid[39m=[32m"run-card"[39m
          [36m>[39m
            [36m<a[39m
              [33mhref[39m=[32m"/runs/run-2"[39m
            [36m>[39m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-title"[39m
              [36m>[39m
                [0mEvening Loop[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-datetime"[39m
              [36m>[39m
                [0m2025-01-16T18:00:00[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-location"[39m
              [36m>[39m
                [0mRiverside Trail[0m
              [36m</span>[39m
              [0m [0m
              [36m<span[39m
                [33mdata-testid[39m=[32m"run-card-count"[39m
              [36m>[39m
                [0m1[0m
              [36m</span>[39m
            [36m</a>[39m
          [36m</li>[39m
        [36m</ul>[39m
      [36m</div>[39m
    [36m</div>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-view"[39m
      [36m>[39m
        [36m<a[39m
          [33mdata-testid[39m=[32m"create-run-link"[39m
          [33mhref[39m=[32m"/create"[39m
        [36m>[39m
          [0mCreate a Run[0m
        [36m</a>[39m
        [36m<div[39m
          [33mdata-testid[39m=[32m"runs-empty-state"[39m
        [36m>[39m
          [36m<p>[39m
            [0mNo runs yet. Create one to get started![0m
          [36m</p>[39m
        [36m</div>[39m
      [36m</div>[39m
    [36m</div>[39m
    [36m<div>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"create-run-view"[39m
      [36m>[39m
        [36m<h1>[39m
          [0mCreate a Run[0m
        [36m</h1>[39m
        [36m<form[39m
          [33mdata-testid[39m=[32m"create-run-form"[39m
        [36m>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"title"[39m
            [36m>[39m
              [0mTitle[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-title"[39m
              [33mid[39m=[32m"title"[39m
              [33mrequired[39m=[32m""[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"datetime"[39m
            [36m>[39m
              [0mDate & Time[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-datetime"[39m
              [33mid[39m=[32m"datetime"[39m
              [33mrequired[39m=[32m""[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"location"[39m
            [36m>[39m
              [0mMeeting Location[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-location"[39m
              [33mid[39m=[32m"location"[39m
              [33mrequired[39m=[32m""[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"distance"[39m
            [36m>[39m
              [0mDistance[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-distance"[39m
              [33mid[39m=[32m"distance"[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"pace"[39m
            [36m>[39m
              [0mPace Target[0m
            [36m</label>[39m
            [36m<input[39m
              [33mdata-testid[39m=[32m"create-run-pace"[39m
              [33mid[39m=[32m"pace"[39m
              [33mtype[39m=[32m"text"[39m
              [33mvalue[39m=[32m""[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<div>[39m
            [36m<label[39m
              [33mfor[39m=[32m"notes"[39m
            [36m>[39m
              [0mRoute Notes[0m
            [36m</label>[39m
            [36m<textarea[39m
              [33mdata-testid[39m=[32m"create-run-notes"[39m
              [33mid[39m=[32m"notes"[39m
            [36m/>[39m
          [36m</div>[39m
          [36m<button[39m
            [33mdata-testid[39m=[32m"create-run-submit"[39m
            [33mtype[39m=[32m"submit"[39m
          [36m>[39m
            [0mCreate Run[0m
          [36m</button>[39m
        [36m</form>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</body>[39m
[36m</html>[39m
 ❯ Proxy.waitForWrapper node_modules/@testing-library/dom/dist/wait-for.js:163:27
 ❯ src/__tests__/runs.test.jsx:99:11
     97|     fireEvent.click(screen.getByTestId('create-run-submit'))
     98| 
     99|     await waitFor(() => {
       |           ^
    100|       expect(screen.getByTestId('create-run-error')).toBeInTheDocument…
    101|     })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/4]⎯

 FAIL  src/__tests__/runs.test.jsx > RunCreateView > submits the form and calls apiFetch with the trimmed payload
TestingLibraryElementError: Found multiple elements by: [data-testid="create-run-title"]

Here are the matching elements:

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"create-run-title"[39m
  [33mid[39m=[32m"title"[39m
  [33mrequired[39m=[32m""[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"create-run-title"[39m
  [33mid[39m=[32m"title"[39m
  [33mrequired[39m=[32m""[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

(If this is intentional, then use the `*AllBy*` variant of the query (like `queryAllByText`, `getAllByText`, or `findAllByText`)).

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ getElementError node_modules/@testing-library/dom/dist/query-helpers.js:20:35
 ❯ getMultipleElementsFoundError node_modules/@testing-library/dom/dist/query-helpers.js:23:10
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:55:13
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:95:19
 ❯ src/__tests__/runs.test.jsx:115:29
    113|     )
    114| 
    115|     fireEvent.change(screen.getByTestId('create-run-title'), { target:…
       |                             ^
    116|     fireEvent.change(screen.getByTestId('create-run-datetime'), { targ…
    117|     fireEvent.change(screen.getByTestId('create-run-location'), { targ…

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[3/4]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > shows an error banner when a duplicate join is rejected
TestingLibraryElementError: Found multiple elements by: [data-testid="join-name-input"]

Here are the matching elements:

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"join-name-input"[39m
  [33mplaceholder[39m=[32m"Your name"[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

Ignored nodes: comments, script, style
[36m<input[39m
  [33mdata-testid[39m=[32m"join-name-input"[39m
  [33mplaceholder[39m=[32m"Your name"[39m
  [33mtype[39m=[32m"text"[39m
  [33mvalue[39m=[32m""[39m
[36m/>[39m

(If this is intentional, then use the `*AllBy*` variant of the query (like `queryAllByText`, `getAllByText`, or `findAllByText`)).

Ignored nodes: comments, script, style
[36m<body>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"runs-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-1"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mMorning 5K[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-15T07:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mCentral Park[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m3[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"run-card"[39m
        [36m>[39m
          [36m<a[39m
            [33mhref[39m=[32m"/runs/run-2"[39m
          [36m>[39m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-title"[39m
            [36m>[39m
              [0mEvening Loop[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-datetime"[39m
            [36m>[39m
              [0m2025-01-16T18:00:00[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-location"[39m
            [36m>[39m
              [0mRiverside Trail[0m
            [36m</span>[39m
            [0m [0m
            [36m<span[39m
              [33mdata-testid[39m=[32m"run-card-count"[39m
            [36m>[39m
              [0m1[0m
            [36m</span>[39m
          [36m</a>[39m
        [36m</li>[39m
      [36m</ul>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"runs-view"[39m
    [36m>[39m
      [36m<a[39m
        [33mdata-testid[39m=[32m"create-run-link"[39m
        [33mhref[39m=[32m"/create"[39m
      [36m>[39m
        [0mCreate a Run[0m
      [36m</a>[39m
      [36m<div[39m
        [33mdata-testid[39m=[32m"runs-empty-state"[39m
      [36m>[39m
        [36m<p>[39m
          [0mNo runs yet. Create one to get started![0m
        [36m</p>[39m
      [36m</div>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"create-run-view"[39m
    [36m>[39m
      [36m<h1>[39m
        [0mCreate a Run[0m
      [36m</h1>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"create-run-form"[39m
      [36m>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"title"[39m
          [36m>[39m
            [0mTitle[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-title"[39m
            [33mid[39m=[32m"title"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"datetime"[39m
          [36m>[39m
            [0mDate & Time[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-datetime"[39m
            [33mid[39m=[32m"datetime"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"location"[39m
          [36m>[39m
            [0mMeeting Location[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-location"[39m
            [33mid[39m=[32m"location"[39m
            [33mrequired[39m=[32m""[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"distance"[39m
          [36m>[39m
            [0mDistance[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-distance"[39m
            [33mid[39m=[32m"distance"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"pace"[39m
          [36m>[39m
            [0mPace Target[0m
          [36m</label>[39m
          [36m<input[39m
            [33mdata-testid[39m=[32m"create-run-pace"[39m
            [33mid[39m=[32m"pace"[39m
            [33mtype[39m=[32m"text"[39m
            [33mvalue[39m=[32m""[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<div>[39m
          [36m<label[39m
            [33mfor[39m=[32m"notes"[39m
          [36m>[39m
            [0mRoute Notes[0m
          [36m</label>[39m
          [36m<textarea[39m
            [33mdata-testid[39m=[32m"create-run-notes"[39m
            [33mid[39m=[32m"notes"[39m
          [36m/>[39m
        [36m</div>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"create-run-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mCreate Run[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"run-detail-view"[39m
    [36m>[39m
      [36m<h1[39m
        [33mdata-testid[39m=[32m"run-detail-title"[39m
      [36m>[39m
        [0mWeekend Trail Run[0m
      [36m</h1>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-datetime"[39m
      [36m>[39m
        [0m2025-03-01T08:00:00[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-location"[39m
      [36m>[39m
        [0mHillcrest Park[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-distance"[39m
      [36m>[39m
        [0m10K[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-pace"[39m
      [36m>[39m
        [0m9:00/mi[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-notes"[39m
      [36m>[39m
        [0mStart at main gate[0m
      [36m</p>[39m
      [36m<h2>[39m
        [0mParticipants ([0m
        [0m2[0m
        [0m)[0m
      [36m</h2>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"participants-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"participant-item"[39m
        [36m>[39m
          [0mAlice[0m
        [36m</li>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"participant-item"[39m
        [36m>[39m
          [0mBob[0m
        [36m</li>[39m
      [36m</ul>[39m
      [36m<h3>[39m
        [0mJoin[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"join-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"join-name-input"[39m
          [33mplaceholder[39m=[32m"Your name"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"join-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mJoin[0m
        [36m</button>[39m
      [36m</form>[39m
      [36m<h3>[39m
        [0mLeave[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"leave-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"leave-name-input"[39m
          [33mplaceholder[39m=[32m"Name to remove"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"leave-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mLeave[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
  [36m<div>[39m
    [36m<div[39m
      [33mdata-testid[39m=[32m"run-detail-view"[39m
    [36m>[39m
      [36m<h1[39m
        [33mdata-testid[39m=[32m"run-detail-title"[39m
      [36m>[39m
        [0mWeekend Trail Run[0m
      [36m</h1>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-datetime"[39m
      [36m>[39m
        [0m2025-03-01T08:00:00[0m
      [36m</p>[39m
      [36m<p[39m
        [33mdata-testid[39m=[32m"run-detail-location"[39m
      [36m>[39m
        [0mHillcrest Park[0m
      [36m</p>[39m
      [36m<h2>[39m
        [0mParticipants ([0m
        [0m1[0m
        [0m)[0m
      [36m</h2>[39m
      [36m<ul[39m
        [33mdata-testid[39m=[32m"participants-list"[39m
      [36m>[39m
        [36m<li[39m
          [33mdata-testid[39m=[32m"participant-item"[39m
        [36m>[39m
          [0mAlice[0m
        [36m</li>[39m
      [36m</ul>[39m
      [36m<h3>[39m
        [0mJoin[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"join-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"join-name-input"[39m
          [33mplaceholder[39m=[32m"Your name"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"join-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mJoin[0m
        [36m</button>[39m
      [36m</form>[39m
      [36m<h3>[39m
        [0mLeave[0m
      [36m</h3>[39m
      [36m<form[39m
        [33mdata-testid[39m=[32m"leave-form"[39m
      [36m>[39m
        [36m<input[39m
          [33mdata-testid[39m=[32m"leave-name-input"[39m
          [33mplaceholder[39m=[32m"Name to remove"[39m
          [33mtype[39m=[32m"text"[39m
          [33mvalue[39m=[32m""[39m
        [36m/>[39m
        [36m<button[39m
          [33mdata-testid[39m=[32m"leave-submit"[39m
          [33mtype[39m=[32m"submit"[39m
        [36m>[39m
          [0mLeave[0m
        [36m</button>[39m
      [36m</form>[39m
    [36m</div>[39m
  [36m</div>[39m
[36m</body>[39m
 ❯ Object.getElementError node_modules/@testing-library/dom/dist/config.js:37:19
 ❯ getElementError node_modules/@testing-library/dom/dist/query-helpers.js:20:35
 ❯ getMultipleElementsFoundError node_modules/@testing-library/dom/dist/query-helpers.js:23:10
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:55:13
 ❯ node_modules/@testing-library/dom/dist/query-helpers.js:95:19
 ❯ src/__tests__/runs.test.jsx:220:29
    218| 
    219|     // Attempt to join with a duplicate name
    220|     fireEvent.change(screen.getByTestId('join-name-input'), { target: …
       |                             ^
    221|     fireEvent.click(screen.getByTestId('join-submit'))
    222| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[4/4]⎯


```


## Error

backend: no test files provided
