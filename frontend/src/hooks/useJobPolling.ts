import { useEffect } from 'react'

import { fetchJob, getErrorMessage } from '../services/api'
import type { Job } from '../types'

type Options = {
  intervalMs?: number
  onUpdate: (job: Job) => void
  onError?: (message: string) => void
}

/**
 * Poll a background job until it reaches a terminal status.
 */
export function useJobPolling(job: Job | null | undefined, options: Options) {
  const { intervalMs = 1000, onUpdate, onError } = options

  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') return

    const timer = window.setInterval(() => {
      fetchJob(job.id)
        .then(onUpdate)
        .catch((err) => onError?.(getErrorMessage(err)))
    }, intervalMs)

    return () => window.clearInterval(timer)
  }, [job, intervalMs, onUpdate, onError])
}
