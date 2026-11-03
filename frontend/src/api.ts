// Cliente mínimo para la API del backend.

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function handle(res: Response) {
  if (!res.ok) {
    let msg = `Error ${res.status}`
    try {
      const j = await res.json()
      msg = j.detail || msg
    } catch {}
    throw new ApiError(msg, res.status)
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res
}

export const api = {
  get: (url: string) => fetch(`/api${url}`).then(handle),
  post: (url: string, body: any = {}) =>
    fetch(`/api${url}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }).then(handle),
  put: (url: string, body: any = {}) =>
    fetch(`/api${url}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }).then(handle),
  del: (url: string) => fetch(`/api${url}`, { method: 'DELETE' }).then(handle),
  form: (url: string, fields: Record<string, string | Blob>) => {
    const fd = new FormData()
    for (const [k, v] of Object.entries(fields)) {
      if (v instanceof Blob) fd.append(k, v, 'audio.wav')
      else fd.append(k, v)
    }
    return fetch(`/api${url}`, { method: 'POST', body: fd }).then(handle)
  },
}
