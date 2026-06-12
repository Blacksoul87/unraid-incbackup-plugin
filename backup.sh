#!/bin/bash

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

source /boot/config/plugins/incbackup/incbackup.cfg
LOGFILE="/var/log/incbackup.log"

DATE=$(date +%Y-%m-%d_%H-%M-%S)
PER_RUN_LOG=""
if [ -n "$LOGDIR" ] && [ -d "$LOGDIR" ]; then
    PER_RUN_LOG="$LOGDIR/backup_${DATE}.log"
fi

log() {
    local msg="$(date '+%Y-%m-%d %H:%M:%S') - $1"
    echo "$msg" >> "$LOGFILE"
    if [ -n "$PER_RUN_LOG" ]; then
        echo "$msg" >> "$PER_RUN_LOG"
    fi
}

if [ -f "$LOGFILE" ]; then
    size=$(stat -c%s "$LOGFILE")
    if [ $size -gt 5242880 ]; then
        mv "$LOGFILE" "$LOGFILE.old"
    fi
fi

PIDFILE=/var/run/incbackup.pid
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log "Ein Backup laeuft bereits (PID $PID). Breche ab."
        exit 0
    else
        rm -f "$PIDFILE"
    fi
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"; exit' INT TERM EXIT

log "--- Inkrementelles Backup gestartet ---"

if [ "$ENABLE" != "yes" ]; then
    log "Backup ist deaktiviert. Beende."
    rm -f "$PIDFILE"
    exit 0
fi

if [ -z "$KEEP" ] || [ "$KEEP" -lt 1 ]; then
    KEEP=7
fi

i=0
HAS_ERROR=0

while true; do
    SRC_VAR="SRC_$i"
    DST_VAR="DST_$i"
    SRC="${!SRC_VAR}"
    DST="${!DST_VAR}"
    
    if [ -z "$SRC" ] || [ -z "$DST" ]; then
        break
    fi
    
    log ">>> Verarbeite Pfad-Paar [$i]: $SRC -> $DST"
    
    if [ ! -d "$SRC" ]; then
        log "FEHLER: Quellverzeichnis $SRC existiert nicht."
        HAS_ERROR=1
        i=$((i+1))
        continue
    fi
    
    mkdir -p "$DST"
    
    LATEST_DIR=$(ls -d "$DST"/20*/ 2>/dev/null | tail -n 1)
    TARGET_DIR="$DST/$DATE"
    
    RSYNC_OUT="/tmp/rsync_out_$$"
    RSYNC_ERR="/tmp/rsync_err_$$"
    
    if [ -n "$LATEST_DIR" ] && [ -d "$LATEST_DIR" ]; then
        log "Verwende inkrementelle Basis (Hardlinks): $LATEST_DIR"
        rsync -a -v --delete --link-dest="$LATEST_DIR" "$SRC/" "$TARGET_DIR/" > "$RSYNC_OUT" 2> "$RSYNC_ERR"
    else
        log "Erstes Voll-Backup (keine Vorversion gefunden)."
        rsync -a -v --delete "$SRC/" "$TARGET_DIR/" > "$RSYNC_OUT" 2> "$RSYNC_ERR"
    fi
    
    RSYNC_EXIT=$?
    
    cat "$RSYNC_OUT" >> "$LOGFILE"
    cat "$RSYNC_ERR" >> "$LOGFILE"
    if [ -n "$PER_RUN_LOG" ]; then
        cat "$RSYNC_OUT" >> "$PER_RUN_LOG"
        cat "$RSYNC_ERR" >> "$PER_RUN_LOG"
    fi
    
    if [ $RSYNC_EXIT -eq 0 ]; then
        log "Rsync erfolgreich beendet für $SRC -> $DST"
        /usr/local/emhttp/webGui/scripts/notify -i "normal" -s "Incremental Backup" -d "Erfolgreich: $SRC" -m "Ziel: $DST abgeschlossen."
    else
        log "WARNUNG: Rsync meldete Fehler bei $SRC -> $DST (Exit Code: $RSYNC_EXIT)"
        HAS_ERROR=1
        
        ERR_MSG=$(head -n 3 "$RSYNC_ERR" | tr '\n' ' ' | tr -d '"' | tr -d "\'")
        if [ -z "$ERR_MSG" ]; then
            ERR_MSG="Unbekannter Fehler (Code $RSYNC_EXIT)."
        fi
        
        /usr/local/emhttp/webGui/scripts/notify -i "warning" -s "Incremental Backup" -d "Fehler bei: $SRC" -m "Ziel: $DST | $ERR_MSG"
    fi
    
    rm -f "$RSYNC_OUT" "$RSYNC_ERR"
    
    log "Pruefe Aufbewahrung (max $KEEP Backups)..."
    DIRS=($(ls -d "$DST"/20*/ 2>/dev/null | sort))
    COUNT=${#DIRS[@]}
    
    if [ $COUNT -gt $KEEP ]; then
        TO_DELETE=$((COUNT - KEEP))
        for ((j=0; j<TO_DELETE; j++)); do
            log "Loesche altes Backup: ${DIRS[$j]}"
            rm -rf "${DIRS[$j]}"
        done
    fi
    
    log "<<< Abgeschlossen fuer [$i]."
    i=$((i+1))
done

log "--- Inkrementelles Backup komplett beendet ---"

if [ "$HAS_ERROR" = "1" ]; then
    /usr/local/emhttp/webGui/scripts/notify -i "warning" -s "Incremental Backup" -d "Backup mit Fehlern abgeschlossen" -m "Bitte pruefe das Log."
else
    /usr/local/emhttp/webGui/scripts/notify -i "normal" -s "Incremental Backup" -d "Backup erfolgreich abgeschlossen"
fi

rm -f "$PIDFILE"
trap - INT TERM EXIT
