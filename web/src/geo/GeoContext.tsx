import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { FuelProduct, GeoLga, GeoState } from '../types'

interface GeoStateShape {
  states: GeoState[]
  products: FuelProduct[]
  loading: boolean
  lgasFor: (stateId: string | undefined) => GeoLga[]
  loadLgas: (stateId: string) => Promise<void>
  stateName: (id: string | null | undefined) => string
  lgaName: (id: string | null | undefined) => string
}

const GeoContext = createContext<GeoStateShape | null>(null)

export function GeoProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [states, setStates] = useState<GeoState[]>([])
  const [products, setProducts] = useState<FuelProduct[]>([])
  const [loading, setLoading] = useState(false)
  const lgaCache = useRef<Record<string, GeoLga[]>>({})
  const [lgaVersion, setLgaVersion] = useState(0)

  useEffect(() => {
    if (!user) {
      setStates([])
      setProducts([])
      lgaCache.current = {}
      return
    }
    setLoading(true)
    Promise.all([
      api.get<GeoState[]>('/geo/states'),
      api.get<FuelProduct[]>('/geo/products').catch(() => []),
    ])
      .then(([stateRows, productRows]) => {
        setStates(stateRows)
        setProducts(productRows)
      })
      .catch(() => {
        setStates([])
      })
      .finally(() => setLoading(false))
  }, [user])

  const loadLgas = useCallback(async (stateId: string) => {
    if (!stateId || lgaCache.current[stateId]) return
    try {
      const rows = await api.get<GeoLga[]>(`/geo/states/${stateId}/lgas`)
      lgaCache.current[stateId] = rows
      setLgaVersion((v) => v + 1)
    } catch {
      lgaCache.current[stateId] = []
    }
  }, [])

  const lgasFor = useCallback((stateId: string | undefined) => {
    if (!stateId) return []
    return lgaCache.current[stateId] ?? []
  }, [])

  const stateName = useCallback(
    (id: string | null | undefined) => states.find((s) => s.id === id)?.name ?? '',
    [states],
  )

  const lgaName = useCallback(
    (id: string | null | undefined) => {
      if (!id) return ''
      for (const rows of Object.values(lgaCache.current)) {
        const match = rows.find((l) => l.id === id)
        if (match) return match.name
      }
      return ''
    },
    // lgaVersion keeps the callback fresh when a cache entry is added.
    [lgaVersion],
  )

  const value = useMemo(
    () => ({ states, products, loading, lgasFor, loadLgas, stateName, lgaName }),
    [states, products, loading, lgasFor, loadLgas, stateName, lgaName],
  )

  return <GeoContext.Provider value={value}>{children}</GeoContext.Provider>
}

export function useGeo() {
  const context = useContext(GeoContext)
  if (!context) throw new Error('useGeo must be used inside GeoProvider')
  return context
}
