{{/*
Expand chart name / fullname helpers.
*/}}
{{- define "ai-sre-copilot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ai-sre-copilot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s" (include "ai-sre-copilot.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "ai-sre-copilot.labels" -}}
app.kubernetes.io/name: {{ include "ai-sre-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- range $k, $v := .Values.global.labels }}
{{ $k }}: {{ $v | quote }}
{{- end }}
{{- end }}

{{- define "ai-sre-copilot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-sre-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "ai-sre-copilot.namespace" -}}
{{- default .Release.Namespace .Values.namespace.name }}
{{- end }}

{{- define "ai-sre-copilot.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.config.postgresUser }}:{{ .Values.secrets.postgresPassword }}@{{ .Values.config.postgresHost }}:5432/{{ .Values.config.postgresDb }}
{{- end }}

{{- define "ai-sre-copilot.databaseUrlSync" -}}
postgresql+psycopg2://{{ .Values.config.postgresUser }}:{{ .Values.secrets.postgresPassword }}@{{ .Values.config.postgresHost }}:5432/{{ .Values.config.postgresDb }}
{{- end }}
