import sys
import os
import base64
import tempfile
import traceback
import requests
import time
import uuid


from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
    QRubberBand,
    QMainWindow,
    QInputDialog,
    QMessageBox
)

from PyQt6.QtCore import (
    Qt,
    QPoint,
    QRect,
    QThread,
    pyqtSignal
)

from PIL import Image
import mss


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://zomet-production.up.railway.app/process-image"

APP_TITLE = "ZOMET AI"

WINDOW_OPACITY = 0.35

MIN_CAPTURE_SIZE = 10

# =========================================================
# SNIPPING TOOL
# =========================================================

class SnippingWidget(QMainWindow):

    def __init__(self, callback):
        super().__init__()

        self.callback = callback

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setWindowOpacity(0.25)

        self.setStyleSheet(
            "background-color: black;"
        )

        self.setCursor(
            Qt.CursorShape.CrossCursor
        )

        self.showFullScreen()

        self.origin = QPoint()

        self.rubberBand = QRubberBand(
            QRubberBand.Shape.Rectangle,
            self
        )

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.origin = event.pos()

            self.rubberBand.setGeometry(
                QRect(self.origin, self.origin)
            )

            self.rubberBand.show()

    def mouseMoveEvent(self, event):

        if not self.origin.isNull():

            rect = QRect(
                self.origin,
                event.pos()
            ).normalized()

            self.rubberBand.setGeometry(rect)

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.rubberBand.hide()

            rect = self.rubberBand.geometry().normalized()

            global_pos = self.mapToGlobal(
                rect.topLeft()
            )

            self.close()

            self.callback(
                global_pos.x(),
                global_pos.y(),
                rect.width(),
                rect.height()
            )


# =========================================================
# WORKER THREAD
# =========================================================

class GeminiWorker(QThread):

    finished_signal = pyqtSignal(str)

    def __init__(self, image_path, license_key):
        super().__init__()

        self.image_path = image_path
        self.license_key = license_key

    def run(self):

        try:

            # =============================================
            # READ IMAGE
            # =============================================

            with open(self.image_path, "rb") as f:

                image_base64 = base64.b64encode(
                    f.read()
                ).decode("utf-8")

            # =============================================
            # SEND TO SERVER
            # =============================================

            payload = {
                "image": image_base64,
                "license_key": self.license_key
            }

            response = requests.post(
                BASE_URL,
                json=payload,
                timeout=90
            )

            print("STATUS:", response.status_code)
            print("RESPONSE:", response.text)

            if response.status_code != 200:

                try:
                    detail = response.json().get("detail", "")
                except Exception:
                    detail = response.text

                if response.status_code == 403:
                    if "Usage limit reached" in detail:
                        msg = (
                            "Usage limit reached.\n\n"
                            "Please contact admin to\n"
                            "upgrade or renew your license."
                        )
                    elif "License inactive" in detail:
                        msg = (
                            "License is inactive.\n\n"
                            "Please contact admin to\n"
                            "reactivate your license."
                        )
                    elif "License expired" in detail:
                        msg = (
                            "License has expired.\n\n"
                            "Please contact admin to\n"
                            "renew your license."
                        )
                    else:
                        msg = "Access denied. Please contact admin."
                elif response.status_code == 401:
                    msg = "Authentication failed. Please contact admin."
                elif response.status_code >= 500:
                    msg = (
                        "Server is experiencing issues.\n\n"
                        "Please try again in a moment."
                    )
                else:
                    msg = f"An error occurred (code {response.status_code})."

                self.finished_signal.emit(msg)
                return

            # =============================================
            # PARSE JSON
            # =============================================

            data = response.json()

            candidates = data.get(
                "candidates",
                []
            )

            if not candidates:

                self.finished_signal.emit(
                    "AI did not return an answer."
                )

                return

            content = candidates[0].get(
                "content",
                {}
            )

            parts = content.get(
                "parts",
                []
            )

            if not parts:

                self.finished_signal.emit(
                    "Empty response from AI."
                )

                return

            text = parts[0].get(
                "text",
                "No answer provided."
            )

            self.finished_signal.emit(text)

        except requests.Timeout:

            self.finished_signal.emit(
                "Connection timed out.\n\n"
                "Please check your internet\n"
                "connection and try again."
            )

        except requests.ConnectionError:

            self.finished_signal.emit(
                "Unable to connect to server.\n\n"
                "Please check your internet connection."
            )

        except Exception:

            traceback.print_exc()

            self.finished_signal.emit(
                "An unexpected error occurred.\n\n"
                "Please try again or contact admin."
            )

        finally:

            try:

                if os.path.exists(self.image_path):
                    os.remove(self.image_path)

            except Exception:
                pass


# =========================================================
# MAIN WINDOW
# =========================================================

class StealthWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.current_opacity = WINDOW_OPACITY

        self.old_pos = QPoint()

        self.worker = None

        self.colors = [
            "#FFFFFF",
            "#00FF00",
            "#00FFFF",
            "#FFFF00",
            "#FF5555"
        ]

        self.color_index = 0

        self.init_ui()

    # =====================================================

    def init_ui(self):

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setWindowOpacity(
            self.current_opacity
        )

        self.label = QLabel(
            f"{APP_TITLE}\n\n"
            "LEFT CLICK + DRAG : Move Window\n"
            "RIGHT CLICK       : Screenshot\n\n"
            "CTRL + UP         : Increase Opacity\n"
            "CTRL + DOWN       : Decrease Opacity\n"
            "CTRL + W          : Change Color\n"
            "ESC               : Exit",
            self
        )

        self.label.setWordWrap(True)

        self.label.setMaximumWidth(600)

        self.label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True
        )

        self.update_style()

        layout = QVBoxLayout()

        layout.addWidget(self.label)

        self.setLayout(layout)

    # =====================================================

    def update_style(self):

        color = self.colors[
            self.color_index
        ]

        self.label.setStyleSheet(f"""
            color: {color};

            font-family: Consolas;
            font-size: 14px;
            font-weight: bold;

            background-color: rgba(0,0,0,220);

            border: 2px solid {color};
            border-radius: 10px;

            padding: 14px;
        """)

    # =====================================================

    def mousePressEvent(self, event):

        # MOVE WINDOW
        if event.button() == Qt.MouseButton.LeftButton:

            self.old_pos = (
                event.globalPosition().toPoint()
            )

        # SCREENSHOT
        elif event.button() == Qt.MouseButton.RightButton:

            self.hide()

            QApplication.processEvents()

            time.sleep(0.15)

            self.snipper = SnippingWidget(
                self.capture_area
            )

            self.snipper.show()

    # =====================================================

    def mouseMoveEvent(self, event):

        if (
            event.buttons() &
            Qt.MouseButton.LeftButton
        ):

            if not self.old_pos.isNull():

                new_pos = (
                    event.globalPosition().toPoint()
                )

                delta = new_pos - self.old_pos

                self.move(
                    self.x() + delta.x(),
                    self.y() + delta.y()
                )

                self.old_pos = new_pos

    # =====================================================

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.old_pos = QPoint()

    # =====================================================

    def keyPressEvent(self, event):

        # EXIT
        if event.key() == Qt.Key.Key_Escape:

            QApplication.quit()

        if (
            event.modifiers() ==
            Qt.KeyboardModifier.ControlModifier
        ):

            # OPACITY UP
            if event.key() == Qt.Key.Key_Up:

                self.current_opacity = min(
                    1.0,
                    self.current_opacity + 0.05
                )

                self.setWindowOpacity(
                    self.current_opacity
                )

                return

            # OPACITY DOWN
            elif event.key() == Qt.Key.Key_Down:

                self.current_opacity = max(
                    0.01,
                    self.current_opacity - 0.05
                )

                self.setWindowOpacity(
                    self.current_opacity
                )

                return

            # CHANGE COLOR
            elif event.key() == Qt.Key.Key_W:

                self.color_index = (
                    self.color_index + 1
                ) % len(self.colors)

                self.update_style()

                return

        super().keyPressEvent(event)

    # =====================================================

    def capture_area(self, x, y, w, h):

        if w < MIN_CAPTURE_SIZE or h < MIN_CAPTURE_SIZE:

            self.show()

            return

        try:

            self.label.setText(
                "Capturing screenshot..."
            )

            with mss.mss() as sct:

                monitor = {
                    "top": y,
                    "left": x,
                    "width": w,
                    "height": h
                }

                screenshot = sct.grab(monitor)

                img = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.bgra,
                    "raw",
                    "BGRX"
                )

            # =============================================
            # UPSCALE OCR
            # =============================================

            img = img.resize(
                (
                    img.width * 2,
                    img.height * 2
                ),
                Image.Resampling.LANCZOS
            )

            # =============================================
            # SAVE TEMP
            # =============================================

            temp_file = tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False
            )

            temp_path = temp_file.name

            temp_file.close()

            img.save(
                temp_path,
                "JPEG",
                quality=95
            )

            # =============================================
            # SEND
            # =============================================

            self.show()

            self.label.setText(
                "Analyzing..."
            )

            self.worker = GeminiWorker(
                temp_path,
                ACTIVE_LICENSE_KEY
            )

            self.worker.finished_signal.connect(
                self.handle_result
            )

            self.worker.start()

        except Exception as e:

            self.show()

            self.label.setText(
                f"SCREENSHOT ERROR\n\n{str(e)}\n\nPlease try again."
            )

    # =====================================================

    def handle_result(self, text):

        self.show()

        self.raise_()

        self.activateWindow()

        clean_text = "".join([
            c for c in text
            if c.isprintable() or c in "\n\r\t"
        ])

        self.label.setText(clean_text)

        self.adjustSize()


# =========================================================
# MAIN
# =========================================================

ACTIVE_LICENSE_KEY = ""

if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(False)

    # =========================================
    # LICENSE CHECK
    # =========================================

    license_key, ok = QInputDialog.getText(
        None,
        "Zomet License",
        "Enter your License Key:"
    )

    if not ok or not license_key:
        sys.exit()

    try:
        hwid = str(uuid.getnode())

        response = requests.post(
            "https://zomet-production.up.railway.app/verify-license",
            json={
                "license_key": license_key,
                "hwid": hwid
            },
            timeout=15
        )

        print(response.text)

        result = response.json()

        print(result)

        if not result.get("valid"):

            msg = QMessageBox()

            msg.setWindowTitle("Zomet License")

            msg.setText("License key not valid!")

            msg.setIcon(QMessageBox.Icon.Critical)

            msg.exec()

            sys.exit()

        ACTIVE_LICENSE_KEY = license_key

    except Exception as e:

        msg = QMessageBox()

        msg.setWindowTitle("Zomet Error")

        msg.setText(
            "Unable to connect to license server.\n\n"
            + str(e)
        )

        msg.setIcon(QMessageBox.Icon.Warning)

        msg.exec()

        sys.exit()

    # =========================================
    # APP START
    # =========================================

    window = StealthWindow()

    window.resize(520, 320)

    window.show()

    window.raise_()

    window.activateWindow()

    sys.exit(app.exec())
