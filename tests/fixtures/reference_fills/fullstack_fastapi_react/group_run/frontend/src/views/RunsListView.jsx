import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api.js'

export default function RunsListView() {
  const [runs, setRuns] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/runs')
      .then(setRuns)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <h1>Group Runs</h1>
      <Link to="/create">Create a run</Link>
      {error && <p role="alert">{error}</p>}
      <ul>
        {runs.map((run) => (
          <li key={run.id}>
            <Link to={`/runs/${run.id}`}>{run.title}</Link> — {run.participants.length} joined
          </li>
        ))}
      </ul>
    </div>
  )
}
