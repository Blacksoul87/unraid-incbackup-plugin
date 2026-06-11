import base64
import html

page_content = """Menu="Utilities"
Title="Incremental Backup"
Icon="backup.png"
---
<?php
$cfg_file = '/boot/config/plugins/incbackup/incbackup.cfg';
$log_file = '/var/log/incbackup.log';
$pid_file = '/var/run/incbackup.pid';

// AJAX Log Loader
if (isset($_POST['action']) && $_POST['action'] == 'get_log') {
    if (file_exists($log_file)) {
        $log_lines = file($log_file);
        if (count($log_lines) > 150) {
            $log_lines = array_slice($log_lines, -150);
        }
        echo htmlspecialchars(implode("", $log_lines));
    } else {
        echo "Noch keine Logs vorhanden. Starten Sie ein Backup.";
    }
    exit;
}

$cfg = @parse_ini_file($cfg_file);
if ($cfg === false) {
    $cfg = ['ENABLE' => 'no', 'KEEP' => '7', 'FREQ' => 'daily', 'HOUR' => '2', 'MINUTE' => '0'];
}

$paths = [];
$i = 0;
while (isset($cfg["SRC_$i"]) && isset($cfg["DST_$i"])) {
    $paths[] = ['src' => $cfg["SRC_$i"], 'dst' => $cfg["DST_$i"]];
    $i++;
}
if (empty($paths)) {
    $paths[] = ['src' => '', 'dst' => ''];
}

// Formularverarbeitung
if (isset($_POST['save'])) {
    $enable = isset($_POST['enable']) ? "yes" : "no";
    $keep = intval($_POST['keep']);
    if ($keep < 1) $keep = 7;
    
    $freq = $_POST['freq'];
    $hour = $_POST['hour'];
    $minute = $_POST['minute'];
    
    // Cron String generieren
    $cron_str = "";
    if ($freq == "hourly") {
        $cron_str = "$minute * * * *";
    } elseif ($freq == "daily") {
        $cron_str = "$minute $hour * * *";
    } elseif ($freq == "weekly") {
        $cron_str = "$minute $hour * * 0";
    } elseif ($freq == "monthly") {
        $cron_str = "$minute $hour 1 * *";
    } else {
        $cron_str = "$minute $hour * * *";
    }

    $cfg_content  = 'ENABLE="' . $enable . '"' . "\\n";
    $cfg_content .= 'KEEP="' . $keep . '"' . "\\n";
    $cfg_content .= 'FREQ="' . $freq . '"' . "\\n";
    $cfg_content .= 'HOUR="' . $hour . '"' . "\\n";
    $cfg_content .= 'MINUTE="' . $minute . '"' . "\\n";

    $sources = isset($_POST['source']) ? $_POST['source'] : [];
    $dests = isset($_POST['dest']) ? $_POST['dest'] : [];
    
    $path_index = 0;
    if (is_array($sources) && is_array($dests)) {
        for ($i = 0; $i < count($sources); $i++) {
            $s = trim($sources[$i]);
            $d = trim($dests[$i]);
            if (!empty($s) && !empty($d)) {
                $cfg_content .= 'SRC_' . $path_index . '="' . str_replace('"', '\\"', $s) . '"' . "\\n";
                $cfg_content .= 'DST_' . $path_index . '="' . str_replace('"', '\\"', $d) . '"' . "\\n";
                $path_index++;
            }
        }
    }
    file_put_contents($cfg_file, $cfg_content);

    // Direct crontab injection
    $cron_script_path = '/usr/local/emhttp/plugins/incbackup/backup.sh';
    $current_cron = shell_exec("crontab -l 2>/dev/null | grep -v " . escapeshellarg($cron_script_path));
    if ($enable == "yes") {
        $new_cron = $current_cron . $cron_str . " " . $cron_script_path . " > /dev/null 2>&1\\n";
        file_put_contents("/tmp/cron_temp", $new_cron);
        exec("crontab /tmp/cron_temp");
    } else {
        file_put_contents("/tmp/cron_temp", $current_cron);
        exec("crontab /tmp/cron_temp");
    }
    @unlink("/tmp/cron_temp");
    
    $message = "Einstellungen gespeichert. Cron-Job wurde direkt im System verankert.";
    
    // Reload cfg
    $cfg = @parse_ini_file($cfg_file);
    $paths = [];
    $i = 0;
    while (isset($cfg["SRC_$i"]) && isset($cfg["DST_$i"])) {
        $paths[] = ['src' => $cfg["SRC_$i"], 'dst' => $cfg["DST_$i"]];
        $i++;
    }
}

if (isset($_POST['run_now'])) {
    exec("/usr/local/emhttp/plugins/incbackup/backup.sh > /dev/null 2>&1 &");
    $message = "Backup im Hintergrund gestartet.";
}

if (isset($_POST['clear_log'])) {
    @unlink($log_file);
    $message = "Logdatei geleert.";
}

if (isset($_POST['check_size'])) {
    $size_output = "";
    foreach ($paths as $p) {
        $dst = $p['dst'];
        if (!empty($dst) && is_dir($dst)) {
            $cmd = "du -shc " . escapeshellarg($dst) . "/* 2>&1";
            $out = shell_exec($cmd);
            $size_output .= "Ziel: " . htmlspecialchars($dst) . "\\n" . htmlspecialchars($out) . "\\n\\n";
        }
    }
    if (empty($size_output)) $size_output = "Keine Zielverzeichnisse gefunden.";
    $message = "<b>Echter Speicherverbrauch (inkl. Hardlink-Berechnung):</b><br><pre style='background:#1e1e1e; color:#0f0; padding:10px; border-radius:4px;'>" . $size_output . "</pre><br><i>Hinweis: Wenn unten bei 'total' (insgesamt) nur ein Bruchteil von 3x der Originalgroesse steht, arbeiten die Hardlinks absolut korrekt! Windows Explorer versteht Hardlinks ueber das Netzwerk nicht und luegt dich bei der Groesse an.</i>";
}

$is_running = false;
$pid = "";
if (file_exists($pid_file)) {
    $pid = trim(file_get_contents($pid_file));
    if (!empty($pid) && is_dir("/proc/" . $pid)) {
        $is_running = true;
    } else {
        @unlink($pid_file);
    }
}
?>

<style>
    .incbackup-container { padding: 20px; background-color: #f9f9f9; border-radius: 8px; border: 1px solid #e0e0e0; margin-bottom: 20px; color: #333; position: relative;}
    .incbackup-form-group { margin-bottom: 15px; }
    .incbackup-form-group label { display: inline-block; width: 250px; font-weight: bold; vertical-align: top;}
    .incbackup-form-group input[type="text"], .incbackup-form-group input[type="number"], .incbackup-form-group select { padding: 5px; border: 1px solid #ccc; border-radius: 4px; background-color: #fff; color: #333;}
    .incbackup-form-group input[type="checkbox"] { transform: scale(1.5); margin-top: 5px;}
    .incbackup-button { padding: 8px 15px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top:5px;}
    .incbackup-button:hover { background-color: #0056b3; }
    .incbackup-button-secondary { background-color: #28a745; margin-left: 10px; }
    .incbackup-button-secondary:hover { background-color: #218838; }
    .incbackup-button-danger { background-color: #dc3545; padding: 4px 8px; margin-left: 5px;}
    .incbackup-button-danger:hover { background-color: #c82333; }
    .incbackup-message { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 4px; margin-bottom: 15px; }
    .path-row { margin-bottom: 10px; display: flex; align-items: center; gap: 5px;}
    
    .status-badge { padding: 5px 10px; border-radius: 4px; font-weight: bold; display: inline-block; margin-bottom: 15px; position: absolute; top: 20px; right: 20px; z-index: 10; }
    .status-running { background-color: #cce5ff; color: #004085; border: 1px solid #b8daff; }
    .status-idle { background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db; }
    .status-disabled { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }

    .dir-picker-item { padding: 8px; cursor: pointer; border-bottom: 1px solid #eee; display:flex; align-items:center; }
    .dir-picker-item:hover { background-color: #e9ecef; }
    
    .incbackup-tips { margin-top: 5px; font-size: 12px; color: #666; display: block; max-width: 600px; line-height: 1.4;}

    @media (prefers-color-scheme: dark) {
        .incbackup-container { background-color: #2c2c2c; border-color: #444; color: #eee;}
        .incbackup-form-group input[type="text"], .incbackup-form-group input[type="number"], .incbackup-form-group select { background-color: #1a1a1a; border-color: #555; color: #eee;}
        .status-idle { background-color: #444; color: #ddd; border-color: #555; }
        .status-running { background-color: #004085; color: #cce5ff; border-color: #b8daff; }
        .status-disabled { background-color: #721c24; color: #f8d7da; border-color: #f5c6cb; }
        .dir-picker-item:hover { background-color: #333; border-color: #444;}
        .incbackup-tips { color: #aaa; }
    }
</style>

<div class="incbackup-container">
    <h2 style="margin-top:0;">Inkrementelle Backup Einstellungen</h2>
    
    <?php if (isset($message)) echo "<div class='incbackup-message'>$message</div>"; ?>

    <?php if ($is_running): ?>
        <div class="status-badge status-running">Status: Backup läuft gerade (PID: <?php echo htmlspecialchars($pid); ?>) <span style="animation: blink 1s linear infinite;">&#9654;</span></div>
    <?php elseif (isset($cfg['ENABLE']) && $cfg['ENABLE'] == 'yes'): ?>
        <div class="status-badge status-idle">Status: Aktiviert (Wartet auf nächsten Lauf)</div>
    <?php else: ?>
        <div class="status-badge status-disabled">Status: Deaktiviert</div>
    <?php endif; ?>

    <form method="POST">
        <div class="incbackup-form-group">
            <label>Backup Aktivieren:</label>
            <input type="checkbox" name="enable" value="yes" <?php echo (isset($cfg['ENABLE']) && $cfg['ENABLE'] == 'yes') ? 'checked' : ''; ?>>
            <span class="incbackup-tips">Aktiviert den automatischen Hintergrund-Cronjob nach dem untenstehenden Zeitplan. Wenn deaktiviert, kannst du Backups nur manuell auslösen.</span>
        </div>
        
        <hr style="border:0; border-top:1px solid #ccc; margin: 20px 0;">
        
        <h3>Zeitplan & Aufbewahrung</h3>
        <div class="incbackup-form-group">
            <label>Aufbewahrung (Max. Backups):</label>
            <input type="number" name="keep" value="<?php echo htmlspecialchars(isset($cfg['KEEP']) ? $cfg['KEEP'] : '7'); ?>" style="width: 80px;" min="1">
            <span class="incbackup-tips">Legt fest, wie viele Versionen maximal behalten werden. Ältere Backups werden nach jedem Lauf automatisch gelöscht, um Platz zu sparen. Standard: 7.</span>
        </div>
        
        <div class="incbackup-form-group">
            <label>Häufigkeit & Uhrzeit:</label>
            <select name="freq">
                <option value="hourly" <?php echo (isset($cfg['FREQ']) && $cfg['FREQ'] == 'hourly') ? 'selected' : ''; ?>>Stündlich</option>
                <option value="daily" <?php echo (!isset($cfg['FREQ']) || $cfg['FREQ'] == 'daily') ? 'selected' : ''; ?>>Täglich</option>
                <option value="weekly" <?php echo (isset($cfg['FREQ']) && $cfg['FREQ'] == 'weekly') ? 'selected' : ''; ?>>Wöchentlich (Sonntags)</option>
                <option value="monthly" <?php echo (isset($cfg['FREQ']) && $cfg['FREQ'] == 'monthly') ? 'selected' : ''; ?>>Monatlich (am 1.)</option>
            </select>
            <span style="margin: 0 5px;">um</span>
            <select name="hour">
                <?php for($h=0; $h<24; $h++): ?>
                    <option value="<?php echo $h; ?>" <?php echo (isset($cfg['HOUR']) && $cfg['HOUR'] == $h) ? 'selected' : ''; ?>><?php echo str_pad($h, 2, "0", STR_PAD_LEFT); ?></option>
                <?php endfor; ?>
            </select> : 
            <select name="minute">
                <?php for($m=0; $m<60; $m+=5): ?>
                    <option value="<?php echo $m; ?>" <?php echo (isset($cfg['MINUTE']) && $cfg['MINUTE'] == $m) ? 'selected' : ''; ?>><?php echo str_pad($m, 2, "0", STR_PAD_LEFT); ?></option>
                <?php endfor; ?>
            </select>
            <span class="incbackup-tips" style="margin-top: 10px;">Der Backup-Prozess läuft komplett im Hintergrund. Unraid wird dadurch nicht blockiert. Tägliche Backups tief in der Nacht (z.B. 02:00 Uhr) werden empfohlen.</span>
        </div>
        
        <hr style="border:0; border-top:1px solid #ccc; margin: 20px 0;">

        <h3>Verzeichnisse</h3>
        <p class="incbackup-tips" style="margin-bottom: 15px;">
            <b>Wichtig für Hardlinks:</b> Wähle als Quelle und Ziel am besten Haupt-Freigaben aus (z.B. <code>/mnt/user/appdata</code> &rarr; <code>/mnt/user/backup</code>). Die Funktion "Hardlinks erlauben" muss in deinen globalen Unraid-Share-Einstellungen aktiviert sein, damit der inkrementelle Platzspar-Effekt funktioniert!
        </p>
        <div id="paths_container">
            <?php $id_c = 0; foreach ($paths as $p): $id_c++; ?>
            <div class="path-row">
                <input type="text" id="src_<?php echo $id_c; ?>" name="source[]" value="<?php echo htmlspecialchars($p['src']); ?>" placeholder="/mnt/user/quelle" style="width: 320px;">
                <button type="button" class="incbackup-button" style="padding: 4px 8px;" onclick="openDirPicker('src_<?php echo $id_c; ?>')">📁</button>
                <span style="margin: 0 10px;"> &rarr; </span>
                <input type="text" id="dst_<?php echo $id_c; ?>" name="dest[]" value="<?php echo htmlspecialchars($p['dst']); ?>" placeholder="/mnt/user/ziel" style="width: 320px;">
                <button type="button" class="incbackup-button" style="padding: 4px 8px;" onclick="openDirPicker('dst_<?php echo $id_c; ?>')">📁</button>
                <button type="button" class="incbackup-button incbackup-button-danger" onclick="this.parentNode.remove()">X</button>
            </div>
            <?php endforeach; ?>
        </div>
        <button type="button" class="incbackup-button" style="margin-top: 10px;" onclick="addPathRow()">+ Verzeichnis hinzufügen</button>
        
        <hr style="border:0; border-top:1px solid #ccc; margin: 20px 0;">
        
        <div style="margin-top: 20px;">
            <input type="submit" name="save" class="incbackup-button" value="Einstellungen Speichern">
            <input type="submit" name="run_now" class="incbackup-button incbackup-button-secondary" value="Backup Jetzt Ausführen" <?php echo $is_running ? 'disabled' : ''; ?>>
            <input type="submit" name="check_size" class="incbackup-button" style="background-color:#17a2b8;" value="Wahren Speicherplatz prüfen" title="Prüft die echte Datengröße inklusive Hardlinks direkt im Linux-System">
        </div>
    </form>
</div>

<div class="incbackup-container">
    <h3>Live Log <span id="log_spinner" style="display:none; font-size:12px; font-weight:normal; color:#007bff; margin-left:10px;">(Aktualisiere...)</span></h3>
    <textarea readonly id="incbackup_log" style="width: 100%; height: 300px; font-family: monospace; background: #1e1e1e; color: #00ff00; padding: 10px; border: 1px solid #444; border-radius: 4px;">
<?php
if (file_exists($log_file)) {
    $output = shell_exec("tail -n 150 " . escapeshellarg($log_file));
    echo htmlspecialchars($output);
} else {
    echo "Noch keine Logs vorhanden. Starten Sie ein Backup.";
}
?>
</textarea>
    <form method="POST" style="margin-top: 10px;">
        <input type="submit" name="clear_log" class="incbackup-button incbackup-button-danger" value="Log Leeren">
    </form>
</div>

<!-- Custom Directory Picker Modal -->
<div id="dirPickerModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:9999;">
    <div style="background:#f9f9f9; width:500px; margin:100px auto; padding:20px; border-radius:8px; color:#333; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
        <h3 style="margin-top:0;">Ordner auswählen</h3>
        <div style="margin-bottom:10px; background:#e2e3e5; padding:8px; border-radius:4px; font-family:monospace; font-size:14px; color:#333;">
            <strong>Aktuell: </strong> <span id="dp_current">/mnt/user</span>
        </div>
        <div id="dp_list" style="height:300px; overflow-y:auto; border:1px solid #ccc; margin-bottom:15px; background:#fff; border-radius:4px; color:#333;">
            <!-- Dirs will be loaded here -->
        </div>
        <div style="text-align:right;">
            <button type="button" class="incbackup-button incbackup-button-secondary" onclick="dpSelect()">Diesen Ordner wählen</button>
            <button type="button" class="incbackup-button incbackup-button-danger" onclick="document.getElementById('dirPickerModal').style.display='none'">Abbrechen</button>
        </div>
    </div>
</div>

<script>
function addPathRow() {
    var id = Date.now();
    var div = document.createElement('div');
    div.className = 'path-row';
    div.innerHTML = '<input type="text" id="src_' + id + '" name="source[]" placeholder="/mnt/user/quelle" style="width: 320px;"> <button type="button" class="incbackup-button" style="padding: 4px 8px;" onclick="openDirPicker(\\'src_' + id + '\\')">📁</button> <span style="margin: 0 10px;"> &rarr; </span> <input type="text" id="dst_' + id + '" name="dest[]" placeholder="/mnt/user/ziel" style="width: 320px;"> <button type="button" class="incbackup-button" style="padding: 4px 8px;" onclick="openDirPicker(\\'dst_' + id + '\\')">📁</button> <button type="button" class="incbackup-button incbackup-button-danger" onclick="this.parentNode.remove()">X</button>';
    document.getElementById('paths_container').appendChild(div);
}
var textarea = document.getElementById('incbackup_log');
textarea.scrollTop = textarea.scrollHeight;

// Auto-Update Log (Direkter Aufruf der separaten PHP Datei um das Unraid Framework zu umgehen)
setInterval(function() {
    document.getElementById('log_spinner').style.display = 'inline';
    fetch('/plugins/incbackup/get_log.php')
    .then(function(r) { 
        if (!r.ok) throw new Error('Network response was not ok');
        return r.text(); 
    })
    .then(function(text) {
        var isAtBottom = (textarea.scrollHeight - textarea.scrollTop <= textarea.clientHeight + 10);
        if (text && text.trim() !== "" && !text.includes('504 Gateway Time-out') && !text.includes('<html>')) {
            textarea.value = text;
        }
        if (isAtBottom) textarea.scrollTop = textarea.scrollHeight;
        document.getElementById('log_spinner').style.display = 'none';
    })
    .catch(function(e) {
        document.getElementById('log_spinner').style.display = 'none';
    });
}, 5000);

var dpTargetId = "";
function openDirPicker(inputId) {
    dpTargetId = inputId;
    var startPath = document.getElementById(inputId).value;
    if (!startPath || startPath.trim() === "") startPath = "/mnt/user";
    loadDir(startPath);
    document.getElementById('dirPickerModal').style.display = 'block';
}

function loadDir(path) {
    document.getElementById('dp_list').innerHTML = '<div style="padding:10px;text-align:center;">Lade...</div>';
    
    fetch('/plugins/incbackup/get_dirs.php?path=' + encodeURIComponent(path))
    .then(function(r) { return r.json(); })
    .then(function(data) {
        document.getElementById('dp_current').innerText = data.current;
        var html = "";
        if (data.dirs && data.dirs.length > 0) {
            data.dirs.forEach(function(d) {
                html += '<div class="dir-picker-item" onclick="loadDir(\\'' + d.path + '\\')"><span style="font-size:18px; margin-right:8px;">📁</span> ' + d.name + '</div>';
            });
        } else {
            html = '<div style="padding:10px; color:#888;">Keine Unterordner vorhanden.</div>';
        }
        document.getElementById('dp_list').innerHTML = html;
    })
    .catch(function(e) {
        document.getElementById('dp_list').innerHTML = '<div style="padding:10px; color:red;">Fehler beim Laden: ' + e + '</div>';
    });
}

function dpSelect() {
    if (dpTargetId) {
        document.getElementById(dpTargetId).value = document.getElementById('dp_current').innerText;
    }
    document.getElementById('dirPickerModal').style.display = 'none';
}
</script>
<style>
@keyframes blink {
    0% { opacity: 1; }
    50% { opacity: 0; }
    100% { opacity: 1; }
}
</style>
"""

