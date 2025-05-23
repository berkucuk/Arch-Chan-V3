# gui_chatbot.py
import sys
import socket
import threading
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                           QLabel, QComboBox, QTextEdit, QLineEdit, QPushButton,
                           QMessageBox, QGraphicsBlurEffect)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import logging
import time
from gtts import gTTS
import pygame

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable for language, managed by the GUI
language = "English"

def play_voice(text, volume=1.0, lang="en"):
    # Create temp_voice directory if it doesn't exist
    if not os.path.exists("temp_voice"):
        os.makedirs("temp_voice")

    # Generate and save the speech file
    tts = gTTS(text, lang=lang)
    tts.save("temp_voice/voice.mp3")

    # Initialize pygame mixer
    pygame.mixer.init()

    # Load the audio file
    pygame.mixer.music.load("temp_voice/voice.mp3")

    # Set volume (0.0 to 1.0)
    pygame.mixer.music.set_volume(min(1.0, max(0.0, volume)))

    # Start playing
    pygame.mixer.music.play()

    # Wait for playback to finish
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    # Stop and quit mixer to release resources
    pygame.mixer.music.stop()
    pygame.mixer.quit()
    
    # Clean up the temporary voice file
    try:
        os.remove("temp_voice/voice.mp3")
    except OSError as e:
        logger.error(f"Error removing temp voice file: {e}")

class ClientHandler(QThread):
    # Signals for communication with the GUI thread
    response_received = pyqtSignal(str, str, str, str) # type, content, voice_text, linux_output
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, host='127.0.0.1', port=12345):
        super().__init__()
        self.host = host
        self.port = port
        self.socket: socket.socket = None
        self.running = True
        self.connected = False

    def run(self):
        self.connect_to_server()
        if self.connected:
            self.listen_for_responses()

    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # Set a timeout for connection attempts
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None) # Remove timeout after successful connection
            self.connected = True
            self.connection_status_changed.emit(True)
            logger.info("Connected to server.")
        except socket.timeout:
            self.error_occurred.emit("Connection timed out. Server might not be running.")
            self.connected = False
            self.connection_status_changed.emit(False)
            logger.error("Connection timed out.")
        except ConnectionRefusedError:
            self.error_occurred.emit("Connection refused. Server might not be running or is unreachable.")
            self.connected = False
            self.connection_status_changed.emit(False)
            logger.error("Connection refused.")
        except Exception as e:
            self.error_occurred.emit(f"Failed to connect to server: {e}")
            self.connected = False
            self.connection_status_changed.emit(False)
            logger.critical(f"Failed to connect: {e}", exc_info=True)

    def listen_for_responses(self):
        while self.running and self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    logger.info("Server disconnected.")
                    self.connected = False
                    self.connection_status_changed.emit(False)
                    self.error_occurred.emit("Server disconnected unexpectedly.")
                    break
                
                parts = data.split('|CONTENT:', 1)
                if len(parts) < 2:
                    logger.warning(f"Malformed response from server: {data}")
                    self.response_received.emit("ERROR", "Received malformed response from server.", "", "")
                    continue

                type_part = parts[0].replace("TYPE:", "").strip()
                remaining_parts = parts[1].split('|VOICE_TEXT:', 1)
                
                if len(remaining_parts) < 2:
                    logger.warning(f"Malformed response from server (missing VOICE_TEXT): {data}")
                    self.response_received.emit("ERROR", "Received malformed response from server (missing voice text).", "", "")
                    continue
                
                content_part = remaining_parts[0].strip()
                
                voice_linux_parts = remaining_parts[1].split('|LINUX_OUTPUT:', 1)
                if len(voice_linux_parts) < 2:
                    logger.warning(f"Malformed response from server (missing LINUX_OUTPUT): {data}")
                    self.response_received.emit("ERROR", "Received malformed response from server (missing linux output).", "", "")
                    continue

                voice_text_part = voice_linux_parts[0].strip()
                linux_output_part = voice_linux_parts[1].strip()

                self.response_received.emit(type_part, content_part, voice_text_part, linux_output_part)

            except socket.error as e:
                if self.running: # Only log as error if we are still supposed to be running
                    logger.error(f"Socket error while listening: {e}")
                    self.error_occurred.emit(f"Server communication error: {e}")
                self.connected = False
                self.connection_status_changed.emit(False)
                break
            except Exception as e:
                logger.critical(f"Unhandled error in client handler listen loop: {e}", exc_info=True)
                self.error_occurred.emit(f"An unexpected error occurred: {e}")
                self.connected = False
                self.connection_status_changed.emit(False)
                break

    def send_message(self, message: str, lang_pref: str):
        if self.connected and self.socket:
            try:
                full_message = f"LANG:{lang_pref}|MSG:{message}"
                self.socket.sendall(full_message.encode('utf-8'))
                logger.info(f"Sent message to server: {message[:100]} (Lang: {lang_pref})")
            except socket.error as e:
                self.error_occurred.emit(f"Failed to send message: {e}")
                self.connected = False
                self.connection_status_changed.emit(False)
                logger.error(f"Failed to send message: {e}")
        else:
            self.error_occurred.emit("Not connected to server.")
            logger.warning("Attempted to send message while not connected.")

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
                logger.info("Client socket closed.")
            except OSError as e:
                logger.warning(f"Error during socket shutdown/close: {e}")
        self.wait() # Wait for the thread to finish execution

class ChatBotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.client_handler = ClientHandler()
        self.client_handler.response_received.connect(self.handle_response)
        self.client_handler.connection_status_changed.connect(self.update_connection_status)
        self.client_handler.error_occurred.connect(self.display_error)
        self.client_handler.start() # Start the client handler thread

    def init_ui(self):
        self.setWindowTitle('Arch-Chan AI Assistant')
        self.setGeometry(100, 100, 800, 600)

        # Set window icon
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'icons', 'arch-chan_mini.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            logger.warning(f"Icon file not found at {icon_path}")

        main_layout = QVBoxLayout()

        # Header with Arch-Chan image and status
        header_layout = QHBoxLayout()
        image_label = QLabel()
        image_path = os.path.join(script_dir, 'icons', 'arch-chan_bg.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            image_label.setPixmap(pixmap.scaledToHeight(150, Qt.SmoothTransformation))
        else:
            logger.warning(f"Image file not found at {image_path}")
        image_label.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("Connecting to server...")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: orange;")

        header_layout.addWidget(image_label)
        header_layout.addWidget(self.status_label)
        main_layout.addLayout(header_layout)

        # Language selection
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "Türkçe"])
        self.lang_combo.setCurrentText(language) # Set initial value from global
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch(1) # Push combo to the left
        main_layout.addLayout(lang_layout)

        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Monospace", 10))
        self.chat_display.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd; padding: 10px;")
        main_layout.addWidget(self.chat_display)

        # Input and send area
        input_layout = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Type your message here...")
        self.user_input.setFont(QFont("Arial", 10))
        self.user_input.returnPressed.connect(self.send_message) # Send on Enter key

        self.send_button = QPushButton("Send")
        self.send_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.user_input)
        input_layout.addWidget(self.send_button)
        main_layout.addLayout(input_layout)

        self.setLayout(main_layout)

        # Apply a subtle blur effect to the background (optional, but can enhance aesthetics)
        # blur_effect = QGraphicsBlurEffect()
        # blur_effect.setBlurRadius(2)
        # self.setGraphicsEffect(blur_effect)

    def on_language_changed(self, index):
        global language
        language = self.lang_combo.currentText()
        logger.info(f"GUI language preference changed to: {language}")
        # Optionally, send a message to the server to update its language preference for this session
        # This will be included with the next user message to the server for processing.

    def send_message(self):
        user_text = self.user_input.text().strip()
        if user_text:
            self.append_message(f"<b style='color: blue;'>You:</b> {user_text}")
            self.user_input.clear()
            # Send message to server via client handler thread
            self.client_handler.send_message(user_text, language)
        else:
            QMessageBox.warning(self, "Empty Message", "Please type a message before sending.")

    def handle_response(self, response_type: str, content: str, voice_text: str, linux_output: str):
        self.append_message(f"<b style='color: green;'>Arch-Chan:</b> {content}")
        
        if linux_output:
            self.append_message(f"<b style='color: #8B008B;'>Linux Output:</b> <pre>{linux_output}</pre>")
        
        # Play voice in a separate thread to avoid blocking the GUI
        voice_thread = threading.Thread(target=play_voice, args=(voice_text, 1.0, self.get_lang_code()))
        voice_thread.start()

    def get_lang_code(self) -> str:
        if language == "Türkçe":
            return "tr"
        return "en"

    def append_message(self, message: str):
        self.chat_display.append(message)
        # Scroll to the bottom
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_label.setText("Connected to Server (Arch-Chan Online!)")
            self.status_label.setStyleSheet("color: green;")
            self.send_button.setEnabled(True)
            self.user_input.setEnabled(True)
            self.user_input.setPlaceholderText("Type your message here...")
            self.append_message("<b style='color: green;'>Arch-Chan:</b> I'm connected and ready to help, nya~!")
        else:
            self.status_label.setText("Disconnected (Server Offline)")
            self.status_label.setStyleSheet("color: red;")
            self.send_button.setEnabled(False)
            self.user_input.setEnabled(False)
            self.user_input.setPlaceholderText("Disconnected. Please restart the server and application.")
            self.append_message("<b style='color: red;'>Arch-Chan:</b> Oh no! I lost connection to the server, sweetie! Please make sure the server is running.")

    def display_error(self, message: str):
        # Display errors in the chat window and also show a QMessageBox for critical errors
        self.append_message(f"<b style='color: red;'>ERROR:</b> {message}")
        logger.error(f"GUI Error: {message}")
        # QMessageBox.warning(self, "Application Error", message) # Only for critical errors

    def closeEvent(self, event):
        # Ensure the client handler thread is properly stopped when the GUI closes
        logger.info("Closing application. Stopping client handler.")
        if self.client_handler and self.client_handler.isRunning():
            self.client_handler.stop()
            # Wait a reasonable time for the thread to terminate
            if not self.client_handler.wait(2000): # Wait for 2 seconds
                logger.warning("Client handler thread did not terminate gracefully.")
            else:
                logger.info("Client handler stopped.")
        super().closeEvent(event)
        logger.info("Application closed.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Set window icon
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, 'icons', 'arch-chan_mini.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        logger.warning(f"Icon for app not found at {icon_path}")

    try:
        window = ChatBotGUI()
        window.show()
        exit_code = app.exec_()
    except Exception as e:
        logger.critical(f"Application crashed: {e}")
        QMessageBox.critical(None, "Fatal Error", f"Application crashed: {e}")
        sys.exit(1) # Exit with error code
    finally:
        # Pygame shutdown might be needed here if initialized globally
        # However, `play_voice` initializes and quits pygame.mixer locally,
        # so a global quit might not be strictly necessary unless mixer is used elsewhere.
        pass