# El Tutos PDF Redactor - WiP
Small, limited, easy to use tool for redacting PDFs by drawing or searching. 

This tool has been written primarily for my own use case - with help of ChatGPT for Python syntax.
It relies basically on Tkinter, MuPDF and Pillow.

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
    sudo apt install -y python3 python3-tk python3-pil python3-pil.imagetk python3-fitz git
    mkdir ~/git
    cd ~/git
    git clone https://github.com/bili123/ElTutosPDFRedactor
    cd ElTutosPDFRedactor
    python -m venv .venv
    source .venv/bin/activate
    pip install -r ./requirements.txt


