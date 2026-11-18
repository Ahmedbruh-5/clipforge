import { Outlet } from 'react-router-dom'

import { Sidebar } from './Sidebar'

export function AppShell() {
  return (
    <div className="flex h-full min-h-screen bg-bg text-text">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
