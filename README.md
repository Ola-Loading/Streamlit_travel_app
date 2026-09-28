
# Streamlit Travel app

## 📌 Overview
This streamlit application leverages the Python-based framework Sreamlit in order to create a simple website that allows users to search for flights from their current location (which they input) to another location that meets their requirements (namely a threshold temperature). A couple API's are used to aid with this such as **OpenMeteo** for weather related data and **AviationStack** for real-time airport and flight data 

## 📂 Project Structure
/Streamlit_Travel_app
│── Streamlit_app.py         # Main script containing functions and workflow for app
├── .env.example              # Example environment file -- place the AviationStack API key within
│── worldcities.csv           # CSV file containg relevant city data such as longitudes and latitudes
│── .gitignore                # Ignore unnecessary files
│── README.md                 # Project documentation
│── requirements.txt          # Dependencies
│── GlobalAirportDatabase.txt # Airport related data such as each airport's IATA code which is necessary for API interaction

## 🛠️ Installation & Setup
### **1. Clone the Repository**
```bash
git clone https://github.com/your-username/Streamlit_travel_app.git
cd Streamlit_travel_app
```

### **2a. Set Up Virtual Environment**
```bash
# Create a virtual environment
python -m venv venv 

# Activate the virtual environment
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# Upgrade PiP if necessary
pip install --upgrade pip setuptools wheel
```


### **3. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **4. Configure Environment Variables**
Copy `.env.example` to `.env` and set your AviationStack API key.
```bash
cp .env.example .env
```

### **5. Run the app**
```bash
streamlit run Streamlit_app.py
```

### **6. Deploy to cloud**
Streamlit Cloud doesn't read `.env` files, so instead you'd set the key via Streamlit's Secrets Manager (app settings > Secrets):
```toml
AVIATION_API_KEY = "your_actual_api_key_here"
```
and swap the `load_dotenv()` / `os.getenv("AVIATION_API_KEY")` call in `Streamlit_app.py` for:
```python
api_key = st.secrets["AVIATION_API_KEY"]
```

## 📜 License
This project is licensed under the [MIT License](LICENSE).

## 🤝 Contributing
Feel free to submit **issues** or **pull requests** if you’d like to contribute!

## 📧 Contact
For questions or suggestions, reach out at [ogunadeolaoluwa@gmail.com].

