'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react'
import { ingestionApi, scheduleApi } from '@/lib/api'
import type { AcademicCycle } from '@/types'
import { useEffect } from 'react'

export function CsvImportZone() {
  const [cycles, setCycles] = useState<AcademicCycle[]>([])
  const [selectedCycle, setSelectedCycle] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [result, setResult] = useState<{ rows_ingested?: number; error_log?: string } | null>(null)

  useEffect(() => {
    scheduleApi.listCycles().then((r) => {
      const active = r.data.filter((c: AcademicCycle) => c.operational_status)
      setCycles(active)
      if (active.length > 0) setSelectedCycle(active[0].id)
    }).catch(() => {})
  }, [])

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
  })

  const handleUpload = async () => {
    if (!file || !selectedCycle) return
    setStatus('uploading')
    try {
      const res = await ingestionApi.uploadCsv(selectedCycle, file)
      setResult(res.data)
      setStatus(res.data.status === 'SUCCESS' ? 'success' : 'error')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setResult({ error_log: e.response?.data?.detail || 'Upload failed' })
      setStatus('error')
    }
  }

  const reset = () => { setFile(null); setStatus('idle'); setResult(null) }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-lg font-semibold text-chronos-text">CSV Data Import</h2>
        <p className="text-sm text-chronos-muted mt-1">
          Upload a student-centric schedule matrix CSV to populate courses, enrollments, and timetable slots.
        </p>
      </div>

      {/* Cycle selector */}
      <div className="glass-card p-5 space-y-3">
        <p className="section-title">Target Academic Cycle</p>
        {cycles.length === 0 ? (
          <p className="text-sm text-chronos-muted">No active cycles found. Create one first.</p>
        ) : (
          <select
            value={selectedCycle ?? ''}
            onChange={(e) => setSelectedCycle(Number(e.target.value))}
            className="input-field"
          >
            {cycles.map((c) => (
              <option key={c.id} value={c.id}>{c.cycle_label} ({c.date_bounds_start} → {c.date_bounds_end})</option>
            ))}
          </select>
        )}
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200 ${
          isDragActive
            ? 'border-chronos-teal bg-chronos-teal/5'
            : file
            ? 'border-chronos-emerald/50 bg-chronos-emerald/5'
            : 'border-chronos-border hover:border-chronos-teal/50 hover:bg-chronos-surface/50'
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          {file ? (
            <FileSpreadsheet className="w-10 h-10 text-chronos-emerald" />
          ) : (
            <Upload className={`w-10 h-10 ${isDragActive ? 'text-chronos-teal' : 'text-chronos-muted'}`} />
          )}
          {file ? (
            <div>
              <p className="text-sm font-medium text-chronos-emerald">{file.name}</p>
              <p className="text-xs text-chronos-muted">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-chronos-text">Drop CSV file here or click to browse</p>
              <p className="text-xs text-chronos-muted mt-1">Required columns: student_id, student_name, student_email, subject_code, subject_title, department, day_of_week_index, time_window_start, time_window_end, teacher_id, room</p>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handleUpload}
          disabled={!file || !selectedCycle || status === 'uploading'}
          className="btn-primary"
        >
          {status === 'uploading' ? <><Loader2 className="w-4 h-4 animate-spin" /> Processing...</> : <><Upload className="w-4 h-4" /> Upload & Import</>}
        </button>
        {file && <button onClick={reset} className="btn-secondary"><X className="w-4 h-4" /> Clear</button>}
      </div>

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`p-4 rounded-xl flex items-start gap-3 ${
              status === 'success' ? 'bg-chronos-emerald/10 border border-chronos-emerald/20' : 'bg-chronos-danger/10 border border-chronos-danger/20'
            }`}
          >
            {status === 'success' ? <CheckCircle2 className="w-5 h-5 text-chronos-emerald shrink-0 mt-0.5" /> : <AlertCircle className="w-5 h-5 text-chronos-danger shrink-0 mt-0.5" />}
            <div>
              {status === 'success' ? (
                <>
                  <p className="text-sm font-medium text-chronos-emerald">Import Successful</p>
                  <p className="text-xs text-chronos-text-dim mt-0.5">{result.rows_ingested} rows ingested into the database.</p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-chronos-danger">Import Failed</p>
                  <p className="text-xs text-chronos-text-dim mt-0.5 font-mono">{result.error_log}</p>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
