import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RunDetailView from '../views/RunDetailView';
import '@testing-library/jest-dom';

const mockRunData = {
  id: 'run-1',
  title: 'Morning Run',
  datetime: '2024-01-15T08:00',
  location: 'Central Park',
  distance: '5K',
  pace_target: '9:00/mi',
  route_notes: 'Loop route',
  participants: [
    { id: 'p1', name: 'Alice' },
    { id: 'p2', name: 'Bob' }
  ]
};

describe('RunDetailView', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('renders run details and participant list', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockRunData)
    });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Morning Run')).toBeInTheDocument();
      expect(screen.getByText('Central Park')).toBeInTheDocument();
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  test('shows error when run is not found (404)', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({
        error_code: 'run_not_found',
        message: 'Run not found'
      })
    });

    render(<RunDetailView runId="invalid-id" />);
    
    await waitFor(() => {
      expect(screen.getByText(/run not found/i)).toBeInTheDocument();
    });
  });

  test('prevents join with empty participant name', () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockRunData)
    });

    render(<RunDetailView runId="run-1" />);
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: '' } });
    fireEvent.click(joinButton);
    
    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/join'),
      expect.anything()
    );
  });

  test('prevents join with whitespace-only participant name', () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockRunData)
    });

    render(<RunDetailView runId="run-1" />);
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: '   ' } });
    fireEvent.click(joinButton);
    
    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/join'),
      expect.anything()
    );
  });

  test('trims whitespace from participant name before join submission', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockRunData,
          participants: [
            ...mockRunData.participants,
            { id: 'p3', name: 'Charlie' }
          ]
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: '  Charlie  ' } });
    fireEvent.click(joinButton);
    
    await waitFor(() => {
      const joinCall = global.fetch.mock.calls.find(
        call => call[0].includes('/join')
      );
      expect(joinCall).toBeDefined();
      const body = JSON.parse(joinCall[1].body);
      expect(body.name).toBe('Charlie');
    });
  });

  test('trims whitespace from participant name before leave submission', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockRunData,
          participants: [{ id: 'p2', name: 'Bob' }]
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const leaveInput = screen.getByLabelText(/leave name/i);
    const leaveButton = screen.getByRole('button', { name: /leave/i });
    
    fireEvent.change(leaveInput, { target: { value: '  Alice  ' } });
    fireEvent.click(leaveButton);
    
    await waitFor(() => {
      const leaveCall = global.fetch.mock.calls.find(
        call => call[0].includes('/leave')
      );
      expect(leaveCall).toBeDefined();
      const body = JSON.parse(leaveCall[1].body);
      expect(body.name).toBe('Alice');
    });
  });

  test('prevents leave with empty participant name', () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockRunData)
    });

    render(<RunDetailView runId="run-1" />);
    
    const leaveInput = screen.getByLabelText(/leave name/i);
    const leaveButton = screen.getByRole('button', { name: /leave/i });
    
    fireEvent.change(leaveInput, { target: { value: '' } });
    fireEvent.click(leaveButton);
    
    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/leave'),
      expect.anything()
    );
  });

  test('shows duplicate participant error on 409 response', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: () => Promise.resolve({
          error_code: 'duplicate_participant',
          message: 'Participant already in this run'
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: 'Alice' } });
    fireEvent.click(joinButton);
    
    await waitFor(() => {
      expect(screen.getByText(/already/i)).toBeInTheDocument();
    });
  });

  test('shows validation error on 422 response for join', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({
          error_code: 'validation_error',
          message: 'Invalid participant name'
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: 'Charlie' } });
    fireEvent.click(joinButton);
    
    await waitFor(() => {
      expect(screen.getByText(/invalid participant name/i)).toBeInTheDocument();
    });
  });

  test('shows participant not found error on leave (404)', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({
          error_code: 'participant_not_found',
          message: 'Participant not found on this run'
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const leaveInput = screen.getByLabelText(/leave name/i);
    const leaveButton = screen.getByRole('button', { name: /leave/i });
    
    fireEvent.change(leaveInput, { target: { value: 'Unknown' } });
    fireEvent.click(leaveButton);
    
    await waitFor(() => {
      expect(screen.getByText(/participant not found/i)).toBeInTheDocument();
    });
  });

  test('updates participant list after successful join', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockRunData,
          participants: [
            ...mockRunData.participants,
            { id: 'p3', name: 'Charlie' }
          ]
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: 'Charlie' } });
    fireEvent.click(joinButton);
    
    await waitFor(() => {
      expect(screen.getByText('Charlie')).toBeInTheDocument();
    });
  });

  test('updates participant list after successful leave', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockRunData,
          participants: [{ id: 'p2', name: 'Bob' }]
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const leaveInput = screen.getByLabelText(/leave name/i);
    const leaveButton = screen.getByRole('button', { name: /leave/i });
    
    fireEvent.change(leaveInput, { target: { value: 'Alice' } });
    fireEvent.click(leaveButton);
    
    await waitFor(() => {
      expect(screen.queryByText('Alice')).not.toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  test('clears join form after successful join', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockRunData,
          participants: [
            ...mockRunData.participants,
            { id: 'p3', name: 'Charlie' }
          ]
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: 'Charlie' } });
    fireEvent.click(joinButton);
    
    await waitFor(() => {
      expect(joinInput.value).toBe('');
    });
  });

  test('clears leave form after successful leave', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          ...mockRunData,
          participants: [{ id: 'p2', name: 'Bob' }]
        })
      });

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const leaveInput = screen.getByLabelText(/leave name/i);
    const leaveButton = screen.getByRole('button', { name: /leave/i });
    
    fireEvent.change(leaveInput, { target: { value: 'Alice' } });
    fireEvent.click(leaveButton);
    
    await waitFor(() => {
      expect(leaveInput.value).toBe('');
    });
  });

  test('handles network error on join gracefully', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockRejectedValueOnce(new Error('Network failure'));

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const joinInput = screen.getByLabelText(/your name/i);
    const joinButton = screen.getByRole('button', { name: /join/i });
    
    fireEvent.change(joinInput, { target: { value: 'Charlie' } });
    fireEvent.click(joinButton);
    
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  test('handles network error on leave gracefully', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRunData)
      })
      .mockRejectedValueOnce(new Error('Network failure'));

    render(<RunDetailView runId="run-1" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
    });
    
    const leaveInput = screen.getByLabelText(/leave name/i);
    const leaveButton = screen.getByRole('button', { name: /leave/i });
    
    fireEvent.change(leaveInput, { target: { value: 'Alice' } });
    fireEvent.click(leaveButton);
    
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});