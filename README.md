# RTLPlayground Switch für Home Assistant

Liest Switches mit der [RTLPlayground](https://github.com/NoDiskNoFun/RTLPlayground)-Firmware über deren **nur lesende Monitoring-API** in einem eigenen VLAN aus. Die Integration kann am Switch nichts verändern: Die Firmware beantwortet in diesem VLAN nur lesende Abfragen, und auch das nur vom erlaubten Client und nur mit gültigem Token.

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

**HACS:** Trage `https://github.com/NoDiskNoFun/ha-RTLPlayground` in HACS unter *Benutzerdefinierte Repositories* mit dem Typ *Integration* ein.

Danach fügst du die Integration unter *Einstellungen → Geräte & Dienste → Integration hinzufügen → RTLPlayground Switch* hinzu. Dort gibst du die **API-Adresse** (nicht die Management-Adresse) und das **Token** ein.

## Geräte und Entitäten

Der Switch erscheint als Gerät, und **jeder Port als eigenes Gerät**, das über den Switch verbunden ist. Wenn du ein Port-Gerät umbenennst, übernehmen alle Entitäten dieses Ports den Namen. Home Assistant bietet dabei an, auch die Entitäts-IDs anzupassen.

**Ports benennen** geht auf zwei Wegen:
- **In Home Assistant:** *Einstellungen → Geräte & Dienste → RTLPlayground Switch → Geräte → Port 3 → Stift-Symbol*. Der Name gilt nur in Home Assistant.
- **Am Switch:** im Webinterface unter Ports oder mit `port 3 name NAS`. Die Integration übernimmt den Namen bei der nächsten Abfrage als Gerätenamen. Hast du den Port schon in Home Assistant benannt, hat dein Name Vorrang.

| Gerät | Entität | Beschreibung |
|---|---|---|
| Switch | Chiptemperatur | Temperatur des Switch-Chips |
| Switch | Letzter Start | Zeitpunkt des letzten Neustarts (Diagnose) |
| Port | Verbunden | Binärsensor: Link vorhanden |
| Port | Geschwindigkeit | Getrennt, 10M … 10G |
| Port | Empfangsrate / Senderate | Durchsatz, berechnet aus den Byte-Zählern |
| Port | Empfangen / Gesendet | Byte-Zähler (standardmäßig deaktiviert) |
| Port | Empfangs-/Sendefehler, gelernte MAC-Adressen | Diagnose (standardmäßig deaktiviert) |
| SFP-Port | SFP-Modul, -Temperatur, -Empfangsleistung, -Sendeleistung | Nur mit Moduldiagnose (DDM) |
| SFP-Port | SFP-Versorgungsspannung, -Laserstrom | Diagnose (standardmäßig deaktiviert) |

**Optionen** (*Geräte & Dienste → RTLPlayground Switch → Konfigurieren*):
- **Intervall** der Abfrage, Standard 30 s.
- **Byte-Zähler und Durchsatz** ein oder aus. Sie kosten pro Abfrage eine zusätzliche Anfrage je Port.
- **Einheit für Durchsatz:** Mbit/s (Standard) oder MB/s, für alle Empfangs- und Senderaten auf einmal. Home Assistant rechnet die Werte um (1 MB/s = 8 Mbit/s). Eine Einheit, die du an einem einzelnen Sensor einstellst, überschreibt die Option beim nächsten Neuladen der Integration.

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
