import React from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import { AppLayout } from './pages/AppLayout'
import { Dashboard } from './pages/Dashboard'
import { Browser } from './pages/Browser'
import { Profile } from './pages/Profile'
import { Portfolio } from './pages/Portfolio'
import { Narrative } from './pages/Narrative'
import { Intents } from './pages/Intents'
import { Settings } from './pages/Settings'

const qc = new QueryClient()

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'memories', element: <Browser /> },
      { path: 'profile', element: <Profile /> },
      { path: 'portfolio', element: <Portfolio /> },
      { path: 'narrative', element: <Narrative /> },
      { path: 'intents', element: <Intents /> },
      { path: 'settings', element: <Settings /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
)
