import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import Splash from './components/Splash'
import './styles.css'

function Root() {
  const [splashDone, setSplashDone] = useState(false)

  return (
    <>
      {!splashDone && <Splash onDone={() => setSplashDone(true)} />}
      <App />
    </>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