sh_content = """#!/bin/bash

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

source /boot/config/plugins/incbackup/incbackup.cfg
LOGFILE="/var/log/incbackup.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
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

DATE=$(date +%Y-%m-%d_%H-%M-%S)
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
    
    if [ -n "$LATEST_DIR" ] && [ -d "$LATEST_DIR" ]; then
        log "Verwende inkrementelle Basis (Hardlinks): $LATEST_DIR"
        rsync -a -v --delete --link-dest="$LATEST_DIR" "$SRC/" "$TARGET_DIR/" >> "$LOGFILE" 2>&1
    else
        log "Erstes Voll-Backup (keine Vorversion gefunden)."
        rsync -a -v --delete "$SRC/" "$TARGET_DIR/" >> "$LOGFILE" 2>&1
    fi
    
    if [ $? -eq 0 ]; then
        log "Rsync erfolgreich beendet."
    else
        log "WARNUNG: Rsync meldete Fehler/Warnungen."
        HAS_ERROR=1
    fi
    
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
"""

php_api = """<?php
header('Content-Type: application/json');
$path = isset($_GET['path']) ? rtrim($_GET['path'], '/') : '/mnt/user';
if (empty($path) || strpos($path, '/mnt') !== 0) {
    $path = '/mnt';
}
$dirs = [];
if ($path !== '/mnt') {
    $dirs[] = ['name' => '.. (Zurueck)', 'path' => dirname($path)];
}
$items = @scandir($path);
if ($items) {
    foreach ($items as $item) {
        if ($item == '.' || $item == '..') continue;
        $fullPath = $path . '/' . $item;
        if (is_dir($fullPath)) {
            $dirs[] = ['name' => $item, 'path' => $fullPath];
        }
    }
}
echo json_encode(['current' => $path, 'dirs' => $dirs]);
?>"""

