import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import RunListView from '../views/RunListView.jsx'
import RunCreateView from '../views/RunCreateView.jsx'
import RunDetailView from '../views/RunDetailView.jsx'

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

// ─── helpers ───────────────────────────────────────────────────────────────────

const mockRun = {
  id: 'run-001',
  title: 'Morning 5K',
  datetime: '2024-12-01T07:00',
  meeting_location: 'Central Park North Gate',
  distance: '5K',
  pace_target: '9:00-10:00/mi',
  route_notes: 'Loop around the reservoir',
  participants: ['Alice', 'Bob'],
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-probe">{location.pathname}</div>
}

function renderWithRouter(element, { initialEntries = ['/'] } = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {element}
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── RunListView ───────────────────────────────────────────────────────────────

describe('RunListView', () => {
  it('shows empty state with create link when no runs exist', async () => {
    apiFetch.mockResolvedValue([])

    renderWithRouter(
      <Routes>
        <Route path="/" element={<RunListView />} />
      </Routes>,
      { initialEntries: ['/'] },
    )

    await waitFor(() => {
      expect(screen.getByTestId('runs-view')).toBeInTheDocument()
    })

    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    expect(screen.getByTestId('create-run-link')).toBeInTheDocument()
  })

  it('renders a run list with rows when runs exist', async () => {
    apiFetch.mockResolvedValue([mockRun])

    renderWithRouter(
      <Routes>
        <Route path="/" element={<RunListView />} />
      </Routes>,
      { initialEntries: ['/'] },
    )

    await waitFor(() => {
      expect(screen.getByTestId('runs-view')).toBeInTheDocument()
    })

    expect(screen.getByTestId('run-list')).toBeInTheDocument()
    const row = screen.getByTestId('run-row')
    expect(row).toBeInTheDocument()
    expect(row).toHaveTextContent('Morning 5K')
    expect(screen.getByTestId('create-run-link')).toBeInTheDocument()
  })
})

// ─── RunCreateView ─────────────────────────────────────────────────────────────

describe('RunCreateView', () => {
  it('renders all required and optional form fields', () => {
    renderWithRouter(
      <Routes>
        <Route path="/runs/new" element={<RunCreateView />} />
      </Routes>,
      { initialEntries: ['/runs/new'] },
    )

    expect(screen.getByTestId('create-view')).toBeInTheDocument()
    expect(screen.getByTestId('create-form')).toBeInTheDocument()
    expect(screen.getByTestId('create-title-input')).toBeInTheDocument()
    expect(screen.getByTestId('create-datetime-input')).toBeInTheDocument()
    expect(screen.getByTestId('create-location-input')).toBeInTheDocument()
    expect(screen.getByTestId('create-submit')).toBeInTheDocument()
  })

  it('shows a validation error when required fields are empty', async () => {
    renderWithRouter(
      <Routes>
        <Route path="/runs/new" element={<RunCreateView />} />
      </Routes>,
      { initialEntries: ['/runs/new'] },
    )

    fireEvent.click(screen.getByTestId('create-submit'))

    const errorEl = await screen.findByTestId('create-error')
    expect(errorEl).toBeInTheDocument()
    expect(errorEl).toHaveTextContent('Title is required.')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('submits the form, calls apiFetch with the payload, and navigates to list', async () => {
    const createdRun = { ...mockRun, id: 'run-new' }
    apiFetch.mockResolvedValue(createdRun)

    renderWithRouter(
      <Routes>
        <Route path="/" element={<LocationProbe />} />
        <Route path="/runs/new" element={<RunCreateView />} />
      </Routes>,
      { initialEntries: ['/runs/new'] },
    )

    fireEvent.change(screen.getByTestId('create-title-input'), { target: { value: 'Morning 5K' } })
    fireEvent.change(screen.getByTestId('create-datetime-input'), { target: { value: '2024-12-01T07:00' } })
    fireEvent.change(screen.getByTestId('create-location-input'), { target: { value: 'Central Park North Gate' } })
    fireEvent.click(screen.getByTestId('create-submit'))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/runs',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Morning 5K'),
        }),
      )
    })

    // After navigation the location probe should show the list route
    await waitFor(() => {
      expect(screen.getByTestId('location-probe')).toHaveTextContent('/')
    })
  })

  it('surfaces API error on create rejection', async () => {
    apiFetch.mockRejectedValue(new ApiError('validation_error', 'Missing required field', 422))

    renderWithRouter(
      <Routes>
        <Route path="/runs/new" element={<RunCreateView />} />
      </Routes>,
      { initialEntries: ['/runs/new'] },
    )

    fireEvent.change(screen.getByTestId('create-title-input'), { target: { value: 'Test' } })
    fireEvent.change(screen.getByTestId('create-datetime-input'), { target: { value: '2024-01-01T00:00' } })
    fireEvent.change(screen.getByTestId('create-location-input'), { target: { value: 'Place' } })
    fireEvent.click(screen.getByTestId('create-submit'))

    const errorEl = await screen.findByTestId('create-error')
    expect(errorEl).toHaveTextContent('Missing required field')
  })
})

