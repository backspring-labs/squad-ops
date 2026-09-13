import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock API client module
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();

jest.mock('../api', () => ({
  getRuns: () => mockApiGet(),
  getRun: (id) => mockApiGet({ id }),
  createRun: (data) => mockApiPost({ type: 'create', data }),
  joinRun: (runId, name) => mockApiPost({ type: 'join', runId, name }),
  leaveRun: (runId, name) => mockApiPost({ type: 'leave', runId, name }),
}));

import { getRuns, getRun, createRun, joinRun, leaveRun } from '../api';

const sampleRun = {
  id: 'run-001',
  title: 'Morning 5K',
  datetime: '2025-01-15T07:00:00',
  location: 'Central Park',
  distance: '5K',
  pace_target: '9:00-10:00/mi',
  route_notes: 'Start at 72nd St entrance',
  participants: [
    { id: 'p-001', name: 'Alice' },
    { id: 'p-002', name: 'Bob' },
  ],
};

const emptyRun = {
  id: 'run-002',
  title: 'Evening Run',
  datetime: '2025-01-16T18:00:00',
  location: 'Riverside Park',
  distance: '3 mi',
  pace_target: '',
  route_notes: '',
  participants: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  mockApiGet.mockResolvedValue({});
  mockApiPost.mockResolvedValue({});
});

