import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../api.js'

export default function RunDetailView() {
  const { id } = useParams()
  const [run, setRun] = useState(null)
  const [name, setName] = useState('')
  const [error, setError] = useState(null)

  const load = () =>
    apiFetch(`/runs/${id}`)
      .then(setRun)
      .catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [id])

  const mutate = (action) => async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const updated = await apiFetch(`/runs/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ name }),
      })
      setRun(updated)
      setName('')
    } catch (err) {
      setError(err.message)
    }
  }

  if (error && !run) return <p role="alert">{error}</p>
  if (!run) return <p>Loading…</p>

  return (
    <div>
      <h1>{run.title}</h1>
      <p>
        {run.location} · {run.datetime}
      </p>
      {error && <p role="alert">{error}</p>}
      <ul>
        {run.participants.map((p) => (
          <li key={p.id}>{p.name}</li>
        ))}
      </ul>
      <form>
        <input placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
        <button onClick={mutate('join')}>Join</button>
        <button onClick={mutate('leave')}>Leave</button>
      </form>
    </div>
  )
}
