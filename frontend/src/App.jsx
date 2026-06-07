import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import Pipeline from './pages/Pipeline.jsx'
import Contacts from './pages/Contacts.jsx'
import Emails from './pages/Emails.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Pipeline />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/emails" element={<Emails />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
