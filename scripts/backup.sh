#!/bin/bash
# scripts/backup.sh
# Backup automático de la base de datos de NIAH

set -e

# Directorios
NIAH_DIR="$HOME/mi-agente-llama"
BACKUP_DIR="$NIAH_DIR/backups"
FECHA=$(date +"%Y-%m-%d_%H-%M-%S")
ARCHIVO="$BACKUP_DIR/niah_backup_$FECHA.tar.gz"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

# Crear el tar.gz con la DB y Chroma
echo "[$(date)] Iniciando backup..."
tar -czf "$ARCHIVO" \
  -C "$NIAH_DIR" \
  niah_history.db \
  rag_chroma \
  2>/dev/null || true

# Tamaño del backup
SIZE=$(du -h "$ARCHIVO" | cut -f1)
echo "[$(date)] Backup creado: $ARCHIVO ($SIZE)"

# Eliminar backups con más de 30 días
ELIMINADOS=$(find "$BACKUP_DIR" -name "niah_backup_*.tar.gz" -mtime +30 -print -delete | wc -l)
if [ "$ELIMINADOS" -gt 0 ]; then
  echo "[$(date)] Backups antiguos eliminados: $ELIMINADOS"
fi

# Contar backups actuales
TOTAL=$(find "$BACKUP_DIR" -name "niah_backup_*.tar.gz" | wc -l)
echo "[$(date)] Total de backups: $TOTAL"
echo "[$(date)] Backup completado"
