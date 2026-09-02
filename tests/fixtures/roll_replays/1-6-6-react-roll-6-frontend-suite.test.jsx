import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RunListView from '../views/RunListView.jsx'
import RunDetailView from '../views/RunDetailView.jsx'

vi.mock('../api.js', () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(code, message, status) {
      super(message)
      this.code = code
      this.status = status
    }
  },
}))

import { apiFetch } from '../api.js'

describe('RunListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders run titles, locations, and participant counts', async () => {
    const sampleRuns = [
      {
        id: 'run-1',
        title: 'Morning Tempo',
        datetime: '2026-09-01T07:30',
        location: 'Riverside Park',
        distance: '5K',
        pace_target: '9:00-10:00/mi',
        route_notes: null,
        participants: ['Alice', 'Bob'],
        participant_count: 2,
      },
      {
        id: 'run-2',
        title: 'Weekend Long Run',
        datetime: '2026-09-06T08:00',
        location: 'Lakefront Trail',
        distance: '10K',
        pace_target: null,
        route_notes: null,
        participants: ['Carol'],
        participant_count: 1,
      },
    ]

    apiFetch.mockResolvedValue(sampleRuns)

    render(
      <MemoryRouter initialEntries={['/']}>
        <RunListView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('run-list')).toBeInTheDocument()
    })

    const titles = screen.getAllByTestId('run-card-title')
    expect(titles[0]).toHaveTextContent('Morning Tempo')
    expect(titles[1]).toHaveTextContent('Weekend Long Run')

    const locations = screen.getAllByTestId('run-card-location')
    expect(locations[0]).toHaveTextContent('Riverside Park')
    expect(locations[1]).toHaveTextContent('Lakefront Trail')

    const counts = screen.getAllByTestId('run-card-participant-count')
    expect(counts[0]).toHaveTextContent('2 participants')
    expect(counts[1]).toHaveTextContent('1 participant')
  })

  it('shows empty state when no runs exist', async () => {
    apiFetch.mockResolvedValue([])

    render(
      <MemoryRouter initialEntries={['/']}>
        <RunListView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    })
  })
})

describe('RunDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders participant names and submits join with expected payload', async () => {
    const sampleRun = {
      id: 'run-123',
      title: 'Sunday Group Run',
      datetime: '2026-09-07T08:00',
      location: 'Central Park',
      distance: '6 mi',
      pace_target: '8:30-9:30/mi',
      route_notes: 'Loop around the lake',
      participants: ['Alice', 'Bob'],
      participant_count: 2,
    }

    const joinedRun = {
      ...sampleRun,
      participants: ['Alice', 'Bob', 'Charlie'],
      participant_count: 3,
    }

    apiFetch
      .mockResolvedValueOnce(sampleRun)
      .mockResolvedValueOnce(joinedRun)

    render(
      <MemoryRouter initialEntries={['/runs/run-123']}>
        <RunDetailView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('run-detail-title')).toBeInTheDocument()
    })

    const participants = screen.getAllByTestId('participant-name')
    expect(participants[0]).toHaveTextContent('Alice')
    expect(participants[1]).toHaveTextContent('Bob')

    const joinInput = screen.getByTestId('join-name-input')
    fireEvent.change(joinInput, { target: { value: 'Charlie' } })
    fireEvent.click(screen.getByTestId('join-submit'))

    await waitFor(() => {
      const updated = screen.getAllByTestId('participant-name')
      expect(updated).toHaveLength(3)
    })

    const joinCall = apiFetch.mock.calls.find(
      (call) => call[0] === '/runs/run-123/join' && call[1] && call[1].method === 'POST',
    )
    expect(joinCall).toBeDefined()
    const parsedBody = JSON.parse(joinCall[1].body)
    expect(parsedBody).toEqual({ name: 'Charlie' })
  })

  it('shows not-found state when the run does not exist', async () => {
    apiFetch.mockRejectedValue(
      Object.assign(new Error('Not found'), { code: 'run_not_found', status: 404 }),
    )

    render(
      <MemoryRouter initialEntries={['/runs/nonexistent']}>
        <RunDetailView />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('not-found-state')).toBeInTheDocument()
    })
  })
})