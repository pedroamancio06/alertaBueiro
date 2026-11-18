"""Converte model/best.pt em model/best.onnx (formato usado pela API na nuvem).

    pip install ultralytics==8.3.40 onnx==1.17.0
    python model/exportar_onnx.py

Rode sempre que trocar o best.pt. O notebook de treino já faz isso no final.
"""
from pathlib import Path

from ultralytics import YOLO

PT = Path(__file__).with_name("best.pt")
destino = YOLO(str(PT)).export(format="onnx", imgsz=640, opset=12, simplify=False, dynamic=False)
print(f"Gerado: {destino}")
