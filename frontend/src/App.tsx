import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { ToastProvider } from './components/common/ToastProvider'
import { AppShell } from './components/layout/AppShell'
import { Dashboard } from './pages/Dashboard'
import { Editor } from './pages/Editor'
import { Library } from './pages/Library'
import { Review } from './pages/Review'
import { Schedule } from './pages/Schedule'
import { Settings } from './pages/Settings'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="library" element={<Library />} />
            <Route path="editor" element={<Editor />} />
            <Route path="review" element={<Review />} />
            <Route path="schedule" element={<Schedule />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
