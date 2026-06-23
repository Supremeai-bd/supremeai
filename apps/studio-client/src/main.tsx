// ============================================================================
// component >> main.tsx
// project >> SupremeAI 2.0
// purpose >> App main entry point
// module >> src
// ============================================================================
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
