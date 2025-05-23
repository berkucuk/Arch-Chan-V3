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
        time.sleep(0.01)

    # Cleanup
    # pygame.quit() # Pygame'i burada global olarak kapatmak yerine,
                  # uygulamanın genel kapanışında veya ihtiyaç duyulmadığında yönetmek daha iyi olabilir.
                  # Ancak mevcut haliyle de play_voice özelinde çalışır.
                  # Eğer başka pygame kullanımları varsa çakışma yaratabilir.
                  # Şimdilik bu satırı olduğu gibi bırakıyorum, çünkü sadece bu fonksiyon etkileniyor.
                  # Eğer genel bir pygame kapanış sorunu varsa, bu ayrıca ele alınmalı.
    # Pygame mixer'i durdur ve kaynakları serbest bırak
    pygame.mixer.music.stop()
    pygame.mixer.quit() # Sadece mixer'i kapatır, pygame'in diğer modüllerini etkilemez.

    # Remove temporary file
    if os.path.exists("temp_voice/voice.mp3"):
        os.remove("temp_voice/voice.mp3")

class ClientSocketHandler(QThread):
    received_message = pyqtSignal(str)
    connection_error = pyqtSignal(str)

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.running = True

    def run(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(1.0)  # Soket operasyonları için 1 saniye zaman aşımı ayarla
            self.socket.connect((self.host, self.port))
            logger.info(f"Connected to server at {self.host}:{self.port}")
            
            while self.running:
                try:
                    # recv çağrısından önce self.running durumunu kontrol et
                    if not self.running:
                        break
                    
                    data_bytes = self.socket.recv(4096)
                    
                    if not data_bytes:
                        logger.info("Connection closed by server.")
                        break  # Sunucu bağlantıyı kapattı
                    
                    data = data_bytes.decode('utf-8')
                    self.received_message.emit(data)

                except socket.timeout:
                    # Zaman aşımı normal bir durum, döngüye devam et ve self.running'i tekrar kontrol et
                    continue
                except OSError as e: # socket.error da OSError'ın bir alt sınıfıdır
                    if self.running: # Eğer self.running False ise, bu bizim tarafımızdan başlatılan bir kapanmadır
                        logger.error(f"Socket OSError in client handler: {e}")
                        self.connection_error.emit(f"Socket error: {e}")
                    break # Soket hatasında döngüden çık
                except Exception as e: # Decode hatası gibi diğer beklenmedik hatalar
                    if self.running:
                        logger.error(f"Unexpected error in client recv loop: {e}")
                        self.connection_error.emit(f"Receive loop error: {e}")
                    break # Beklenmedik hatada döngüden çık

        except ConnectionRefusedError:
            if self.running: # Yalnızca hala çalışıyorsak hata yayınla
                self.connection_error.emit("Connection refused. Make sure the server is running.")
            logger.error("Connection refused by server.")
        except socket.timeout: # connect() zaman aşımına uğrarsa
            if self.running:
                self.connection_error.emit("Connection attempt timed out.")
            logger.error("Connection attempt timed out.")
        except Exception as e: # connect() veya diğer kurulum hataları
            if self.running:
                self.connection_error.emit(f"Socket setup error: {e}")
                logger.error(f"Socket setup error in client handler: {e}")
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except OSError as e:
                    logger.info(f"Error closing socket in finally: {e}")
            logger.info("Client socket handler run method finished.")


    def send_message(self, message):
        if self.socket and self.running: # Sadece soket varsa ve çalışıyorsa gönder
            try:
                self.socket.sendall(message.encode('utf-8'))
            except OSError as e: # Soket kapatılmış veya bozuk olabilir
                if self.running:
                    self.connection_error.emit(f"Failed to send message: {e}")
                    logger.error(f"Failed to send message: {e}")
                # Bağlantı hatasından sonra iş parçacığını durdurmayı düşünebilirsiniz
                # self.running = False 
            except Exception as e:
                if self.running:
                    self.connection_error.emit(f"Failed to send message: {e}")
                    logger.error(f"Failed to send message: {e}")


    def stop(self):
        self.running = False
        # Soketi kapatmak, recv() çağrısının (eğer engellenmişse) bir hata ile sonlanmasına neden olabilir,
        # bu da run() metodundaki döngünün sonlanmasına yardımcı olur.
        if self.socket:
            try:
                # Soketin her iki yönünü de kapatmayı deneyebiliriz, bu recv'in daha hızlı sonlanmasına yardımcı olabilir.
                # Ancak, bu bazen zaten kapalı bir sokette hata verebilir, bu yüzden try-except içinde olmalı.
                # self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except OSError:
                pass # Soket zaten kapalıysa veya hatalı durumdaysa yoksay
        logger.info("ClientSocketHandler stop method called.")


class ChatBotGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.current_language = "English"
        self.voice_active = False  # Default voice state
        self.setWindowTitle('Linux Chan AI (Gemini)')
        self.setFixedSize(500, 900)

        global language # Access the global language variable
        language = "English" # Default language

        # Define placeholder text translations
        self.placeholder_texts = {
            "English": "Type your message here...",
            "Turkish": "Mesajınızı buraya yazın...",
            "Spanish": "Escribe tu mensaje aquí...",
            "German": "Schreiben Sie Ihre Nachricht hier...",
            "French": "Écrivez votre message ici...",
            "Russian": "Введите ваше сообщение здесь..."
        }

        # Define send button text translations
        self.send_button_texts = {
            "English": "Send",
            "Turkish": "Gönder",
            "Spanish": "Enviar",
            "German": "Senden",
            "French": "Envoyer",
            "Russian": "Отправить"
        }

        # Define voice switch translations
        self.voice_switch_texts = {
            "English": "Voice: ",
            "Turkish": "Ses: ",
            "Spanish": "Voz: ",
            "German": "Stimme: ",
            "French": "Voix: ",
            "Russian": "Голос: "
        }

        self.init_ui()
        self.client_handler = ClientSocketHandler('127.0.0.1', 12345)
        self.client_handler.received_message.connect(self.handle_server_response)
        self.client_handler.connection_error.connect(self.handle_connection_error)
        self.client_handler.start()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Top Controls Layout
        top_controls = QHBoxLayout()

        # Language Selection
        self.setup_language_selector(top_controls)

        # Voice Switch
        self.setup_voice_switch(top_controls)

        layout.addLayout(top_controls)

        # Image
        self.setup_image(layout)

        # Chat Display
        self.setup_chat_display(layout)

        # Input Area
        self.setup_input_area(layout)

        self.setLayout(layout)

    def setup_language_selector(self, layout):
        label = QLabel("Language/Dil:")
        label.setFont(QFont("Arial", 11, QFont.Bold))

        self.language_combo = QComboBox()
        self.language_combo.setFont(QFont("Arial", 11))
        self.language_combo.addItems([
            "English", "Turkish", "Spanish", "German", "French", "Russian"
        ])
        self.language_combo.currentTextChanged.connect(self.change_language)

        layout.addWidget(label)
        layout.addWidget(self.language_combo)
        layout.addStretch()

    def setup_voice_switch(self, layout):
        voice_layout = QHBoxLayout()

        self.voice_label = QLabel(self.voice_switch_texts["English"])
        self.voice_label.setFont(QFont("Arial", 11, QFont.Bold))

        self.voice_combo = QComboBox()
        self.voice_combo.setFont(QFont("Arial", 11))
        self.voice_combo.addItems(["OFF", "ON"])
        self.voice_combo.setCurrentText("OFF")  # Default state
        self.voice_combo.currentTextChanged.connect(self.toggle_voice)
        self.voice_active = False
        voice_layout.addWidget(self.voice_label)
        voice_layout.addWidget(self.voice_combo)
        layout.addLayout(voice_layout)
        
    def toggle_voice(self, state):
        self.voice_active = (state == "ON")
        print(f"Voice mode: {self.voice_active}")

    def setup_image(self, layout):
        # Load the photo
        pixmap = QPixmap("/usr/share/Arch-Chan-AI/icons/arch-chan.png")

        if not pixmap.isNull():
            # Create container widget
            container = QWidget(self)
            container.setFixedSize(500, 400)
            
            # --- Blurred background photo ---
            blur_label = QLabel(container)
            blurred_pixmap = pixmap.scaled(500, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            blur_label.setPixmap(blurred_pixmap)
            
            blur_effect = QGraphicsBlurEffect()
            blur_effect.setBlurRadius(20)  # Blur level
            blur_label.setGraphicsEffect(blur_effect)
            blur_label.setAlignment(Qt.AlignCenter)
            blur_label.setGeometry(0, 0, 500, 400)  # Absolute positioning

            # --- Sharp foreground photo ---
            front_label = QLabel(container)
            front_pixmap = pixmap.scaled(500, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            front_label.setPixmap(front_pixmap)
            front_label.setAlignment(Qt.AlignCenter)
            front_label.setGeometry(0, 0, 500, 400)  # Absolute positioning

            # Add container to layout
            layout.addWidget(container)
        else:
            QMessageBox.warning(self, "Warning", "Failed to load image")

    def setup_chat_display(self, layout):
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(200)
        self.chat_display.setFont(QFont("Courier New", 11))
        layout.addWidget(self.chat_display)

    def setup_input_area(self, layout):
        input_layout = QHBoxLayout()

        self.entry = QLineEdit()
        self.entry.setFont(QFont("Arial", 12))
        self.entry.setPlaceholderText(self.placeholder_texts["English"])
        self.entry.returnPressed.connect(self.handle_request)

        self.send_button = QPushButton(self.send_button_texts["English"])
        self.send_button.setFont(QFont("Arial", 11))
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4285F4;
                color: white;
                border-radius: 15px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3367D6;
            }
            QPushButton:pressed {
                background-color: #2850A7;
            }
        """)
        self.send_button.clicked.connect(self.handle_request)

        input_layout.addWidget(self.entry, stretch=4)
        input_layout.addWidget(self.send_button, stretch=1)
        layout.addLayout(input_layout)

    def change_language(self, new_language):
        global language
        self.current_language = new_language
        language = new_language # Update the global language variable

        # Update placeholder text and send button text based on selected language
        self.entry.setPlaceholderText(self.placeholder_texts.get(new_language, "Type your message here..."))
        self.send_button.setText(self.send_button_texts.get(new_language, "Send"))
        self.voice_label.setText(self.voice_switch_texts.get(new_language, "Voice: "))

    def handle_request(self):
        user_input = self.entry.text().strip()
        if not user_input:
            self.chat_display.append("[Error] Please enter a message.")
            return

        self.send_button.setEnabled(False)
        self.entry.clear()
        
        # Add user message to chat display
        self.chat_display.append(f"You: {user_input}\n")

        # Send message to server with language prefix
        message_to_send = f"LANG:{self.current_language}|MSG:{user_input}"
        # Sadece client_handler çalışıyorsa mesaj gönder
        if self.client_handler and self.client_handler.isRunning():
            self.client_handler.send_message(message_to_send)
        else:
            self.chat_display.append("[Error] Not connected to server.\n")
            self.send_button.setEnabled(True)


    def handle_server_response(self, response_data):
        # Parse the incoming message from the server
        # Expected format: "TYPE:<type>|CONTENT:<content>|VOICE_TEXT:<voice_text>|LINUX_OUTPUT:<linux_output>"
        parts = response_data.split('|CONTENT:', 1)
        if len(parts) == 2:
            type_part = parts[0]
            content_and_voice_and_linux = parts[1]

            response_type = type_part.split('TYPE:')[1] if 'TYPE:' in type_part else "UNKNOWN"

            # Further split for VOICE_TEXT and LINUX_OUTPUT
            content_parts = content_and_voice_and_linux.split('|VOICE_TEXT:', 1)
            response_content = content_parts[0]
            voice_text = ""
            linux_cmd_output = ""

            if len(content_parts) == 2:
                voice_and_linux_parts = content_parts[1].split('|LINUX_OUTPUT:', 1)
                voice_text = voice_and_linux_parts[0]
                if len(voice_and_linux_parts) == 2:
                    linux_cmd_output = voice_and_linux_parts[1]
            
            # Display content
            self.chat_display.append(f"{response_content}\n")

            # Display Linux command output if available
            if response_type == "LINUX_CMD" and linux_cmd_output:
                self.chat_display.append(f"-> Terminal Output:\n{linux_cmd_output}\n")

            # Only play voice if voice_active is True
            if self.voice_active and voice_text:
                voice_lang = {
                    "English": "en",
                    "Turkish": "tr",
                    "Spanish": "es",
                    "German": "de",
                    "French": "fr",
                    "Russian": "ru"
                }
                # play_voice'ı bir QThread içinde çalıştırmak donmaları engelleyebilir
                # Şimdilik doğrudan çağırıyoruz, eğer donma yaparsa iyileştirilebilir.
                try:
                    play_voice(
                        text=voice_text,
                        volume=0.5,
                        lang=voice_lang.get(self.current_language, "en") # Default to English if language not found
                    )
                except Exception as e:
                    logger.error(f"Error playing voice: {e}")
                    self.chat_display.append(f"[Voice Error] Could not play audio: {e}\n")

        else:
            self.chat_display.append(f"[Server Response Error] Invalid format: {response_data}\n")

        self.send_button.setEnabled(True)

    def handle_connection_error(self, error_message):
        # Check if the widget is still valid before showing a message box
        if self.isVisible():
             QMessageBox.critical(self, "Connection Error", error_message)
        self.chat_display.append(f"[Connection Error] {error_message}\n")
        self.send_button.setEnabled(True) # Buton etkinleştirilmeli

    def closeEvent(self, event):
        logger.info("Close event triggered.")
        if self.client_handler:
            logger.info("Stopping client handler...")
            self.client_handler.stop()
            # İş parçacığının sonlanması için makul bir süre bekle
            # Eğer wait() çok uzun sürüyorsa, bu iş parçacığının düzgün sonlanmadığı anlamına gelir.
            if not self.client_handler.wait(2000): # 2 saniye bekle
                logger.warning("Client handler thread did not terminate gracefully.")
            else:
                logger.info("Client handler stopped.")
        # Pygame'i global olarak burada sonlandırmak iyi bir pratik olabilir,
        # eğer play_voice dışında başka yerlerde de başlatılıyorsa.
        # Ancak play_voice kendi içinde pygame.mixer.quit() yaptığı için bu elzem olmayabilir.
        # pygame.quit() # Tüm pygame modüllerini kapatır
        super().closeEvent(event)
        logger.info("Application closed.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('/usr/share/Arch-Chan-AI/icons/arch-chan_mini.png'))

    # pygame'i ana iş parçacığında bir kere başlatmak ve kapatmak daha güvenli olabilir.
    # pygame.init() # Ana uygulamada bir kere başlat

    try:
        window = ChatBotGUI()
        window.show()
        exit_code = app.exec_()
    except Exception as e:
        logger.critical(f"Application crashed: {e}")
        QMessageBox.critical(None, "Fatal Error", f"Application crashed: {e}")
        sys.exit(1) # Hata durumunda çıkış yap
    finally:
        # pygame.quit() # Ana uygulamadan çıkarken pygame'i kapat
        sys.exit(exit_code)