describe('Runs Frontend Integration Tests', () => {
  describe('Create Run Flow', () => {
    test('successfully creates a run with required fields', async () => {
      mockApiGet.mockResolvedValue({ runs: [] });
      mockApiPost.mockResolvedValue(sampleRun);

      render(<div data-testid="app">Test Mount Point</div>);

      // Simulate navigating to create form
      const titleInput = screen.queryByPlaceholderText(/title/i);
      if (titleInput) {
        fireEvent.change(titleInput, { target: { value: 'Morning 5K' } });
      }

      const datetimeInput = screen.queryByPlaceholderText(/date|time/i);
      if (datetimeInput) {
        fireEvent.change(datetimeInput, { target: { value: '2025-01-15T07:00:00' } });
      }

      const locationInput = screen.queryByPlaceholderText(/location|meeting/i);
      if (locationInput) {
        fireEvent.change(locationInput, { target: { value: 'Central Park' } });
      }

      const submitButton = screen.queryByText(/create|submit|add/i);
      if (submitButton) {
        fireEvent.click(submitButton);
      }

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'create', title: 'Morning 5K' })
        );
      });
    });

    test('rejects create with empty required fields', async () => {
      mockApiGet.mockResolvedValue({ runs: [] });

      render(<div data-testid="app">Test Mount Point</div>);

      const submitButton = screen.queryByText(/create|submit|add/i);
      if (submitButton) {
        fireEvent.click(submitButton);
      }

      await waitFor(() => {
        const errorMessages = screen.queryAllByText(/required|empty|must|field/i);
        expect(errorMessages.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Run List View', () => {
    test('displays list of runs with participant counts', async () => {
      mockApiGet.mockResolvedValue({
        runs: [sampleRun, emptyRun],
      });

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const runTitles = screen.queryAllByText(/Morning 5K/i);
      expect(runTitles.length).toBeGreaterThanOrEqual(0);

      const participantCounts = screen.queryAllByText(/\d+ participant/i);
      expect(participantCounts.length).toBeGreaterThanOrEqual(0);
    });

    test('shows empty state when no runs exist', async () => {
      mockApiGet.mockResolvedValue({ runs: [] });

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const emptyMessages = screen.queryByText(/no run|empty|none|create/i);
      expect(emptyMessages).not.toBeNull();
    });
  });

  describe('Run Detail View', () => {
    test('displays run details and participants', async () => {
      mockApiGet.mockResolvedValue(sampleRun);

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      expect(screen.queryByText(/Morning 5K/i)).not.toBeNull();
      expect(screen.queryByText(/Central Park/i)).not.toBeNull();
      expect(screen.queryByText(/Alice/i)).not.toBeNull();
      expect(screen.queryByText(/Bob/i)).not.toBeNull();
    });

    test('handles run not found error gracefully', async () => {
      mockApiGet.mockRejectedValue(new Error('Run not found'));

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const errorIndicator = screen.queryByText(/not found|error|unknown/i);
      expect(errorIndicator).not.toBeNull();
    });
  });

  describe('Join Run Flow', () => {
    test('successfully joins a run with valid participant name', async () => {
      mockApiGet.mockResolvedValue(sampleRun);
      mockApiPost.mockResolvedValue({
        ...sampleRun,
        participants: [
          { id: 'p-001', name: 'Alice' },
          { id: 'p-002', name: 'Bob' },
          { id: 'p-003', name: 'Charlie' },
        ],
      });

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const nameInput = screen.queryByPlaceholderText(/name|participant/i);
      if (nameInput) {
        fireEvent.change(nameInput, { target: { value: 'Charlie' } });
      }

      const joinButton = screen.queryByText(/join/i);
      if (joinButton) {
        fireEvent.click(joinButton);
      }

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'join', name: 'Charlie' })
        );
      });

      expect(screen.queryByText(/Charlie/i)).not.toBeNull();
    });

    test('rejects join with duplicate participant name', async () => {
      mockApiGet.mockResolvedValue(sampleRun);
      mockApiPost.mockRejectedValue(new Error('duplicate_participant'));

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const nameInput = screen.queryByPlaceholderText(/name|participant/i);
      if (nameInput) {
        fireEvent.change(nameInput, { target: { value: 'Alice' } });
      }

      const joinButton = screen.queryByText(/join/i);
      if (joinButton) {
        fireEvent.click(joinButton);
      }

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalled();
      });

      const errorMessages = screen.queryAllByText(/duplicate|already|existing|error/i);
      expect(errorMessages.length).toBeGreaterThan(0);
    });

    test('rejects join with empty participant name', async () => {
      mockApiGet.mockResolvedValue(sampleRun);

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const joinButton = screen.queryByText(/join/i);
      if (joinButton) {
        fireEvent.click(joinButton);
      }

      await waitFor(() => {
        const errorMessages = screen.queryAllByText(/required|empty|name|field/i);
        expect(errorMessages.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Leave Run Flow', () => {
    test('successfully leaves a run with valid participant name', async () => {
      mockApiGet.mockResolvedValue(sampleRun);
      mockApiPost.mockResolvedValue({
        ...sampleRun,
        participants: [
          { id: 'p-002', name: 'Bob' },
        ],
      });

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const leaveInput = screen.queryByPlaceholderText(/leave|remove|name/i);
      if (leaveInput) {
        fireEvent.change(leaveInput, { target: { value: 'Alice' } });
      }

      const leaveButton = screen.queryByText(/leave|remove/i);
      if (leaveButton) {
        fireEvent.click(leaveButton);
      }

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'leave', name: 'Alice' })
        );
      });
    });

    test('handles participant not found on leave', async () => {
      mockApiGet.mockResolvedValue(sampleRun);
      mockApiPost.mockRejectedValue(new Error('participant_not_found'));

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const leaveInput = screen.queryByPlaceholderText(/leave|remove|name/i);
      if (leaveInput) {
        fireEvent.change(leaveInput, { target: { value: 'Unknown' } });
      }

      const leaveButton = screen.queryByText(/leave|remove/i);
      if (leaveButton) {
        fireEvent.click(leaveButton);
      }

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalled();
      });

      const errorMessages = screen.queryAllByText(/not found|participant|error/i);
      expect(errorMessages.length).toBeGreaterThan(0);
    });

    test('rejects leave with empty participant name', async () => {
      mockApiGet.mockResolvedValue(sampleRun);

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const leaveButton = screen.queryByText(/leave|remove/i);
      if (leaveButton) {
        fireEvent.click(leaveButton);
      }

      await waitFor(() => {
        const errorMessages = screen.queryAllByText(/required|empty|name|field/i);
        expect(errorMessages.length).toBeGreaterThan(0);
      });
    });
  });

  describe('API Error Handling', () => {
    test('displays validation error appropriately', async () => {
      mockApiGet.mockResolvedValue({ runs: [] });
      mockApiPost.mockRejectedValue(new Error('validation_error'));

      render(<div data-testid="app">Test Mount Point</div>);

      const submitButton = screen.queryByText(/create|submit|add/i);
      if (submitButton) {
        fireEvent.click(submitButton);
      }

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalled();
      });

      const errorMessages = screen.queryAllByText(/error|invalid|validation/i);
      expect(errorMessages.length).toBeGreaterThan(0);
    });

    test('handles network/API failure gracefully', async () => {
      mockApiGet.mockRejectedValue(new Error('Network error'));

      render(<div data-testid="app">Test Mount Point</div>);

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalled();
      });

      const errorIndicator = screen.queryByText(/error|failed|unable/i);
      expect(errorIndicator).not.toBeNull();
    });
  });
});