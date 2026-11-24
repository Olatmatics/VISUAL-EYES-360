import { useEffect, useRef } from 'react'
import $ from 'jquery'

/**
 * App-entry splash screen.
 *
 * jQuery drives the motion: a fuel nozzle glides left -> right while three
 * dots pulse, then the overlay fades out once the app is ready.
 */
export default function Splash({ onDone }: { onDone: () => void }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const doneRef = useRef(false)

  useEffect(() => {
    const finish = () => {
      if (doneRef.current) return
      doneRef.current = true
      onDone()
    }

    const el = rootRef.current
    if (!el) {
      finish()
      return
    }

    const $root = $(el)

    // Glide the nozzle across the track, then loop it.
    const $nozzle = $root.find('.splash-nozzle')
    const $track = $root.find('.splash-track')

    const runNozzle = () => {
      const width = $track.innerWidth() || 260
      $nozzle
        .stop(true)
        .css({ left: -70, opacity: 0 })
        .animate({ opacity: 1 }, 180)
        .animate({ left: width + 10 }, 1500, 'linear', () => {
          $nozzle.animate({ opacity: 0 }, 160, runNozzle)
        })
    }
    runNozzle()

    // Fade the whole splash out after the minimum display time.
    const timer = window.setTimeout(() => {
      $root.animate({ opacity: 0 }, 460, 'swing', finish)
    }, 2200)

    return () => {
      window.clearTimeout(timer)
      $root.stop(true, true)
      $nozzle.stop(true, true)
    }
  }, [onDone])

  return (
    <div className="splash" ref={rootRef} role="status" aria-label="Loading VISUAL EYES 360">
      <div className="splash-inner">
        <div className="splash-logo">
          <div className="splash-mark">VE</div>
          <div className="splash-brand">
            <strong>VISUAL EYES 360</strong>
            <span>AUTOMATION</span>
          </div>
        </div>

        <div className="splash-track">
          <div className="splash-nozzle" aria-hidden="true">
            <svg viewBox="0 0 64 40" width="58" height="36" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* nozzle body */}
              <rect x="4" y="10" width="30" height="20" rx="4" fill="#0ea5a4" />
              <rect x="8" y="14" width="14" height="5" rx="2.5" fill="#0b1b2b" opacity=".55" />
              {/* hose swing joint */}
              <path d="M34 14h8a6 6 0 0 1 6 6v6" stroke="#22b8a6" strokeWidth="3.5" strokeLinecap="round" />
              {/* spout */}
              <path d="M48 26h10" stroke="#f0b429" strokeWidth="4" strokeLinecap="round" />
              <circle cx="59" cy="26" r="3" fill="#f0b429" />
              {/* handle */}
              <path d="M10 30v5h12v-5" stroke="#0b1b2b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {/* flowing fuel droplet trail */}
            <span className="splash-drip" />
          </div>
        </div>

        <div className="splash-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="splash-progress" aria-hidden="true"><span className="splash-progress-fill" /></div>
        <p className="splash-tag">Fuel Station Automation &amp; Control</p>
        <p className="splash-status">Establishing secure station link…</p>
      </div>
    </div>
  )
}
