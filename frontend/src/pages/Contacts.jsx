import { useState, useEffect } from 'react'
import client from '../api/client.js'

export default function Contacts() {
  const [contacts, setContacts] = useState([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    client.get('/api/contacts')
      .then(({ data }) => setContacts(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Contacts</h1>
        <p className="mt-1 text-sm text-gray-500">Decision makers found by the latest pipeline run.</p>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : contacts.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg px-5 py-10 text-center">
          <p className="text-sm text-gray-400">No contacts yet. Run the pipeline first.</p>
        </div>
      ) : (
        <>
          <p className="text-sm text-gray-500">
            <span className="font-medium text-gray-700">{contacts.length}</span> contact{contacts.length !== 1 ? 's' : ''} found
          </p>
          <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Name', 'Title', 'Company', 'Email', 'LinkedIn'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {contacts.map((c, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">{c.name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.title || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.company || c.domain || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{c.email || '—'}</td>
                    <td className="px-4 py-3">
                      {c.linkedin_url
                        ? <a href={c.linkedin_url} target="_blank" rel="noreferrer"
                            className="text-blue-600 hover:underline text-xs">View</a>
                        : <span className="text-gray-300">—</span>}
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
