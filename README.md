# RTLPlayground Switch für Home Assistant

Liest Switches mit der [RTLPlayground](https://github.com/logicog/RTLPlayground)-Firmware über deren **nur lesende Monitoring-API** in einem eigenen VLAN aus. Die Integration kann am Switch nichts verändern: Die Firmware beantwortet in diesem VLAN nur lesende Abfragen, und auch das nur vom erlaubten Client und nur mit gültigem Token.

## Voraussetzungen

Die Firmware muss die Monitoring-API enthalten (`api`-Befehl, Karte „Monitoring-API“ unter System). Dort richtest du ein:

1. **VLAN** für die API. Es muss sich vom Management-VLAN unterscheiden und Home Assistant erreichen. Lege das VLAN wie gewohnt im VLAN-Tab an.
2. **IP-Adresse und Netzmaske** des Switches in diesem VLAN.
3. **Erlaubter Client**: die IP-Adresse von Home Assistant im selben Subnetz. Ein Gateway gibt es nicht.
4. **Token erzeugen** und kopieren.
5. **API einschalten** und die Konfiguration im Flash speichern.

Per Konsole sieht das so aus:
```
api vlan 20
api ip 10.20.0.2 255.255.255.0
api allow 10.20.0.10
api token new
api on
```

## Installation

**Manuell:** Kopiere den Ordner `custom_components/rtlplayground` nach `/config/custom_components/` und starte Home Assistant neu.

**HACS:** Lege dieses Verzeichnis als eigenes GitHub-Repository an. Trage es dann in HACS unter *Benutzerdefinierte Repositories* mit dem Typ *Integration* ein.

Danach fügst du die Integration unter *Einstellungen → Geräte & Dienste → Integration hinzufügen → RTLPlayground Switch* hinzu. Dort gibst du die **API-Adresse** (nicht die Management-Adresse) und das **Token** ein.

## Entitäten

| Entität | Beschreibung |
|---|---|
| Chiptemperatur | Temperatur des Switch-Chips |
| Letzter Start | Zeitpunkt des letzten Neustarts (Diagnose) |
| Port *n* (Binärsensor) | Verbindung vorhanden |
| Port *n* Verbindung | Link-Geschwindigkeit: getrennt, 10M … 10G |
| Port *n* Empfangsrate / Senderate | Durchsatz, berechnet aus den Byte-Zählern |
| Port *n* empfangen / gesendet | Byte-Zähler (standardmäßig deaktiviert) |
| Port *n* Empfangs-/Sendefehler, gelernte MACs | Diagnose (standardmäßig deaktiviert) |
| Port *n* SFP-Modul, -Temperatur, -Empfangsleistung, -Sendeleistung | Nur bei SFP-Ports mit Moduldiagnose (DDM) |
| Port *n* SFP-Spannung, -Laserstrom | Diagnose (standardmäßig deaktiviert) |

**Optionen:** Abfrageintervall (Standard 30 s) und Byte-Zähler/Durchsatz ein oder aus. Die Byte-Zähler kosten pro Abfrage eine zusätzliche Anfrage je Port.

Wird das Token am Switch neu erzeugt, fragt Home Assistant automatisch nach dem neuen Token.

## Hinweise

- Der Switch verarbeitet nur eine TCP-Verbindung gleichzeitig. Die Integration stellt ihre Anfragen deshalb nacheinander. Ein Intervall unter 30 s bringt wenig.
- Die Übertragung ist unverschlüsseltes HTTP. Halte das API-VLAN auf Switch und Home Assistant beschränkt.
- SFP-Module mit externer Kalibrierung liefern keine Messwerte. Ihre Rohwerte wären ohne die Kalibrierkonstanten falsch.

## Tests

Die Tests laufen gegen den Simulator der Firmware (`tests/httpd_sim.py`, aus `tools/` des Firmware-Repos):
```
pip install pytest-homeassistant-custom-component
pytest
```
