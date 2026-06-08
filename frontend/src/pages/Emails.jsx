import { useState, useEffect } from 'react'
import client from '../api/client.js'

const STATUS_STYLE = {
  sent:   'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

export default function Emails() {
  const [emails,  setEmails]  = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/api/emails')
      .then(({ data }) => setEmails(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const sent   = emails.filter(e => e.status === 'sent').length
  const failed = emails.filter(e => e.status === 'failed').length

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Emails</h1>
        <p className="mt-1 text-sm text-gray-500">Send log from the latest completed pipeline run.</p>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : emails.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg px-5 py-10 text-center">
          <p className="text-sm text-gray-400">No emails sent yet. Complete a pipeline run first.</p>
        </div>
      ) : (
        <>
          <div className="flex gap-4">
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-center min-w-[80px]">
              <p className="text-2xl font-bold text-green-700">{sent}</p>
              <p className="text-xs text-green-600 mt-0.5">Sent</p>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-center min-w-[80px]">
              <p className="text-2xl font-bold text-red-700">{failed}</p>
              <p className="text-xs text-red-600 mt-0.5">Failed</p>
            </div>
          </div>

          <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Name', 'Email', 'Company', 'Status', 'Sent At'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {emails.map((e, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">{e.name || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{e.email || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{e.company || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLE[e.status] ?? 'bg-gray-100 text-gray-500'}`}>
                        {e.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {e.sent_at ? new Date(e.sent_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
