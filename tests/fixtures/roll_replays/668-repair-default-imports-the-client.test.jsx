import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import RunsListView from '../views/RunsListView';
import RunDetailView from '../views/RunDetailView';
import CreateRunView from '../views/CreateRunView';
import apiFetch from '../api';

jest.mock('../api', () => ({
  __esModule: true,
  default: jest.fn(),
}));

describe('Runs core flow', () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  test('create run then navigate to detail view shows the run title', async () => {
    const mockRun = {
      id: 'run-123',
      title: 'Lake Loop',
      datetime: '2025-01-01T09:00:00',
      location: 'Lake Park',
      distance: '5K',
      pace_target: '10:00/mi',
      route_notes: 'Easy loop around the lake',
      participants: [],
    };

    apiFetch
      .mockResolvedValueOnce(mockRun);

    render(
      <MemoryRouter initialEntries={['/create']}>
        <Routes>
          <Route path="/create" element={<CreateRunView />} />
          <Route path="/runs/:run_id" element={<RunDetailView />} />
        </Routes>
      </MemoryRouter>
    );

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: 'Lake Loop' } });
    fireEvent.change(inputs[1], { target: { value: '2025-01-01T09:00' } });
    fireEvent.change(inputs[2], { target: { value: 'Lake Park' } });

    const createBtn = screen.getByRole('button', { name: /create run/i });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('POST', '/runs', expect.objectContaining({ title: 'Lake Loop' }));
    });

    apiFetch.mockResolvedValueOnce(mockRun);

    render(
      <MemoryRouter initialEntries={['/runs/run-123']}>
        <Routes>
          <Route path="/runs/:run_id" element={<RunDetailView />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Lake Loop')).toBeInTheDocument();
    });
  });
});