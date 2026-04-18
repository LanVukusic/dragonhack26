from ultralytics import YOLO
import cv2

model = YOLO("YOLOV8s_Barcode_Detection.pt")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, verbose=False)
    boxes = results[0].boxes

    for i in range(len(boxes)):
        x1, y1, x2, y2 = boxes.xyxy[i]
        conf = boxes.conf[i]
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color=(0, 255, 0), thickness=2)
        cv2.putText(
            frame,
            f"{conf:.2f}",
            (x1, y1 - 10),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=1,
            color=(0, 255, 0),
            thickness=2,
        )

    cv2.imshow("Barcode Detection (press q to quit)", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
