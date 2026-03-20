# Prosumer Compensare - Home Assistant

Dashboard Home Assistant pentru prosumeri din Romania cu sistem solar. Calculeaza automat cati kWh poti importa gratuit din retea pe baza energiei exportate, folosind raportul de compensare al furnizorului (ex: Hidroelectrica).

## Cum functioneaza

In Romania, prosumerii (cei care au panouri solare si vand energie in retea) primesc compensare:
- **Exporti** energie in retea la un pret mic (ex: 0.464 RON/kWh)
- **Importi** energie din retea la un pret mare (ex: 1.16 RON/kWh)
- **Raport**: pentru fiecare 2.5 kWh exportati, primesti 1 kWh gratuit
- **Ciclul** de compensare: Martie → Februarie (an urmator)

Acest proiect iti arata in timp real:
- Cati **kWh poti importa gratuit** (credit acumulat)
- **Balanta in RON** (valoare export vs cost import)
- **Procent compensare** (cat % din import e acoperit)
- Grafic **import vs export** pe ultimele 30 zile
- Balanta **zilnica** si **lunara**

## Cerinte

- **Home Assistant** 2024.1+
- **HACS** instalat
- **Mushroom Cards** (HACS → Frontend)
- **ApexCharts Card** (HACS → Frontend)
- Un **inverter solar** integrat in HA (Deye, Huawei, Fronius, SolarEdge, etc.)

## Instalare

### Pasul 1: Activeaza packages in HA

Adauga in `configuration.yaml` (daca nu exista deja):

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Creaza folderul `/config/packages/` daca nu exista.

### Pasul 2: Copiaza package-ul

Copiaza fisierul `packages/prosumer_compensare.yaml` in `/config/packages/`.

### Pasul 3: Configureaza entity ID-urile

Deschide `prosumer_compensare.yaml` si inlocuieste placeholders cu entity ID-urile tale.

Foloseste **Find & Replace** (Ctrl+H):

| Placeholder | Ce sa pui | Exemplu (Deye 10KW) |
|---|---|---|
| `sensor.YOUR_TOTAL_ENERGY_IMPORT` | Senzor total energie importata (kWh, total_increasing) | `sensor.inverter_deye_10kw_total_energy_import` |
| `sensor.YOUR_TOTAL_ENERGY_EXPORT` | Senzor total energie exportata (kWh, total_increasing) | `sensor.inverter_deye_10kw_total_energy_export` |
| `sensor.YOUR_TODAY_ENERGY_IMPORT` | Senzor import azi (kWh) | `sensor.inverter_deye_10kw_today_energy_import` |
| `sensor.YOUR_TODAY_ENERGY_EXPORT` | Senzor export azi (kWh) | `sensor.inverter_deye_10kw_today_energy_export` |
| `sensor.YOUR_GRID_POWER` | Putere grid in timp real (W) | `sensor.inverter_deye_10kw_grid_power` |
| `sensor.YOUR_PV_POWER` | Putere panouri solare (W) | `sensor.inverter_deye_10kw_pv_power` |
| `sensor.YOUR_BATTERY_SOC` | Nivel baterie (%) | `sensor.inverter_deye_10kw_battery` |

**Cum gasesti entity ID-urile:**
1. Mergi la **Developer Tools → States**
2. Cauta `total_energy_import` sau `grid_power`
3. Copiaza `entity_id`-ul complet

### Pasul 4: Restart Home Assistant

**Settings → System → Restart**

### Pasul 5: Adauga dashboard-ul

1. **Settings → Dashboards → Add Dashboard** (from scratch)
2. Numeste-l "Prosumer" → Create
3. Deschide dashboard-ul → click **creionul** (edit) → **⋮** → **Raw Configuration Editor**
4. Sterge tot si paste continutul din `dashboard/prosumer_dashboard.yaml`
5. **Atentie:** Fa acelasi Find & Replace si in dashboard YAML (aceleasi 7 placeholders)
6. **Save**

### Pasul 6: Configureaza preturile

Dupa restart, mergi la dashboard-ul Prosumer si modifica:
- **Pret Import** (cat platesti pe kWh cand cumperi din retea)
- **Pret Export** (cat primesti pe kWh cand vinzi in retea)
- **Raport compensare** (cati kWh exportati = 1 kWh gratuit, de obicei 2.5)

## Invertere testate

| Inverter | Integrare HA | Status |
|---|---|---|
| Deye 10KW (hybrid, trifazat) | Solarman | Testat |
| Huawei SUN2000 | Huawei Solar | Ar trebui sa mearga |
| Fronius | Fronius Integration | Ar trebui sa mearga |
| SolarEdge | SolarEdge Modbus | Ar trebui sa mearga |

Daca l-ai testat cu alt inverter, deschide un Issue sau PR.

## Structura fisiere

```
packages/
  prosumer_compensare.yaml    ← Package HA (senzori + utility meters)
dashboard/
  prosumer_dashboard.yaml     ← Dashboard YAML (copy-paste in HA)
```

## Senzori creati

Dupa instalare, vei avea acesti senzori noi:

| Senzor | Ce arata |
|---|---|
| `sensor.prosumer_credit_gratuit_kwh` | Cati kWh poti importa gratuit |
| `sensor.prosumer_credit_gratuit_ron` | Balanta in RON |
| `sensor.prosumer_balanta_azi_kwh` | Balanta zilei curente |
| `sensor.prosumer_balanta_luna_kwh` | Balanta lunii curente |
| `sensor.prosumer_procent_compensare` | Cat % din import e acoperit |
| `sensor.grid_directie_acum` | Import/Export/Echilibru in timp real |

## Licenta

MIT - foloseste-l liber.
