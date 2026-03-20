# Prosumer Compensare Romania - Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Integrare Home Assistant pentru prosumeri din Romania cu sistem solar. Calculeaza automat cati kWh poti importa gratuit din retea pe baza energiei exportate, folosind raportul de compensare al furnizorului (ex: Hidroelectrica).

## Cum functioneaza

In Romania, prosumerii (cei care au panouri solare si vand energie in retea) primesc compensare:
- **Exporti** energie in retea la un pret mic (ex: 0.464 RON/kWh)
- **Importi** energie din retea la un pret mare (ex: 1.16 RON/kWh)
- **Raport**: pentru fiecare 2.5 kWh exportati, primesti 1 kWh gratuit
- **Ciclul** de compensare: Martie → Februarie (an urmator)

Integrarea iti arata in timp real:
- Cati **kWh poti importa gratuit** (credit acumulat din Martie)
- **Balanta in RON** (valoare export vs cost import)
- **Procent compensare** (cat % din import e acoperit)
- **Balanta zilnica** (azi cat ai castigat/pierdut)
- **Directia grid** (importi sau exporti acum)

## Instalare prin HACS

### Pasul 1: Adauga repository-ul in HACS

1. Deschide **HACS** in Home Assistant
2. Click pe **⋮** (meniu) din dreapta sus → **Custom repositories**
3. Adauga URL: `https://github.com/Scripted20/ha-prosumer-compensare`
4. Categoria: **Integration**
5. Click **Add**

### Pasul 2: Instaleaza integrarea

1. In HACS, cauta **"Prosumer Compensare"**
2. Click **Download**
3. **Restart Home Assistant**

### Pasul 3: Configureaza

1. Mergi la **Settings → Devices & Services → Add Integration**
2. Cauta **"Prosumer Compensare"**
3. **Pasul 1**: Selecteaza senzorii de energie din dropdown-uri:
   - Total Energie Importata (obligatoriu)
   - Total Energie Exportata (obligatoriu)
   - Import Azi, Export Azi, Putere Grid, Putere PV, Baterie (optional)
4. **Pasul 2**: Seteaza preturile:
   - Pret import (RON/kWh) — implicit 1.16
   - Pret export (RON/kWh) — implicit 0.464
   - Raport compensare — implicit 2.5

### Pasul 4: Dashboard (optional)

1. **Settings → Dashboards → Add Dashboard** (from scratch)
2. Numeste-l "Prosumer" → Create
3. Deschide → **creionul** (edit) → **⋮** → **Raw Configuration Editor**
4. Paste continutul din `dashboard/prosumer_dashboard.yaml`
5. Inlocuieste placeholder-urile `sensor.YOUR_*` cu senzorii tai
6. **Save**

**Cerinte dashboard:** Mushroom Cards + ApexCharts Card (instalabile din HACS → Frontend)

## Modificare preturi ulterior

Dupa instalare, poti modifica preturile oricand:
**Settings → Devices & Services → Prosumer Compensare → Configure**

## Cerinte

- **Home Assistant** 2024.1+
- **HACS** instalat
- Un **inverter solar** integrat in HA (Deye, Huawei, Fronius, SolarEdge, etc.)

## Invertere testate

| Inverter | Integrare HA | Status |
|---|---|---|
| Deye 10KW (hybrid, trifazat) | Solarman | Testat |
| Huawei SUN2000 | Huawei Solar | Netestat |
| Fronius | Fronius Integration | Netestat |
| SolarEdge | SolarEdge Modbus | Netestat |

Daca l-ai testat cu alt inverter, deschide un Issue sau PR.

## Senzori creati

| Senzor | Ce arata |
|---|---|
| Credit Gratuit | Cati kWh poti importa gratuit (din Martie) |
| Credit Gratuit RON | Balanta in RON |
| Balanta Azi | Credit/debit azi |
| Procent Compensare | Cat % din import e acoperit de export |
| Grid Directie | Import/Export/Echilibru in timp real |

## Cum functioneaza tehnic

- Senzorii asculta schimbarile de stare ale senzorilor sursa (fara polling)
- Valorile "din Martie" sunt calculate folosind baseline-uri persistate (se reseteaza automat pe 1 Martie)
- Preturile se pot modifica din UI fara restart

## Licenta

MIT