// ─── RunDetailView ─────────────────────────────────────────────────────────────

describe('RunDetailView', () => {
  it('renders run details and participant list', async () => {
    apiFetch.mockResolvedValue(mockRun)

    renderWithRouter(
      <Routes>
        <Route path="/runs/:run_id" element={<RunDetailView />} />
      </Routes>,
      { initialEntries: ['/runs/run-001'] },
    )

    await waitFor(() => {
      expect(screen.getByTestId('detail-view')).toBeInTheDocument()
    })

    expect(screen.getByTestId('run-title')).toHaveTextContent('Morning 5K')
    expect(screen.getByTestId('run-datetime')).toHaveTextContent('2024-12-01T07:00')
    expect(screen.getByTestId('run-location')).toHaveTextContent('Central Park North Gate')

    const list = screen.getByTestId('participant-list')
    expect(list).toBeInTheDocument()

    const names = screen.getAllByTestId('participant-name')
    expect(names).toHaveLength(2)
    expect(names[0]).toHaveTextContent('Alice')
    expect(names[1]).toHaveTextContent('Bob')

    // Join form
    expect(screen.getByTestId('join-form')).toBeInTheDocument()
    expect(screen.getByTestId('join-name-input')).toBeInTheDocument()
    expect(screen.getByTestId('join-submit')).toBeInTheDocument()

    // Leave form
    expect(screen.getByTestId('leave-form')).toBeInTheDocument()
    expect(screen.getByTestId('leave-name-input')).toBeInTheDocument()
    expect(screen.getByTestId('leave-submit')).toBeInTheDocument()
  })

  it('shows detail-error for a run that is not found', async () => {
    apiFetch.mockRejectedValue(new ApiError('run_not_found', 'Run not found', 404))

    renderWithRouter(
      <Routes>
        <Route path="/runs/:run_id" element={<RunDetailView />} />
      </Routes>,
      { initialEntries: ['/runs/nonexistent'] },
    )

    const errorEl = await screen.findByTestId('detail-error')
    expect(errorEl).toHaveTextContent('Run not found')
  })

  it('submits join form and calls apiFetch with the correct join path', async () => {
    // Initial fetch succeeds
    apiFetch.mockResolvedValueOnce(mockRun)

    // Join call succeeds
    const updatedRun = { ...mockRun, participants: ['Alice', 'Bob', 'Charlie'] }
    apiFetch.mockResolvedValueOnce(updatedRun)

    renderWithRouter(
      <Routes>
        <Route path="/runs/:run_id" element={<RunDetailView />} />
      </Routes>,
      { initialEntries: ['/runs/run-001'] },
    )

    await waitFor(() => {
      expect(screen.getByTestId('detail-view')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('join-name-input'), { target: { value: 'Charlie' } })
    fireEvent.click(screen.getByTestId('join-submit'))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/runs/run-001/join',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Charlie' }),
        }),
      )
    })
  })

  it('surfaces duplicate-participant rejection on join', async () => {
    apiFetch.mockResolvedValueOnce(mockRun)
    apiFetch.mockRejectedValueOnce(
      new ApiError('duplicate_participant', 'A participant with this name already exists', 409),
    )

    renderWithRouter(
      <Routes>
        <Route path="/runs/:run_id" element={<RunDetailView />} />
      </Routes>,
      { initialEntries: ['/runs/run-001'] },
    )

    await waitFor(() => {
      expect(screen.getByTestId('detail-view')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('join-name-input'), { target: { value: 'Alice' } })
    fireEvent.click(screen.getByTestId('join-submit'))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('A participant with this name already exists')
  })

  // Previously failing case: leave form must call apiFetch with the correct run_id path
  it('submits leave form and calls apiFetch leave endpoint', async () => {
    apiFetch.mockResolvedValueOnce(mockRun)
    const updatedRun = { ...mockRun, participants: ['Bob'] }
    apiFetch.mockResolvedValueOnce(updatedRun)

    renderWithRouter(
      <Routes>
        <Route path="/runs/:run_id" element={<RunDetailView />} />
      </Routes>,
      { initialEntries: ['/runs/run-001'] },
    )

    await waitFor(() => {
      expect(screen.getByTestId('detail-view')).toBeInTheDocument()
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