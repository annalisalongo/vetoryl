# Monitor Vetoryl di Zoe

App Streamlit per controllare:
- quante pasticche restano
- quando richiedere la ricetta
- quando riordinare
- quando finisce la scorta
- una piccola vista calendario con le date chiave
- pulsanti per aprire gli eventi direttamente in Google Calendar

## Avvio con ambiente virtuale

```bash
cd zoe_vetoryl_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Dati iniziali caricati

- Vetoryl 10 mg: acquisto 02/04/2026, 2 scatole, 30 pasticche a scatola, 2 al giorno
- Vetoryl 5 mg: acquisto 08/04/2026, 2 scatole, 30 pasticche a scatola, 2 al giorno

## Note

- La configurazione può essere salvata in un file locale `zoe_vetoryl_config.json`.
- La richiesta ricetta e il riordino hanno anticipo configurabile dalla sidebar.
- Nella sezione Google Calendar trovi i pulsanti per creare al volo gli eventi sul tuo calendario.
