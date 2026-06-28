import { createBrowserRouter } from 'react-router-dom'
import { App } from './App'
import { Landing } from './pages/Landing'
import { PlannersDesk } from './modes/normal/PlannersDesk'
import { KnowledgeCockpit } from './modes/advanced/KnowledgeCockpit'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Landing /> },
      { path: 'normal', element: <PlannersDesk /> },
      { path: 'advanced', element: <KnowledgeCockpit /> },
    ],
  },
])
