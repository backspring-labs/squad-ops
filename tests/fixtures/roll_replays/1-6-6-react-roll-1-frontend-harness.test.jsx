// Scaffold-owned harness proof (frozen): vitest + jsdom + Testing Library +
// router wiring all work in this workspace. Write real UI tests in NEW files
// beside this one (e.g. views.test.jsx) — render with MemoryRouter exactly as
// below; jest-dom matchers are already registered via src/test-setup.js.
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App.jsx'

describe('frontend test harness', () => {
  it('renders the app shell under a memory router', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/__harness__']}>
        <App />
      </MemoryRouter>,
    )
    expect(container.querySelector('.app')).toBeInTheDocument()
  })
})
