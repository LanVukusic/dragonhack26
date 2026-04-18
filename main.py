from qrdet import QRDetector
import cv2

detector = QRDetector(model_size="n")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Could not open webcam")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 512)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 288)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    detections = detector.detect(image=frame, is_bgr=True)

    for detection in detections:
        x1, y1, x2, y2 = detection["bbox_xyxy"]
        confidence = detection["confidence"]
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color=(0, 255, 0), thickness=2)
        cv2.putText(
            frame,
            f"{confidence:.2f}",
            (x1, y1 - 10),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=1,
            color=(0, 255, 0),
            thickness=2,
        )

    cv2.imshow("QR Detection (press q to quit)", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
