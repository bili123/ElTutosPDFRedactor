# El Tutos PDF Redactor - WiP
Small, limited, easy to use tool for redacting PDFs by drawing or searching. 

This tool has been written primarily for my own use case - with help of ChatGPT for Python syntax.
It relies basically on Tkinter, MuPDF and Pillow.

Features:

- Redacting by drawing rectangles
- Redacting by using simple search or regular expressions
- Removing rectangles via right-click
- Retaining not redacted text
- Saves only copies of PDF, no overwriting
- Extremely ugly GUI (sorry, but I dont' really care)

<img width="551" height="416" alt="eltutospdfredactor" src="https://github.com/user-attachments/assets/e0239a5d-eecf-4379-b7ac-198af59c47a9" />

## Installation - Windows 11
You can just use the portable, compiled EXE file from the release section, no installation needed.

Alternatively you can use the Python script itself:

1. Install Python
2. Download or clone this repo
3. Enter directory in terminal
4. Use virtual environment:
     -     python -m venv .venv
     -     source .venv/Scripts/activate  
5. Install requirements (pymupdf, pillow):
    -     pip install -r ./requirements.txt
6. Start script:
    -     python pdf_redactor_0.1.py

## Installation - Ubuntu 24.04

    sudo apt update
    sudo apt install -y python3 python3-tk python3-pil python3-pil.imagetk python3-fitz python3.12-venv git pip
    mkdir ~/git
    cd ~/git
    git clone https://github.com/bili123/ElTutosPDFRedactor.git
    cd ElTutosPDFRedactor
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r ./requirements.txt


