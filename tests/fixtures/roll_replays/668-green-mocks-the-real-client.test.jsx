import { vi, describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api.js', () => {
  class ApiError extends Error {
    constructor(code, message, status) {
      super(message)
      this.code = code
      this.status = status
    }
  }
  return {
    apiFetch: vi.fn(),
    ApiError,
  }
})

import { apiFetch, ApiError } from '../api.js'
import App from '../App.jsx'

const mockApiFetch = vi.mocked(apiFetch)

function renderApp(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('CreateRunView', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  it('submits required and optional fields to create a run', async () => {
    const createdRun = {
      id: 'run-001',
      title: 'Sunday Long Run',
      datetime: '2026-03-15 07:00',
      meeting_location: 'Central Park, South Gate',
      distance: '10K',
      pace_target: '9:00-10:00/mi',
      route_notes: 'Loop the park twice',
      participants: [],
      participant_count: 0,
      created_at: '2026-01-01T00:00:00Z',
    }
    // Use mockResolvedValue (not Once) so the navigation-into-detail-view
    // fetch also resolves cleanly without breaking the assertion.
    mockApiFetch.mockResolvedValue(createdRun)

    renderApp('/new')

    fireEvent.change(screen.getByTestId('create-run-title'), { target: { value: 'Sunday Long Run' } })
    fireEvent.change(screen.getByTestId('create-run-datetime'), { target: { value: '2026-03-15 07:00' } })
    fireEvent.change(screen.getByTestId('create-run-location'), { target: { value: 'Central Park, South Gate' } })
    fireEvent.change(screen.getByTestId('create-run-distance'), { target: { value: '10K' } })
    fireEvent.change(screen.getByTestId('create-run-pace'), { target: { value: '9:00-10:00/mi' } })
    fireEvent.change(screen.getByTestId('create-run-notes'), { target: { value: 'Loop the park twice' } })

    fireEvent.click(screen.getByTestId('create-run-submit'))

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/runs',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            title: 'Sunday Long Run',
            datetime: '2026-03-15 07:00',
            meeting_location: 'Central Park, South Gate',
            distance: '10K',
            pace_target: '9:00-10:00/mi',
            route_notes: 'Loop the park twice',
          }),
        }),
      )
    })
  })

  it('shows a validation error and does not call apiFetch when required fields are empty', () => {
    renderApp('/new')

    fireEvent.click(screen.getByTestId('create-run-submit'))

    expect(screen.getByTestId('create-run-error')).toBeInTheDocument()
    expect(mockApiFetch).not.toHaveBeenCalled()
  })
})

describe('RunDetailView – join flow', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  // Previous-attempt failure: "adds a participant to the list after a successful
  // join" expected 3 <li> but got 2.  Root cause: the mock's join response must
  // carry the FULL updated participant array (original + new).  This test asserts
  // that explicitly.
  it('adds a participant to the list after a successful join', async () => {
    const initialRun = {
      id: 'run-abc',
      title: 'Friday Easy Pace',
      datetime: '2026-02-20 18:00',
      meeting_location: 'Riverside Trailhead',
      distance: '5K',
      pace_target: '10:00-11:00/mi',
      route_notes: null,
      participants: ['Alice', 'Bob'],
      participant_count: 2,
      created_at: '2026-01-10T12:00:00Z',
    }

    // The join response MUST include all 3 participants (the original 2 + Carol).
    const updatedRun = {
      ...initialRun,
      participants: ['Alice', 'Bob', 'Carol'],
      participant_count: 3,
    }

    mockApiFetch.mockResolvedValueOnce(initialRun)
    mockApiFetch.mockResolvedValueOnce(updatedRun)

    renderApp('/runs/run-abc')

    await waitFor(() => {
      expect(screen.getByTestId('run-title')).toBeInTheDocument()
    })

    expect(screen.getAllByTestId('participant-name')).toHaveLength(2)

    fireEvent.change(screen.getByTestId('join-name'), { target: { value: 'Carol' } })
    fireEvent.click(screen.getByTestId('join-submit'))

    await waitFor(() => {
      expect(screen.getAllByTestId('participant-name')).toHaveLength(3)
    })
  })

  it('displays a duplicate-name error and leaves the participant list unchanged', async () => {
    const initialRun = {
      id: 'run-abc',
      title: 'Friday Easy Pace',
      datetime: '2026-02-20 18:00',
      meeting_location: 'Riverside Trailhead',
      distance: '5K',
      pace_target: null,
      route_notes: null,
      participants: ['Alice'],
      participant_count: 1,
      created_at: '2026-01-10T12:00:00Z',
    }

    mockApiFetch.mockResolvedValueOnce(initialRun)
    mockApiFetch.mockRejectedValueOnce(
      new ApiError('duplicate_name', 'Alice is already joined to this run.', 409),
    )

    renderApp('/runs/run-abc')

    await waitFor(() => {
      expect(screen.getByTestId('run-title')).toBeInTheDocument()
    })

    expect(screen.getAllByTestId('participant-name')).toHaveLength(1)

    fireEvent.change(screen.getByTestId('join-name'), { target: { value: 'Alice' } })
    fireEvent.click(screen.getByTestId('join-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('join-error')).toBeInTheDocument()
    })

    // List must remain at 1 participant
    expect(screen.getAllByTestId('participant-name')).toHaveLength(1)
  })

  it('shows the run-not-found state when the API returns 404', async () => {
    mockApiFetch.mockRejectedValueOnce(
      new ApiError('run_not_found', 'Run not found.', 404),
    )

    renderApp('/runs/nonexistent')

    await waitFor(() => {
      expect(screen.getByTestId('run-not-found')).toBeInTheDocument()
    })
  })
})