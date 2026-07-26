import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MotionConfig } from 'framer-motion'
import './index.css'
import './styles/layout-lock.css'
import App from './App.jsx'
import { ConfirmProvider } from './components/ConfirmProvider'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {/* reducedMotion="user" makes every Framer Motion animation in the app respect
        the OS/browser prefers-reduced-motion setting automatically. */}
    <MotionConfig reducedMotion="user">
      <ConfirmProvider>
        <App />
      </ConfirmProvider>
    </MotionConfig>
  </StrictMode>,
)
