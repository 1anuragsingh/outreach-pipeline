import { useState, useEffect, useRef } from 'react'
import client from '../api/client.js'

// ── Constants ──────────────────────────────────────────────────────────────

const STAGES = [
  { num: 1, tool: 'Ocean.io',  countKey: 'companies', label: 'companies' },
  { num: 2, tool: 'Prospeo',   countKey: 'people',    label: 'people'    },
  { num: 3, tool: 'Eazyreach', countKey: 'contacts',  label: 'contacts'  },
  { num: 4, tool: 'Brevo',     countKey: null,        label: 'emails'    },
]

// checkpoint is NOT terminal — after confirm, backend moves to sending → done
const TERMINAL = new Set(['done', 'error', 'aborted'])

// ── Helpers ────────────────────────────────────────────────────────────────

function getCardStatus(cardStage, currentStage, overallStatus) {
  if (!overallStatus) return 'pending'
  if (overallStatus === 'done') return 'done'
  if (overallStatus === 'error' && currentStage === cardStage) return 'error'
  // checkpoint means stages 1-3 all finished successfully
  if (overallStatus === 'checkpoint' && cardStage <= 3) return 'done'
  if (currentStage > cardStage) return 'done'
  if (
    currentStage === cardStage &&
    (overallStatus === 'running' || overallStatus === 'sending')
  ) return 'running'
  return 'pending'
}

const BADGE = {
  running: { bg: 'bg-blue-100 text-blue-700',  dot: 'bg-blue-500',  text: 'Running' },
  done:    { bg: 'bg-green-100 text-green-700', dot: 'bg-green-500', text: 'Done'    },
  pending: { bg: 'bg-gray-100 text-gray-400',   dot: 'bg-gray-300',  text: 'Pending' },
  error:   { bg: 'bg-red-100 text-red-700',     dot: 'bg-red-500',   text: 'Error'   },
}

// ── Component ──────────────────────────────────────────────────────────────

