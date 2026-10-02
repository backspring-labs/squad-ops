import { describe, expect, it, vi, beforeEach } from 'vitest'
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
  const apiFetch = vi.fn()
  return { ApiError, apiFetch }
})

import { apiFetch, ApiError } from '../api.js'
import RunCreateView from '../views/RunCreateView.jsx'
import RunDetailView from '../views/RunDetailView.jsx'
import RunListView from '../views/RunListView.jsx'

const mockRun = {
  id: 'run-001',
  title: 'Saturday Morning 5K',
  datetime: '2025-03-15T08:00',
  meeting_location: 'Central Park East Entrance',
  distance: '5K',
  pace_target: '9:00-10:00/mi',
  route_notes: 'Loop around the reservoir, then two miles out and back.',
  participants: ['Alice', 'Bob'],
}

describe('RunCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fills required fields, submits, and calls apiFetch with POST /runs', async () => {
    apiFetch.mockResolvedValueOnce({ ...mockRun, participants: [] })

    render(
      <MemoryRouter initialEntries={['/runs/new']}>
        <RunCreateView />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByTestId('create-title-input'), { target: { value: 'Saturday Morning 5K' } })
    fireEvent.change(screen.getByTestId('create-datetime-input'), { target: { value: '2025-03-15T08:00' } })
    fireEvent.change(screen.getByTestId('create-location-input'), { target: { value: 'Central Park East Entrance' } })
    fireEvent.click(screen.getByTestId('create-submit'))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/runs',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('shows create-error anchor when required fields are empty', async () => {
    render(
      <MemoryRouter initialEntries={['/runs/new']}>
        <RunCreateView />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByTestId('create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('create-error')).toBeInTheDocument()
    })
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows create-error anchor when backend rejects with ApiError', async () => {
    apiFetch.mockRejectedValueOnce(new ApiError('validation_error', 'Title is required.', 422))

    render(
      <MemoryRouter initialEntries={['/runs/new']}>
        <RunCreateView />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByTestId('create-title-input'), { target: { value: 'Test Run' } })
    fireEvent.change(screen.getByTestId('create-datetime-input'), { target: { value: '2025-03-15T08:00' } })
    fireEvent.change(screen.getByTestId('create-location-input'), { target: { value: 'Riverside Park' } })
    fireEvent.click(screen.getByTestId('create-submit'))

    await waitFor(() => {
      expect(screen.getByTestId('create-error')).toBeInTheDocument()
    })
  })
})

describe('RunDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders run-title, run-datetime, run-location, and participant-list with participant-name entries', async () => {
    apiFetch.mockResolvedValueOnce(mockRun)

    render(
      <MemoryRouter initialEntries={['/runs/run-001']}>
        <RunDetailView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('run-title')).toBeInTheDocument()
    })
    expect(screen.getByTestId('run-datetime')).toBeInTheDocument()
    expect(screen.getByTestId('run-location')).toBeInTheDocument()
    expect(screen.getByTestId('participant-list')).toBeInTheDocument()
    expect(screen.getAllByTestId('participant-name')).toHaveLength(2)
  })

  it('shows detail-error anchor when run is not found', async () => {
    apiFetch.mockRejectedValueOnce(new ApiError('run_not_found', 'Run not found', 404))

    render(
      <MemoryRouter initialEntries={['/runs/unknown-id']}>
        <RunDetailView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('detail-error')).toBeInTheDocument()
    })
  })

  it('submits join form and surfaces duplicate-participant rejection via apiFetch call', async () => {
    apiFetch
      .mockResolvedValueOnce(mockRun)
      .mockRejectedValueOnce(new ApiError('duplicate_participant', 'Alice is already a participant.', 409))

    render(
      <MemoryRouter initialEntries={['/runs/run-001']}>
        <RunDetailView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('run-title')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('join-name-input'), { target: { value: 'Alice' } })
    fireEvent.click(screen.getByTestId('join-submit'))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/runs/run-001/join',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Alice' }),
        }),
      )
    })
  })

  it('submits leave form and calls apiFetch leave endpoint', async () => {
    apiFetch
      .mockResolvedValueOnce(mockRun)
      .mockResolvedValueOnce({ ...mockRun, participants: ['Bob'] })

    render(
      <MemoryRouter initialEntries={['/runs/run-001']}>
        <RunDetailView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('run-title')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('leave-name-input'), { target: { value: 'Alice' } })
    fireEvent.click(screen.getByTestId('leave-submit'))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/runs/run-001/leave',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Alice' }),
        }),
      )
    })
  })
})

describe('RunListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty-state and create-run-link when no runs exist', async () => {
    apiFetch.mockResolvedValueOnce([])

    render(
      <MemoryRouter initialEntries={['/']}>
        <RunListView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    })
    expect(screen.getByTestId('create-run-link')).toBeInTheDocument()
  })

  it('renders run-list containing run-row entries when runs exist', async () => {
    const runs = [
      mockRun,
      { ...mockRun, id: 'run-002', title: 'Sunday Long Run', participants: ['Charlie'] },
    ]
    apiFetch.mockResolvedValueOnce(runs)

    render(
      <MemoryRouter initialEntries={['/']}>
        <RunListView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('run-list')).toBeInTheDocument()
    })
    expect(screen.getAllByTestId('run-row')).toHaveLength(2)
    expect(screen.getByTestId('create-run-link')).toBeInTheDocument()
  })
})