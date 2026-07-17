import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api.js'

export default function CreateRunView() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ title: '', datetime: '', location: '' })
  const [error, setError] = useState(null)

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const run = await apiFetch('/runs', { method: 'POST', body: JSON.stringify(form) })
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={submit}>
      <h1>Create a run</h1>
      {error && <p role="alert">{error}</p>}
      <input placeholder="Title" value={form.title} onChange={update('title')} />
      <input placeholder="Date and time" value={form.datetime} onChange={update('datetime')} />
      <input placeholder="Location" value={form.location} onChange={update('location')} />
      <button type="submit">Create</button>
    </form>
  )
}