php_log = """<?php
$log_file = '/var/log/incbackup.log';
if (file_exists($log_file)) {
    $output = shell_exec("tail -n 150 " . escapeshellarg($log_file));
    echo htmlspecialchars($output);
} else {
    echo "Noch keine Logs vorhanden.";
}
?>"""

page_b64 = base64.encodebytes(page_content.encode('utf-8')).decode('utf-8')
sh_b64 = base64.encodebytes(sh_content.encode('utf-8')).decode('utf-8')
php_b64 = base64.encodebytes(php_api.encode('utf-8')).decode('utf-8')
log_b64 = base64.encodebytes(php_log.encode('utf-8')).decode('utf-8')

plg_content = f"""<?xml version="1.0" standalone="yes"?>
<PLUGIN name="incbackup" author="Antigravity" version="2026.06.11-18" pluginURL="https://raw.githubusercontent.com/DEIN_GITHUB_NAME/unraid-incbackup-plugin/main/incbackup.plg" icon="https://raw.githubusercontent.com/DEIN_GITHUB_NAME/unraid-incbackup-plugin/main/icon.png">

<FILE Name="/boot/config/plugins/incbackup/incbackup.cfg">
<INLINE>
ENABLE="no"
KEEP="7"
FREQ="daily"
HOUR="2"
MINUTE="0"
SRC_0=""
DST_0=""
</INLINE>
</FILE>

<FILE Run="/bin/bash">
<INLINE>
mkdir -p /usr/local/emhttp/plugins/incbackup

base64 -d &lt;&lt;EOF &gt; /usr/local/emhttp/plugins/incbackup/incbackup.page
{page_b64}EOF

base64 -d &lt;&lt;EOF &gt; /usr/local/emhttp/plugins/incbackup/backup.sh
{sh_b64}EOF

base64 -d &lt;&lt;EOF &gt; /usr/local/emhttp/plugins/incbackup/get_dirs.php
{php_b64}EOF

base64 -d &lt;&lt;EOF &gt; /usr/local/emhttp/plugins/incbackup/get_log.php
{log_b64}EOF

chmod +x /usr/local/emhttp/plugins/incbackup/backup.sh

source /boot/config/plugins/incbackup/incbackup.cfg
if [ "$ENABLE" == "yes" ]; then
    CRON_STR=""
    if [ "$FREQ" == "hourly" ]; then CRON_STR="$MINUTE * * * *";
    elif [ "$FREQ" == "daily" ]; then CRON_STR="$MINUTE $HOUR * * *";
    elif [ "$FREQ" == "weekly" ]; then CRON_STR="$MINUTE $HOUR * * 0";
    elif [ "$FREQ" == "monthly" ]; then CRON_STR="$MINUTE $HOUR 1 * *";
    else CRON_STR="$MINUTE $HOUR * * *"; fi
    
    CRON_JOB="$CRON_STR /usr/local/emhttp/plugins/incbackup/backup.sh &gt; /dev/null 2&gt;&amp;1"
    crontab -l 2&gt;/dev/null | grep -v "/usr/local/emhttp/plugins/incbackup/backup.sh" &gt; /tmp/cron_temp
    echo "$CRON_JOB" &gt;&gt; /tmp/cron_temp
    crontab /tmp/cron_temp
    rm -f /tmp/cron_temp
fi

echo ""
echo "----------------------------------------------------"
echo " incbackup plugin installed (Update 18)"
echo "----------------------------------------------------"
echo ""
</INLINE>
</FILE>

<FILE Run="/bin/bash" Method="remove">
<INLINE>
rm -rf /usr/local/emhttp/plugins/incbackup
crontab -l 2&gt;/dev/null | grep -v "/usr/local/emhttp/plugins/incbackup/backup.sh" &gt; /tmp/cron_temp
crontab /tmp/cron_temp
rm -f /tmp/cron_temp

echo ""
echo "----------------------------------------------------"
echo " incbackup plugin uninstalled"
echo "----------------------------------------------------"
echo ""
</INLINE>
</FILE>

</PLUGIN>
"""

with open("incbackup.plg", "w") as f:
    f.write(plg_content)
