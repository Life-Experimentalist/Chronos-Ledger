{{/* Copyright 2026 Chronos Ledger Contributors (Apache 2.0) */}}

{{- define "chronos-ledger.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "chronos-ledger.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "chronos-ledger.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "chronos-ledger.labels" -}}
helm.sh/chart: {{ include "chronos-ledger.chart" . }}
app.kubernetes.io/name: {{ include "chronos-ledger.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* Call with (dict "root" . "component" "backend"). */}}
{{- define "chronos-ledger.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chronos-ledger.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Call with (dict "root" . "image" .Values.backend.image). */}}
{{- define "chronos-ledger.image" -}}
{{- $tag := default (printf "v%s" .root.Chart.AppVersion) .image.tag -}}
{{- printf "%s:%s" .image.repository $tag -}}
{{- end -}}
