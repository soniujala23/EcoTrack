SMART WASTE MANAGEMENT - SOFTWARE SIMULATION

1. Install Python 3.10 or newer.
2. Extract this ZIP folder.
3. Open the project folder in VS Code.
4. Open Terminal in VS Code and run:

   python -m venv venv

   Windows:
   venv\Scripts\activate

   macOS/Linux:
   source venv/bin/activate

5. Install dependencies:

   pip install -r requirements.txt

6. Start the app:

   python app.py

7. Open this address in your browser:

   http://127.0.0.1:5000

The app creates database.db automatically on first run.

IMPORTANT:
This is a software simulation. Fill, moisture and gas values are generated
by Python; no ESP32 or physical sensors are connected. Gas is shown as a
simulated index (0-100), not a calibrated ppm measurement.

The map uses illustrative coordinates and Leaflet/OpenStreetMap tiles,
which require an internet connection. All core dashboard data is local.
