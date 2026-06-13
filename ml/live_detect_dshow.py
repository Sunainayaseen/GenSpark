import argparse
import os
import sys
from pathlib import Path

# Must be set before OpenCV opens the camera on Windows.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2
from ultralytics import YOLO


def default_model_paths():
    root = Path(__file__).resolve().parent
    return [
        Path.home() / "yolov5" / "runs" / "detect" / "runs" / "detect" / "train" / "weights" / "best.pt",
        root / "runs" / "detect" / "train" / "weights" / "best.pt",
        root / "runs" / "detect" / "runs" / "detect" / "train" / "weights" / "best.pt",
        root / "yolov8n.pt",
    ]


def resolve_model(model_arg):
    if model_arg:
        path = Path(model_arg)
        if path.exists():
            return path
        raise FileNotFoundError(f"Model not found: {path}")

    for path in default_model_paths():
        if path.exists():
            return path

    raise FileNotFoundError("No YOLO model found. Pass one with --model path\\to\\best.pt")


def main():
    parser = argparse.ArgumentParser(description="Run GenSpark YOLO detection with DirectShow camera capture.")
    parser.add_argument("--model", default="", help="Path to trained best.pt. Defaults to the GenSpark trained model.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index. Usually 0 for laptop webcam.")
    parser.add_argument("--conf", type=float, default=0.55, help="Confidence threshold to reduce false positives.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO image size.")
    parser.add_argument("--width", type=int, default=640, help="Requested webcam width.")
    parser.add_argument("--height", type=int, default=480, help="Requested webcam height.")
    args = parser.parse_args()

    model_path = resolve_model(args.model)
    print(f"Using model: {model_path}")
    print("Opening camera with DirectShow..." if sys.platform.startswith("win") else "Opening camera...")

    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else 0
    cap = cv2.VideoCapture(args.camera, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera}. Try --camera 1.")

    model = YOLO(str(model_path))
    print("Live detection started. Press q or Esc to quit.")

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                print("Could not read camera frame.")
                break

            results = model.predict(frame, conf=args.conf, imgsz=args.imgsz, verbose=False)
            annotated = results[0].plot()
            cv2.imshow("GenSpark Camera Detection", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
