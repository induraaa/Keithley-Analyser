# Keithley Analyser
Interactive KDF Visualisation Tool

A powerful desktop application for exploring and analysing semiconductor wafer test data with intuitive visualisations and rich statistics.

## ✨ Features

🟢 Interactive Wafer Map
Visualise die-level data across the wafer
Zoom, hover, and click to inspect values

📊 Advanced Data Analysis
Built-in statistics (mean, std dev, yield, etc.)
Histogram with normal distribution overlay
Scatter plots and yield trends

🎯 Pass/Fail & Limits
Spec limits and production limits
Colour-coded dies (pass / fail / warning)
Continuous heatmap mode

🔍 Detailed Inspection
Click any die to view all measurements
Multi-design (subsite) support

📁 Flexible Input
Supports KDF files from Keithley ACS systems

📤 Export Options
Export wafer maps as images
Export to Excel for further analysis

🖥️ Preview
[ Add screenshots here — wafer map, histogram, UI panels ]
⚙️ Installation
1. Clone the repository
git clone https://github.com/yourusername/wafer-map-viewer.git
cd wafer-map-viewer
2. Install dependencies
pip install PySide6

▶️ Usage
python wafer_mapper_light.py your_file.kdf

Or simply run:

python wafer_mapper_light.py

Then open a .kdf file from the UI.

🧠 How It Works
Parses KDF files into:
Header metadata
Site coordinates (X, Y)
Measurement values per design
Renders:
Wafer layout with spatial accuracy
Colour-coded dies based on limits or value gradients
Provides:
Statistical summaries
Visual analytics panels
🎨 UI Highlights
Clean, modern theme (custom Qt styling)
Smooth zoom and interaction
Responsive layout with multiple panels:
Wafer view
Site detail
Statistics
Charts
📦 Project Structure
.
├── wafer_mapper_light.py   # Main application
├── assets/                 # Icons (optional)
├── README.md
🚀 Future Improvements
Batch wafer comparison
CSV / database import support
Dark mode toggle
Performance optimisation for large datasets
🤝 Contributing

Pull requests are welcome. For major changes, open an issue first to discuss ideas.

📄 License

MIT License — feel free to use and modify.

🙌 Acknowledgements
Built with PySide6 (Qt for Python)
Designed for semiconductor test data workflows
⭐ Support

If you find this useful, give it a star ⭐ — it helps a lot!

If you want, I can upgrade this further with:

real badges (build, license, Python version)
embedded GIF demo
a more “portfolio-level” README (great for internships like Arup)