export default function Pipeline() {
  const [domain,      setDomain]      = useState('')
  const [isStarting,  setIsStarting]  = useState(false)
  const [jobId,       setJobId]       = useState(null)
  const [jobData,     setJobData]     = useState(null)
  const [contacts,    setContacts]    = useState([])
  const [actionTaken, setActionTaken] = useState(false)
  const intervalRef = useRef(null)

  const status = jobData?.status ?? null
  const stage  = jobData?.stage  ?? 0
  const counts = jobData?.counts ?? { companies: 0, people: 0, contacts: 0 }
  const error  = jobData?.error  ?? null
  const isBusy = isStarting || status === 'running' || status === 'sending'

  // ── Polling ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const { data } = await client.get(`/api/status/${jobId}`)
        setJobData(data)
        if (TERMINAL.has(data.status)) {
          clearInterval(intervalRef.current)
        }
      } catch (err) {
        console.error('Status poll failed:', err)
        clearInterval(intervalRef.current)
      }
    }

    poll() // fire immediately on mount / new jobId
    intervalRef.current = setInterval(poll, 2000)
    return () => clearInterval(intervalRef.current)
  }, [jobId])

  // ── Fetch contacts once checkpoint is reached ─────────────────────────────
  useEffect(() => {
    if (status !== 'checkpoint') return
    client
      .get('/api/contacts')
      .then(({ data }) => setContacts(data))
      .catch(console.error)
  }, [status])

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleRun = async () => {
    const trimmed = domain.trim()
    if (!trimmed || isBusy) return

    clearInterval(intervalRef.current)
    setJobId(null)
    setJobData(null)
    setContacts([])
    setActionTaken(false)
    setIsStarting(true)

    try {
      const { data } = await client.post('/api/run', { domain: trimmed })
      setJobId(data.job_id)
    } catch (err) {
      console.error('Failed to start pipeline:', err)
    } finally {
      setIsStarting(false)
    }
  }

  const handleConfirm = async () => {
    try {
      await client.post(`/api/confirm/${jobId}`)
      setActionTaken(true)
      // Polling is still running — it will pick up sending → done automatically
    } catch (err) {
      console.error('Confirm failed:', err)
    }
  }

  const handleAbort = async () => {
    try {
      await client.post(`/api/abort/${jobId}`)
      setActionTaken(true)
      setJobData(prev => ({ ...prev, status: 'aborted' }))
      clearInterval(intervalRef.current)
    } catch (err) {
      console.error('Abort failed:', err)
    }
  }

  const previewContacts = contacts.slice(0, 5)

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Pipeline</h1>
        <p className="mt-1 text-sm text-gray-500">
          Enter a seed domain to find lookalike companies and reach their decision makers.
        </p>
      </div>

      {/* ── Domain input ──────────────────────────────────────────────────── */}
      <div className="flex gap-3">
        <input
          type="text"
          value={domain}
          onChange={e => setDomain(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleRun()}
          placeholder="company.domain"
          disabled={isBusy}
          className="
            flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed
            transition
          "
        />
        <button
          onClick={handleRun}
          disabled={isBusy || !domain.trim()}
          className="
            px-5 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg shadow-sm
            hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            disabled:opacity-50 disabled:cursor-not-allowed transition-colors
          "
        >
          {isStarting ? 'Starting…' : isBusy ? 'Running…' : 'Run Pipeline'}
        </button>
      </div>

      {/* ── Stage cards ───────────────────────────────────────────────────── */}
      {jobId && (
        <div className="grid grid-cols-4 gap-4">
          {STAGES.map(({ num, tool, countKey, label }) => {
            const cs = getCardStatus(num, stage, status)
            const badge = BADGE[cs]
            const count = countKey ? counts[countKey] : (status === 'done' ? counts.contacts : '—')
            const isActive = stage === num && (status === 'running' || status === 'sending')

            return (
              <div
                key={num}
                className={`
                  relative bg-white rounded-xl border p-5 transition-all
                  ${isActive
                    ? 'border-blue-300 shadow-lg shadow-blue-100 ring-1 ring-blue-200'
                    : 'border-gray-200 shadow-sm'
                  }
                `}
              >
                {/* Pulsing dot for active stage */}
                {isActive && (
                  <span className="absolute top-4 right-4 flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
                  </span>
                )}

                <p className="text-xs font-medium text-gray-400">Stage {num}</p>
                <p className="mt-0.5 text-sm font-semibold text-gray-800">{tool}</p>

                <p className="mt-4 text-3xl font-bold text-gray-900 tabular-nums leading-none">
                  {count}
                </p>
                <p className="mt-0.5 text-xs text-gray-400">{label}</p>

                <span className={`mt-4 inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full ${badge.bg}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
                  {badge.text}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Error banner ──────────────────────────────────────────────────── */}
      {status === 'error' && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg px-5 py-4">
          <span className="text-red-400 text-lg leading-none mt-0.5">✕</span>
          <div>
            <p className="text-sm font-semibold text-red-800">Pipeline failed</p>
            <p className="mt-0.5 text-sm text-red-700">{error ?? 'An unexpected error occurred.'}</p>
          </div>
        </div>
      )}

      {/* ── Done banner ───────────────────────────────────────────────────── */}
      {status === 'done' && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg px-5 py-4">
          <span className="text-green-500 text-lg leading-none">✓</span>
          <p className="text-sm font-semibold text-green-800">
            Pipeline complete.&nbsp;
            {counts.contacts} email{counts.contacts !== 1 ? 's' : ''} sent.
          </p>
        </div>
      )}

      {/* ── Checkpoint bar ────────────────────────────────────────────────── */}
      {status === 'checkpoint' && !actionTaken && (
        <div className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-lg px-5 py-4 gap-4">
          <div>
            <p className="text-sm font-semibold text-amber-900">
              {counts.contacts} contact{counts.contacts !== 1 ? 's' : ''} ready to send.
              &nbsp;Review before firing.
            </p>
            <p className="mt-0.5 text-xs text-amber-700">
              Check the contacts below, then confirm or abort.
            </p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <button
              onClick={handleAbort}
              className="
                px-4 py-2 text-sm font-medium text-red-600 border border-red-300 rounded-lg
                hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-1
                transition-colors
              "
            >
              Abort
            </button>
            <button
              onClick={handleConfirm}
              className="
                px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg shadow-sm
                hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1
                transition-colors
              "
            >
              Confirm Send
            </button>
          </div>
        </div>
      )}

      {/* ── Contacts preview table ────────────────────────────────────────── */}
      {contacts.length > 0 && (
        <div>
          <p className="text-sm text-gray-500 mb-3">
            Showing&nbsp;
            <span className="font-medium text-gray-700">{previewContacts.length}</span>
            &nbsp;of&nbsp;
            <span className="font-medium text-gray-700">{contacts.length}</span>
            &nbsp;contact{contacts.length !== 1 ? 's' : ''}
          </p>

          <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Name', 'Title', 'Company', 'Email'].map(h => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {previewContacts.map((c, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                      {c.name || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {c.title || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {c.company || c.domain || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                      {c.email || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  )
}
